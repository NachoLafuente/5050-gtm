# 5050-gtm

**GTM skills for Claude Code, built by [5050Growth](https://5050growth.com).**

Cohort analysis, proposals, disco prep — pull from your CRM, hit a CSV, never spin up a dashboard you forget about. Built for founders, RevOps folks, and Attio consultants who want answers in five minutes, not a six-figure analytics vendor.

If you're paying $400/mo for ChartMogul to read three numbers a quarter, this repo is for you.

---

## What are Skills?

[Claude Code Skills](https://docs.claude.com/en/docs/claude-code/skills) are markdown files that give Claude (or Codex, Cursor, Gemini CLI) specialized knowledge for a specific GTM task. Each skill knows what to ask, where to pull data from, and what to spit out.

This repo collects skills we use internally at 5050Growth on real client work — productized so anyone can run them.

---

## Available Skills

| Skill | What it does |
|---|---|
| [`/cohort-analysis`](skills/cohort-analysis/) | Build a customer cohort retention table from your CRM (Attio, Stripe) joined to revenue (Stripe, Attio attrs, CSV). Output: CSV, SQL, or DuckDB+Evidence. |

**Coming soon** (drop a star and watch — these are next out of our internal pile):

- `/proposal` — turn a sales call transcript into a 12-section proposal
- `/disco-prep` — pre-discovery brief from an intro email
- `/lifecycle-audit` — find broken handoffs in your Attio lifecycle stages
- `/lead-scoring` — rules-engine score from CRM attrs, output as Attio formula

---

## Install

### Option 1 — Project-level skill (recommended)

Copy a skill into your project's `.claude/skills/` folder:

```bash
git clone https://github.com/NachoLafuente/5050-gtm.git
cp -r 5050-gtm/skills/cohort-analysis /path/to/your-project/.claude/skills/
```

Now `/cohort-analysis` is available in Claude Code from that project.

### Option 2 — User-level skill (available everywhere)

```bash
git clone https://github.com/NachoLafuente/5050-gtm.git
cp -r 5050-gtm/skills/cohort-analysis ~/.claude/skills/
```

### Option 3 — Standalone Python CLI

You don't need Claude Code. Each skill is also a plain Python script:

```bash
git clone https://github.com/NachoLafuente/5050-gtm.git
cd 5050-gtm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Try it on the included demo data — no API keys needed:
python skills/cohort-analysis/run.py \
  --crm csv --money csv \
  --csv-customers skills/cohort-analysis/examples/customers.csv \
  --csv-revenue skills/cohort-analysis/examples/revenue.csv \
  --output csv \
  --out-dir /tmp/cohort-demo

cat /tmp/cohort-demo/cohort_table.csv
```

### Option 4 — Fork it, change it, keep it

The whole point of MIT-licensing this is that your CRM is yours. If your stack is HubSpot + Chargebee instead of Attio + Stripe, fork the repo and write a `pullers/hubspot.py`. The rest of the pipeline (cohort math + output writers) is source-agnostic.

---

## Philosophy

A few rules we follow when building these:

- **CSV is the default.** Excel is the most popular GTM tool on earth. Don't fight it.
- **No cron, no warehouse.** One-shot scripts. If you need a refreshing dashboard, buy ChartMogul.
- **No SaaS.** Your data stays on your laptop. We never POST anywhere.
- **Sources are pluggable.** Each skill has a `pullers/` folder. Add one for your CRM in ~30 lines.
- **Honest about limits.** When a source can't do something (e.g. Attio has no revenue history), the skill *tells you* before it runs, not after.

---

## How `/cohort-analysis` works

```
                 ┌─────────────────┐
                 │  CRM (Attio /   │
                 │  Stripe / CSV)  │  → customer_id, email, signup_date
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Money source    │
                 │ (Stripe /       │  → customer_id, event_date, amount
                 │  Attio / CSV)   │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ cohort.py       │  joins on email/id/domain,
                 │ (matrix builder)│  bucketed by signup month
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │ Output writer   │  → CSV (default)
                 │                 │  → SQL DDL+inserts
                 │                 │  → DuckDB + Evidence project
                 └─────────────────┘
```

The skill asks three questions before running: which CRM, which money source, which output format. Then it tells you which env vars to set, validates them, and runs.

---

## Contributing

PRs welcome. The shape of a new skill:

```
skills/<your-skill>/
  SKILL.md            ← frontmatter + instructions for Claude
  run.py              ← entry point (or whatever the skill does)
  README.md           ← optional, if extra docs help
```

Match the tone: direct, no fluff, honest about what doesn't work.

---

## Who built this

[5050Growth](https://5050growth.com) — Attio CRM consultancy. Migrations, integrations, GTM systems for VCs and B2B SaaS. Founder: [Nacho Lafuente](https://www.linkedin.com/in/nachoegues/) ([nacho@5050growth.com](mailto:nacho@5050growth.com)).

If you want this stuff *built for you* on your CRM, that's the day job. Otherwise, fork away.

## License

MIT — see [LICENSE](LICENSE).
