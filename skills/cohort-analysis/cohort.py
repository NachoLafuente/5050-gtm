"""Build the full SaaS cohort analysis from a normalized customer list +
revenue events (+ optional CACs).

Output structure (`build_cohorts` returns):
  cohorts: ordered list of cohort labels (e.g. ['2026-01', '2026-02', ...])
  cohort_start_dates: {cohort: first-of-month date}
  max_observable_lt: {cohort: int} - latest lifetime month observable per cohort
  n_customers_base: {cohort: int}
  cohort_mrr_base:  {cohort: float}
  gross_margin: float (0..1)
  cacs: {cohort: float} or {}
  profitable_since: {cohort: int_or_None}
  tables: {
    # Customer churn
    'retained_customers':           {cohort: {lt: int}},
    'churned_customers':            {cohort: {lt: int}},
    'pct_retained_customers':       {cohort: {lt: float}},
    'pct_churned_vs_base_customers':{cohort: {lt: float}},
    'pct_churned_vs_prev_customers':{cohort: {lt: float}},
    # MRR churn (signed: negative = expansion)
    'retained_mrr':                 {cohort: {lt: float}},
    'churned_mrr':                  {cohort: {lt: float}},
    'pct_retained_mrr':             {cohort: {lt: float}},
    'pct_churned_vs_base_mrr':      {cohort: {lt: float}},
    'pct_churned_vs_prev_mrr':      {cohort: {lt: float}},
    # CAC payback (only meaningful if cacs provided)
    'cumulative_gross_profit':      {cohort: {lt: float}},
  }
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone


def _parse_date(s) -> date | None:
    if not s:
        return None
    if isinstance(s, date) and not isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None


def _bucket(d: date, grain: str) -> str:
    if grain == "quarter":
        return f"{d.year}-Q{(d.month - 1) // 3 + 1}"
    return f"{d.year}-{d.month:02d}"


def _bucket_to_start_date(label: str, grain: str) -> date:
    if grain == "quarter":
        year, q = label.split("-Q")
        return date(int(year), (int(q) - 1) * 3 + 1, 1)
    year, month = label.split("-")
    return date(int(year), int(month), 1)


def _periods_between(a: date, b: date, grain: str) -> int:
    if grain == "quarter":
        return (b.year - a.year) * 4 + ((b.month - 1) // 3 - (a.month - 1) // 3)
    return (b.year - a.year) * 12 + (b.month - a.month)


def _index_customers(customers: list[dict]) -> dict[tuple, dict]:
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


def build_cohorts(
    customers: list[dict],
    revenue: list[dict],
    cacs: dict[str, float] | None = None,
    gross_margin: float = 0.8,
    grain: str = "month",
) -> dict:
    cacs = cacs or {}
    idx = _index_customers(customers)

    cohort_of: dict[str, tuple[date, str]] = {}
    for c in customers:
        signup = _parse_date(c.get("signup_date"))
        if signup and c.get("customer_id"):
            cohort_of[c["customer_id"]] = (signup, _bucket(signup, grain))

    cust_at = defaultdict(lambda: defaultdict(set))
    rev_at = defaultdict(lambda: defaultdict(float))

    cutoff: date | None = None
    for ev in revenue:
        cust = _match(ev, idx)
        if not cust or cust["customer_id"] not in cohort_of:
            continue
        signup, cohort = cohort_of[cust["customer_id"]]
        ev_date = _parse_date(ev.get("event_date"))
        if not ev_date:
            continue
        cutoff = ev_date if cutoff is None or ev_date > cutoff else cutoff
        lt = _periods_between(signup, ev_date, grain)
        if lt < 0:
            continue
        cust_at[cohort][lt].add(cust["customer_id"])
        rev_at[cohort][lt] += float(ev.get("amount") or 0)

    if cutoff is None:
        cutoff = datetime.now(timezone.utc).date()

    n_customers_base: dict[str, int] = defaultdict(int)
    for cust_id, (signup, cohort) in cohort_of.items():
        n_customers_base[cohort] += 1

    cohort_labels = sorted(n_customers_base.keys())
    cohort_starts = {c: _bucket_to_start_date(c, grain) for c in cohort_labels}

    max_observable_lt = {
        c: max(0, _periods_between(cohort_starts[c], cutoff, grain))
        for c in cohort_labels
    }
    global_max_lt = max(max_observable_lt.values()) if max_observable_lt else 0

    tables = {
        "retained_customers": defaultdict(dict),
        "churned_customers": defaultdict(dict),
        "pct_retained_customers": defaultdict(dict),
        "pct_churned_vs_base_customers": defaultdict(dict),
        "pct_churned_vs_prev_customers": defaultdict(dict),
        "retained_mrr": defaultdict(dict),
        "churned_mrr": defaultdict(dict),
        "pct_retained_mrr": defaultdict(dict),
        "pct_churned_vs_base_mrr": defaultdict(dict),
        "pct_churned_vs_prev_mrr": defaultdict(dict),
        "cumulative_gross_profit": defaultdict(dict),
    }
    profitable_since: dict[str, int | None] = {}

    for cohort in cohort_labels:
        base_n = n_customers_base[cohort]
        m0_mrr = rev_at[cohort].get(0, 0.0)
        max_lt = max_observable_lt[cohort]

        prev_n: int | None = None
        prev_mrr: float | None = None
        cumulative = 0.0
        cohort_cac = cacs.get(cohort)
        breakeven: int | None = None

        for lt in range(max_lt + 1):
            n_lt = len(cust_at[cohort].get(lt, set()))
            mrr_lt = rev_at[cohort].get(lt, 0.0)

            tables["retained_customers"][cohort][lt] = n_lt
            churned_n = 0 if prev_n is None else max(0, prev_n - n_lt)
            tables["churned_customers"][cohort][lt] = churned_n
            tables["pct_retained_customers"][cohort][lt] = (
                n_lt / base_n if base_n else 0.0
            )
            tables["pct_churned_vs_base_customers"][cohort][lt] = (
                churned_n / base_n if base_n else 0.0
            )
            tables["pct_churned_vs_prev_customers"][cohort][lt] = (
                churned_n / prev_n if prev_n else 0.0
            )

            tables["retained_mrr"][cohort][lt] = mrr_lt
            churned_mrr_val = 0.0 if prev_mrr is None else (prev_mrr - mrr_lt)
            tables["churned_mrr"][cohort][lt] = churned_mrr_val
            tables["pct_retained_mrr"][cohort][lt] = (
                mrr_lt / m0_mrr if m0_mrr else 0.0
            )
            tables["pct_churned_vs_base_mrr"][cohort][lt] = (
                churned_mrr_val / m0_mrr if m0_mrr else 0.0
            )
            tables["pct_churned_vs_prev_mrr"][cohort][lt] = (
                churned_mrr_val / prev_mrr if prev_mrr else 0.0
            )

            cumulative += mrr_lt * gross_margin
            tables["cumulative_gross_profit"][cohort][lt] = cumulative
            if cohort_cac and breakeven is None and cumulative >= cohort_cac:
                breakeven = lt

            prev_n = n_lt
            prev_mrr = mrr_lt

        profitable_since[cohort] = breakeven

    return {
        "cohorts": cohort_labels,
        "cohort_start_dates": cohort_starts,
        "max_observable_lt": max_observable_lt,
        "global_max_lt": global_max_lt,
        "n_customers_base": dict(n_customers_base),
        "cohort_mrr_base": {c: rev_at[c].get(0, 0.0) for c in cohort_labels},
        "gross_margin": gross_margin,
        "cacs": dict(cacs),
        "profitable_since": profitable_since,
        "cutoff_date": cutoff,
        "tables": {k: dict(v) for k, v in tables.items()},
    }


def quick_summary(data: dict) -> str:
    cohorts = data["cohorts"]
    if not cohorts:
        return "no cohorts"
    first = cohorts[0]
    base = data["n_customers_base"][first]
    base_mrr = data["cohort_mrr_base"][first]
    max_lt = data["max_observable_lt"][first]
    if max_lt < 1 or base == 0:
        return f"{first} cohort: {base} customers (insufficient history for retention)"
    last_pct = data["tables"]["pct_retained_mrr"][first].get(max_lt, 0) * 100
    last_n = data["tables"]["retained_customers"][first].get(max_lt, 0)
    return (
        f"{first} cohort: {base} customers @ ${base_mrr:,.0f} MRR → "
        f"M{max_lt}: {last_n} customers, {last_pct:.0f}% MRR retained"
    )
