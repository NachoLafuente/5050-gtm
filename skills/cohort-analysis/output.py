"""Output writers — CSV (default), SQL, DuckDB+Evidence scaffold."""

from __future__ import annotations

import csv
from pathlib import Path


def _sorted_periods(matrix: dict) -> list[int]:
    periods = set()
    for row in matrix.values():
        periods.update(row.keys())
    return sorted(periods)


def write_csv(out_dir: Path, matrix: dict, customers: list[dict], revenue: list[dict]):
    cohort_path = out_dir / "cohort_table.csv"
    cohorts = sorted(matrix.keys())
    periods = _sorted_periods(matrix)

    with cohort_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cohort"] + [f"M{p}" for p in periods])
        for c in cohorts:
            row = matrix[c]
            w.writerow([c] + [row.get(p, "") for p in periods])

    with (out_dir / "customers.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["customer_id", "email", "domain", "name", "signup_date"]
        )
        w.writeheader()
        for c in customers:
            w.writerow({k: c.get(k, "") for k in w.fieldnames})

    with (out_dir / "revenue.csv").open("w", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["customer_id", "email", "event_date", "amount", "currency"]
        )
        w.writeheader()
        for r in revenue:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})


def write_sql(out_dir: Path, matrix: dict, customers: list[dict], revenue: list[dict]):
    sql_path = out_dir / "cohort.sql"
    lines = [
        "-- Cohort tables (DDL + data). Run in any SQL engine.",
        "DROP TABLE IF EXISTS customers;",
        "DROP TABLE IF EXISTS revenue;",
        "DROP TABLE IF EXISTS cohort_matrix;",
        "",
        "CREATE TABLE customers (",
        "  customer_id TEXT PRIMARY KEY,",
        "  email TEXT,",
        "  domain TEXT,",
        "  name TEXT,",
        "  signup_date DATE",
        ");",
        "",
        "CREATE TABLE revenue (",
        "  customer_id TEXT,",
        "  email TEXT,",
        "  event_date DATE,",
        "  amount NUMERIC,",
        "  currency TEXT",
        ");",
        "",
        "CREATE TABLE cohort_matrix (",
        "  cohort TEXT,",
        "  period_offset INT,",
        "  value NUMERIC,",
        "  PRIMARY KEY (cohort, period_offset)",
        ");",
        "",
    ]

    for c in customers:
        lines.append(
            "INSERT INTO customers VALUES ({}, {}, {}, {}, {});".format(
                _sql(c.get("customer_id")),
                _sql(c.get("email")),
                _sql(c.get("domain")),
                _sql(c.get("name")),
                _sql(c.get("signup_date")),
            )
        )

    for r in revenue:
        lines.append(
            "INSERT INTO revenue VALUES ({}, {}, {}, {}, {});".format(
                _sql(r.get("customer_id")),
                _sql(r.get("email")),
                _sql(r.get("event_date")),
                r.get("amount") or 0,
                _sql(r.get("currency")),
            )
        )

    for cohort_key, row in matrix.items():
        for period, value in row.items():
            lines.append(
                f"INSERT INTO cohort_matrix VALUES ({_sql(cohort_key)}, {period}, {value});"
            )

    sql_path.write_text("\n".join(lines) + "\n")


def _sql(v) -> str:
    if v is None or v == "":
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def write_evidence(out_dir: Path, matrix: dict, customers: list[dict], revenue: list[dict]):
    """Bootstrap a DuckDB file + minimal Evidence project pointing at it."""
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
        CREATE TABLE cohort_matrix (
            cohort TEXT, period_offset INT, value DOUBLE
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
    rows = [(k, p, v) for k, row in matrix.items() for p, v in row.items()]
    con.executemany("INSERT INTO cohort_matrix VALUES (?, ?, ?)", rows)
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
        f"name: cohort\ntype: duckdb\noptions:\n  filename: ../../cohort.duckdb\n"
    )
    (pages / "index.md").write_text(
        "# Cohort Retention\n\n"
        "```sql cohort\nselect * from cohort.cohort_matrix order by cohort, period_offset\n```\n\n"
        "<DataTable data={cohort} />\n\n"
        "<BarChart data={cohort} x=period_offset y=value series=cohort />\n"
    )
    (ev_dir / "README.md").write_text(
        "# Evidence dashboard\n\n"
        "```bash\ncd evidence\nnpm install\nnpm run dev\n```\n\n"
        "Open http://localhost:3000 — DuckDB file lives at ../cohort.duckdb.\n"
    )
