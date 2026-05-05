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
| [`/cohort-analysis`](skills/cohort-analysis/) | Customer cohort retention table from your CRM (Attio/Stripe/CSV) joined to revenue (Stripe/Attio/CSV). Output: CSV, SQL, or DuckDB+Evidence. |

### SEO / Demand

| Skill | What it does |
|---|---|
| [`/gsc-lighthouse`](skills/gsc-lighthouse/) | One-shot Google Search Console + Lighthouse health check for a verified GSC property. Sitemap status, per-URL index coverage, 28-day search analytics, and PageSpeed Insights on the top 10 pages, all in one report grouped by theme. |

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
