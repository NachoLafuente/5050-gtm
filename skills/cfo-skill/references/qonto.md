# Qonto: Cash, AR & Transactions

Qonto holds the **cash side** of the CFO picture: bank balance, transactions, AR (client invoices).

## Auth

- Header: `Authorization: {QONTO_SECRET_KEY}:{QONTO_API_KEY}`
- The secret key is the org slug (e.g. `acme-corp-1234`); the API key is the actual key.
- Base URL: `https://thirdparty.qonto.com/v2`
- Docs: `https://docs.qonto.com/` (site blocks scraping; rely on this reference)

## CFO Question → Endpoint Map

### "What's our cash balance?"

```http
GET /v2/organization
```

Returns the authenticated organization plus a `bank_accounts` array. Each bank account has:
- `id` (UUID)
- `iban`
- `currency`
- `balance`, numeric cents in `balance_cents` and minor unit
- `authorized_balance_cents`, balance minus pending holds

Sum `balance_cents` across all bank accounts (after currency-converting if multi-currency). Report per-account too, concentrating cash in one account is a risk.

### "What's our trailing 3-month burn?"

```http
GET /v2/transactions?bank_account_id={id}&settled_at_from=<3 months ago iso>&per_page=100
```

Paginate via `meta.next_page` until exhausted. Sum:

- **Inflows**: transactions with `side = "credit"` (money in)
- **Outflows**: transactions with `side = "debit"` (money out)

```
Net burn = (sum of debits − sum of credits) / N months
```

Use trailing 3 months for stability. For monthly granularity, group by `settled_at` month.

⚠️ This includes EVERYTHING, payroll, rent, vendor payments, refunds, owner draws. Categorization happens in Moss (for cards) or in Qonto's own labels (if user labels transactions). Without categorization, "burn" is gross outflow, not OpEx.

### "Runway"

```
Runway (months) = Total Cash / Trailing 3-month Avg Net Burn
```

Pull cash balance + trailing burn from the two queries above. Flag if:
- Burn is volatile (max-min spread > 50% of mean), runway is approximate.
- Runway < 12 months → danger-zone heuristic.

### "AR aging: unpaid invoices by age"

```http
GET /v2/client_invoices?status=unpaid&per_page=100
```

Each invoice has `due_date`. Bucket by days past due:

| Bucket | Days past due |
|--------|---------------|
| Current | < 0 (not yet due) |
| 1-30 | 1-30 |
| 31-60 | 31-60 |
| 61-90 | 61-90 |
| 90+ | over 90 |

Heuristic: anything 60+ days past due is a collection problem.

### "Days Sales Outstanding (DSO)"

```
DSO = (Accounts Receivable / Total Credit Sales over period) × Days in period
```

- AR = sum of unpaid invoices (above)
- Credit sales = sum of `total_amount` on invoices issued in the period (status `paid` + `unpaid`)

```http
GET /v2/client_invoices?issue_date_from=<period start>&issue_date_to=<period end>&per_page=100
```

Heuristic: DSO < 30 excellent · 30-45 good · 45-60 watch · >60 problem.

### "What's our biggest single outflow this month?"

```http
GET /v2/transactions?bank_account_id={id}&settled_at_from=<month start>&side=debit&sort_by=amount&per_page=20
```

Sort client-side if the API doesn't accept `sort_by` (some Qonto endpoints don't). Report top 10 with counterparty + amount.

### "Recurring outflows / subscriptions"

Qonto doesn't classify recurring vs one-off natively. Approximate by:

1. Pull last 90 days of debits.
2. Group by counterparty name (`label` or `counterparty_name`).
3. Flag any counterparty appearing 3+ times with similar amounts.

This is a heuristic, verify before acting.

## What Qonto CAN'T do

- Customer revenue / MRR → use Attio
- Itemized expense categorization (food vs SaaS vs travel) → use Moss for card spend
- Multi-org consolidated view (one API key per Qonto org)
- Future-dated cash projections

## Rate limits

Not publicly documented in detail. Backoff on `429`. The skill should fetch in batches and cache for the session.

## Qonto API surface (relevant subset)

| Endpoint | Use |
|----------|-----|
| `GET /v2/organization` | Auth check + bank account list with balances |
| `GET /v2/transactions` | Transaction list (filterable by account, date, side) |
| `GET /v2/transactions/{id}` | Single transaction detail |
| `GET /v2/client_invoices` | Issued invoices (AR) |
| `GET /v2/clients` | Customer list (Qonto-side, not the source of truth, Attio is) |
| `GET /v2/attachments/{id}` | Receipt/file attached to transaction |
| `GET /v2/memberships` | Org members (for headcount sanity check) |

Stick to GET endpoints in this skill. Writes are out of scope.
