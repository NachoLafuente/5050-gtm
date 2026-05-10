"""CFO compute layer: load CSVs, compute the metrics.

All inputs are dicts (CSV rows). All outputs are plain dicts/lists.
No I/O here besides CSV reading. Pure functions for everything else.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()


def _to_float(s: str) -> float:
    if s is None or s == "":
        return 0.0
    return float(str(s).replace(",", "").strip())


def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))


def load_all(csv_dir: Path) -> dict:
    return {
        "customers": load_csv(csv_dir / "customers.csv"),
        "movements": load_csv(csv_dir / "cash_movements.csv"),
        "invoices": load_csv(csv_dir / "invoices.csv"),
        "balances": load_csv(csv_dir / "balances.csv"),
    }


def compute_cash_balance(balances: list[dict]) -> dict:
    by_currency: dict[str, float] = defaultdict(float)
    by_account: dict[str, float] = {}
    for b in balances:
        amt = _to_float(b["balance"])
        cur = b.get("currency", "EUR")
        by_currency[cur] += amt
        by_account[b["account"]] = amt
    return {
        "by_currency": dict(by_currency),
        "by_account": by_account,
        "total": sum(by_currency.values()),
    }


def compute_burn(movements: list[dict], months: int = 3, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    cutoff = as_of - timedelta(days=months * 30)

    monthly_in: dict[str, float] = defaultdict(float)
    monthly_out: dict[str, float] = defaultdict(float)

    for m in movements:
        d = _parse_date(m.get("date"))
        if d is None or d < cutoff or d > as_of:
            continue
        if m.get("category") == "transfer":
            continue
        key = d.strftime("%Y-%m")
        amt = _to_float(m["amount"])
        if m["direction"] == "in":
            monthly_in[key] += amt
        else:
            monthly_out[key] += amt

    months_seen = sorted(set(monthly_in.keys()) | set(monthly_out.keys()))
    rows = [
        {
            "month": k,
            "inflow": monthly_in.get(k, 0.0),
            "outflow": monthly_out.get(k, 0.0),
            "net": monthly_in.get(k, 0.0) - monthly_out.get(k, 0.0),
        }
        for k in months_seen
    ]
    if not rows:
        return {"months": [], "avg_net_burn": 0.0, "avg_gross_burn": 0.0}
    avg_net = -sum(r["net"] for r in rows) / len(rows)
    avg_gross = sum(r["outflow"] for r in rows) / len(rows)
    return {"months": rows, "avg_net_burn": avg_net, "avg_gross_burn": avg_gross}


def compute_runway(cash_total: float, avg_net_burn: float) -> float:
    if avg_net_burn <= 0:
        return float("inf")
    return cash_total / avg_net_burn


def compute_mrr(customers: list[dict]) -> dict:
    active = [c for c in customers if c.get("status") == "active"]
    mrr = sum(_to_float(c.get("mrr", 0)) for c in active)
    return {
        "mrr": mrr,
        "arr": mrr * 12,
        "active_customers": len(active),
        "churned_customers": sum(1 for c in customers if c.get("status") == "churned"),
    }


def compute_concentration(customers: list[dict]) -> dict:
    active = sorted(
        [c for c in customers if c.get("status") == "active"],
        key=lambda c: _to_float(c.get("mrr", 0)),
        reverse=True,
    )
    total = sum(_to_float(c.get("mrr", 0)) for c in active)
    if total == 0:
        return {"top_1_pct": 0, "top_5_pct": 0, "top_10_pct": 0, "top_customers": []}

    def pct(n: int) -> float:
        return 100 * sum(_to_float(c.get("mrr", 0)) for c in active[:n]) / total

    top = [
        {
            "name": c["customer_name"],
            "mrr": _to_float(c.get("mrr", 0)),
            "pct": 100 * _to_float(c.get("mrr", 0)) / total,
            "plan": c.get("plan", ""),
        }
        for c in active[:10]
    ]
    return {
        "top_1_pct": pct(1),
        "top_5_pct": pct(5),
        "top_10_pct": pct(10),
        "top_customers": top,
    }


def compute_ar_aging(invoices: list[dict], as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    buckets = {"current": 0.0, "1-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
    rows = []
    for inv in invoices:
        if inv.get("status") != "unpaid":
            continue
        due = _parse_date(inv.get("due_at"))
        amt = _to_float(inv.get("amount", 0))
        if due is None:
            continue
        days_past = (as_of - due).days
        if days_past < 0:
            bucket = "current"
        elif days_past <= 30:
            bucket = "1-30"
        elif days_past <= 60:
            bucket = "31-60"
        elif days_past <= 90:
            bucket = "61-90"
        else:
            bucket = "90+"
        buckets[bucket] += amt
        rows.append(
            {
                "invoice_id": inv["invoice_id"],
                "customer": inv["customer"],
                "due_at": inv["due_at"],
                "amount": amt,
                "days_past_due": days_past,
                "bucket": bucket,
            }
        )
    return {"buckets": buckets, "total": sum(buckets.values()), "rows": rows}


def compute_dso(invoices: list[dict], days: int = 90, as_of: date | None = None) -> float:
    as_of = as_of or date.today()
    cutoff = as_of - timedelta(days=days)
    period_sales = sum(
        _to_float(i.get("amount", 0))
        for i in invoices
        if (d := _parse_date(i.get("issued_at"))) and d >= cutoff and i.get("status") in ("paid", "unpaid")
    )
    if period_sales == 0:
        return 0.0
    ar = sum(_to_float(i.get("amount", 0)) for i in invoices if i.get("status") == "unpaid")
    return (ar / period_sales) * days


def compute_spend_by_category(movements: list[dict]) -> list[dict]:
    cat: dict[str, float] = defaultdict(float)
    for m in movements:
        if m.get("direction") != "out" or m.get("category") in ("transfer", "revenue"):
            continue
        cat[m.get("category") or "uncategorized"] += _to_float(m.get("amount", 0))
    rows = sorted([{"category": k, "amount": v} for k, v in cat.items()], key=lambda r: r["amount"], reverse=True)
    total = sum(r["amount"] for r in rows)
    for r in rows:
        r["pct"] = (100 * r["amount"] / total) if total else 0
    return rows


def compute_top_vendors(movements: list[dict], n: int = 10) -> list[dict]:
    by_vendor: dict[str, dict] = defaultdict(lambda: {"amount": 0.0, "count": 0})
    for m in movements:
        if m.get("direction") != "out" or m.get("category") in ("transfer", "revenue"):
            continue
        v = m.get("counterparty") or "unknown"
        by_vendor[v]["amount"] += _to_float(m.get("amount", 0))
        by_vendor[v]["count"] += 1
    rows = [{"vendor": k, **v} for k, v in by_vendor.items()]
    rows.sort(key=lambda r: r["amount"], reverse=True)
    total = sum(r["amount"] for r in rows)
    for r in rows[:n]:
        r["pct"] = (100 * r["amount"] / total) if total else 0
    return rows[:n]


def compute_recurring_vendors(movements: list[dict], min_occurrences: int = 3) -> list[dict]:
    by_vendor: dict[str, list[float]] = defaultdict(list)
    for m in movements:
        if m.get("direction") != "out" or m.get("category") in ("transfer", "revenue"):
            continue
        v = m.get("counterparty") or "unknown"
        by_vendor[v].append(_to_float(m.get("amount", 0)))
    rows = []
    for v, amts in by_vendor.items():
        if len(amts) < min_occurrences:
            continue
        avg = sum(amts) / len(amts)
        rows.append(
            {
                "vendor": v,
                "occurrences": len(amts),
                "avg_amount": avg,
                "annualized": avg * 12,
                "total": sum(amts),
            }
        )
    rows.sort(key=lambda r: r["annualized"], reverse=True)
    return rows


def compute_departmental_burn(movements: list[dict]) -> list[dict]:
    by_dept: dict[str, float] = defaultdict(float)
    for m in movements:
        if m.get("direction") != "out" or m.get("category") in ("transfer", "revenue"):
            continue
        dept = m.get("department") or "unallocated"
        by_dept[dept] += _to_float(m.get("amount", 0))
    rows = sorted(
        [{"department": k, "amount": v} for k, v in by_dept.items()],
        key=lambda r: r["amount"],
        reverse=True,
    )
    total = sum(r["amount"] for r in rows)
    for r in rows:
        r["pct"] = (100 * r["amount"] / total) if total else 0
    return rows


def summarize(data: dict, as_of: date | None = None) -> dict:
    as_of = as_of or date.today()
    cash = compute_cash_balance(data["balances"])
    burn = compute_burn(data["movements"], months=3, as_of=as_of)
    runway = compute_runway(cash["total"], burn["avg_net_burn"])
    mrr = compute_mrr(data["customers"])
    conc = compute_concentration(data["customers"])
    ar = compute_ar_aging(data["invoices"], as_of=as_of)
    dso = compute_dso(data["invoices"], as_of=as_of)
    spend_cat = compute_spend_by_category(data["movements"])
    top_vendors = compute_top_vendors(data["movements"])
    recurring = compute_recurring_vendors(data["movements"])
    dept_burn = compute_departmental_burn(data["movements"])

    burn_multiple = None
    if mrr["mrr"] > 0 and burn["avg_net_burn"] > 0:
        burn_multiple = burn["avg_net_burn"] / mrr["mrr"]

    return {
        "as_of": as_of.isoformat(),
        "cash": cash,
        "burn": burn,
        "runway_months": runway,
        "burn_multiple": burn_multiple,
        "mrr": mrr,
        "concentration": conc,
        "ar": ar,
        "dso": dso,
        "spend_by_category": spend_cat,
        "top_vendors": top_vendors,
        "recurring_vendors": recurring,
        "departmental_burn": dept_burn,
    }
