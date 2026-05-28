# Sample output

Anonymized output from a real run on a small B2B marketing site (~50 indexed URLs, ~14k impressions / 28d).

```
## GSC + Lighthouse: 2026-05-05

### Sitemap
- https://example.com/sitemap-index.xml
    submitted 2026-05-04, downloaded 2026-05-04, errors 0, warnings 0

Total URLs in sitemap: 49

### Index coverage
- Indexed (PASS): 18
- Pending / unknown (NEUTRAL): 31
- Excluded / failed (FAIL): 0

Flagged URLs:
  /attio-for/agencies/  [Crawled - currently not indexed]
  /blog/example-post/  CANONICAL MISMATCH (google=https://example.com/blog/example-post/)

### Search performance (last 28d vs prior 28d)
Window: 2026-04-05 → 2026-05-02
- Clicks:      33 (+6%)
- Impressions: 14251 (-11%)
- CTR:         0.23% (-25%)
- Avg position: 9.2 (prev 9.0)

### Top pages (28d)
  /                                  clicks=  10  impr=   71  pos=2.9
  /attio-vs/hubspot                  clicks=   5  impr= 6460  pos=7.8
  /attio-vs/salesforce               clicks=   4  impr= 1099  pos=9.2
  ...

### Top queries (28d)
  attio vs hubspot                   clicks=   1  impr=  271  pos=9.0
  attio vs pipedrive                 clicks=   1  impr=   53  pos=25.3
  ...

### Lighthouse: top pages (mobile)
| Page | Perf | SEO | A11y | Best | LCP | TBT | Console |
|------|-----:|----:|-----:|-----:|-----|-----|--------:|
| / | 82 | 100 | 96 | 100 | 3.6 s | 0 ms | 0 |
| /attio-vs/hubspot | 84 | 100 | 96 | 100 | 3.5 s | 0 ms | 0 |
| /attio-vs/close | 85 | 100 | 96 | 100 | 3.4 s | 0 ms | 0 |
| /blog/example-post | 86 | 100 | 96 | 100 | 3.3 s | 0 ms | 0 |
...

Median perf: 85

### Fix themes (>=2 pages)
  [10 pages] Reduce unused JavaScript
  [ 9 pages] Background and foreground colors do not have a sufficient contrast ratio.
  [ 7 pages] Avoid multiple page redirects
  [ 6 pages] Improve image delivery
  [ 5 pages] Render blocking requests
```

The ranked themes at the bottom are the actionable part. Instead of "page X has unused JS, page Y has unused JS, ..." 10 times, you see one line: 10 pages share this issue. One PR fixes them all.
