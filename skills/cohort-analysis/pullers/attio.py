"""Attio puller, Companies or Persons as customers, currency + date attrs as
revenue timeline.

Attio doesn't store revenue history natively, so we reconstruct it from:
  - amount_attr (e.g. `mrr`), the recurring amount
  - date_paid_attr, when the customer started paying
  - date_churned_attr (optional), when they churned (or assume still active)

Each customer becomes one event per month between date_paid and
date_churned (or today). This works for steady-state subscriptions but
won't capture mid-cycle upgrades/downgrades, for that, use Stripe.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import requests

API = "https://api.attio.com/v2"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _query_records(api_key: str, object_slug: str) -> list[dict]:
    records = []
    cursor = None
    while True:
        body = {"limit": 500}
        if cursor:
            body["cursor"] = cursor
        r = requests.post(
            f"{API}/objects/{object_slug}/records/query",
            headers=_headers(api_key),
            json=body,
            timeout=60,
        )
        r.raise_for_status()
        page = r.json()
        records.extend(page.get("data", []))
        cursor = page.get("next_cursor")
        if not cursor:
            break
    return records


def _first_value(values: list, key: str = "value") -> str | None:
    if not values:
        return None
    return values[0].get(key)


def _first_email(values: list) -> str | None:
    if not values:
        return None
    v = values[0]
    return v.get("email_address") or v.get("value")


def _first_domain(values: list) -> str | None:
    if not values:
        return None
    v = values[0]
    return v.get("domain") or v.get("value")


def _parse_date(s) -> date | None:
    if not s:
        return None
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    year = d.year + m // 12
    month = m % 12 + 1
    return date(year, month, 1)


def pull_customers(api_key: str, object_slug: str = "companies") -> list[dict]:
    records = _query_records(api_key, object_slug)
    out = []
    for rec in records:
        vals = rec.get("values", {})
        rid = rec["id"]["record_id"]
        email = _first_email(vals.get("email_addresses") or vals.get("primary_email_address") or [])
        domain = _first_domain(vals.get("domains") or [])
        created = rec.get("created_at") or _first_value(vals.get("created_at") or [])
        name = _first_value(vals.get("name") or []) or _first_value(vals.get("full_name") or [])
        out.append({
            "customer_id": rid,
            "email": (email or "").lower() or None,
            "domain": (domain or "").lower() or None,
            "name": name,
            "signup_date": created,
        })
    return out


def pull_revenue(
    api_key: str,
    object_slug: str,
    amount_attr: str,
    date_paid_attr: str,
    date_churned_attr: str | None = None,
) -> list[dict]:
    """Expand each record into one monthly revenue event between date_paid
    and date_churned (or today)."""
    records = _query_records(api_key, object_slug)
    today = datetime.now(timezone.utc).date()
    out = []
    for rec in records:
        vals = rec.get("values", {})
        rid = rec["id"]["record_id"]

        amount_vals = vals.get(amount_attr) or []
        if not amount_vals:
            continue
        amt = amount_vals[0].get("currency_value") or amount_vals[0].get("value")
        if amt is None:
            continue

        paid_vals = vals.get(date_paid_attr) or []
        start = _parse_date(paid_vals[0].get("value") if paid_vals else None)
        if not start:
            continue

        end = today
        if date_churned_attr:
            churn_vals = vals.get(date_churned_attr) or []
            churned = _parse_date(churn_vals[0].get("value") if churn_vals else None)
            if churned:
                end = churned

        cursor = date(start.year, start.month, 1)
        end_month = date(end.year, end.month, 1)
        while cursor <= end_month:
            out.append({
                "customer_id": rid,
                "email": None,
                "event_date": cursor.isoformat(),
                "amount": float(amt),
            })
            cursor = _add_months(cursor, 1)
    return out
