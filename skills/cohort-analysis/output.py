"""Output writers — styled xlsx workbook + per-section CSVs + audit trail.

Optional: SQL DDL dump, DuckDB + Evidence scaffold.
"""

from __future__ import annotations

import csv
from pathlib import Path


# Friendly filename per table key
_TABLE_FILENAMES = {
    "retained_customers":            "01_retained_customers.csv",
    "churned_customers":             "02_churned_customers.csv",
    "pct_retained_customers":        "03_pct_retained_customers.csv",
    "pct_churned_vs_base_customers": "04_pct_churned_vs_base_customers.csv",
    "pct_churned_vs_prev_customers": "05_pct_churned_vs_prev_customers.csv",
    "retained_mrr":                  "06_retained_mrr.csv",
    "churned_mrr":                   "07_churned_mrr.csv",
    "pct_retained_mrr":              "08_pct_retained_mrr_NRR.csv",
    "pct_churned_vs_base_mrr":       "09_pct_mrr_churn_vs_base.csv",
    "pct_churned_vs_prev_mrr":       "10_pct_mrr_churn_vs_prev.csv",
    "cumulative_gross_profit":       "11_cac_payback_cumulative_gross_profit.csv",
}


def _write_table_csv(path: Path, table: dict, cohorts: list, max_lt: int):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cohort"] + [f"M{lt}" for lt in range(max_lt + 1)])
        for cohort in cohorts:
            row_data = table.get(cohort, {})
            w.writerow([cohort] + [row_data.get(lt, "") for lt in range(max_lt + 1)])


def write_cohort_csvs(out_dir: Path, data: dict):
    """Write 11 sub-table CSVs (one per cohort metric)."""
    cohorts = data["cohorts"]
    max_lt = data["global_max_lt"]
    for key, filename in _TABLE_FILENAMES.items():
        _write_table_csv(out_dir / filename, data["tables"][key], cohorts, max_lt)

    # Headline cohort_table.csv = retained MRR (the most familiar shape)
    _write_table_csv(out_dir / "cohort_table.csv", data["tables"]["retained_mrr"], cohorts, max_lt)

    # Summary CSV — base counts, base MRR, profitable_since, CAC
    with (out_dir / "00_summary.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cohort", "n_customers_base", "cohort_mrr_base",
                    "cac", "profitable_since", "max_observable_lt"])
        for c in cohorts:
            since = data["profitable_since"].get(c)
            w.writerow([
                c,
                data["n_customers_base"][c],
                round(data["cohort_mrr_base"][c], 2),
                round(data["cacs"].get(c, 0), 2) if data["cacs"] else "",
                f"M{since}" if since is not None else ("Not yet profitable" if data["cacs"] else ""),
                data["max_observable_lt"][c],
            ])


def write_audit(out_dir: Path, customers: list, revenue: list):
    """Audit trail — what got included as input."""
    with (out_dir / "audit_customers.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["customer_id", "email", "domain", "name", "signup_date"]
        )
        w.writeheader()
        for c in customers:
            w.writerow({k: c.get(k, "") for k in w.fieldnames})

    with (out_dir / "audit_revenue.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["customer_id", "email", "event_date", "amount", "currency"]
        )
        w.writeheader()
        for r in revenue:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})


def write_xlsx(out_dir: Path, data: dict):
    """Write the styled .xlsx workbook with conditional formatting."""
    from xlsx_writer import write_cohort_workbook
    write_cohort_workbook(out_dir / "cohort_workbook.xlsx", data)


def write_sql(out_dir: Path, data: dict, customers: list, revenue: list):
    """Dump everything as SQL DDL + INSERTs."""
    sql_path = out_dir / "cohort.sql"
    cohorts = data["cohorts"]
    max_lt = data["global_max_lt"]

    lines = [
        "-- Cohort analysis — DDL + data. Run in any SQL engine.",
        "DROP TABLE IF EXISTS customers;",
        "DROP TABLE IF EXISTS revenue;",
        "DROP TABLE IF EXISTS cohort_metrics;",
        "",
        "CREATE TABLE customers (",
        "  customer_id TEXT PRIMARY KEY,",
        "  email TEXT, domain TEXT, name TEXT, signup_date DATE",
        ");",
        "",
        "CREATE TABLE revenue (",
        "  customer_id TEXT, email TEXT, event_date DATE,",
        "  amount NUMERIC, currency TEXT",
        ");",
        "",
        "CREATE TABLE cohort_metrics (",
        "  cohort TEXT, lifetime_month INT, metric TEXT, value NUMERIC,",
        "  PRIMARY KEY (cohort, lifetime_month, metric)",
        ");",
        "",
    ]

    for c in customers:
        lines.append(
            "INSERT INTO customers VALUES ({}, {}, {}, {}, {});".format(
                _sql(c.get("customer_id")), _sql(c.get("email")),
                _sql(c.get("domain")), _sql(c.get("name")),
                _sql(c.get("signup_date")),
            )
        )
    for r in revenue:
        lines.append(
            "INSERT INTO revenue VALUES ({}, {}, {}, {}, {});".format(
                _sql(r.get("customer_id")), _sql(r.get("email")),
                _sql(r.get("event_date")), r.get("amount") or 0,
                _sql(r.get("currency")),
            )
        )

    for metric_key in _TABLE_FILENAMES.keys():
        table = data["tables"][metric_key]
        for cohort in cohorts:
            for lt in range(max_lt + 1):
                v = table.get(cohort, {}).get(lt)
                if v is None:
                    continue
                lines.append(
                    "INSERT INTO cohort_metrics VALUES ({}, {}, {}, {});".format(
                        _sql(cohort), lt, _sql(metric_key), v
                    )
                )

    sql_path.write_text("\n".join(lines) + "\n")


def _sql(v) -> str:
    if v is None or v == "":
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def write_evidence(out_dir: Path, data: dict, customers: list, revenue: list):
    """DuckDB file + Evidence project scaffold."""
    import duckdb

    db_path = out_dir / "cohort.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("""
        CREATE TABLE customers (
            customer_id TEXT, email TEXT, domain TEXT,
            name TEXT, signup_date DATE
        );
        CREATE TABLE revenue (
            customer_id TEXT, email TEXT, event_date DATE,
            amount DOUBLE, currency TEXT
        );
        CREATE TABLE cohort_metrics (
            cohort TEXT, lifetime_month INT, metric TEXT, value DOUBLE
        );
    """)
    con.executemany(
        "INSERT INTO customers VALUES (?, ?, ?, ?, ?)",
        [(c.get("customer_id"), c.get("email"), c.get("domain"),
          c.get("name"), c.get("signup_date")) for c in customers],
    )
    con.executemany(
        "INSERT INTO revenue VALUES (?, ?, ?, ?, ?)",
        [(r.get("customer_id"), r.get("email"), r.get("event_date"),
          float(r.get("amount") or 0), r.get("currency")) for r in revenue],
    )
    rows = []
    for metric_key in _TABLE_FILENAMES.keys():
        table = data["tables"][metric_key]
        for cohort in data["cohorts"]:
            for lt, v in table.get(cohort, {}).items():
                rows.append((cohort, lt, metric_key, float(v)))
    con.executemany("INSERT INTO cohort_metrics VALUES (?, ?, ?, ?)", rows)
    con.close()

    ev_dir = out_dir / "evidence"
    pages = ev_dir / "pages"
    sources = ev_dir / "sources" / "cohort"
    pages.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)

    (ev_dir / "package.json").write_text(
        '{\n  "name": "cohort-dashboard",\n  "scripts": {\n'
        '    "dev": "evidence dev",\n    "build": "evidence build"\n  },\n'
        '  "devDependencies": { "@evidence-dev/evidence": "latest", '
        '"@evidence-dev/duckdb": "latest" }\n}\n'
    )
    (sources / "connection.yaml").write_text(
        "name: cohort\ntype: duckdb\noptions:\n  filename: ../../cohort.duckdb\n"
    )
    (pages / "index.md").write_text(
        "# Cohort Retention\n\n"
        "```sql nrr\nselect cohort, lifetime_month, value\n"
        "from cohort.cohort_metrics where metric = 'pct_retained_mrr'\n"
        "order by cohort, lifetime_month\n```\n\n"
        "<DataTable data={nrr} />\n\n"
        "<LineChart data={nrr} x=lifetime_month y=value series=cohort />\n"
    )
    (ev_dir / "README.md").write_text(
        "# Evidence dashboard\n\n```bash\ncd evidence\nnpm install\nnpm run dev\n```\n"
    )
