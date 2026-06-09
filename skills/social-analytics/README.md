# /social-analytics

Turn a LinkedIn Creator analytics export into a **"what works / what doesn't"** report.

No dashboards, no third-party analytics SaaS, no API keys. Two local files in, a report and
a styled Excel workbook out. Built for founders and creators who post on LinkedIn and want
to know what's actually driving reach and engagement, not vibes.

## What it does

Reads the export(s) LinkedIn gives you and:

- computes headline KPIs (impressions, members reached, followers, engagement rate)
- tags every post by **topic**, **hook style**, **day of week**, and **length**
- ranks those tags by average impressions / engagements / engagement rate
- joins each top post to its **full text** (so you see the actual copy, not just URLs)
- surfaces your **top posts** (by engagement and by ER) and your **weakest winners**
- runs simple correlations (does length matter? does reach drive engagement?)
- writes a multi-tab Excel workbook + a tagged CSV you can pivot

## Inputs

| File | Where to get it | Required? |
|---|---|---|
| `AggregateAnalytics_<name>_<dates>.xlsx` | LinkedIn → profile → **Analytics** → **Export** | **Yes** |
| `Complete_LinkedInDataExport` (zip → `Shares_*.csv`) | **Settings → Data Privacy → Get a copy of your data → larger archive** (email, ~24h) | Optional, recommended |

The analytics export alone gives you impressions/engagements per post (top ~50). Adding the
data archive joins each post to its full text and unlocks topic tagging.

## Usage

```bash
cd skills/social-analytics
pip install openpyxl>=3.1   # only dependency

# analytics only
python analyze.py --analytics "AggregateAnalytics_Jane_2025-06-09_2026-06-08.xlsx"

# analytics + full text (recommended)
python analyze.py \
  --analytics "AggregateAnalytics_Jane_2025-06-09_2026-06-08.xlsx" \
  --archive   "~/Desktop/Complete_LinkedInDataExport" \
  --out ./out
```

`--archive` accepts either the `Shares_*.csv` directly or the unzipped export folder (it
finds the CSV). `--top N` limits to the top N posts by impressions. `--no-files` prints the
report without writing anything.

## Outputs (`./out/`)

- `linkedin_analysis.xlsx` - Summary · Post Performance (tagged) · Daily Engagement · Followers · Demographics
- `linkedin_posts_tagged.csv` - one row per post with topic/hook/day/length tags
- `linkedin_posts.json` - the enriched dataset, for further scripting

## Read the numbers honestly

Two things the script reminds you of every run, because they flip the interpretation:

1. **Engagement rate is inversely tied to reach.** A 12k-impression post mathematically
   shows a lower ER% than a 900-impression post with the same raw engagement. Judge big
   posts by **absolute engagement**, small posts by **ER**. Don't rank on ER alone.
2. **Survivorship bias.** LinkedIn's export is your **top ~50 posts only**. It tells you
   what made your best tier - not what a flop looks like. "Bottom 5" = weakest of your
   winners.

Also: "engagements" is one blended number (no reaction/comment/share split), and native
image/carousel posts usually have no `MediaUrl` in the archive, so the skill can't reliably
prove whether media beats text. It won't pretend to.

## Customizing for your niche

Topic and hook detection are two regex dicts at the top of `analyze.py` (`TOPICS`, `HOOKS`).
Defaults suit a B2B / GTM / CRM brand. Edit them for your space - matched case-insensitively
against post text, and a post can match multiple topics.

## How the post-text join works

LinkedIn's analytics URLs use `ugcPost`/`activity` URN IDs while the data archive uses
`share` URN IDs - they don't match on ID. But the analytics URL embeds a text slug
(`attio-just-dropped-gtm-atlas-...`), so the script matches posts by normalizing your archive
post text to the same slug shape and comparing prefixes. Typical match rate is ~80%; image/
video posts with little commentary are the usual misses (their URLs still appear, just
without text).

---

Part of [5050-gtm](../../README.md) - GTM skills for Claude Code by [5050Growth](https://5050growth.com). MIT licensed.
