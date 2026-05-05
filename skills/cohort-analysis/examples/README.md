# Demo data

A realistic SaaS-shaped fixture you can run end-to-end with no API credentials:

- **`customers.csv`** — 914 customers across 8 monthly cohorts (Jan-Aug 2026)
- **`revenue.csv`** — ~4,900 monthly revenue events through Oct 2026 with ~94% M1 retention, ~80% M9 retention, and gentle price expansion on retained customers
- **`cacs.csv`** — CAC per cohort, scaled so most break even around month 6-8

## Run it

```bash
# From the repo root, with the venv active and openpyxl installed:
python skills/cohort-analysis/run.py \
  --crm csv --money csv \
  --csv-customers skills/cohort-analysis/examples/customers.csv \
  --csv-revenue skills/cohort-analysis/examples/revenue.csv \
  --cacs skills/cohort-analysis/examples/cacs.csv \
  --gross-margin 0.8 \
  --output all \
  --out-dir /tmp/cohort-demo

open /tmp/cohort-demo/cohort_workbook.xlsx
```

## What you get

- `cohort_workbook.xlsx` — styled workbook with three sections (Customer Churn, MRR Churn, CAC Payback) and conditional formatting
- 11 per-section CSVs — one per metric, for SQL/raw consumption
- `00_summary.csv` — base counts, base MRR, profitable-since per cohort
- `audit_customers.csv` + `audit_revenue.csv` — what got included as input

The fixture is generated so the Jan-2026 cohort starts at ~$8,000 MRR and decays to ~$6,300 by M9 (~80% NRR), with CAC payback hitting around M7-M8 — typical mid-stage B2B-SaaS shape that you can sanity-check the math against.
