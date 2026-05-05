"""Build a cohort matrix from a normalized customer list + revenue events."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def _bucket(d: date, grain: str) -> str:
    if grain == "quarter":
        return f"{d.year}-Q{(d.month - 1) // 3 + 1}"
    return f"{d.year}-{d.month:02d}"


def _months_between(a: date, b: date, grain: str) -> int:
    if grain == "quarter":
        return (b.year - a.year) * 4 + ((b.month - 1) // 3 - (a.month - 1) // 3)
    return (b.year - a.year) * 12 + (b.month - a.month)


def _index_customers(customers: list[dict]) -> dict[str, dict]:
    """Build lookup by customer_id, email, and domain."""
    idx = {}
    for c in customers:
        if c.get("customer_id"):
            idx[("id", c["customer_id"])] = c
        if c.get("email"):
            idx[("email", c["email"].lower())] = c
        if c.get("domain"):
            idx[("domain", c["domain"].lower())] = c
    return idx


def _match(event: dict, idx: dict[tuple, dict]) -> dict | None:
    cid = event.get("customer_id")
    if cid and ("id", cid) in idx:
        return idx[("id", cid)]
    email = (event.get("email") or "").lower()
    if email and ("email", email) in idx:
        return idx[("email", email)]
    if email and "@" in email:
        domain = email.split("@", 1)[1]
        if ("domain", domain) in idx:
            return idx[("domain", domain)]
    return None


def build_matrix(
    customers: list[dict],
    revenue: list[dict],
    metric: str = "revenue",
    grain: str = "month",
) -> tuple[dict, dict]:
    idx = _index_customers(customers)

    cohort_of = {}
    for c in customers:
        signup = _parse_date(c.get("signup_date"))
        if signup:
            cohort_of[c["customer_id"]] = (signup, _bucket(signup, grain))

    # matrix[cohort_key][period_offset] = sum_amount or set_of_customer_ids
    if metric == "count":
        matrix: dict[str, dict[int, set]] = defaultdict(lambda: defaultdict(set))
    else:
        matrix: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))

    matched = 0
    for ev in revenue:
        cust = _match(ev, idx)
        if not cust or cust["customer_id"] not in cohort_of:
            continue
        signup, cohort_key = cohort_of[cust["customer_id"]]
        ev_date = _parse_date(ev.get("event_date"))
        if not ev_date:
            continue
        offset = _months_between(signup, ev_date, grain)
        if offset < 0:
            continue
        if metric == "count":
            matrix[cohort_key][offset].add(cust["customer_id"])
        else:
            matrix[cohort_key][offset] += float(ev.get("amount") or 0)
        matched += 1

    if metric == "count":
        matrix = {k: {p: len(v) for p, v in row.items()} for k, row in matrix.items()}

    n_cohorts = len(matrix)
    highlight = None
    if matrix:
        first = sorted(matrix.keys())[0]
        m0 = matrix[first].get(0, 0)
        latest = max(matrix[first].keys()) if matrix[first] else 0
        if m0 and latest > 0:
            ml = matrix[first].get(latest, 0)
            pct = (ml / m0 * 100) if metric == "revenue" else (ml / m0 * 100)
            highlight = (
                f"{first} cohort: M0={m0:,.0f}, M{latest}={ml:,.0f} "
                f"({pct:.0f}% retained, {metric})"
            )

    meta = {
        "n_customers": len(customers),
        "n_events": len(revenue),
        "n_matched_events": matched,
        "n_cohorts": n_cohorts,
        "metric": metric,
        "grain": grain,
        "highlight": highlight,
    }
    return matrix, meta
