"""Output writers, xlsx workbook + CSV tables + markdown summary."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path


def write_xlsx(out_dir: Path, out) -> None:
    from xlsx_writer import write_ltv_workbook
    write_ltv_workbook(out_dir / "ltv_cac_workbook.xlsx", out)


def write_csvs(out_dir: Path, out) -> None:
    # LTV summary
    with (out_dir / "ltv_summary.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["formula", "ltv_dollars", "ltv_cac_ratio", "citation", "notes"])
        for ltv, (_, ratio) in zip(out.ltv_results, out.ltv_cac_ratios):
            w.writerow([
                ltv.formula,
                f"{ltv.ltv:.2f}" if ltv.ltv is not None else "",
                f"{ratio:.4f}" if ratio is not None else "",
                ltv.citation,
                ltv.notes,
            ])

    # CAC payback
    with (out_dir / "cac_payback.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["method", "payback_months"])
        if out.cac_payback_basic is not None:
            w.writerow(["basic", f"{out.cac_payback_basic:.2f}"])
        if out.cac_payback_ai_adjusted is not None:
            w.writerow(["ai_adjusted", f"{out.cac_payback_ai_adjusted:.2f}"])

    # NDR
    with (out_dir / "ndr.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["window", "ndr"])
        w.writerow(["monthly", f"{out.monthly_ndr:.6f}"])
        w.writerow(["annual_compounded", f"{out.annual_ndr:.6f}"])

    # Sensitivity
    s = out.sensitivity
    with (out_dir / "sensitivity.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([f"{s['row_label']} \\ {s['col_label']}"] + s["cols"])
        for row_label, row_cells in zip(s["rows"], s["cells"]):
            w.writerow([row_label] + [
                f"{v:.4f}" if v is not None else "" for v in row_cells
            ])

    # Cohort
    cohort = out.cohort
    with (out_dir / "cohort_projection.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lifetime_month", "customers", "mrr_dollars",
                    "cumulative_gross_profit_dollars", "vs_cac_dollars"])
        for i, m in enumerate(cohort["months"]):
            delta = cohort["cum_gross_profit"][i] - cohort["cac_total"]
            w.writerow([
                m,
                f"{cohort['customers'][i]:.4f}",
                f"{cohort['mrr'][i]:.2f}",
                f"{cohort['cum_gross_profit'][i]:.2f}",
                f"{delta:.2f}",
            ])

    # Inputs JSON (re-runnable)
    with (out_dir / "inputs.json").open("w") as f:
        json.dump(asdict(out.inputs), f, indent=2)


def write_markdown_summary(out_dir: Path, out) -> None:
    inputs = out.inputs
    lines = [
        "# LTV / CAC summary",
        "",
        f"**Verdict:** {out.verdict}",
        "",
        "## Inputs",
        "",
        f"- ARPU: ${inputs.arpu:,.0f}/mo",
        f"- Customer churn: {inputs.churn_rate*100:.2f}%/mo",
        f"- Net revenue expansion: {inputs.expansion_rate*100:.2f}%/mo",
        f"- Gross margin: {inputs.gross_margin*100:.0f}%",
        f"- CAC: ${inputs.cac:,.0f}",
        f"- Inference / variable cost: ${inputs.inference_cost:,.0f}/cust/mo",
        "",
        "## LTV by formula",
        "",
        "| Formula | LTV ($) | LTV/CAC | Citation |",
        "|---|---:|---:|---|",
    ]
    for ltv, (_, ratio) in zip(out.ltv_results, out.ltv_cac_ratios):
        ltv_str = f"${ltv.ltv:,.0f}" if ltv.ltv is not None else "undefined"
        ratio_str = f"{ratio:.2f}" if ratio is not None else "-"
        lines.append(f"| {ltv.formula} | {ltv_str} | {ratio_str} | {ltv.citation} |")

    lines.extend([
        "",
        "## CAC Payback",
        "",
    ])
    if out.cac_payback_basic is not None:
        lines.append(f"- **Basic** (CAC ÷ gross profit/mo): **{out.cac_payback_basic:.1f} months**")
    if out.cac_payback_ai_adjusted is not None:
        lines.append(f"- **AI-adjusted** (subtract inference): **{out.cac_payback_ai_adjusted:.1f} months**")

    lines.extend([
        "",
        "## NDR",
        "",
        f"- Monthly: {out.monthly_ndr*100:.2f}%",
        f"- Annual (compounded): {out.annual_ndr*100:.1f}%",
        "",
        "## Frameworks referenced",
        "",
        "- David Skok, *SaaS Metrics 2.0*, for-entrepreneurs.com",
        "- a16z, *The 16 Startup Metrics*, a16z.com",
        "- Sequoia Capital, *LTV/CAC*, sequoiacap.com",
        "- Tomasz Tunguz, *Unit Economics of LLMs*, tomtunguz.com",
        "",
    ])
    (out_dir / "summary.md").write_text("\n".join(lines))
