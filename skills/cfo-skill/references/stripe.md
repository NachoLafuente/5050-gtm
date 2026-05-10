# Stripe — Authoritative SaaS Revenue Source

Stripe is the **canonical revenue source** for SaaS founders that bill through it. If you have Stripe AND Attio, Stripe wins on customer-side data — it has actual subscription state, real MRR, and authoritative churn timestamps.

## Auth

- Header: `Authorization: Bearer {STRIPE_SECRET_KEY}` (the SDK handles this).
- Env var: `STRIPE_SECRET_KEY` (use a **restricted** key with read-only scope on customers, subscriptions, invoices, and payouts).
- Base URL: `https://api.stripe.com/v1`.
- Docs: https://stripe.com/docs/api

## CFO Question → Endpoint Map

### "What's our MRR / ARR?"

```
GET /v1/subscriptions?status=all&limit=100
```

For each active/trialing/past_due subscription, sum `price.unit_amount × quantity`, normalized to a monthly cadence:
- `interval=month` → divide by `interval_count`
- `interval=year` → divide by `12 × interval_count`
- `interval=week` → multiply by `52/12 / interval_count`

ARR = MRR × 12.

### "Active customers"

`GET /v1/customers?limit=100` — paginate with `starting_after`. Cross-reference with subscriptions to determine status:
- Has active/trialing/past_due sub → `active`
- Had a sub, all canceled → `churned` (use latest `canceled_at`)
- No sub ever → `lead` (skip; not a paying customer)

### "Customer concentration"

After computing per-customer MRR (above), sort descending. Compute top 1 / 5 / 10 percentages of total MRR.

### "AR aging — unpaid invoices"

```
GET /v1/invoices?status=open&limit=100
```

Each invoice has `created` (issue date), `due_date`, and `total` (in cents).

Bucket by days past `due_date` (vs today):
- `<0` → current
- `1-30` / `31-60` / `61-90` / `90+`

### "DSO"

Combine `status=open` (AR) with `status=paid` issued in the last 90 days:

```
DSO = (AR / total_invoiced_in_last_90d) × 90
```

### "Cash inflows from Stripe"

```
GET /v1/payouts?limit=100
```

Each payout is a single deposit to your bank. If you also pull Qonto, **don't write these** — Qonto already shows them as bank credits and you'd double-count. The puller respects `STRIPE_INCLUDE_PAYOUTS=1` to opt in only when Qonto isn't connected.

## Stripe + Attio: who wins?

| Field | Authoritative source |
|-------|----------------------|
| MRR / ARR | Stripe (real subscription state) |
| Customer count | Stripe (paying) vs Attio (CRM total) — different definitions |
| Plan / pricing | Stripe (current price) |
| Churn timestamp | Stripe (`subscription.canceled_at`) |
| Customer name / industry / segment | Attio (richer metadata) |
| Pipeline / deals | Attio |
| Lifecycle metadata | Attio |

If both pullers run, the puller order in `--providers` decides who wins on overlap. Default order writes Stripe last for `customers.csv` so Stripe MRR wins.

## Rate limits

Stripe limits 100 read req/sec in live mode (lower in test mode). The SDK handles backoff automatically. Pagination is cursor-based via `starting_after`.

## What Stripe CAN'T do

- Bank balance / total cash → Qonto
- Categorized expenses (SaaS vs payroll vs marketing) → Moss
- Pipeline / non-paying leads / segmentation → Attio
- AP (vendor invoices owed by you) → Qonto / Moss
