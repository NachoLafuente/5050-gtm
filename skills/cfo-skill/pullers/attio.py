"""Attio puller — writes customers.csv from Attio companies.

Required env: ATTIO_API_KEY
Optional env:
  ATTIO_MRR_ATTR    — slug of the MRR/recurring revenue attribute (default: "mrr")
  ATTIO_STATUS_ATTR — slug of the status/lifecycle attribute (default: "status")
  ATTIO_ACTIVE_VAL  — option ID or text of "active" status (default: "active")
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import requests

BASE = "https://api.attio.com/v2"


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _attr_value(values: list, attr: str) -> str:
    arr = values.get(attr) if isinstance(values, dict) else None
    if not arr:
        return ""
    v = arr[0]
    for k in ("value", "currency_value", "option_id", "title", "name"):
        if k in v and v[k] is not None:
            return str(v[k])
    return str(v)


def _attr_number(values: dict, attr: str) -> float:
    arr = values.get(attr)
    if not arr:
        return 0.0
    v = arr[0]
    for k in ("currency_value", "value", "number_value"):
        if k in v and v[k] is not None:
            try:
                return float(v[k])
            except (TypeError, ValueError):
                pass
    return 0.0


def discover_attrs(key: str, object_slug: str = "companies") -> list[dict]:
    r = requests.get(f"{BASE}/objects/{object_slug}/attributes", headers=_headers(key), timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def fetch_companies(key: str, limit: int = 500) -> list[dict]:
    out: list[dict] = []
    offset = 0
    while True:
        body = {"limit": limit, "offset": offset}
        r = requests.post(
            f"{BASE}/objects/companies/records/query",
            headers=_headers(key),
            json=body,
            timeout=60,
        )
        r.raise_for_status()
        page = r.json().get("data", [])
        if not page:
            break
        out.extend(page)
        if len(page) < limit:
            break
        offset += limit
    return out


def write_customers_csv(out_path: Path) -> int:
    key = os.getenv("ATTIO_API_KEY")
    if not key:
        raise RuntimeError("ATTIO_API_KEY not set")

    mrr_attr = os.getenv("ATTIO_MRR_ATTR", "mrr")
    status_attr = os.getenv("ATTIO_STATUS_ATTR", "status")
    active_val = os.getenv("ATTIO_ACTIVE_VAL", "active")
    churned_attr = os.getenv("ATTIO_CHURNED_ATTR", "churned_at")
    plan_attr = os.getenv("ATTIO_PLAN_ATTR", "plan")
    name_attr = os.getenv("ATTIO_NAME_ATTR", "name")

    companies = fetch_companies(key)

    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["customer_id", "customer_name", "status", "signed_up_at", "churned_at", "mrr", "plan"])
        for c in companies:
            vals = c.get("values", {})
            cid = c.get("id", {}).get("record_id", "")
            name = _attr_value(vals, name_attr) or _attr_value(vals, "domains") or cid
            status_raw = _attr_value(vals, status_attr).lower()
            status = "active" if active_val.lower() in status_raw else ("churned" if status_raw else "unknown")
            churned_at = _attr_value(vals, churned_attr) if status == "churned" else ""
            signed_up = c.get("created_at", "")[:10]
            mrr = _attr_number(vals, mrr_attr)
            plan = _attr_value(vals, plan_attr)
            w.writerow([cid, name, status, signed_up, churned_at, f"{mrr:.2f}", plan])

    return len(companies)
