"""GSC + Lighthouse audit — one-shot.

Pulls Google Search Console health for a verified property, runs Lighthouse
via the PageSpeed Insights API on the top N pages by clicks, writes a
structured report to stdout and a JSON dump to ./out/audit-<date>.json.

Usage:
    python audit.py --site "sc-domain:example.com"
    python audit.py --site "https://example.com/" --top 5 --no-lighthouse

Auth:
    GSC: Application Default Credentials. Run once:
        gcloud auth application-default login --scopes=...
        (See SKILL.md "Setup: GSC auth" for full scope list.)
    PSI: PAGESPEED_API_KEY in env or .env.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PSI_CATEGORIES = ["performance", "seo", "accessibility", "best-practices"]
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


# ────────────────────────────────────────────────────────────────────
# GSC pull
# ────────────────────────────────────────────────────────────────────


def gsc_client():
    """Build a Search Console v1 client from ADC. Fails fast with a clear hint."""
    try:
        from google.auth import default
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit(
            "Missing dependencies. Install with:\n"
            "  pip install google-api-python-client google-auth requests python-dotenv"
        )

    try:
        creds, _ = default()
        return build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    except Exception as exc:
        sys.exit(
            f"GSC auth failed: {exc}\n"
            "Run:\n"
            "  gcloud auth application-default login --scopes="
            "https://www.googleapis.com/auth/webmasters.readonly,"
            "https://www.googleapis.com/auth/webmasters,openid,"
            "https://www.googleapis.com/auth/userinfo.email"
        )


def fetch_sitemap_urls(sitemap_paths: list[str]) -> list[str]:
    """Walk one level of sitemap-index, return all child URLs."""
    urls: list[str] = []
    for sm_url in sitemap_paths:
        try:
            body = requests.get(sm_url, timeout=15).content
            root = ET.fromstring(body)
        except Exception as exc:
            print(f"  (couldn't fetch {sm_url}: {exc})", file=sys.stderr)
            continue

        # If this is a sitemap-index, recurse one level
        for child in root.findall("sm:sitemap/sm:loc", SITEMAP_NS):
            try:
                child_body = requests.get(child.text, timeout=15).content
                child_root = ET.fromstring(child_body)
                for u in child_root.findall("sm:url/sm:loc", SITEMAP_NS):
                    urls.append(u.text)
            except Exception as exc:
                print(f"  (couldn't fetch {child.text}: {exc})", file=sys.stderr)

        # Or a flat sitemap
        for u in root.findall("sm:url/sm:loc", SITEMAP_NS):
            urls.append(u.text)

    return sorted(set(urls))


def pull_gsc(svc, site: str) -> dict[str, Any]:
    """Pull sitemaps, per-URL inspection, search analytics, top pages/queries."""
    out: dict[str, Any] = {"site": site, "generated_at": datetime.utcnow().isoformat() + "Z"}

    # 1. Sitemaps
    sitemaps = svc.sitemaps().list(siteUrl=site).execute().get("sitemap", [])
    out["sitemaps"] = []
    sitemap_paths: list[str] = []
    for s in sitemaps:
        sitemap_paths.append(s["path"])
        contents = (s.get("contents") or [{}])[0]
        out["sitemaps"].append(
            {
                "path": s["path"],
                "last_submitted": s.get("lastSubmitted", "")[:10],
                "last_downloaded": s.get("lastDownloaded", "")[:10],
                "errors": s.get("errors", 0),
                "warnings": s.get("warnings", 0),
                "is_pending": s.get("isPending", False),
                "submitted_count": contents.get("submitted", "?"),
                "indexed_count": contents.get("indexed", "?"),
            }
        )

    # 2. Sitemap URLs → per-URL inspection
    all_urls = fetch_sitemap_urls(sitemap_paths)
    out["total_urls_in_sitemap"] = len(all_urls)

    buckets: dict[str, list[dict]] = defaultdict(list)
    for url in all_urls:
        try:
            resp = (
                svc.urlInspection()
                .index()
                .inspect(body={"inspectionUrl": url, "siteUrl": site})
                .execute()
            )
            idx = resp.get("inspectionResult", {}).get("indexStatusResult", {})
            verdict = idx.get("verdict", "OTHER")
            entry = {
                "url": url,
                "coverage": idx.get("coverageState", "?"),
                "google_canonical": idx.get("googleCanonical"),
                "user_canonical": idx.get("userCanonical"),
                "robots_txt": idx.get("robotsTxtState"),
                "indexing": idx.get("indexingState"),
                "last_crawl": idx.get("lastCrawlTime", "")[:10],
            }
            entry["canonical_mismatch"] = bool(
                entry["google_canonical"]
                and entry["user_canonical"]
                and entry["google_canonical"] != entry["user_canonical"]
            )
            buckets[verdict].append(entry)
        except Exception as exc:
            buckets["OTHER"].append({"url": url, "error": str(exc)})
    out["index_status"] = dict(buckets)

    # 3. Search analytics: 28d vs prior 28d (3-day GSC lag)
    today = date.today()

    def daterange(end_offset: int, days: int = 28) -> tuple[str, str]:
        end = today - timedelta(days=end_offset)
        start = end - timedelta(days=days - 1)
        return start.isoformat(), end.isoformat()

    cur_s, cur_e = daterange(3, 28)
    prev_s, prev_e = daterange(31, 28)

    def totals(start: str, end: str) -> dict:
        rows = (
            svc.searchanalytics()
            .query(siteUrl=site, body={"startDate": start, "endDate": end, "dimensions": []})
            .execute()
            .get("rows", [{}])
        )
        return rows[0] if rows else {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}

    cur, prev = totals(cur_s, cur_e), totals(prev_s, prev_e)
    out["search_performance"] = {
        "current_window": [cur_s, cur_e],
        "prior_window": [prev_s, prev_e],
        "current": cur,
        "prior": prev,
    }

    # 4. Top pages + queries
    def topn(dim: str, n: int = 10) -> list[dict]:
        return (
            svc.searchanalytics()
            .query(
                siteUrl=site,
                body={
                    "startDate": cur_s,
                    "endDate": cur_e,
                    "dimensions": [dim],
                    "rowLimit": n,
                },
            )
            .execute()
            .get("rows", [])
        )

    out["top_pages"] = topn("page", 10)
    out["top_queries"] = topn("query", 10)

    return out


# ────────────────────────────────────────────────────────────────────
# Lighthouse via PSI
# ────────────────────────────────────────────────────────────────────


def audit_one(url: str, api_key: str) -> tuple[str, dict]:
    """Run Lighthouse mobile audit against one URL via PSI. Returns (url, result)."""
    params = [
        ("url", url),
        ("strategy", "mobile"),
        ("key", api_key),
        *[("category", c) for c in PSI_CATEGORIES],
    ]
    try:
        r = requests.get(PSI_ENDPOINT, params=params, timeout=120)
    except Exception as exc:
        return url, {"error": str(exc)}
    if not r.ok:
        return url, {"error": f"HTTP {r.status_code}: {r.text[:200]}"}

    data = r.json()
    lh = data.get("lighthouseResult", {})
    cats = lh.get("categories", {})
    audits = lh.get("audits", {})

    scores = {k: round((cats.get(k, {}).get("score") or 0) * 100) for k in PSI_CATEGORIES}
    cwv_lab = {
        "LCP": audits.get("largest-contentful-paint", {}).get("displayValue"),
        "CLS": audits.get("cumulative-layout-shift", {}).get("displayValue"),
        "TBT": audits.get("total-blocking-time", {}).get("displayValue"),
        "FCP": audits.get("first-contentful-paint", {}).get("displayValue"),
    }

    # Surface failed audits worth fixing (score < 0.9)
    issues = []
    for aid, a in audits.items():
        score = a.get("score")
        if score is None or score >= 0.9:
            continue
        if a.get("scoreDisplayMode") in ("manual", "notApplicable", "informative"):
            continue
        title = a.get("title", aid)
        savings_ms = a.get("details", {}).get("overallSavingsMs")
        savings_bytes = a.get("details", {}).get("overallSavingsBytes")
        tag = ""
        if savings_ms:
            tag = f" (-{int(savings_ms)}ms)"
        elif savings_bytes:
            tag = f" (-{int(savings_bytes / 1024)}KB)"
        issues.append({"id": aid, "title": title + tag, "score": score})
    issues.sort(key=lambda x: x["score"])

    field = data.get("loadingExperience", {}).get("metrics", {})
    cwv_field = {k: v.get("category") for k, v in field.items()}

    console_errors = []
    ce = audits.get("errors-in-console", {})
    for item in ce.get("details", {}).get("items", []):
        console_errors.append(
            {
                "source": item.get("source", "?"),
                "description": item.get("description", "?"),
                "url": item.get("sourceLocation", {}).get("url"),
            }
        )

    return url, {
        "scores": scores,
        "cwv_lab": cwv_lab,
        "cwv_field": cwv_field,
        "issues": issues[:8],
        "console_errors": console_errors,
    }


def run_lighthouse(urls: list[str], api_key: str, max_workers: int = 4) -> dict[str, dict]:
    """Run Lighthouse on a list of URLs in parallel. Returns dict[url] -> result."""
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(audit_one, u, api_key): u for u in urls}
        for fut in as_completed(futs):
            url, res = fut.result()
            results[url] = res
    return results


# ────────────────────────────────────────────────────────────────────
# Reporting
# ────────────────────────────────────────────────────────────────────


def fmt_pct(cur: float, prev: float) -> str:
    return f"{((cur - prev) / prev * 100):+.0f}%" if prev else "n/a"


def host_of(url: str) -> str:
    return url.split("/")[2] if "://" in url else url


def short_path(url: str, base: str) -> str:
    """Strip the property base so paths read cleanly."""
    if base.startswith("sc-domain:"):
        host = base[len("sc-domain:") :]
        for prefix in (f"https://{host}", f"http://{host}"):
            if url.startswith(prefix):
                p = url[len(prefix) :]
                return p or "/"
        return url
    if url.startswith(base):
        p = url[len(base.rstrip("/")) :]
        return p or "/"
    return url


def render_report(gsc: dict, lh: dict[str, dict] | None, base: str) -> str:
    """Compose the human-readable report."""
    lines: list[str] = []
    lines.append(f"## GSC + Lighthouse — {date.today().isoformat()}\n")

    # Sitemap
    lines.append("### Sitemap")
    for sm in gsc["sitemaps"]:
        lines.append(f"- {sm['path']}")
        lines.append(
            f"    submitted {sm['last_submitted']}, downloaded {sm['last_downloaded']}, "
            f"errors {sm['errors']}, warnings {sm['warnings']}"
        )
    lines.append(f"\nTotal URLs in sitemap: {gsc['total_urls_in_sitemap']}\n")

    # Index coverage
    buckets = gsc["index_status"]
    pass_n = len(buckets.get("PASS", []))
    neutral_n = len(buckets.get("NEUTRAL", []))
    fail_n = len(buckets.get("FAIL", []))
    other_n = len(buckets.get("OTHER", []))
    lines.append("### Index coverage")
    lines.append(f"- Indexed (PASS): {pass_n}")
    lines.append(f"- Pending / unknown (NEUTRAL): {neutral_n}")
    lines.append(f"- Excluded / failed (FAIL): {fail_n}")
    if other_n:
        lines.append(f"- Other / errors: {other_n}")

    # Surface specific worry coverage states
    worry_states = {
        "Crawled - currently not indexed",
        "Discovered - currently not indexed",
        "Soft 404",
        "Duplicate without user-selected canonical",
        "Excluded by 'noindex' tag",
        "Alternate page with proper canonical tag",
    }
    flagged = []
    for verdict, items in buckets.items():
        for it in items:
            if isinstance(it, dict) and it.get("coverage") in worry_states:
                flagged.append(f"  {short_path(it['url'], base)} [{it['coverage']}]")
            if isinstance(it, dict) and it.get("canonical_mismatch"):
                flagged.append(
                    f"  {short_path(it['url'], base)} CANONICAL MISMATCH "
                    f"(google={it['google_canonical']})"
                )
    if flagged:
        lines.append("\nFlagged URLs:")
        lines.extend(flagged[:30])
    lines.append("")

    # Search performance
    sp = gsc["search_performance"]
    cur, prev = sp["current"], sp["prior"]
    lines.append("### Search performance (last 28d vs prior 28d)")
    lines.append(f"Window: {sp['current_window'][0]} → {sp['current_window'][1]}")
    lines.append(
        f"- Clicks:      {cur.get('clicks', 0)} ({fmt_pct(cur.get('clicks', 0), prev.get('clicks', 0))})"
    )
    lines.append(
        f"- Impressions: {cur.get('impressions', 0)} "
        f"({fmt_pct(cur.get('impressions', 0), prev.get('impressions', 0))})"
    )
    lines.append(
        f"- CTR:         {cur.get('ctr', 0) * 100:.2f}% "
        f"({fmt_pct(cur.get('ctr', 0), prev.get('ctr', 0))})"
    )
    lines.append(
        f"- Avg position: {cur.get('position', 0):.1f} (prev {prev.get('position', 0):.1f})\n"
    )

    # Top movers
    lines.append("### Top pages (28d)")
    for row in gsc["top_pages"][:10]:
        path = short_path(row["keys"][0], base)
        lines.append(
            f"  {path:50s}  clicks={row['clicks']:>4}  "
            f"impr={row['impressions']:>5}  pos={row['position']:.1f}"
        )
    lines.append("")
    lines.append("### Top queries (28d)")
    for row in gsc["top_queries"][:10]:
        q = row["keys"][0][:60]
        lines.append(
            f"  {q:60s}  clicks={row['clicks']:>4}  "
            f"impr={row['impressions']:>5}  pos={row['position']:.1f}"
        )
    lines.append("")

    # Lighthouse
    if lh:
        lines.append("### Lighthouse — top pages (mobile)")
        lines.append("| Page | Perf | SEO | A11y | Best | LCP | TBT | Console |")
        lines.append("|------|-----:|----:|-----:|-----:|-----|-----|--------:|")
        scored = []
        for url, res in lh.items():
            if "error" in res:
                lines.append(
                    f"| {short_path(url, base)} | ERROR | | | | | | |  ({res['error']})"
                )
                continue
            s = res["scores"]
            c = res["cwv_lab"]
            ce = len(res["console_errors"])
            scored.append(s["performance"])
            lines.append(
                f"| {short_path(url, base)} | {s['performance']} | {s['seo']} | "
                f"{s['accessibility']} | {s['best-practices']} | {c['LCP']} | {c['TBT']} | {ce} |"
            )
        if scored:
            scored.sort()
            median = scored[len(scored) // 2]
            lines.append(f"\nMedian perf: {median}")

        # Aggregated themes
        lines.append("\n### Fix themes (>=2 pages)")
        theme_pages: dict[str, list[str]] = defaultdict(list)
        theme_titles: dict[str, str] = {}
        for url, res in lh.items():
            if "error" in res:
                continue
            for issue in res["issues"]:
                theme_pages[issue["id"]].append(short_path(url, base))
                theme_titles[issue["id"]] = issue["title"].split(" (-")[0]
        themes = sorted(theme_pages.items(), key=lambda x: -len(x[1]))
        for aid, pages in themes:
            if len(pages) >= 2:
                lines.append(f"  [{len(pages):>2} pages] {theme_titles[aid]}")
        if not any(len(p) >= 2 for _, p in themes):
            lines.append("  (no theme hits 2+ pages — site is in good shape)")

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
# Entry
# ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="GSC + Lighthouse audit. Reads ADC for GSC and PAGESPEED_API_KEY for PSI."
    )
    parser.add_argument(
        "--site",
        required=True,
        help="GSC property. Use 'sc-domain:example.com' or 'https://example.com/'.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of top-by-clicks pages to audit with Lighthouse. Default: 10.",
    )
    parser.add_argument(
        "--no-lighthouse",
        action="store_true",
        help="Skip the PSI / Lighthouse step.",
    )
    parser.add_argument(
        "--out",
        default="out",
        help="Directory to write the JSON dump. Default: ./out",
    )
    args = parser.parse_args()

    # GSC
    print(f"Pulling GSC for {args.site}...", file=sys.stderr)
    svc = gsc_client()
    gsc = pull_gsc(svc, args.site)

    # Lighthouse
    lh: dict[str, dict] | None = None
    if not args.no_lighthouse:
        api_key = os.environ.get("PAGESPEED_API_KEY")
        if not api_key:
            print(
                "WARNING: PAGESPEED_API_KEY not set. Skipping Lighthouse step.\n"
                "  See SKILL.md 'Setup: PSI API key' for the 30-second setup.",
                file=sys.stderr,
            )
        else:
            top_urls = [r["keys"][0] for r in gsc["top_pages"][: args.top]]
            print(f"Running Lighthouse on {len(top_urls)} pages (mobile)...", file=sys.stderr)
            lh = run_lighthouse(top_urls, api_key)

    # Render + persist
    report = render_report(gsc, lh, args.site)
    print(report)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    dump_path = out_dir / f"audit-{date.today().isoformat()}.json"
    dump_path.write_text(
        json.dumps({"gsc": gsc, "lighthouse": lh}, indent=2, default=str)
    )
    print(f"\n(JSON dump: {dump_path})", file=sys.stderr)


if __name__ == "__main__":
    main()
