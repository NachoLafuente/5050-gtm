#!/usr/bin/env python3
"""Attio <-> CSV bridge for the attio-deepline-enrich skill.

Attio is the source and the sink. Deepline does the paid enrichment in
between (`deepline enrich` on the CSV this script produces). Attio reads
and writes are free, so we use the Attio REST API directly here and keep
every credit-spending step inside Deepline, behind the skill's cost gate.

Three subcommands:

  attrs   List an object's attributes (slug, title, type). Free. Run first
          so you pick real slugs instead of guessing.

  pull    Query records and write a CSV of record_id + chosen input columns.
          Optionally keep only records that are still missing the target
          attribute(s), so you never pay to re-enrich rows you already have.

  push    Read an enriched CSV and write chosen columns back into Attio.
          append -> PATCH (adds values, safe default).
          replace -> PUT  (overwrites the attribute's values).

Env: ATTIO_API_KEY (Settings -> Apps & integrations -> API).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from typing import Any

import requests

try:
    from dotenv import load_dotenv

    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
except ImportError:
    pass

API = "https://api.attio.com/v2"
PAGE = 500  # Attio query page cap
WRITE_PAUSE = 0.05  # ~20 writes/sec, under Attio's 25/sec write limit


def _key() -> str:
    key = os.environ.get("ATTIO_API_KEY")
    if not key:
        sys.exit("ATTIO_API_KEY is not set. Copy .env.example to .env and fill it in.")
    return key


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}


def _flatten(values: list[dict[str, Any]] | None) -> str:
    """Reduce an Attio value array to a single scalar string for CSV.

    Attio stores every attribute as a list of typed value objects. For
    enrichment inputs we only need the first/primary value as plain text.
    """
    if not values:
        return ""
    v = values[0]
    for k in (
        "value",
        "domain",
        "email_address",
        "phone_number",
        "full_name",
        "target_object",  # record reference: fall back to id below
        "currency_value",
        "number",
    ):
        if k in v and v[k] not in (None, ""):
            return str(v[k])
    # option-style (select / status) and record references
    if isinstance(v.get("option"), dict):
        return str(v["option"].get("title", ""))
    if isinstance(v.get("status"), dict):
        return str(v["status"].get("title", ""))
    if "target_record_id" in v:
        return str(v["target_record_id"])
    # last resort: first non-meta scalar on the object
    for k, val in v.items():
        if k not in ("active_from", "active_until", "created_by_actor", "attribute_type") and isinstance(
            val, (str, int, float)
        ):
            return str(val)
    return ""


# ---------------------------------------------------------------- attrs


def cmd_attrs(args: argparse.Namespace) -> None:
    r = requests.get(f"{API}/objects/{args.object}/attributes", headers=_headers(), timeout=30)
    r.raise_for_status()
    rows = r.json().get("data", [])
    width = max((len(a["api_slug"]) for a in rows), default=10)
    print(f"{'slug'.ljust(width)}  type            title")
    print(f"{'-' * width}  --------------  -----")
    for a in rows:
        print(f"{a['api_slug'].ljust(width)}  {a['type'].ljust(14)}  {a['title']}")


# ---------------------------------------------------------------- pull


def _query_page(obj: str, limit: int, offset: int) -> list[dict[str, Any]]:
    body = {"limit": limit, "offset": offset, "sorts": [{"attribute": "created_at", "direction": "desc"}]}
    r = requests.post(f"{API}/objects/{obj}/records/query", headers=_headers(), json=body, timeout=60)
    r.raise_for_status()
    return r.json().get("data", [])


def cmd_pull(args: argparse.Namespace) -> None:
    inputs = [c.strip() for c in args.inputs.split(",") if c.strip()]
    targets = [c.strip() for c in args.target.split(",") if c.strip()] if args.target else []

    collected: list[dict[str, str]] = []
    offset = 0
    while len(collected) < args.limit:
        batch = _query_page(args.object, min(PAGE, args.limit * 2 if args.only_missing else args.limit), offset)
        if not batch:
            break
        for rec in batch:
            vals = rec.get("values", {})
            if args.only_missing and targets:
                # keep only rows where every target attribute is still empty
                if any(_flatten(vals.get(t)) for t in targets):
                    continue
            row = {"record_id": rec["id"]["record_id"]}
            for col in inputs:
                row[col] = _flatten(vals.get(col))
            collected.append(row)
            if len(collected) >= args.limit:
                break
        offset += len(batch)
        if len(batch) < PAGE:
            break

    fields = ["record_id", *inputs]
    with open(args.output, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(collected)

    print(f"Wrote {len(collected)} rows to {args.output}")
    if args.only_missing and targets:
        print(f"(filtered to records missing all of: {', '.join(targets)})")
    print(f"Columns: {', '.join(fields)}")


# ---------------------------------------------------------------- push


def _write_record(obj: str, rid: str, values: dict[str, Any], replace: bool) -> tuple[bool, str]:
    method = requests.put if replace else requests.patch
    r = method(
        f"{API}/objects/{obj}/records/{rid}",
        headers=_headers(),
        json={"data": {"values": values}},
        timeout=30,
    )
    if r.status_code == 429:
        time.sleep(float(r.headers.get("Retry-After", "1")))
        return _write_record(obj, rid, values, replace)
    if not r.ok:
        return False, f"{r.status_code} {r.text[:160]}"
    return True, "ok"


def cmd_push(args: argparse.Namespace) -> None:
    # map is csv_column=attio_slug, comma-separated
    mapping = dict(p.split("=", 1) for p in args.map.split(",") if "=" in p)
    if not mapping:
        sys.exit("--map needs at least one csv_column=attio_slug pair")
    replace = args.mode == "replace"

    with open(args.input, newline="") as f:
        rows = list(csv.DictReader(f))

    if "record_id" not in (rows[0] if rows else {}):
        sys.exit("Input CSV has no record_id column. Use the CSV produced by `pull`.")

    ok = skipped = failed = 0
    for row in rows:
        rid = row["record_id"].strip()
        values = {slug: row[col].strip() for col, slug in mapping.items() if row.get(col, "").strip()}
        if not rid or not values:
            skipped += 1
            continue
        if args.dry_run:
            verb = "PUT" if replace else "PATCH"
            print(f"[dry-run] {verb} {rid}  {values}")
            ok += 1
            continue
        good, msg = _write_record(args.object, rid, values, replace)
        if good:
            ok += 1
        else:
            failed += 1
            print(f"  FAIL {rid}: {msg}", file=sys.stderr)
        time.sleep(WRITE_PAUSE)

    tag = "[dry-run] " if args.dry_run else ""
    print(f"{tag}{ok} written, {skipped} skipped (empty), {failed} failed.")


# ---------------------------------------------------------------- cli


def main() -> None:
    p = argparse.ArgumentParser(description="Attio <-> CSV bridge for attio-deepline-enrich")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("attrs", help="List an object's attributes")
    a.add_argument("--object", required=True, help="Object slug, e.g. companies, people")
    a.set_defaults(func=cmd_attrs)

    pu = sub.add_parser("pull", help="Query records -> CSV of record_id + input columns")
    pu.add_argument("--object", required=True)
    pu.add_argument("--inputs", required=True, help="Comma-separated attribute slugs to export as enrichment inputs")
    pu.add_argument("--target", default="", help="Comma-separated target slugs (the ones you'll fill)")
    pu.add_argument("--only-missing", action="store_true", help="Keep only records where all target slugs are empty")
    pu.add_argument("--limit", type=int, default=50)
    pu.add_argument("--output", required=True)
    pu.set_defaults(func=cmd_pull)

    ps = sub.add_parser("push", help="Enriched CSV -> Attio")
    ps.add_argument("--object", required=True)
    ps.add_argument("--input", required=True, help="Enriched CSV (must keep the record_id column)")
    ps.add_argument("--map", required=True, help="csv_column=attio_slug,csv_column=attio_slug ...")
    ps.add_argument("--mode", choices=["append", "replace"], default="append", help="append=PATCH, replace=PUT")
    ps.add_argument("--dry-run", action="store_true")
    ps.set_defaults(func=cmd_push)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
