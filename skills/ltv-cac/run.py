"""LTV / CAC unit economics runner.

Either pass inputs as flags or via --inputs <path-to-json>. Default output
is a styled .xlsx workbook + CSV tables + markdown summary.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from ltv import Inputs, compute_ltv
from output import write_csvs, write_markdown_summary, write_xlsx


def main():
    p = argparse.ArgumentParser(
        description="LTV / CAC unit economics with Skok 3:1, NDR, AI-inference, contribution-margin views.",
    )
    p.add_argument("--inputs", default=None,
                   help="Path to a JSON file with all inputs (overrides flags).")
    p.add_argument("--arpu", type=float, default=None,
                   help="Monthly ARPU per customer ($)")
    p.add_argument("--churn", type=float, default=None,
                   help="Monthly customer churn rate (decimal, e.g. 0.03 for 3%%)")
    p.add_argument("--expansion", type=float, default=0.0,
                   help="Monthly net revenue expansion rate (decimal). Default 0.")
    p.add_argument("--gross-margin", type=float, default=0.78,
                   help="Gross margin (decimal). Default 0.78.")
    p.add_argument("--cac", type=float, default=None,
                   help="Customer acquisition cost ($)")
    p.add_argument("--inference-cost", type=float, default=0.0,
                   help="Variable cost per customer per month ($, AI inference). Default 0.")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--output", choices=["all", "xlsx", "csv", "markdown"], default="all")
    args = p.parse_args()

    if args.inputs:
        with open(Path(args.inputs).expanduser()) as f:
            data = json.load(f)
        inputs = Inputs(**data)
    else:
        if args.arpu is None or args.churn is None or args.cac is None:
            sys.exit(
                "Provide either --inputs <path.json> or all of --arpu, --churn, --cac.\n"
                "Optional: --expansion, --gross-margin, --inference-cost."
            )
        inputs = Inputs(
            arpu=args.arpu,
            churn_rate=args.churn,
            expansion_rate=args.expansion,
            gross_margin=args.gross_margin,
            cac=args.cac,
            inference_cost=args.inference_cost,
        )

    if not 0 <= inputs.churn_rate <= 1:
        sys.exit("--churn must be a decimal between 0 and 1 (e.g. 0.03 for 3%).")
    if not 0 <= inputs.gross_margin <= 1:
        sys.exit("--gross-margin must be a decimal between 0 and 1.")

    out_dir = Path(args.out_dir or f"/tmp/ltv-cac-{datetime.now():%Y-%m-%d-%H%M%S}")
    out_dir.mkdir(parents=True, exist_ok=True)

    out = compute_ltv(inputs)

    if args.output in ("all", "csv"):
        write_csvs(out_dir, out)
    if args.output in ("all", "xlsx"):
        try:
            write_xlsx(out_dir, out)
        except ImportError:
            print("  (skipping xlsx, `pip install openpyxl` to enable)")
    if args.output in ("all", "markdown"):
        write_markdown_summary(out_dir, out)

    # Console summary
    print()
    print(f"Done. → {out_dir}/")
    if args.output in ("all", "xlsx"):
        print(f"  → {out_dir}/ltv_cac_workbook.xlsx (open in Excel)")
    if args.output in ("all", "markdown"):
        print(f"  → {out_dir}/summary.md")
    print()
    print(out.verdict)
    print()
    print("LTV by formula:")
    for ltv, (label, ratio) in zip(out.ltv_results, out.ltv_cac_ratios):
        ltv_str = f"${ltv.ltv:>12,.0f}" if ltv.ltv is not None else f"{'undefined':>13}"
        ratio_str = f"{ratio:6.2f}x" if ratio is not None else f"{'-':>7}"
        print(f"  {label:<40s} {ltv_str}   LTV/CAC = {ratio_str}")
    if out.cac_payback_basic is not None:
        print(f"\nCAC payback: {out.cac_payback_basic:.1f} months (basic)", end="")
        if out.cac_payback_ai_adjusted is not None and out.inputs.inference_cost > 0:
            print(f" / {out.cac_payback_ai_adjusted:.1f} months (AI-adjusted)", end="")
        print()
    print(f"NDR: monthly {out.monthly_ndr*100:.2f}% / annual {out.annual_ndr*100:.1f}%")


if __name__ == "__main__":
    main()
