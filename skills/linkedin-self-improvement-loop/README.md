# /linkedin-self-improvement-loop

A **build-measure-learn loop** for your LinkedIn. Not a report you read once - a loop that
keeps state and compounds every time you run it.

No dashboards, no analytics SaaS, no API keys. Feed it your LinkedIn export on a cadence;
it tells you whether your last bet worked, updates what it believes about your audience,
and hands you the next experiment to run.

## The loop

```
  1. MEASURE  -> 2. RECONCILE -> 3. UPDATE BELIEFS
  (ingest export)  (did last bet    (confidence rises if a
        ^           hold up?)         pattern held, halves if broke)
        |                                  |
  6. WAIT  <- 5. DRAFT BRIEFS <- 4. PROPOSE ONE EXPERIMENT
  (re-run next  (hand to a          (biggest effect on the
   export)       drafting skill)     least-settled belief)
```

**Advisory by design.** It proposes experiments and emits draft briefs. A human writes and
posts every post. It never touches LinkedIn.

## Why a loop beats a report

A one-shot analyzer tells you what *happened*. It has no memory, so it can't tell you whether
anything *improved*. This keeps a belief model in `state/` and reconciles it against each new
export: patterns that survive get promoted to laws, patterns that break get archived, and the
loop always advances to the next highest-leverage experiment. One bet at a time, so you can
actually attribute the result.

## Inputs (same two files each cycle)

| File | Where | Required? |
|---|---|---|
| `AggregateAnalytics_<name>_<dates>.xlsx` | LinkedIn -> profile -> **Analytics** -> **Export** | **Yes** |
| `Complete_LinkedInDataExport` (-> `Shares_*.csv`) | **Settings -> Data Privacy -> Get a copy of your data -> larger archive** | Optional, recommended (adds post text -> topic/hook tagging) |

## Usage

```bash
cd skills/linkedin-self-improvement-loop
pip install openpyxl>=3.1   # only dependency

# run a cycle
python loop.py \
  --analytics "AggregateAnalytics_Jane_2025-06-09_2026-06-08.xlsx" \
  --archive   "~/Desktop/Complete_LinkedInDataExport" \
  --state ./state \
  --metric engagements        # engagements (default) | impressions | er
```

Schedule it (this is what makes it a loop):

```
/schedule a linkedin-self-improvement-loop run every 2 weeks
```

### One-off deep report

Want the full static read (all tables, top/bottom posts, correlations, Excel workbook)
without the loop state? Run the MEASURE stage directly:

```bash
python analyze.py --analytics "...xlsx" --archive "...folder" --out ./out
```

## State (`./state`, never committed)

| File | What |
|---|---|
| `beliefs.json` / `beliefs.md` | The model: traits with confidence that updates each cycle |
| `ledger.jsonl` | One line per cycle (audit trail) |
| `snapshots/<date>.json` | Parsed metrics per export, for cross-cycle trends |

`state/.gitignore` keeps your personal LinkedIn data and belief model **out of git**. Back
it up if you want the history; delete it to start fresh.

## Read the numbers honestly

The loop reminds you every run:

1. **Engagement rate is inversely tied to reach.** Default metric `engagements` sidesteps it;
   `er` rewards small posts.
2. **Survivorship bias fades over cycles.** Any single export is your top ~50 posts only. The
   `snapshots/` defeat this over time; in cycle 1 a "loss" just means weakest of your winners.
3. **Small n.** It ignores anything under n=3 and shows n everywhere. A 1.6x effect on n=3 is a
   hint, not a law, until cycles confirm it.

It won't pretend to know things it can't: "engagements" is one blended number (no
reaction/comment/share split), and native image/carousel posts have no `MediaUrl`, so it
won't claim media beats text.

## Customizing

- **Niche:** edit the `TOPICS` / `HOOKS` regex dicts at the top of `analyze.py`.
- **Loop behavior:** learning rate, noise deadband, min sample size, and seed confidence are
  tunable constants at the top of `loop.py`.

## How the post-text join works

LinkedIn's analytics URLs use `ugcPost`/`activity` URN IDs while the data archive uses `share`
IDs - they don't match on ID. But the analytics URL embeds a text slug
(`attio-just-dropped-gtm-atlas-...`), so the loop matches posts by normalizing archive text to
the same slug shape and comparing prefixes. Typical match ~80%; image/video posts with little
commentary are the usual misses (their URLs still appear, just without text).

---

Part of [5050-gtm](../../README.md) - GTM skills for Claude Code by [5050Growth](https://5050growth.com). MIT licensed.
