"""LTV / CAC unit economics calculator.

Implements four canonical LTV formulas, CAC payback, LTV/CAC verdict, a
sensitivity grid (churn × gross margin), and a synthetic cohort projection.

Frameworks referenced (cited in the workbook output, not endorsed by them):
  - David Skok / Matrix Partners — "SaaS Metrics 2.0", the LTV/CAC 3:1 rule
  - Sequoia Capital — contribution-margin LTV (variable costs out of GM)
  - Andreessen Horowitz (a16z) — "16 Startup Metrics" + NDR adjustment
  - Tomasz Tunguz (Theory) — inference-cost erosion for AI products

All inputs are monthly unless noted.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Inputs:
    arpu: float                    # monthly revenue per customer ($)
    churn_rate: float              # monthly customer churn (decimal, e.g. 0.03)
    expansion_rate: float = 0.0    # monthly net revenue expansion (decimal)
    gross_margin: float = 0.78     # gross margin (decimal)
    cac: float = 0.0               # cost to acquire one customer ($)
    inference_cost: float = 0.0    # variable cost per customer per month ($)


@dataclass
class LTVResult:
    formula: str
    citation: str
    ltv: float | None              # None = undefined (e.g. expansion > churn)
    notes: str = ""


@dataclass
class Outputs:
    inputs: Inputs
    ltv_results: list[LTVResult]
    cac_payback_basic: float | None
    cac_payback_ai_adjusted: float | None
    ltv_cac_ratios: list[tuple[str, float | None]]  # (formula_label, ratio)
    monthly_ndr: float
    annual_ndr: float
    verdict: str
    verdict_color: str             # "red" | "yellow" | "green" | "blue"
    sensitivity: dict              # {"rows": [...], "cols": [...], "cells": [[...]]}
    cohort: dict                   # {"months": [...], "customers": [...], "mrr": [...], "cum_gp": [...], "payback_month": int|None}


def compute_ltv(inputs: Inputs) -> Outputs:
    a = inputs.arpu
    c = inputs.churn_rate
    e = inputs.expansion_rate
    g = inputs.gross_margin
    cac = inputs.cac
    i = inputs.inference_cost

    # ── LTV formulas ────────────────────────────────────────────────────
    ltv_results: list[LTVResult] = []

    # Skok basic
    if c > 0:
        ltv_results.append(LTVResult(
            "Skok basic — ARPU × GM / churn",
            "David Skok, SaaS Metrics 2.0",
            (a * g) / c,
        ))
    else:
        ltv_results.append(LTVResult(
            "Skok basic — ARPU × GM / churn",
            "David Skok, SaaS Metrics 2.0",
            None,
            "Churn rate is 0 — LTV is undefined (infinite).",
        ))

    # With expansion (a16z NDR-adjusted)
    net = c - e
    if net > 0:
        ltv_results.append(LTVResult(
            "NDR-adjusted — ARPU × GM / (churn - expansion)",
            "a16z 16 Startup Metrics",
            (a * g) / net,
        ))
    elif net == 0:
        ltv_results.append(LTVResult(
            "NDR-adjusted — ARPU × GM / (churn - expansion)",
            "a16z 16 Startup Metrics",
            None,
            "Expansion equals churn — net retention exactly 100%, theoretical LTV is infinite.",
        ))
    else:
        ltv_results.append(LTVResult(
            "NDR-adjusted — ARPU × GM / (churn - expansion)",
            "a16z 16 Startup Metrics",
            None,
            "Expansion > churn (negative net churn). LTV is theoretically infinite — use a finite horizon (e.g. 5 years) to bound it.",
        ))

    # AI-adjusted (Tunguz: subtract inference from gross profit per customer-month)
    if c > 0:
        contribution_per_month = (a * g) - i
        if contribution_per_month <= 0:
            ltv_results.append(LTVResult(
                "AI-adjusted — (ARPU × GM − inference) / churn",
                "Tomasz Tunguz, Unit Economics of LLMs",
                contribution_per_month / c if c > 0 else None,
                f"Inference cost (${i:.0f}/mo) ≥ gross profit per customer (${a*g:.0f}/mo). Each retained customer is unprofitable on a per-period basis.",
            ))
        else:
            ltv_results.append(LTVResult(
                "AI-adjusted — (ARPU × GM − inference) / churn",
                "Tomasz Tunguz, Unit Economics of LLMs",
                contribution_per_month / c,
            ))

    # Sequoia contribution-margin (combine NDR + variable costs)
    if net > 0:
        contribution_per_month = (a * g) - i
        if contribution_per_month > 0:
            ltv_results.append(LTVResult(
                "Sequoia contribution-margin — (ARPU × GM − variable) / (churn − expansion)",
                "Sequoia Capital, LTV/CAC 2025",
                contribution_per_month / net,
            ))
        else:
            ltv_results.append(LTVResult(
                "Sequoia contribution-margin — (ARPU × GM − variable) / (churn − expansion)",
                "Sequoia Capital, LTV/CAC 2025",
                None,
                "Variable costs exceed gross profit — contribution margin is negative.",
            ))
    else:
        ltv_results.append(LTVResult(
            "Sequoia contribution-margin — (ARPU × GM − variable) / (churn − expansion)",
            "Sequoia Capital, LTV/CAC 2025",
            None,
            "Net churn ≤ 0 (expansion ≥ churn) — bound this with a finite horizon.",
        ))

    # ── CAC payback ─────────────────────────────────────────────────────
    gp_per_month = a * g
    cac_payback_basic = (cac / gp_per_month) if gp_per_month > 0 and cac > 0 else None

    cm_per_month = (a * g) - i
    cac_payback_ai = (cac / cm_per_month) if cm_per_month > 0 and cac > 0 else None

    # ── LTV / CAC ratios ────────────────────────────────────────────────
    ratios: list[tuple[str, float | None]] = []
    for r in ltv_results:
        if r.ltv is None or r.ltv < 0 or cac <= 0:
            ratios.append((r.formula.split(" — ")[0], None))
        else:
            ratios.append((r.formula.split(" — ")[0], r.ltv / cac))

    # ── Verdict (anchored on Skok basic LTV/CAC) ────────────────────────
    skok_ratio = ratios[0][1]
    if skok_ratio is None or cac <= 0:
        verdict = "Cannot compute LTV/CAC — provide CAC and ensure churn > 0."
        verdict_color = "yellow"
    elif skok_ratio < 1:
        verdict = (
            f"🔴 Underwater: LTV/CAC = {skok_ratio:.2f}. Each customer loses money. "
            "Fix churn or cut CAC before scaling."
        )
        verdict_color = "red"
    elif skok_ratio < 3:
        verdict = (
            f"🟡 Tight: LTV/CAC = {skok_ratio:.2f}. Skok's 3:1 rule says be careful. "
            "Lower CAC, raise prices, or improve retention before pouring fuel on."
        )
        verdict_color = "yellow"
    elif skok_ratio < 5:
        verdict = (
            f"🟢 Healthy: LTV/CAC = {skok_ratio:.2f}. In Skok's 3:1–5:1 sweet spot. "
            "Fine to scale acquisition."
        )
        verdict_color = "green"
    else:
        verdict = (
            f"🟦 Possibly under-investing: LTV/CAC = {skok_ratio:.2f}. "
            "Above 5 may mean you're leaving growth on the table — Skok suggests 3-5x is optimal."
        )
        verdict_color = "blue"

    # CAC payback flag
    if cac_payback_basic and cac_payback_basic > 12:
        verdict += f" CAC payback is {cac_payback_basic:.1f} months (> 12 = slow)."
    elif cac_payback_basic:
        verdict += f" CAC payback {cac_payback_basic:.1f} months."

    # AI divergence flag
    if i > 0 and ratios[0][1] is not None and ratios[2][1] is not None:
        diff_pct = (ratios[0][1] - ratios[2][1]) / ratios[0][1] * 100
        if diff_pct > 20:
            verdict += (
                f" ⚠ Inference costs erode LTV by {diff_pct:.0f}%; "
                "watch this if usage scales faster than ARPU (Tunguz)."
            )

    # ── NDR ─────────────────────────────────────────────────────────────
    monthly_ndr = (1 - c) * (1 + e / (1 - c)) if c < 1 else 0
    annual_ndr = monthly_ndr ** 12

    # ── Sensitivity grid (churn × gross margin → LTV/CAC) ──────────────
    churn_axis = [0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.10]
    gm_axis = [0.50, 0.60, 0.70, 0.78, 0.85, 0.90]
    cells = []
    for cc in churn_axis:
        row = []
        for gg in gm_axis:
            ltv = (a * gg) / cc
            row.append(ltv / cac if cac > 0 else None)
        cells.append(row)

    sensitivity = {
        "rows": [f"{int(x*100)}%" for x in churn_axis],
        "cols": [f"{int(x*100)}%" for x in gm_axis],
        "cells": cells,
        "row_label": "Monthly churn rate",
        "col_label": "Gross margin",
        "cell_label": "LTV / CAC",
    }

    # ── Cohort projection (synthetic 100-customer cohort, 36 months) ───
    horizon = 36
    customers = [100.0]
    arpu_t = [a]
    mrr = [100.0 * a]
    cum_gp = [(100.0 * a * g) - (100.0 * i)]
    payback_month = None
    if cum_gp[0] >= 100.0 * cac > 0:
        payback_month = 0
    for t in range(1, horizon + 1):
        # apply churn to customers
        next_customers = customers[-1] * (1 - c)
        # apply expansion to ARPU
        next_arpu = arpu_t[-1] * (1 + e)
        next_mrr = next_customers * next_arpu
        gp_t = next_mrr * g - next_customers * i
        next_cum = cum_gp[-1] + gp_t
        customers.append(next_customers)
        arpu_t.append(next_arpu)
        mrr.append(next_mrr)
        cum_gp.append(next_cum)
        if payback_month is None and cac > 0 and next_cum >= 100.0 * cac:
            payback_month = t

    cohort = {
        "months": list(range(horizon + 1)),
        "customers": customers,
        "mrr": mrr,
        "cum_gross_profit": cum_gp,
        "cac_total": 100.0 * cac,
        "payback_month": payback_month,
    }

    return Outputs(
        inputs=inputs,
        ltv_results=ltv_results,
        cac_payback_basic=cac_payback_basic,
        cac_payback_ai_adjusted=cac_payback_ai,
        ltv_cac_ratios=ratios,
        monthly_ndr=monthly_ndr,
        annual_ndr=annual_ndr,
        verdict=verdict,
        verdict_color=verdict_color,
        sensitivity=sensitivity,
        cohort=cohort,
    )
