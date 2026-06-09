---
name: social-analytics
description: Turn a LinkedIn Creator analytics export into a "what works / what doesn't" report. Parses the AggregateAnalytics_*.xlsx (and, optionally, the Shares_*.csv from your full data archive so each post is joined to its full text), tags every post by topic / hook / day / length, computes engagement rate, ranks winners and losers, and writes a styled Excel workbook + tagged CSV. Use when the user says "/social-analytics", "analyze my LinkedIn posts", "what content works", "post performance analysis", or hands over a LinkedIn analytics export. No API keys, local files in, report out.
---

# Social Analytics - what works on your LinkedIn

Most "analyze my content" advice is vibes. This skill reads the two files LinkedIn
actually gives you and tells you, with numbers, which topics / hooks / days / lengths
drove reach and engagement, and which ones quietly tanked.

The point: feed real performance data back into your content engine instead of guessing.
Pairs with a drafting skill (e.g. `social-content`) - analyze first, then draft toward
what the data says works.

## What the user needs to download first

LinkedIn splits this across two exports. You want both (the second is optional but makes
the report far richer):

1. **Creator analytics export (required)** - `AggregateAnalytics_<name>_<dates>.xlsx`.
   Get it from LinkedIn → your profile → **Analytics** → **Export** (top-right). Contains
   impressions, engagements, top-50 posts, follower growth, and audience demographics.
   *Note: LinkedIn caps this at your top ~50 posts of the last 365 days.*

2. **Full data archive (optional, recommended)** - the `Complete_LinkedInDataExport` zip.
   Get it from **Settings → Data Privacy → Get a copy of your data → larger archive**
   (takes ~24h to generate, arrives by email). Inside is `Shares_*.csv` with the full text
   of every post. The skill joins this to the analytics so the report shows the actual post
   copy, not just URLs.

If the user only has #1, the skill still runs - it just can't show post text or tag topics
(every post falls into "Other").

## Step 1: Locate the files

Ask the user where the export is, or look on the Desktop / Downloads:

```bash
ls ~/Desktop ~/Downloads 2>/dev/null | grep -iE "AggregateAnalytics|LinkedInDataExport"
```

You need the path to the `AggregateAnalytics_*.xlsx`. If they also have the data archive,
grab the folder path (the script finds `Shares_*.csv` inside it automatically).

## Step 2: Run the analysis

```bash
cd skills/social-analytics
python analyze.py \
  --analytics "/path/to/AggregateAnalytics_Name_2025-..-...xlsx" \
  --archive   "/path/to/Complete_LinkedInDataExport_folder" \
  --out ./out
```

Flags:
- `--analytics PATH` (required) - the Creator analytics xlsx.
- `--archive PATH` (optional) - the `Shares_*.csv` directly, or the unzipped data-export
  folder (script finds the CSV). Enables post-text join + topic tagging.
- `--out DIR` - where to write outputs (default `./out`).
- `--top N` - limit to the top N posts by impressions (default: all available).
- `--no-files` - print the report only, skip writing xlsx/csv.

The script prints a structured report to stdout and writes three files to `--out`:
`linkedin_analysis.xlsx` (Summary, Post Performance, Daily Engagement, Followers,
Demographics), `linkedin_posts_tagged.csv`, and `linkedin_posts.json`.

## Step 3: Report back

Read the script's stdout straight back to the user - it's already structured. Lead with the
caveats block (the script prints it), then the by-topic / by-hook / by-day tables, then the
top/bottom posts.

**Always surface these two caveats - they change how every number is read:**

- **Engagement rate is inversely tied to reach.** A 12k-impression post will show a lower
  ER% than a 900-impression post with the same raw engagement. Judge **big posts by absolute
  engagement/reach**, **small posts by ER**. Never rank on ER alone - it rewards small posts.
- **Survivorship bias.** The analytics export is your **top ~50 posts only**. It shows what
  made your best tier, not what a flop looks like. "Bottom 5" means the weakest of your
  *winners*, not your worst posts overall.

Two more honest gaps to mention if relevant:
- "Engagements" is a single blended number - no reaction / comment / share / repost split.
- The archive `MediaUrl` is usually empty for native image/document/carousel posts, so the
  skill can't reliably tell you whether media beats text. Flag it; don't fake a conclusion.

If the user wants a TL;DR, summarize in this shape:

```
## LinkedIn: what works ({date range})
Reach: {impressions} impressions, {reach} members reached, {followers} followers
Winners:  {top 2-3 topics/hooks by engagement, with one example post each}
Losers:   {worst topic bucket + the kind of post that tanks}
Cadence:  {best vs worst day}, {length verdict}
Do more:  {2-3 concrete actions}
Do less:  {1-2 concrete cuts}
```

## Step 4 (optional): close the loop

If a drafting skill like `social-content` exists, offer to save the winning patterns
(top topics, best hook styles, best day) as a memory or a note that the drafting skill
reads, so future drafts are evidence-based rather than blind.

## Tuning the taxonomy

Topic and hook detection lives in two dicts at the top of `analyze.py` (`TOPICS`, `HOOKS`).
Defaults are tuned for a B2B / GTM / CRM personal brand. For a different niche, edit the
regexes - they're matched case-insensitively against post text. Keep them broad; a post can
match several topics and all are credited in the per-topic averages.
