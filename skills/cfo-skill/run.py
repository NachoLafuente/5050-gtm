"""CFO skill runner.

Two modes:
  --source csv   read CSVs from a folder (default: ./examples)
  --source api   pull live from Attio + Qonto + Moss into a temp folder, then run

Both modes produce the same Excel dashboard.

⚠ This skill displays data. It is NOT financial, legal, tax, or investment advice.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from cfo import load_all, summarize  # noqa: E402
from xlsx_writer import write_workbook  # noqa: E402

load_dotenv()


DISCLAIMER = (
    "⚠  DISCLAIMER: This tool displays data only. It is NOT financial, legal, tax, "
    "or investment advice. Numbers may be stale or miscategorized. Verify in the "
    "source system and consult a qualified professional before making decisions."
)


def parse_as_of(s: str | None) -> date:
    if not s:
        return date.today()
    return datetime.strptime(s, "%Y-%m-%d").date()


def pull_api(out_dir: Path, providers: list[str]) -> dict:
    """Run pullers in the order given by --providers. Last writer wins on overwrite,
    appenders add rows. Default order puts Stripe last so its MRR wins over Attio.
    """
    counts = {}
    if "qonto" in providers:
        from pullers import qonto
        print("→ pulling Qonto org + transactions + invoices …")
        counts.update({f"qonto_{k}": v for k, v in qonto.pull_all(out_dir).items()})
    if "attio" in providers:
        from pullers import attio
        print("→ pulling Attio companies …")
        counts["attio_customers"] = attio.write_customers_csv(out_dir / "customers.csv")
    if "stripe" in providers:
        from pullers import stripe_source
        print("→ pulling Stripe customers + subscriptions + invoices …")
        counts.update({f"stripe_{k}": v for k, v in stripe_source.pull_all(out_dir).items()})
    if "moss" in providers:
        from pullers import moss
        print("→ pulling Moss expenses (appending to cash_movements) …")
        counts["moss_expenses"] = moss.append_movements(out_dir / "cash_movements.csv")
    return counts


def main() -> int:
    ap = argparse.ArgumentParser(description="CFO data dashboard, Attio + Qonto + Moss")
    ap.add_argument("--source", choices=["csv", "api"], default="csv")
    ap.add_argument("--csv-dir", type=Path, default=SKILL_DIR / "examples", help="Folder with input CSVs (csv mode)")
    ap.add_argument(
        "--providers",
        default="all",
        help="Comma-separated, in priority order (later writers win on customers.csv / invoices.csv): "
             "qonto,attio,stripe,moss, or 'all'. Example: --providers qonto,stripe,moss",
    )
    ap.add_argument("--output", "-o", type=Path, default=Path("cfo-dashboard.xlsx"))
    ap.add_argument("--as-of", default=None, help="Reporting date (YYYY-MM-DD), default today")
    args = ap.parse_args()

    print(DISCLAIMER + "\n")

    if args.source == "api":
        providers = (
            ["qonto", "attio", "stripe", "moss"] if args.providers == "all"
            else [p.strip() for p in args.providers.split(",") if p.strip()]
        )
        tmp = Path(tempfile.mkdtemp(prefix="cfo-skill-"))
        print(f"Pulling live data into {tmp}")
        try:
            counts = pull_api(tmp, providers)
            print("Pulled:", counts)
        except Exception as e:
            print(f"\n❌ API pull failed: {e}")
            print("Tip: run with --source csv to use CSV templates instead.")
            return 1
        csv_dir = tmp
    else:
        csv_dir = args.csv_dir

    print(f"\nLoading CSVs from {csv_dir}")
    data = load_all(csv_dir)
    if not any(data.values()):
        print(f"❌ No data found in {csv_dir}. Provide customers.csv / cash_movements.csv / invoices.csv / balances.csv")
        print(f"   Templates live at {SKILL_DIR / 'templates'}")
        return 1

    metrics = summarize(data, as_of=parse_as_of(args.as_of))

    print("\n=== HEADLINE METRICS ===")
    print(f"  Cash balance:      {metrics['cash']['total']:>12,.0f}")
    print(f"  Avg net burn (3m): {metrics['burn']['avg_net_burn']:>12,.0f} / month")
    runway = metrics["runway_months"]
    runway_str = "∞ (no burn)" if runway == float("inf") else f"{runway:.1f} months"
    print(f"  Runway:            {runway_str:>12}")
    print(f"  MRR:               {metrics['mrr']['mrr']:>12,.0f}  ({metrics['mrr']['active_customers']} active customers)")
    print(f"  ARR:               {metrics['mrr']['arr']:>12,.0f}")
    print(f"  Top customer:      {metrics['concentration']['top_1_pct']:>11.1f}% of MRR")
    print(f"  AR outstanding:    {metrics['ar']['total']:>12,.0f}")
    print(f"  DSO:               {metrics['dso']:>12.0f} days")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_workbook(metrics, data["customers"], args.output)
    print(f"\n✓ Wrote dashboard → {args.output.resolve()}")
    print("\n" + DISCLAIMER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
