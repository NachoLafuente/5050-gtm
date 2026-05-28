# gsc-lighthouse

One-shot SEO health check for any verified Google Search Console property.

Pulls indexing coverage, search analytics, and runs Lighthouse on your top 10 pages by clicks. Outputs a single report grouped by theme so you can ship one PR instead of chasing a hundred warnings.

Built for marketing site owners and consultants who want a clean diagnostic without paying for an SEO SaaS.

## What it audits

**Google Search Console**
- Sitemap status (errors, warnings, last download)
- Per-URL index coverage for every URL in your sitemap (PASS / NEUTRAL / FAIL)
- Canonical mismatches (Google chose a different canonical than you declared)
- 28-day search analytics with delta vs prior 28d (clicks, impressions, CTR, avg position)
- Top 10 pages and queries by clicks

**Lighthouse via PageSpeed Insights** (mobile, the strategy Google ranks on)
- Performance / SEO / Accessibility / Best Practices scores per page
- Core Web Vitals lab (LCP, CLS, TBT, FCP) and field data (CrUX) when available
- Console errors per page
- Failed audits with concrete savings (`-1050ms`, `-340KB`)
- Themes hitting 2+ pages so you fix once, win everywhere

## Why not just use Search Console + PageSpeed Insights manually?

Both tools live in different UIs. GSC's sitemap stats panel often shows "0 indexed" on Domain properties even when pages are indexed. PSI gives you 100 metrics, none of them prioritized. Single-run Lighthouse has ±10-point variance you'll mistake for regression.

This skill batches the data, applies known calibration ("don't cry wolf" rules), groups fixes by theme, and gives you a single report that says: *here's what's broken, here's what's noise, here's what to fix first*.

## Install

### Option A: drop into your repo's Claude Code skills folder

```bash
git clone https://github.com/NachoLafuente/5050-gtm.git
cp -r 5050-gtm/skills/gsc-lighthouse /path/to/your-project/.claude/skills/
```

In Claude Code: `/gsc-lighthouse`.

### Option B: install user-wide

```bash
git clone https://github.com/NachoLafuente/5050-gtm.git
cp -r 5050-gtm/skills/gsc-lighthouse ~/.claude/skills/
```

### Option C: standalone Python CLI

```bash
git clone https://github.com/NachoLafuente/5050-gtm.git
cd 5050-gtm
pip install -r requirements.txt
pip install google-api-python-client google-auth
python skills/gsc-lighthouse/audit.py --site "sc-domain:example.com"
```

## Setup (one-time, ~2 minutes)

### 1. GSC auth

Sign in with the Google Account that owns the GSC property. Service accounts don't work on Domain properties (Google's known limitation).

```bash
gcloud auth application-default login --scopes=\
https://www.googleapis.com/auth/webmasters.readonly,\
https://www.googleapis.com/auth/webmasters,\
openid,\
https://www.googleapis.com/auth/userinfo.email
```

If you don't have `gcloud`, install via [Google Cloud SDK](https://cloud.google.com/sdk/docs/install).

### 2. PageSpeed Insights API key (optional but recommended)

Anonymous PSI gets rate-limited fast. With a key, the limit is 25,000/day.

```bash
gcloud services enable pagespeedonline.googleapis.com --project=YOUR_GCP_PROJECT
gcloud beta services api-keys create \
  --display-name="PageSpeed Insights" \
  --project=YOUR_GCP_PROJECT \
  --format='value(response.keyString)'
echo "PAGESPEED_API_KEY=<paste-keyString>" >> .env
```

Recommended: restrict the key to PSI-only via the [GCP console](https://console.cloud.google.com/apis/credentials).

If you skip this step, run with `--no-lighthouse` and you still get the GSC audit.

## Usage

```bash
# Domain property (covers all subdomains and protocols)
python audit.py --site "sc-domain:example.com"

# URL-prefix property
python audit.py --site "https://example.com/"

# Custom number of top pages for Lighthouse
python audit.py --site "sc-domain:example.com" --top 20

# GSC only, skip Lighthouse
python audit.py --site "sc-domain:example.com" --no-lighthouse
```

Output:
- Structured report to stdout (also embeddable in a Claude Code session)
- Full JSON dump at `./out/audit-YYYY-MM-DD.json`

## Sample output

See [`examples/sample-report.md`](examples/sample-report.md).

## Calibration: what this skill ignores on purpose

A lot of SEO advice is noise. This skill explicitly skips the following non-issues:

| Symptom | Why it's not actually a problem |
|---|---|
| Sitemap stats show "0 indexed" on a Domain property | Known GSC reporting quirk. Trust per-URL inspection. |
| Many pages "URL is unknown to Google" right after first sitemap submit | Google hasn't crawled them yet. Wait 7+ days. |
| Pages "Discovered - currently not indexed" | Only an issue if older than 14 days. |
| Lighthouse perf swing of ±10 points between runs | Single-run lab variance. Re-run after warming origin. |
| Lighthouse TBT spike with stable LCP/FCP | Cold-start signature on serverless. Warm with curl loop. |
| Lighthouse green on lab + CrUX yellow/red | Trust field data. Lab is synthetic; ranking uses field. |

Real problems the skill does flag:
- Sitemap errors > 0
- Canonical mismatches (Google picked a different URL than declared)
- Pages "Crawled - currently not indexed" (Google decided not to index, quality signal)
- Pages stuck "Discovered - currently not indexed" > 14 days
- Soft 404s
- Sudden traffic drops > 30% week-over-week
- LCP > 4s on top traffic pages
- Console errors from third-party tags

## Limitations

- The skill audits up to 50 sitemap URLs for index coverage (GSC URL Inspection API rate limit). For sites with > 50 indexed URLs, only the first 50 alphabetically are inspected. Search analytics still covers everything.
- Lighthouse PSI runs are single-shot. For statistically reliable perf scores, run 3 times and take the median. The skill prioritizes getting a fast snapshot over statistical rigor.
- Field CWV (CrUX) data only appears once your site has enough real-user traffic for Google to compute it. Newer or low-traffic sites will show no field data, that's expected.

## Built by

[5050Growth](https://5050growth.com), Attio CRM consultancy. We open-source the GTM tooling we build for clients. If you want this kind of SEO audit run on your site as part of a CRM implementation or reporting setup, [book a call](https://5050growth.com/book/).
