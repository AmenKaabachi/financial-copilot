"""Import generated CSV data into Supabase tables."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database.supabase_client import get_supabase_client

DATASET_FILES = {
    "erp_transactions": BACKEND_DIR.parent / "datasets" / "erp" / "erp_transactions.csv",
    "bank_transactions": BACKEND_DIR.parent / "datasets" / "bank" / "bank_transactions.csv",
    "reconciliations": BACKEND_DIR.parent / "datasets" / "reconciliations" / "reconciliation_results.csv",
    "anomalies": BACKEND_DIR.parent / "datasets" / "reconciliations" / "anomalies.csv",
}

BATCH_SIZE = int(os.getenv("SUPABASE_IMPORT_BATCH_SIZE", "500"))


def _load_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing dataset file: {path}")

    frame = pd.read_csv(path)
    frame = frame.where(pd.notnull(frame), None)
    return frame.to_dict(orient="records")


def _chunk_rows(rows: list[dict], chunk_size: int) -> Iterable[list[dict]]:
    for start in range(0, len(rows), chunk_size):
        yield rows[start : start + chunk_size]


def import_table(table_name: str, csv_path: Path) -> int:
    client = get_supabase_client()
    rows = _load_csv(csv_path)

    for batch in _chunk_rows(rows, BATCH_SIZE):
        client.table(table_name).insert(batch).execute()

    return len(rows)


def main() -> None:
    total_rows = 0

    for table_name, csv_path in DATASET_FILES.items():
        imported_rows = import_table(table_name, csv_path)
        total_rows += imported_rows
        print(f"Imported {imported_rows} rows into {table_name}")

    print(f"Completed import of {total_rows} total rows")


if __name__ == "__main__":
    main()
