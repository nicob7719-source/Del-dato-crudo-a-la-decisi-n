"""Tests del modelo canonico (src/transform.py) sobre los CSV raw reales.

No hace falta red: usa los CSV ya congelados en data/raw/. Si faltan, se
saltan (el pipeline completo se valida en la Fase 10 desde limpio).
"""
import pytest

from src.config import DATA_RAW_DIR
from src.transform import (
    _assert_schema,
    build_dim_period,
    build_game_quarterly,
    build_market_quarterly,
)

pytestmark = pytest.mark.skipif(
    not (DATA_RAW_DIR / "accounts.csv").exists(),
    reason="Faltan CSV raw; ejecuta antes python -m src.extract",
)


def test_dim_period_has_unique_ordered_periods():
    dim_period = build_dim_period()
    assert dim_period["period_id"].is_unique
    assert (dim_period["period_order"].sort_values().reset_index(drop=True) == dim_period["period_order"]).all()


def test_market_quarterly_has_no_zero_denominators():
    market = build_market_quarterly()
    for col in ["deposits_eur", "active_accounts_avg", "new_accounts"]:
        assert (market[col] > 0).all(), f"'{col}' tiene valores <= 0"


def test_game_quarterly_ggr_share_sums_to_one_per_period():
    market = build_market_quarterly()
    game = build_game_quarterly(market)
    share_sum = game.groupby("period_id")["ggr_share"].sum()
    assert ((share_sum - 1.0).abs() < 0.01).all()


def test_full_schema_assertion_passes_on_real_data():
    dim_period = build_dim_period()
    market = build_market_quarterly()
    game = build_game_quarterly(market)
    assert _assert_schema(dim_period, market, game) == []
