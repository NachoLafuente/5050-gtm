# 5050-gtm

**A growing collection of GTM skills for Claude Code, built by [5050Growth](https://5050growth.com).**

Skills you can drop into Claude Code (or run as plain Python) to handle the GTM work that doesn't justify a SaaS subscription. CRM-aware, CSV-friendly, no dashboards, no cron jobs, MIT-licensed.

Built for founders, RevOps folks, and Attio consultants who'd rather run a script than buy another tool.

---

## What are Skills?

[Claude Code Skills](https://docs.claude.com/en/docs/claude-code/skills) are markdown files that give Claude (or Codex, Cursor, Gemini CLI) specialized knowledge for a specific task. Each skill knows what to ask, where to pull data from, and what to spit out. You invoke them with `/skill-name`.

The skills here are productized versions of work we do at 5050Growth on real client engagements. We open-source them so the next person doesn't have to rebuild the wheel.

---

## Available Skills

### Revenue Analytics

| Skill | What it does |
|---|---|
| [`/cohort-analysis`](skills/cohort-analysis/) | Full SaaS cohort analysis from your CRM (Attio/Stripe/CSV) joined to revenue (Stripe/Attio/CSV). Outputs a styled Excel workbook + 11 per-section CSVs. |
| [`/ltv-cac`](skills/ltv-cac/) | Forward-looking LTV / CAC / payback model. Four formulas side by side (Skok basic, NDR-adjusted, AI-inference-adjusted, Sequoia contribution-margin) plus a sensitivity heatmap and a 36-month synthetic cohort projection. Verdict anchored on Skok's 3:1 rule. |

**What you get from `/cohort-analysis`** — every metric a B2B-SaaS investor or founder asks for, in one workbook:

| KPI | What it means | Where it lives |
|---|---|---|
| **NRR** (Net Revenue Retention) | % of M0 MRR each cohort still pays at M1, M3, M6, M12… The headline retention metric. | Sheet section 2, table 3 |
| **GRR** (Gross Revenue Retention) | Customer-side retention curve — % of each cohort still paying at M_n. | Sheet section 1, table 3 |
| **MRR retention curve** | Dollar amount each cohort is paying every month since signup. | Sheet section 2, table 1 |
| **Net dollar churn** | Signed: positive = churn, negative = expansion (so NDR > 100% shows green). | Sheet section 2, table 2 |
| **Customer churn rate** | % of cohort lost each month — both vs-base (severity) and vs-previous-month (period rate). | Sheet section 1, tables 4–5 |
| **MRR churn rate** | Same in dollars, signed so expansion is visible. | Sheet section 2, tables 4–5 |
| **CAC payback period** | Lifetime month each cohort breaks even on its acquisition cost (given CAC + gross margin). | Sheet section 3 |
| **Cumulative gross profit** | Dollars of GP each cohort has produced, month by month, vs their CAC. | Sheet section 3 |
| **Cohort base size** | Customers in each signup cohort + their initial MRR (M0). | Header row of every section |
| **Lifetime month cutoff** | Per-cohort observable horizon, inferred from your data — newer cohorts only show what's been observed. | Header row + summary CSV |

CAC payback is opt-in (provide a `cohort,cac_amount` CSV). Gross margin defaults to 80%, configurable. Everything else falls out of customers + revenue alone.

**What you get from `/ltv-cac`** — forward-looking unit economics from a handful of inputs:

| KPI | What it means | Where it lives |
|---|---|---|
| **Skok basic LTV** | `ARPU × GM / churn` — the canonical 3:1 rule reference | Verdict sheet |
| **NDR-adjusted LTV** | `ARPU × GM / (churn − expansion)` — credits net dollar retention | Verdict sheet |
| **AI-adjusted LTV** | `(ARPU × GM − inference) / churn` — handles variable inference cost erosion | Verdict sheet |
| **Sequoia contribution-margin LTV** | Combines NDR + variable-cost adjustments | Verdict sheet |
| **CAC payback** | Months to recover CAC; basic and AI-adjusted | Verdict sheet |
| **LTV/CAC verdict** | 🔴 underwater / 🟡 tight / 🟢 healthy / 🟦 under-investing — anchored on Skok 3:1 | Verdict sheet |
| **NDR** | Monthly + annual-compounded net dollar retention | Verdict sheet |
| **Sensitivity heatmap** | LTV/CAC across churn (1–10%) × gross margin (50–90%) — see what cutting churn or improving GM does | Sensitivity sheet |
| **Cohort projection** | 100-customer synthetic cohort over 36 months: customers retained, MRR, cumulative gross profit vs. CAC, line chart | Cohort Projection sheet |

Sources cited inline: Skok (Matrix), a16z, Sequoia, Tunguz.

### SEO / Demand

| Skill | What it does |
|---|---|
| [`/gsc-lighthouse`](skills/gsc-lighthouse/) | One-shot Google Search Console + Lighthouse health check for a verified GSC property. Sitemap status, per-URL index coverage, 28-day search analytics, and PageSpeed Insights on the top 10 pages, all in one report grouped by theme. |

### Finance / CFO

| Skill | What it does |
|---|---|
| [`/cfo-skill`](skills/cfo-skill/) | CFO data dashboard for bootstrapped startups. Two modes: **CSV templates** (works with any stack — HubSpot/Salesforce/Attio + Mercury/Brex/Qonto + Stripe/Chargebee + Ramp/Pleo/Moss) or **live API pull** from Stripe + Attio + Qonto + Moss. Outputs an Excel workbook with runway, burn, MRR/ARR, customer concentration, AR aging, DSO, vendor spend, departmental burn. Read-only. **Not financial, legal, tax, or investment advice.** |

**Two modes, same output:**

```bash
# Mode 1 — CSV templates (any stack, zero auth)
python skills/cfo-skill/run.py --source csv --csv-dir ./my-data

# Mode 2 — live pull from Stripe + Attio + Qonto + Moss
python skills/cfo-skill/run.py --source api --providers stripe,qonto,moss
```

**What `/cfo-skill` answers — pulled from the right system:**

| Question | Best source | Endpoint |
|---|---|---|
| MRR / ARR / customer churn | **Stripe** (subscriptions) | `GET /v1/subscriptions` |
| Customer concentration / pipeline / lifecycle | Attio | `POST /v2/objects/{companies,deals}/records/query` |
| Cash balance, runway, burn rate | Qonto | `GET /v2/organization` + `/v2/transactions` |
| AR aging / DSO | Stripe **or** Qonto | `/v1/invoices` or `/v2/client_invoices` |
| Spend by category / vendor / department | Moss | `/v1/expenses` + `/v1/suppliers` + `/v1/departments` |
| Recurring SaaS spend (heuristic) | Moss + Qonto | grouped over time |

**Excel output** — 8 sheets: Summary (with heuristic flags), Cash Flow, Customers, Concentration, AR Aging, Spend Breakdown, Recurring Vendors, Disclaimer.

Frameworks (LTV:CAC, runway, burn multiple, Rule of 40) and bootstrapped case studies (Mailchimp, Zapier, Basecamp, ConvertKit, Zoho) bundled as references — adapted from [EveryInc/charlie-cfo-skill](https://github.com/EveryInc/charlie-cfo-skill) (MIT). Read-only by design — never requests write scopes.

### Coming soon

We're adding skills as we productize internal work. Star the repo to follow along:

- **Sales Ops** — proposal generation from call transcripts, pre-discovery briefs, lead scoring rules
- **Lifecycle / RevOps** — Attio lifecycle audit, ownership rules, list hygiene
- **SEO / Demand** — programmatic page generators, schema markup audits
- **Reporting** — Evidence/DuckDB scaffolds for any CRM source

If there's something specific you'd want, [open an issue](https://github.com/NachoLafuente/5050-gtm/issues).

---

## Install

### Option 1 — Project-level skill (recommended)

Copy a skill into your project's `.claude/skills/` folder:

```bash
git clone https://github.com/NachoLafuente/5050-gtm.git
cp -r 5050-gtm/skills/<skill-name> /path/to/your-project/.claude/skills/
```

The skill becomes available as `/<skill-name>` in Claude Code from that project.

### Option 2 — User-level skill (available everywhere)

```bash
git clone https://github.com/NachoLafuente/5050-gtm.git
cp -r 5050-gtm/skills/<skill-name> ~/.claude/skills/
```

### Option 3 — Standalone Python CLI

You don't need Claude Code. Each skill is also runnable as a plain Python script:

```bash
git clone https://github.com/NachoLafuente/5050-gtm.git
cd 5050-gtm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python skills/<skill-name>/run.py --help
```

Most skills ship with an `examples/` fixture so you can try the pipeline before plugging in real credentials.

### Option 4 — Fork it

The point of MIT-licensing this is that your stack is yours. If you're on HubSpot + Chargebee instead of Attio + Stripe, fork and add a puller. Most skills are <300 lines of Python — easy to extend.

---

## Philosophy

A few rules we follow when building these:

- **CSV is the default.** Excel is the most popular GTM tool on earth. Don't fight it.
- **No cron, no warehouse.** One-shot scripts. If you need a refreshing dashboard, buy ChartMogul.
- **No SaaS.** Your data stays on your laptop. We never POST anywhere.
- **Sources are pluggable.** Skills that pull data have a `pullers/` folder. Add one for your CRM in ~30 lines.
- **Honest about limits.** When a source can't do something (e.g. Attio has no native revenue history), the skill *tells you* before it runs, not after.

---

## Contributing

PRs welcome. The shape of a new skill:

```
skills/<your-skill>/
  SKILL.md            ← frontmatter + instructions for Claude
  run.py              ← entry point (or whatever the skill does)
  examples/           ← optional fixture so people can try without API keys
  README.md           ← optional, if extra docs help
```

Match the tone: direct, no fluff, honest about what doesn't work.

---

## Inspiration

Learning from the best — [Point Nine](https://www.pointnine.com/) and other great B2B-SaaS investors who publish their playbooks publicly (Bessemer, a16z, OpenView, Lenny). These skills turn proven frameworks into one-shot scripts you can run on your own data.

---

## Star history

If this is useful, a star helps a lot — both for visibility and for keeping us motivated to ship more.

[![Star History Chart](https://api.star-history.com/svg?repos=NachoLafuente/5050-gtm&type=Date)](https://star-history.com/#NachoLafuente/5050-gtm&Date)

---

## Who built this

[5050Growth](https://5050growth.com) — Attio CRM consultancy. Migrations, integrations, GTM systems for VCs and B2B SaaS.

Founder: [Nacho Lafuente](https://www.linkedin.com/in/nachoegues/) ([nacho@5050growth.com](mailto:nacho@5050growth.com))

If you want this kind of work *built for you* on your CRM, that's the day job. Otherwise, fork away.

## License

MIT — see [LICENSE](LICENSE).
