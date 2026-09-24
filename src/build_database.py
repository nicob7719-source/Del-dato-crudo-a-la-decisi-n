"""Construye responsible_gambling.duckdb desde cero (Fase 5).

Lee sql/schema.sql, crea las tablas, y las carga desde data/processed/*.csv.
No transforma datos: usa tal cual lo que produjo src/transform.py.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from src.config import DATA_PROCESSED_DIR, PROJECT_ROOT

SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"
DB_PATH = PROJECT_ROOT / "responsible_gambling.duckdb"

TABLE_SOURCES = {
    "dim_period": DATA_PROCESSED_DIR / "dim_period.csv",
    "market_quarterly": DATA_PROCESSED_DIR / "market_quarterly.csv",
    "game_quarterly": DATA_PROCESSED_DIR / "game_quarterly.csv",
}


def build_database(db_path: Path = DB_PATH) -> dict:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"No se encuentra el esquema: {SCHEMA_PATH}")
    for name, path in TABLE_SOURCES.items():
        if not path.exists():
            raise FileNotFoundError(
                f"Falta {path} para cargar '{name}'. Ejecuta antes: python -m src.transform"
            )

    con = duckdb.connect(str(db_path))
    try:
        con.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
        for table, csv_path in TABLE_SOURCES.items():
            con.execute(
                f"INSERT INTO {table} SELECT * FROM read_csv_auto(?, header=True)",
                [str(csv_path)],
            )

        counts = {}
        for table in TABLE_SOURCES:
            counts[table] = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        return counts
    finally:
        con.close()


def main() -> int:
    counts = build_database()
    print(f"Base construida en {DB_PATH}")
    for table, n in counts.items():
        print(f"  {table}: {n} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
