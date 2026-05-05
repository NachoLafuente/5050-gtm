# Demo data

Run the skill against this fixture to see what the output looks like:

```bash
python skills/cohort-analysis/run.py \
  --crm csv --money csv \
  --csv-customers skills/cohort-analysis/examples/customers.csv \
  --csv-revenue skills/cohort-analysis/examples/revenue.csv \
  --output csv \
  --out-dir /tmp/cohort-demo

cat /tmp/cohort-demo/cohort_table.csv
```

You should see a 4-cohort matrix (Jan/Feb/Mar/Apr 2026) with a few months of retention. The Jan-2026 cohort drops to 33% by M2 — that's customer c2 churning while c1 keeps paying.

This fixture is here so you can try the pipeline without setting up Attio or Stripe credentials.
