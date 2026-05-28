"""Stripe puller, Customers as cohort source, paid Invoices as revenue."""

from __future__ import annotations

from datetime import datetime, timezone

import stripe


def _to_iso(unix_ts: int | None) -> str | None:
    if unix_ts is None:
        return None
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).date().isoformat()


def pull_customers(api_key: str) -> list[dict]:
    stripe.api_key = api_key
    out = []
    for c in stripe.Customer.list(limit=100).auto_paging_iter():
        if c.get("deleted"):
            continue
        out.append({
            "customer_id": c["id"],
            "email": (c.get("email") or "").lower() or None,
            "domain": None,
            "name": c.get("name"),
            "signup_date": _to_iso(c.get("created")),
        })
    return out


def pull_revenue(api_key: str) -> list[dict]:
    stripe.api_key = api_key
    out = []
    for inv in stripe.Invoice.list(status="paid", limit=100).auto_paging_iter():
        amount = (inv.get("amount_paid") or 0) / 100.0
        if amount <= 0:
            continue
        ts = inv.get("status_transitions", {}).get("paid_at") or inv.get("created")
        out.append({
            "customer_id": inv.get("customer"),
            "email": (inv.get("customer_email") or "").lower() or None,
            "event_date": _to_iso(ts),
            "amount": amount,
            "currency": inv.get("currency"),
        })
    return out
