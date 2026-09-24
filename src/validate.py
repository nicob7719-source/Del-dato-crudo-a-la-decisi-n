"""Valida el modelo canonico ya construido en data/processed/ (independiente
de src/transform.py, para poder re-chequear sin re-transformar).

Uso: python -m src.validate
"""
from __future__ import annotations

import pandas as pd

from src.config import DATA_PROCESSED_DIR
from src.transform import _assert_schema


def run_validation() -> None:
    dim_period = pd.read_csv(DATA_PROCESSED_DIR / "dim_period.csv")
    market = pd.read_csv(DATA_PROCESSED_DIR / "market_quarterly.csv")
    game = pd.read_csv(DATA_PROCESSED_DIR / "game_quarterly.csv")

    problems = _assert_schema(dim_period, market, game)
    if problems:
        raise AssertionError(
            "Fallaron las aserciones de calidad del modelo canonico:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )
    print(
        f"OK: dim_period={len(dim_period)} filas, "
        f"market_quarterly={len(market)} filas, game_quarterly={len(game)} filas. "
        "Claves unicas, sin period_id huerfanos, ggr_share~1 por periodo, "
        "sin denominadores <= 0."
    )


def main() -> int:
    run_validation()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
