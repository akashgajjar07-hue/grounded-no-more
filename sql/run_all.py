#!/usr/bin/env python
"""Run every planner query in sql/*.sql against data/processed/grounded.duckdb.

Writes sql/results/<query>.csv (one per query). With --update-examples it also rewrites the
"Example output" block of each .sql file (between the <<EXAMPLE>> markers) with the first rows of
the real result, so the comment always shows output that the query actually produced.

The DuckDB file holds views over data/processed/history/*.parquet (SIMULATED v2 history of the
fictional Falcon Hub Airways, weeks 0-103 under the legacy policy P0). If it is missing, run `python scripts/build_history.py` first.

Usage:
    python sql/run_all.py [--update-examples] [--rows N]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
RESULTS = SQL_DIR / "results"
DB = ROOT / "data" / "processed" / "grounded.duckdb"
EXAMPLE_RE = re.compile(r"(-- <<EXAMPLE>>\n)(.*?)(-- <</EXAMPLE>>)", re.S)
ROWS_RE = re.compile(r"^-- Example rows: (\d+)$", re.M)  # optional per-file override of --rows


def query_files() -> list[Path]:
    return sorted(SQL_DIR.glob("[0-9][0-9]_*.sql"))


def connect() -> duckdb.DuckDBPyConnection:
    if not DB.exists():
        raise FileNotFoundError(f"{DB} missing: run `python scripts/build_history.py` first")
    return duckdb.connect(str(DB), read_only=True)


def run_query(con: duckdb.DuckDBPyConnection, path: Path) -> pd.DataFrame:
    rel = con.execute(path.read_text())
    types = [str(d[1]) for d in rel.description]
    df = rel.df()
    # SUM over integers returns HUGEINT, which pandas receives as float64: cast those back to integers.
    for col, t in zip(df.columns, types):
        if t.upper() == "HUGEINT":
            df[col] = df[col].astype("Int64")
    return df


def _example_block(df: pd.DataFrame, rows: int, max_width: int = 260) -> str:
    with pd.option_context("display.width", 400, "display.max_columns", 50):
        text = df.head(rows).to_string(index=False)
    lines = []
    for ln in text.splitlines():
        lines.append("-- " + (ln if len(ln) <= max_width else ln[: max_width - 3] + "..."))
    lines.append(f"-- ({len(df)} row{'s' if len(df) != 1 else ''} in total; full result in sql/results/{df.attrs.get('stem', '')}.csv)")
    return "\n".join(lines) + "\n"


def update_example(path: Path, df: pd.DataFrame, rows: int) -> None:
    df.attrs["stem"] = path.stem
    text = path.read_text()
    m = ROWS_RE.search(text)
    rows = int(m.group(1)) if m else rows
    new = EXAMPLE_RE.sub(lambda m: m.group(1) + _example_block(df, rows) + m.group(3), text, count=1)
    if new != text:
        path.write_text(new)


def run_all(update_examples: bool = False, rows: int = 8) -> dict[str, pd.DataFrame]:
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = {}
    with connect() as con:
        for f in query_files():
            df = run_query(con, f)
            df.to_csv(RESULTS / f"{f.stem}.csv", index=False)
            if update_examples:
                update_example(f, df, rows)
            out[f.stem] = df
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--update-examples", action="store_true", help="rewrite the example-output comment in each .sql")
    ap.add_argument("--rows", type=int, default=8, help="rows shown in each example block (default 8)")
    a = ap.parse_args()
    res = run_all(a.update_examples, a.rows)
    for k, df in res.items():
        print(f"{k:40s} {len(df):4d} rows -> sql/results/{k}.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
