# Attio: Customer & Revenue Data

Attio holds the **customer and revenue side** of the CFO picture. This file maps CFO questions to the exact API calls that answer them.

## Auth

- Header: `Authorization: Bearer {ATTIO_API_KEY}`
- Base URL: `https://api.attio.com/v2`
- Spec: `https://api.attio.com/openapi/api` (core) + `https://api.attio.com/openapi/standard-objects` (concrete people/companies/deals routes)

## Workspace assumptions

Attio is schema-flexible, every workspace has different attributes. The skill must:

1. **First call** `GET /v2/objects/{object}/attributes` to discover the actual attribute slugs.
2. **Never assume** `mrr`, `arr`, `contract_value` exist. Look them up.
3. **Map** common concepts (MRR, status, signup date) to the real slugs the workspace uses.

## CFO Question → Endpoint Map

### "How many active customers?"

```http
POST /v2/objects/companies/records/query
Content-Type: application/json

{
  "filter": { "<status_attr>": { "$eq": "<active_status_option_id>" } },
  "limit": 500
}
```

Iterate with `offset` until exhausted. Return `meta.total` if the workspace exposes it (some endpoints return total counts, others require pagination to count).

### "What's our MRR/ARR?"

1. Discover the MRR/ARR attribute slug via `GET /v2/objects/companies/attributes` (look for currency/number attrs named like `mrr`, `monthly_revenue`, `arr`).
2. Query active customers (above).
3. Sum the attribute across the result set.

```http
POST /v2/objects/companies/records/query
{
  "filter": { "<status_attr>": { "$eq": "<active>" } },
  "limit": 500
}
```

Then: `sum(record.values.<mrr_attr>[0].currency_value for record in results)`.

⚠️ If the workspace doesn't have an MRR attribute, say so. Don't compute MRR from deal stages without the user confirming the model.

### "Customer concentration: top 10 by revenue"

Same query as MRR, but sort by the revenue attribute descending. Attio doesn't support server-side sort on all attribute types reliably, fetch all active customers and sort client-side.

Then compute:
- Top 1 customer % of total
- Top 5 customers % of total
- Top 10 customers % of total

Heuristic flag: any customer >10% of revenue, or top 5 >25%.

### "Pipeline value (open deals)"

```http
POST /v2/objects/deals/records/query
{
  "filter": { "stage": { "$not_in": ["closed_won", "closed_lost"] } },
  "limit": 500
}
```

Sum the deal value attribute (typically `value` or `amount`, verify with `GET /v2/objects/deals/attributes`).

### "Churned customers in last N months"

If the workspace tracks churn via a list ("Churned customers"):

```http
POST /v2/lists/{list_id}/entries/query
{
  "filter": { "created_at": { "$gte": "<N months ago iso>" } },
  "limit": 500
}
```

If the workspace tracks churn via a status attribute change, this is harder, Attio's API doesn't expose attribute history without paid tier add-ons. In that case: report what you can see (current churned count) and flag the limitation.

### "Net Revenue Retention (NRR)"

NRR requires cohort revenue at two points in time. Attio shows the **current state** of each customer's MRR, not historical. Three options:

1. If the workspace has an `mrr_at_signup` or similar historical attribute → use it.
2. If a third-party tool (Stripe, ChartMogul) writes monthly snapshots into Attio → query those.
3. Otherwise → say "NRR can't be computed from Attio alone in this workspace; need a revenue history source."

Don't fabricate NRR.

## Discovering the workspace schema

Always start a CFO session with:

```http
GET /v2/objects/companies/attributes
GET /v2/objects/people/attributes
GET /v2/objects/deals/attributes
GET /v2/lists
```

Cache the results for the session. Map common CFO concepts to the workspace's actual slugs:

| Concept | Common slug names to look for |
|---------|-------------------------------|
| Customer status | `status`, `lifecycle_stage`, `customer_status` |
| MRR | `mrr`, `monthly_revenue`, `monthly_recurring_revenue` |
| ARR | `arr`, `annual_revenue`, `annual_recurring_revenue` |
| Contract value | `contract_value`, `acv`, `tcv` |
| Industry | `industry`, `categories`, `sector` |
| Plan/tier | `plan`, `tier`, `subscription_plan` |
| Churn date | `churned_at`, `cancellation_date`, `lost_date` |

If multiple candidates exist, ask the user which one to use. Don't guess.

## Rate limits

Attio's documented limit is 1,000 req/min per workspace token (subject to change, check headers). Backoff on `429`.

## What Attio CAN'T do

- Bank balances, cash flow, transactions → use Qonto
- Vendor spend, expenses → use Moss
- Forward-looking forecasts (it shows current state, not projections)
- Historical revenue snapshots without a third-party tool writing them in
