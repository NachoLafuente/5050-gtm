# Sample output

Anonymized illustration of what `analyze.py` prints (numbers are real-shaped, identity
stripped). Run with `--archive` for the post-text join shown here.

```
======================================================================
LINKEDIN PERFORMANCE — what works / what doesn't
======================================================================

## Summary
  Impressions: 92461
  Members reached: 35079
  Total followers: 4192

## Dataset: 50 posts (LinkedIn caps the analytics export at top ~50)
  Impressions  median 716 | mean 1698 | max 12834
  Engagements  median 20 | mean 25.3 | max 71
  Eng rate %   median 1.95 | mean 2.27 | max 7.37
  Text-matched to archive: 41/50

  !! Engagement rate is inversely tied to reach: big posts dilute ER.
     Judge big posts by absolute engagement, small posts by ER.
     This is your TOP tier only (survivorship bias) — not what flops look like.

## By TOPIC  (avg imp / avg eng / avg ER% / n)
  CRM              imp    2726 | eng  37.0 | ER  2.36% | n=17
  GTM/Sales        imp    1795 | eng  34.3 | ER  2.71% | n=9
  Automation       imp    2456 | eng  30.5 | ER  2.26% | n=11
  ...
  Other            imp     871 | eng  20.1 | ER  2.53% | n=12

## By HOOK STYLE  (avg imp / avg eng / avg ER% / n)
  Personal-I       imp    3806 | eng  42.6 | ER  1.62% | n=5
  Contrarian       imp    6782 | eng  42.3 | ER  0.95% | n=3
  Statement        imp    1331 | eng  25.2 | ER  2.60% | n=33
  ...

## By DAY OF WEEK  (avg imp / avg eng / avg ER% / n)
  Wed              imp    2037 | eng  35.8 | ER  2.72% | n=5
  Tue              imp    2470 | eng  29.0 | ER  2.15% | n=15
  Thu              imp    1180 | eng  19.7 | ER  2.27% | n=14
  ...

## Correlations (Pearson)
  length vs engagements:      +0.07
  impressions vs engagements: +0.71

## Top 8 by engagements
  eng  71 | imp    963 | ER  7.4% | Wed | 'Product just dropped a free resource. No gate.'
  eng  63 | imp  12834 | ER  0.5% | Tue | 'Once I show clients X, they never go back...'
  ...

## Bottom 5 by engagements (your weakest top-tier posts)
  eng   2 | imp    479 | 'Generic event promo with a link...'
  eng   2 | imp    445 | 'Off-brand macro statistic...'
  ...
```

## How to read it

- **CRM / GTM topics win**; the off-brand "Other" bucket is the weakest — cut it.
- **Contrarian and personal-story hooks** drive the most reach (judge them by raw
  engagement, not ER — they're high-impression so their ER looks diluted).
- **Wednesday over-performs but is under-used; Thursday drags.** Test shifting posts.
- **Length barely correlates** (+0.07) — no need to write long.
