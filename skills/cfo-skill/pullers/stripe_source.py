"""Stripe puller — writes customers.csv (with MRR from active subs) and invoices.csv.

Stripe is the canonical SaaS revenue source. For founders billing through Stripe,
this is the most accurate MRR/ARR/churn picture.

Required env: STRIPE_SECRET_KEY

Notes:
  - We do NOT write cash_movements from Stripe by default — Stripe payouts already
    show up as bank credits in Qonto, so adding them again would double-count.
    If you don't pull Qonto, you can opt in via STRIPE_INCLUDE_PAYOUTS=1.
"""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import stripe


def _setup() -> None:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise RuntimeError("STRIPE_SECRET_KEY not set")
    stripe.api_key = key


def _interval_to_monthly(amount: float, interval: str, interval_count: int) -> float:
    """Normalize a price (in major currency units) to a monthly equivalent."""
    if interval == "month":
        return amount / max(interval_count, 1)
    if interval == "year":
        return amount / (12 * max(interval_count, 1))
    if interval == "week":
        return amount * (52 / 12) / max(interval_count, 1)
    if interval == "day":
        return amount * 30 / max(interval_count, 1)
    return amount


def fetch_customers_with_mrr() -> dict:
    """Returns {customer_id: {name, email, created, status, mrr, plan, churned_at}}."""
    _setup()

    customers: dict[str, dict] = {}
    for c in stripe.Customer.list(limit=100).auto_paging_iter():
        customers[c.id] = {
            "name": c.name or c.email or c.id,
            "email": c.email or "",
            "created": datetime.utcfromtimestamp(c.created).date().isoformat(),
            "status": "lead",
            "mrr": 0.0,
            "plan": "",
            "churned_at": "",
        }

    sub_mrr: dict[str, float] = defaultdict(float)
    sub_plan: dict[str, str] = {}
    for s in stripe.Subscription.list(status="all", limit=100).auto_paging_iter():
        cid = s.customer if isinstance(s.customer, str) else s.customer.id
        items = s.get("items", {}).get("data", [])
        for item in items:
            price = item.get("price") or {}
            unit = (price.get("unit_amount") or 0) / 100
            qty = item.get("quantity", 1)
            recurring = price.get("recurring") or {}
            interval = recurring.get("interval", "month")
            interval_count = recurring.get("interval_count", 1)
            monthly = _interval_to_monthly(unit * qty, interval, interval_count)

            if s.status in ("active", "trialing", "past_due"):
                sub_mrr[cid] += monthly
                if cid in customers:
                    customers[cid]["status"] = "active"
            elif s.status in ("canceled", "incomplete_expired", "unpaid"):
                if cid in customers and customers[cid]["status"] != "active":
                    customers[cid]["status"] = "churned"
                    if s.get("canceled_at"):
                        customers[cid]["churned_at"] = (
                            datetime.utcfromtimestamp(s["canceled_at"]).date().isoformat()
                        )

            nickname = price.get("nickname") or ""
            product = price.get("product")
            if not nickname and product:
                try:
                    p = stripe.Product.retrieve(product) if isinstance(product, str) else product
                    nickname = p.get("name", "")
                except Exception:
                    pass
            sub_plan[cid] = nickname or sub_plan.get(cid, "")

    for cid, mrr in sub_mrr.items():
        if cid in customers:
            customers[cid]["mrr"] = mrr
            customers[cid]["plan"] = sub_plan.get(cid, "")

    return customers


def write_customers_csv(out_path: Path) -> int:
    customers = fetch_customers_with_mrr()
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["customer_id", "customer_name", "status", "signed_up_at", "churned_at", "mrr", "plan"])
        for cid, c in customers.items():
            if c["status"] == "lead" and c["mrr"] == 0:
                continue
            w.writerow([cid, c["name"], c["status"], c["created"], c["churned_at"], f"{c['mrr']:.2f}", c["plan"]])
    return len(customers)


def write_invoices_csv(out_path: Path) -> int:
    _setup()
    rows = []
    for inv in stripe.Invoice.list(limit=100, status="open").auto_paging_iter():
        rows.append(_invoice_row(inv, "unpaid"))
    for inv in stripe.Invoice.list(limit=100, status="paid").auto_paging_iter():
        rows.append(_invoice_row(inv, "paid"))

    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["invoice_id", "customer", "issued_at", "due_at", "amount", "currency", "status"])
        w.writerows(rows)
    return len(rows)


def _invoice_row(inv, status: str) -> list:
    issued = datetime.utcfromtimestamp(inv.created).date().isoformat()
    due_ts = inv.get("due_date")
    due = datetime.utcfromtimestamp(due_ts).date().isoformat() if due_ts else issued
    amount = (inv.total or 0) / 100
    customer = inv.get("customer_email") or inv.get("customer_name") or inv.customer or ""
    return [inv.number or inv.id, customer, issued, due, f"{amount:.2f}", (inv.currency or "eur").upper(), status]


def append_payouts(out_path: Path) -> int:
    """Optional: append Stripe payouts as bank inflows. Only enable when NOT using Qonto."""
    if os.getenv("STRIPE_INCLUDE_PAYOUTS") != "1":
        return 0
    _setup()
    write_header = not out_path.exists()
    n = 0
    with out_path.open("a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["date", "account", "direction", "amount", "currency", "counterparty", "category", "department", "note"])
        for p in stripe.Payout.list(limit=100).auto_paging_iter():
            d = datetime.utcfromtimestamp(p.arrival_date).date().isoformat()
            amt = (p.amount or 0) / 100
            w.writerow([d, "stripe_payout", "in", f"{amt:.2f}", (p.currency or "eur").upper(), "Stripe", "revenue", "", "stripe payout"])
            n += 1
    return n


def pull_all(out_dir: Path) -> dict:
    return {
        "customers": write_customers_csv(out_dir / "customers.csv"),
        "invoices": write_invoices_csv(out_dir / "invoices.csv"),
        "payouts": append_payouts(out_dir / "cash_movements.csv"),
    }
