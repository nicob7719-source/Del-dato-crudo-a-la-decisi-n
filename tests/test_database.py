"""Tests de integridad de la base DuckDB (Fase 5).

Se ejecutan contra una copia temporal de la base para no interferir con
responsible_gambling.duckdb usado por el notebook.
"""
from pathlib import Path

import duckdb
import pytest

from src.build_database import build_database
from src.config import DATA_PROCESSED_DIR


@pytest.fixture(scope="module")
def db_path(tmp_path_factory):
    if not (DATA_PROCESSED_DIR / "market_quarterly.csv").exists():
        pytest.skip("Faltan datos procesados; ejecuta antes python -m src.transform")
    path = tmp_path_factory.mktemp("db") / "test.duckdb"
    build_database(db_path=path)
    return path


def test_tables_exist(db_path):
    con = duckdb.connect(str(db_path), read_only=True)
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    con.close()
    assert {"dim_period", "market_quarterly", "game_quarterly"}.issubset(tables)


def test_dim_period_key_is_unique(db_path):
    con = duckdb.connect(str(db_path), read_only=True)
    total, distinct = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT period_id) FROM dim_period"
    ).fetchone()
    con.close()
    assert total == distinct
    assert total > 0


def test_market_quarterly_join_dim_period(db_path):
    con = duckdb.connect(str(db_path), read_only=True)
    orphan_count = con.execute(
        "SELECT COUNT(*) FROM market_quarterly mq "
        "LEFT JOIN dim_period dp ON dp.period_id = mq.period_id "
        "WHERE dp.period_id IS NULL"
    ).fetchone()[0]
    con.close()
    assert orphan_count == 0


def test_game_quarterly_ggr_share_sums_to_one_per_period(db_path):
    con = duckdb.connect(str(db_path), read_only=True)
    bad_periods = con.execute(
        "SELECT period_id, SUM(ggr_share) AS s FROM game_quarterly "
        "GROUP BY period_id HAVING ABS(SUM(ggr_share) - 1.0) > 0.01"
    ).fetchall()
    con.close()
    assert bad_periods == []


def test_no_negative_deposits_or_active_accounts(db_path):
    con = duckdb.connect(str(db_path), read_only=True)
    bad = con.execute(
        "SELECT COUNT(*) FROM market_quarterly "
        "WHERE deposits_eur <= 0 OR active_accounts_avg <= 0"
    ).fetchone()[0]
    con.close()
    assert bad == 0


def test_analysis_queries_run_and_return_rows(db_path):
    project_root = Path(__file__).resolve().parent.parent
    sql_text = (project_root / "sql" / "analysis.sql").read_text(encoding="utf-8")
    code_lines = [line for line in sql_text.splitlines() if not line.strip().startswith("--")]
    statements = [s.strip() for s in "\n".join(code_lines).split(";") if s.strip()]

    assert len(statements) == 4, "Se esperan exactamente 4 consultas en sql/analysis.sql"

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for stmt in statements:
            df = con.execute(stmt).fetchdf()
            assert len(df) > 0
    finally:
        con.close()
