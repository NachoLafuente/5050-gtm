"""Qonto puller — writes balances.csv, cash_movements.csv, invoices.csv.

Required env:
  QONTO_API_KEY     — your Qonto API key
  QONTO_SECRET_KEY  — your Qonto org slug (Qonto's "secret key" looks like an org id)
"""

from __future__ import annotations

import csv
import os
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = "https://thirdparty.qonto.com/v2"


def _headers() -> dict:
    key = os.getenv("QONTO_API_KEY")
    secret = os.getenv("QONTO_SECRET_KEY")
    if not (key and secret):
        raise RuntimeError("QONTO_API_KEY and QONTO_SECRET_KEY must be set")
    return {"Authorization": f"{secret}:{key}"}


def fetch_organization() -> dict:
    r = requests.get(f"{BASE}/organization", headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("organization", {})


def fetch_transactions(bank_account_id: str, settled_from: str) -> list[dict]:
    out = []
    page = 1
    while True:
        params = {
            "bank_account_id": bank_account_id,
            "settled_at_from": settled_from,
            "current_page": page,
            "per_page": 100,
        }
        r = requests.get(f"{BASE}/transactions", headers=_headers(), params=params, timeout=60)
        r.raise_for_status()
        body = r.json()
        page_data = body.get("transactions", [])
        out.extend(page_data)
        next_page = body.get("meta", {}).get("next_page")
        if not next_page:
            break
        page = next_page
    return out


def fetch_invoices() -> list[dict]:
    out = []
    page = 1
    while True:
        params = {"current_page": page, "per_page": 100}
        r = requests.get(f"{BASE}/client_invoices", headers=_headers(), params=params, timeout=60)
        r.raise_for_status()
        body = r.json()
        page_data = body.get("client_invoices", [])
        out.extend(page_data)
        next_page = body.get("meta", {}).get("next_page")
        if not next_page:
            break
        page = next_page
    return out


def write_balances_csv(out_path: Path, org: dict, today: str) -> int:
    accounts = org.get("bank_accounts", [])
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["account", "currency", "balance", "as_of"])
        for a in accounts:
            balance = a.get("balance") or (a.get("balance_cents", 0) / 100)
            w.writerow([a.get("slug") or a.get("iban"), a.get("currency", "EUR"), f"{balance:.2f}", today])
    return len(accounts)


def write_movements_csv(out_path: Path, org: dict, months: int = 6) -> int:
    cutoff = (date.today() - timedelta(days=months * 31)).isoformat()
    accounts = org.get("bank_accounts", [])
    rows = 0
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "account", "direction", "amount", "currency", "counterparty", "category", "department", "note"])
        for a in accounts:
            bid = a.get("id")
            account_label = a.get("slug") or a.get("iban") or bid
            txs = fetch_transactions(bid, cutoff)
            for t in txs:
                d = (t.get("settled_at") or t.get("emitted_at") or "")[:10]
                direction = "in" if t.get("side") == "credit" else "out"
                amount = t.get("amount") or (t.get("amount_cents", 0) / 100)
                counterparty = t.get("counterparty_name") or t.get("label") or ""
                category = t.get("operation_type") or ""
                w.writerow([d, account_label, direction, f"{amount:.2f}", t.get("currency", "EUR"), counterparty, category, "", t.get("note") or ""])
                rows += 1
    return rows


def write_invoices_csv(out_path: Path) -> int:
    invoices = fetch_invoices()
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["invoice_id", "customer", "issued_at", "due_at", "amount", "currency", "status"])
        for inv in invoices:
            client = inv.get("client", {}) or {}
            customer = client.get("name") or client.get("email") or ""
            total = inv.get("total_amount") or {}
            amount = total.get("value") if isinstance(total, dict) else inv.get("total_amount_cents", 0) / 100
            currency = total.get("currency") if isinstance(total, dict) else "EUR"
            w.writerow([
                inv.get("number") or inv.get("id"),
                customer,
                (inv.get("issue_date") or "")[:10],
                (inv.get("due_date") or "")[:10],
                f"{float(amount):.2f}",
                currency,
                inv.get("status", ""),
            ])
    return len(invoices)


def pull_all(out_dir: Path) -> dict:
    org = fetch_organization()
    today = date.today().isoformat()
    return {
        "balances": write_balances_csv(out_dir / "balances.csv", org, today),
        "movements": write_movements_csv(out_dir / "cash_movements.csv", org),
        "invoices": write_invoices_csv(out_dir / "invoices.csv"),
    }
