---
name: cfo-skill
description: Read-only financial data layer for bootstrapped startups. Pulls live numbers from Attio (revenue, customers, pipeline), Qonto (cash, AR, transactions), and Moss (spend, vendors, departments) to compute runway, burn rate, LTV:CAC, NRR, customer concentration, AR aging, and vendor spend. Use when the user asks "what's our runway?", "how much cash do we have?", "what's our burn?", "who are our biggest customers?", "where is spend going?", "what's our LTV:CAC?", or any question that boils down to surfacing finance numbers. NOT financial, legal, tax, or investment advice.
---

# CFO Skill: Read-Only Financial Data Layer

> ## ⚠️ DISCLAIMER — READ BEFORE USING
>
> **This skill fetches and displays data. It is NOT financial, legal, tax, accounting, or investment advice.**
>
> - Numbers may be stale, miscategorized, or reflect bugs in the upstream systems (Attio, Qonto, Moss).
> - The frameworks below (LTV:CAC, runway, burn multiple, Rule of 40, etc.) are heuristics, not guarantees.
> - Decisions about hiring, fundraising, distributions, taxes, dividends, solvency, or any matter with legal or financial consequences must be made by you in consultation with a qualified CFO, accountant, lawyer, or tax advisor.
> - The author and contributors accept no liability for decisions made based on this skill's output.
> - Always verify critical numbers directly in the source system before acting on them.
>
> Use this skill to **see your numbers faster**, not to replace professional judgment.

---

## What This Skill Does

1. **Pulls live data** from three connected systems via their public APIs:
   - **Attio** — customer, revenue, pipeline data
   - **Qonto** — bank balance, transactions, AR
   - **Moss** — corporate spend, vendors, departments
2. **Computes standard SaaS finance metrics** from that data (runway, burn, LTV:CAC, NRR, etc.).
3. **Surfaces frameworks** the user can apply themselves.

**It never gives a recommendation on a hire, raise, distribution, or any decision with legal/tax/financial consequences.** It shows the numbers and the framework. The human decides.

---

## Data Sources

| Source | Answers | Reference |
|--------|---------|-----------|
| Attio | MRR/ARR, NRR, customer concentration, pipeline, churn signals | [references/attio.md](references/attio.md) |
| Qonto | Cash balance, runway, burn rate, AR aging, transactions | [references/qonto.md](references/qonto.md) |
| Moss | Spend by department/vendor/category, expense detail | [references/moss.md](references/moss.md) |

Each reference file maps **CFO question → exact API call(s)**.

---

## Question → Source Map

| Question | Data needed | Sources |
|----------|-------------|---------|
| What's our cash balance? | Bank balances | Qonto + Moss bank-accounts |
| What's our runway? | Cash ÷ trailing burn | Qonto transactions + Moss expenses |
| What's our burn multiple? | Net burn ÷ net new ARR | Qonto + Moss + Attio |
| What's our MRR / ARR? | Active subscriptions | Attio (custom MRR field) |
| What's our NRR? | Cohort revenue retention | Attio + revenue source |
| Customer concentration? | Top customers by revenue | Attio |
| AR aging? | Unpaid invoices by age | Qonto invoices |
| Where is spend going? | Expenses by category/vendor/dept | Moss |
| Top vendors by spend? | Supplier-aggregated expenses | Moss |
| Departmental burn? | Expenses grouped by team | Moss |
| LTV:CAC? | Revenue + churn + S&M spend | Attio + Moss |

If a question maps to data the connected systems can't answer, say so explicitly. Don't fabricate.

---

## Core Mental Models (Heuristics — Not Advice)

**Profit is a constraint, not a goal.** Capital discipline forces better decisions in bootstrapped companies.

**Unit economics targets** (industry heuristics):
- LTV ≥ 3× CAC (best-in-class: 7-8×)
- CAC payback < 12 months (high performers: 5-7 months)

**Revenue per employee benchmarks**:
- $110-150K at $1-5M ARR
- $200-250K at $10-50M ARR
- Bootstrapped companies typically run 40-70% higher than VC-backed peers.

**Runway heuristics**:
- Minimum: 24-36 months
- Danger zone: <12 months

**Burn multiple** = Net Burn ÷ Net New ARR
- <1×: efficient · 1-1.5×: acceptable · >2×: concerning

**Rule of 40**: Revenue Growth % + EBITDA Margin % ≥ 40%

For full benchmarks see [references/metrics-benchmarks.md](references/metrics-benchmarks.md).
For bootstrapped case studies see [references/case-studies.md](references/case-studies.md).

---

## How to Answer a CFO Question

1. **Restate the question in numerical terms.** ("What's our runway?" → "I need cash balance and trailing 3-month net burn.")
2. **Identify the data source(s)** from the table above.
3. **Open the relevant reference file** and use the documented API call(s).
4. **Show the raw numbers first**, then the computed metric, then the framework.
5. **Repeat the disclaimer** if the user is making a real decision.
6. **Flag data quality issues** explicitly: stale data, missing fields, miscategorized expenses.

Example response shape:

> Cash balance (Qonto, as of 2026-05-10): €42,300
> Trailing 3-month net burn (Qonto outflows − inflows): €8,100/mo
> **Runway: ~5.2 months**
>
> Heuristic: <12 months runway is the danger zone.
>
> ⚠️ This is data, not advice. Verify numbers in Qonto directly before acting. Consult a qualified advisor for decisions about fundraising, hiring freezes, or cuts.

---

## Auth & Setup

The skill assumes the following environment variables are set:

| Variable | System | Where to get it |
|----------|--------|-----------------|
| `ATTIO_API_KEY` | Attio | Attio workspace settings → API |
| `QONTO_API_KEY` + `QONTO_SECRET_KEY` | Qonto | Qonto settings → Integrations → API |
| `MOSS_KEY_ID` + `MOSS_SECRET_KEY` | Moss | Moss settings → Developers → OAuth client |

Missing credentials → say so, don't guess. Never log or echo a secret.

---

## What This Skill Does NOT Do

- ❌ Make recommendations on hiring, raises, distributions, or fundraising
- ❌ Give tax, legal, or accounting advice
- ❌ Project cash flow into the future as a "forecast" the user can rely on
- ❌ Determine whether the company is solvent
- ❌ Write to any of the three systems (read-only by design)

For any of these, the answer is: "I can show you the numbers. The decision and any forward-looking interpretation is for you and a qualified advisor."

---

## Attribution

Frameworks, benchmarks, and case studies adapted from [EveryInc/charlie-cfo-skill](https://github.com/EveryInc/charlie-cfo-skill) (MIT licensed, © 2026 Every).

Data layer (Attio + Qonto + Moss integrations) added by 5050Growth.
