"""Moss puller — enriches cash_movements.csv with categorized expenses.

Moss expenses get appended to cash_movements.csv with category + department
populated from Moss's expense accounts and teams/departments.

Required env:
  MOSS_KEY_ID      — Moss OAuth client ID (kid_…)
  MOSS_SECRET_KEY  — Moss OAuth client secret (sk_…)
Optional env:
  MOSS_BASE_URL    — defaults to https://public-api.getmoss.com
"""

from __future__ import annotations

import csv
import os
from datetime import date, timedelta
from pathlib import Path

import requests

DEFAULT_BASE = "https://public-api.getmoss.com"


def _base() -> str:
    return os.getenv("MOSS_BASE_URL", DEFAULT_BASE).rstrip("/")


def get_token() -> str:
    kid = os.getenv("MOSS_KEY_ID")
    sk = os.getenv("MOSS_SECRET_KEY")
    if not (kid and sk):
        raise RuntimeError("MOSS_KEY_ID and MOSS_SECRET_KEY must be set")
    r = requests.post(
        f"{_base()}/oauth2/token",
        data={"grant_type": "client_credentials", "client_id": kid, "client_secret": sk, "scope": "read"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _get(token: str, path: str, params: dict | None = None) -> dict:
    r = requests.get(f"{_base()}/v1{path}", headers={"Authorization": f"Bearer {token}"}, params=params or {}, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_expenses(token: str, months: int = 6) -> list[dict]:
    cutoff = (date.today() - timedelta(days=months * 31)).isoformat()
    out: list[dict] = []
    offset = 0
    while True:
        body = _get(token, "/expenses", {"from": cutoff, "limit": 200, "offset": offset})
        items = body.get("data") or body.get("items") or []
        if not items:
            break
        out.extend(items)
        if len(items) < 200:
            break
        offset += 200
    return out


def fetch_lookup(token: str, path: str) -> dict[str, str]:
    body = _get(token, path, {"limit": 200})
    items = body.get("data") or body.get("items") or []
    return {i.get("id"): (i.get("name") or i.get("title") or i.get("label") or "") for i in items}


def append_movements(out_path: Path) -> int:
    token = get_token()
    expenses = fetch_expenses(token)
    accounts = fetch_lookup(token, "/expense-accounts")
    suppliers = fetch_lookup(token, "/suppliers")
    teams = fetch_lookup(token, "/teams")
    departments = fetch_lookup(token, "/departments")

    write_header = not out_path.exists()
    with out_path.open("a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["date", "account", "direction", "amount", "currency", "counterparty", "category", "department", "note"])
        for e in expenses:
            amt_obj = e.get("amount") or {}
            amount = amt_obj.get("value") if isinstance(amt_obj, dict) else (e.get("amount_cents", 0) / 100)
            currency = amt_obj.get("currency") if isinstance(amt_obj, dict) else "EUR"
            d = (e.get("paymentDate") or e.get("createdAt") or "")[:10]
            category = accounts.get(e.get("expenseAccountId"), "")
            counterparty = suppliers.get(e.get("supplierId"), e.get("merchantName") or "")
            dept = departments.get(e.get("departmentId")) or teams.get(e.get("teamId"), "")
            w.writerow([d, "moss", "out", f"{float(amount or 0):.2f}", currency, counterparty, category, dept, e.get("type", "")])
    return len(expenses)
