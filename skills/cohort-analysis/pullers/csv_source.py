"""CSV puller — escape hatch for any CRM or billing system that exports CSV.

Customers CSV columns: customer_id, email, signup_date [, name, domain]
Revenue CSV columns:   customer_id (or email), event_date, amount [, currency]
CACs CSV columns:      cohort, cac_amount
"""

from __future__ import annotations

import csv
from pathlib import Path


def pull_customers(path: str) -> list[dict]:
    out = []
    with open(Path(path).expanduser()) as f:
        for row in csv.DictReader(f):
            out.append({
                "customer_id": row.get("customer_id") or row.get("id"),
                "email": (row.get("email") or "").lower() or None,
                "domain": (row.get("domain") or "").lower() or None,
                "name": row.get("name"),
                "signup_date": row.get("signup_date") or row.get("created_at"),
            })
    return out


def pull_revenue(path: str) -> list[dict]:
    out = []
    with open(Path(path).expanduser()) as f:
        for row in csv.DictReader(f):
            amount = row.get("amount")
            if not amount:
                continue
            out.append({
                "customer_id": row.get("customer_id") or row.get("id"),
                "email": (row.get("email") or "").lower() or None,
                "event_date": row.get("event_date") or row.get("date"),
                "amount": float(amount),
                "currency": row.get("currency"),
            })
    return out


def pull_cacs(path: str) -> dict[str, float]:
    """Load a CAC-per-cohort CSV. Columns: cohort, cac_amount."""
    out: dict[str, float] = {}
    with open(Path(path).expanduser()) as f:
        for row in csv.DictReader(f):
            cohort = (row.get("cohort") or "").strip()
            amount = row.get("cac_amount") or row.get("cac")
            if not cohort or not amount:
                continue
            out[cohort] = float(amount)
    return out
