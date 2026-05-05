---
name: cohort-analysis
description: Build a customer cohort table by joining CRM signup data with revenue/invoice data. Default output is CSV (Excel-friendly), with SQL or DuckDB+Evidence as upgrades. Use when the user says "/cohort-analysis", "build a cohort table", "cohort analysis for <client>", "retention by signup month", or "show me NRR by cohort". No cron, no warehouse — one-shot, interactive. Asks 3 questions up front: which CRM, which money source, which output format.
---

# Cohort Analysis

Build a customer cohort retention table from a CRM (signup date) joined to a money source (invoices / charges). One-shot, no scheduling. Default output is CSV — clients open it in Excel.

## Step 1 — Ask 3 questions before doing anything

Ask these in order. Don't skip. Don't pick defaults silently.

1. **Where do your clients live?** (CRM source)
   - `attio` — Attio Persons or Companies, `created_at` is the cohort key
   - `stripe` — Stripe Customers themselves (no separate CRM)
   - `csv` — paste a path to a CSV with columns `customer_id`, `email`, `signup_date`

2. **Where's the money?** (revenue source)
   - `stripe` — Stripe Invoices (paid)
   - `attio` — currency attribute on a CRM record (requires extra info — see Step 1b)
   - `csv` — path to CSV with columns `customer_id` (or `email`), `event_date`, `amount`

3. **Output format?**
   - `csv` (default — opens in Excel)
   - `sql` — DDL + INSERT statements you can run in any SQL engine
   - `evidence` — DuckDB file + Evidence project scaffold (suggest only if they want a live dashboard)

## Step 1b — Attio money source disclaimer (IMPORTANT)

If they picked **Attio for money**, STOP and show this verbatim before going further:

> ⚠️ **Heads up — Attio doesn't store revenue history natively.** It only holds current attribute values, so we have to reconstruct the timeline from date attributes on each customer record. To do that I need three attribute slugs:
>
> 1. **Amount per period** — the recurring amount (e.g. `mrr`, `arr`, `subscription_amount`, `monthly_value`)
> 2. **Date paid / first invoice** — when they started paying (e.g. `date_paid`, `subscription_start`, `first_invoice_date`)
> 3. **Date churned** — *optional*. When they stopped paying. Leave blank and we'll assume they're still active today.
>
> Each customer becomes one event per month between date-paid and date-churned at the amount you give. **This works for steady-state subscriptions** but won't capture mid-cycle upgrades, downgrades, partial refunds, or one-off charges. For real revenue accuracy, point me at Stripe instead — or export your billing data to CSV.
>
> What are the three Attio attribute slugs? (paste them as `amount=mrr date_paid=date_paid date_churned=date_churned`)

Wait for them to give you the 3 slugs (or 2, if they're skipping `date_churned`).

## Step 2 — Confirm env vars are set

After they answer, list which env vars need to be in `.env` and check them:

| Source | Env var |
|--------|---------|
| Attio (CRM or money) | `ATTIO_API_KEY` |
| Stripe (CRM or money) | `STRIPE_SECRET_KEY` |
| CSV | none — just a path |

Run `python skills/cohort-analysis/run.py --check-env --crm <X> --money <Y>` to validate. If a key is missing, stop and tell the user to add it.

## Step 3 — Run

```bash
python skills/cohort-analysis/run.py \
  --crm <attio|stripe|csv> \
  --money <stripe|attio|csv> \
  --output <csv|sql|evidence> \
  --out-dir /tmp/cohort-<client>-<date>
```

Optional flags:
- `--attio-object companies|people` (default `companies`)
- `--attio-amount-attr <slug>` (required if `--money attio`)
- `--attio-date-paid-attr <slug>` (required if `--money attio`)
- `--attio-date-churned-attr <slug>` (optional, only if `--money attio`)
- `--csv-customers <path>` (only if `--crm csv`)
- `--csv-revenue <path>` (only if `--money csv`)
- `--metric revenue|count` (default `revenue` — sum of amounts; `count` = customers still paying)
- `--cohort-grain month|quarter` (default `month`)

Output goes to `/tmp/cohort-<client>-<date>/`:
- `cohort_table.csv` — rows = signup cohort, cols = M0/M1/M2…
- `customers.csv` — normalized signup list (audit trail)
- `revenue.csv` — normalized revenue events (audit trail)
- `cohort.sql` (only if `--output sql`)
- `cohort.duckdb` + `evidence/` (only if `--output evidence`)

## Step 4 — After running

Show a 4-line summary:
- N customers, N revenue events, N cohorts
- Path to `cohort_table.csv`
- One-line read of the matrix (e.g. "Jan-2025 cohort retained 78% of M0 revenue at M6")
- If they picked CSV and the data looks rich, suggest: "If you want a live dashboard, re-run with `--output evidence` — it'll bootstrap an Evidence project from a DuckDB file."

## When to use

- User says `/cohort-analysis` or "cohort analysis for <client>"
- A client asks for retention/NRR by signup month
- Quarterly review of a SaaS book of business

## When NOT to use

- The client wants a continuously refreshing dashboard → recommend ChartMogul or Baremetrics, don't build this.
- The client has <10 customers → cohorts aren't statistically useful, just show a churn list instead.

## Try it without API keys

The `examples/` folder has a fixture you can run end-to-end with no setup:

```bash
python skills/cohort-analysis/run.py \
  --crm csv --money csv \
  --csv-customers skills/cohort-analysis/examples/customers.csv \
  --csv-revenue skills/cohort-analysis/examples/revenue.csv \
  --output csv \
  --out-dir /tmp/cohort-demo
```

## Notes

- Joins are on `email` (lowercased) by default. Stripe customers usually carry email; Attio Persons too. For Companies → Stripe, falls back to `domain` match.
- CSV mode is the universal escape hatch — if the user has an "alternative" billing system (Qonto, Chargebee, custom), they export to CSV and we ingest it.
- No data is sent anywhere. Everything stays local in `/tmp/cohort-<client>-<date>/`.
