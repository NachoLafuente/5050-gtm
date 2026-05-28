# Moss: Spend, Vendors & Departments

Moss holds the **categorized spend side** of the CFO picture: card transactions, expenses, suppliers, departments, accounting attributes.

## Auth

OAuth 2.0 client credentials flow:

1. **Token exchange**: `POST {server_url}/oauth2/token` with `MOSS_KEY_ID` (`kid_…`) and `MOSS_SECRET_KEY` (`sk_…`).
2. Returns a Bearer JWT, expires in 1 hour. Cache for the session, refresh on 401.
3. Use `Authorization: Bearer <token>` on all subsequent calls.
4. Scope `read` is sufficient for this skill, never request `write`.

- Base URL: `https://public-api.getmoss.com/v1`
- Spec: `https://developers.getmoss.com/specs/latest/openapi.yaml`
- Rate limits: 180 req/min on reads, 20 req/min on writes.

## CFO Question → Endpoint Map

### "Where is spend going? (last N days, by category)"

```http
GET /v1/expenses?from=<iso>&to=<iso>&limit=200
```

Each expense has:
- `amount` (with currency)
- `expenseAccountId` → maps to GL category via `GET /v1/expense-accounts/{id}`
- `supplierId` → vendor
- `teamId` / `departmentId` → cost center
- `dimensionItemIds` → custom tags (project, campaign, etc.)
- `type`, card transaction, invoice, reimbursement
- `status`, pending, approved, exported

**Strategy**: paginate full result set, then group by `expenseAccountId`. Resolve account names in a second pass via `GET /v1/expense-accounts`.

### "Top 10 vendors by spend (last 90 days)"

```http
GET /v1/expenses?from=<90d ago>&to=<today>&limit=200
GET /v1/suppliers?limit=200
```

Group expenses by `supplierId`, sum `amount`, sort desc, take top 10. Resolve supplier names from the suppliers list.

Flag concentration: any single vendor >20% of total spend = supplier risk heuristic.

### "Departmental burn"

```http
GET /v1/departments
GET /v1/teams
GET /v1/expenses?from=<period>&to=<period>&limit=200
```

Group expenses by `departmentId` (or `teamId`). Compare to:
- Headcount per department (`GET /v1/users` → group by team/department)
- Spending benchmarks (see `references/metrics-benchmarks.md`)

Heuristic flags:
- Spend per head wildly different across departments
- Single department >40% of total OpEx without obvious justification

### "Recurring SaaS spend"

Moss doesn't natively flag "subscription" vs one-off. Heuristic:

1. Pull 6 months of card transactions: `POST /v1/bank-transactions/search-query` (Moss-managed cards).
2. Group by `supplierId` (or counterparty name if no supplier link).
3. Flag any supplier with 3+ transactions in 6 months at similar amounts as recurring.
4. Cross-reference with `GET /v1/suppliers` for category context.

Output: list of recurring vendors, monthly amount, annualized cost. Flag duplicates (e.g. two video tools).

### "Bank balances on Moss-managed accounts"

```http
GET /v1/bank-accounts
GET /v1/bank-accounts/{id}/balance
```

If the company funds Moss cards from a top-up account, this is the float. Combine with Qonto for total cash.

### "Headcount"

```http
GET /v1/users?limit=200
```

Filter for active users. Group by `teamId` / `departmentId` for departmental headcount. Note: Moss `users` are people with Moss seats, not necessarily total company headcount. Cross-reference with HR if precision matters.

### "Spend by accounting dimension (project, campaign, etc.)"

If the workspace uses Moss dimensions:

```http
GET /v1/dimensions
GET /v1/dimensions/{id}/items
GET /v1/expenses?from=<period>&to=<period>&limit=200
```

Each expense has `dimensionItemIds`. Group expenses by the relevant dimension item to get per-project / per-campaign spend.

## What Moss CAN'T do

- Customer revenue / MRR → use Attio
- AR / unpaid invoices issued to customers → use Qonto
- Total company cash (only shows Moss-managed account balances) → combine with Qonto
- Authoritative headcount (only Moss seat-holders)

## Moss API surface (read-only subset used here)

| Endpoint | Use |
|----------|-----|
| `GET /v1/expenses` | All expenses (cards + invoices + reimbursements) |
| `GET /v1/expense-accounts` | GL category list |
| `GET /v1/dimensions` + `/v1/dimensions/{id}/items` | Custom tagging (projects, campaigns) |
| `GET /v1/suppliers` | Vendor list |
| `GET /v1/payment-terms` | Vendor payment terms |
| `GET /v1/tax-rates` | VAT/tax setup |
| `GET /v1/users` | Moss seat holders |
| `GET /v1/teams` + `/v1/departments` | Org structure |
| `GET /v1/bank-accounts` + `/{id}/balance` | Moss-managed account balances |
| `POST /v1/bank-transactions/search-query` | Moss card transactions |
| `POST /v1/files/search-query` + `/v1/files/{id}/content` | Receipts |

Skill is read-only. Never call `POST`/`PATCH` mutating endpoints.

## Pagination

Offset-based via `offset` + `limit` parameters. Loop until response returns fewer than `limit` items.
