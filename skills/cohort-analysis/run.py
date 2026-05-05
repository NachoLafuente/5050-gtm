"""Cohort analysis runner. Asks 3 questions worth of CLI args, pulls from CRM
+ money source, joins, writes a cohort table."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from cohort import build_matrix
from output import write_csv, write_evidence, write_sql
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
    p = argparse.ArgumentParser()
    p.add_argument("--crm", choices=["attio", "stripe", "csv"], required=False)
    p.add_argument("--money", choices=["stripe", "attio", "csv"], required=False)
    p.add_argument("--output", choices=["csv", "sql", "evidence"], default="csv")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--attio-object", default="companies")
    p.add_argument("--attio-amount-attr", default=None)
    p.add_argument("--attio-date-paid-attr", default=None)
    p.add_argument("--attio-date-churned-attr", default=None)
    p.add_argument("--csv-customers", default=None)
    p.add_argument("--csv-revenue", default=None)
    p.add_argument("--metric", choices=["revenue", "count"], default="revenue")
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

    out_dir = Path(args.out_dir or f"/tmp/cohort-{datetime.now():%Y-%m-%d-%H%M%S}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Pulling customers from {args.crm}...")
    customers = pull_customers(args)
    print(f"  {len(customers)} customers")

    print(f"Pulling revenue from {args.money}...")
    revenue = pull_revenue(args)
    print(f"  {len(revenue)} revenue events")

    matrix, meta = build_matrix(
        customers=customers,
        revenue=revenue,
        metric=args.metric,
        grain=args.cohort_grain,
    )

    write_csv(out_dir, matrix, customers, revenue)
    if args.output == "sql":
        write_sql(out_dir, matrix, customers, revenue)
    elif args.output == "evidence":
        write_evidence(out_dir, matrix, customers, revenue)

    print()
    print(f"Done. {meta['n_customers']} customers, {meta['n_events']} events, "
          f"{meta['n_cohorts']} cohorts.")
    print(f"  → {out_dir}/cohort_table.csv")
    if meta.get("highlight"):
        print(f"  → {meta['highlight']}")


if __name__ == "__main__":
    main()
