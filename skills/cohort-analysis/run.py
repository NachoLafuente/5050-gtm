"""Cohort analysis runner.

Asks 3 (or 5) CLI args worth of questions, pulls from CRM + money source,
builds the full cohort suite, writes the .xlsx workbook + per-section CSVs.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from cohort import build_cohorts, quick_summary
from output import write_audit, write_cohort_csvs, write_evidence, write_sql, write_xlsx
from pullers import attio, csv_source, stripe_source

load_dotenv()


REQUIRED_ENV = {
    "attio": "ATTIO_API_KEY",
    "stripe": "STRIPE_SECRET_KEY",
    "csv": None,
}


def check_env(crm: str, money: str) -> list[str]:
    missing = []
    for source in {crm, money}:
        var = REQUIRED_ENV.get(source)
        if var and not os.getenv(var):
            missing.append(f"{source} → {var}")
    return missing


def pull_customers(args) -> list[dict]:
    if args.crm == "attio":
        return attio.pull_customers(
            api_key=os.environ["ATTIO_API_KEY"],
            object_slug=args.attio_object,
        )
    if args.crm == "stripe":
        return stripe_source.pull_customers(api_key=os.environ["STRIPE_SECRET_KEY"])
    if args.crm == "csv":
        return csv_source.pull_customers(args.csv_customers)
    raise ValueError(f"unknown crm: {args.crm}")


def pull_revenue(args) -> list[dict]:
    if args.money == "stripe":
        return stripe_source.pull_revenue(api_key=os.environ["STRIPE_SECRET_KEY"])
    if args.money == "attio":
        return attio.pull_revenue(
            api_key=os.environ["ATTIO_API_KEY"],
            object_slug=args.attio_object,
            amount_attr=args.attio_amount_attr,
            date_paid_attr=args.attio_date_paid_attr,
            date_churned_attr=args.attio_date_churned_attr,
        )
    if args.money == "csv":
        return csv_source.pull_revenue(args.csv_revenue)
    raise ValueError(f"unknown money source: {args.money}")


def main():
    p = argparse.ArgumentParser(
        description="Build a SaaS cohort analysis from your CRM + money source.",
    )
    p.add_argument("--crm", choices=["attio", "stripe", "csv"])
    p.add_argument("--money", choices=["stripe", "attio", "csv"])
    p.add_argument(
        "--output",
        choices=["xlsx", "csv", "all", "sql", "evidence"],
        default="all",
        help="all = xlsx + per-section CSVs (default). xlsx-only or csv-only also valid.",
    )
    p.add_argument("--out-dir", default=None)
    p.add_argument("--attio-object", default="companies")
    p.add_argument("--attio-amount-attr", default=None)
    p.add_argument("--attio-date-paid-attr", default=None)
    p.add_argument("--attio-date-churned-attr", default=None)
    p.add_argument("--csv-customers", default=None)
    p.add_argument("--csv-revenue", default=None)
    p.add_argument(
        "--cacs",
        default=None,
        help="Path to a CSV with columns: cohort, cac_amount. Enables CAC payback section.",
    )
    p.add_argument(
        "--gross-margin",
        type=float,
        default=0.8,
        help="Gross margin as a decimal (default 0.8 = 80%%). Used for CAC payback.",
    )
    p.add_argument("--cohort-grain", choices=["month", "quarter"], default="month")
    p.add_argument("--check-env", action="store_true")
    args = p.parse_args()

    if not args.crm or not args.money:
        sys.exit("--crm and --money are required (see SKILL.md for the 3 questions)")

    missing = check_env(args.crm, args.money)
    if missing:
        print("Missing env vars in .env:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)
    if args.check_env:
        print("env OK")
        return

    if args.money == "attio":
        if not args.attio_amount_attr:
            sys.exit("--attio-amount-attr is required when --money attio")
        if not args.attio_date_paid_attr:
            sys.exit("--attio-date-paid-attr is required when --money attio")
    if args.crm == "csv" and not args.csv_customers:
        sys.exit("--csv-customers is required when --crm csv")
    if args.money == "csv" and not args.csv_revenue:
        sys.exit("--csv-revenue is required when --money csv")
    if not 0 < args.gross_margin <= 1:
        sys.exit("--gross-margin must be between 0 and 1 (e.g. 0.8 for 80%)")

    out_dir = Path(args.out_dir or f"/tmp/cohort-{datetime.now():%Y-%m-%d-%H%M%S}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Pulling customers from {args.crm}...")
    customers = pull_customers(args)
    print(f"  {len(customers)} customers")

    print(f"Pulling revenue from {args.money}...")
    revenue = pull_revenue(args)
    print(f"  {len(revenue)} revenue events")

    cacs = {}
    if args.cacs:
        cacs = csv_source.pull_cacs(args.cacs)
        print(f"  {len(cacs)} CAC values loaded")

    data = build_cohorts(
        customers=customers,
        revenue=revenue,
        cacs=cacs,
        gross_margin=args.gross_margin,
        grain=args.cohort_grain,
    )

    write_audit(out_dir, customers, revenue)

    if args.output in ("all", "csv"):
        write_cohort_csvs(out_dir, data)
    if args.output in ("all", "xlsx"):
        try:
            write_xlsx(out_dir, data)
        except ImportError:
            print("  (skipping xlsx — `pip install openpyxl` to enable)")
    if args.output == "sql":
        write_cohort_csvs(out_dir, data)
        write_sql(out_dir, data, customers, revenue)
    if args.output == "evidence":
        write_cohort_csvs(out_dir, data)
        write_evidence(out_dir, data, customers, revenue)

    print()
    print(f"Done. {len(customers)} customers, {len(revenue)} events, "
          f"{len(data['cohorts'])} cohorts.")
    if args.output in ("all", "xlsx"):
        print(f"  → {out_dir}/cohort_workbook.xlsx (open in Excel)")
    print(f"  → {out_dir}/  (per-section CSVs + audit trail)")
    print(f"  → {quick_summary(data)}")
    if cacs:
        unprofitable = [c for c, m in data["profitable_since"].items() if m is None]
        if unprofitable:
            print(f"  → CAC payback: {len(unprofitable)} cohort(s) not yet profitable")
        else:
            print("  → CAC payback: every cohort with a CAC value has paid back ✓")


if __name__ == "__main__":
    main()
