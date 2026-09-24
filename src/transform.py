"""Transformacion y modelo canonico (Fase 4).

Construye, a partir de los CSV congelados en data/raw/ (solo lectura), tres
tablas procesadas en data/processed/:

- dim_period: una fila por trimestre, para el JOIN de la Fase 5.
- market_quarterly: una fila por trimestre, metricas de mercado agregadas.
- game_quarterly: una fila por trimestre y modalidad de juego.

Decisiones de agregacion mensual -> trimestral (justificadas en el docstring
de cada funcion, no asumidas en silencio):

- Metricas de flujo (depositos, retiradas, GGR, cantidades jugadas, gasto
  promocional, cuentas nuevas): SUMA de los 3 meses del trimestre.
- Cuentas activas (foto mensual, no acumulable): PROMEDIO de los 3 meses del
  trimestre, no suma. Ver profiling (Fase 3): el valor mensual sube y baja,
  sumarlo infla el numero de cuentas distintas.
- "Nº de depositos": queda en la tabla pero SIN usarse en ninguna metrica
  derivada, porque el perfilado (Fase 3) confirmo que esta en 0 de forma
  consistente desde 2018-01 (DGOJ dejo de reportarla). Usarla en un ratio
  produciria una metrica falsa para 93 de 153 meses.
"""
from __future__ import annotations

import pandas as pd

from src.config import DATA_PROCESSED_DIR, DATA_RAW_DIR

MONTH_ORDER = {
    m: i for i, m in enumerate(
        ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], start=1
    )
}

DIM_PERIOD_PATH = DATA_PROCESSED_DIR / "dim_period.csv"
MARKET_QUARTERLY_PATH = DATA_PROCESSED_DIR / "market_quarterly.csv"
GAME_QUARTERLY_PATH = DATA_PROCESSED_DIR / "game_quarterly.csv"


def _read_raw(name: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_RAW_DIR / f"{name}.csv", sep=";", encoding="utf-8-sig")
    df["_month_num"] = df["Mes"].map(MONTH_ORDER)
    if df["_month_num"].isna().any():
        bad = df.loc[df["_month_num"].isna(), "Mes"].unique()
        raise ValueError(f"Nombres de mes no reconocidos en {name}: {bad}")
    df["quarter_num"] = df["Trimestre"].str.extract(r"T(\d)").astype(int)
    df["period_id"] = df["Año"].astype(str) + "-T" + df["quarter_num"].astype(str)
    return df


def build_dim_period() -> pd.DataFrame:
    """Una fila por trimestre presente en los datos, con orden cronologico."""
    acc = _read_raw("accounts")
    periods = acc[["Año", "quarter_num", "period_id"]].drop_duplicates()
    periods = periods.rename(columns={"Año": "year", "quarter_num": "quarter"})
    periods["period_start"] = pd.to_datetime(
        periods["year"].astype(str) + "-" + ((periods["quarter"] - 1) * 3 + 1).astype(str) + "-01"
    )
    periods["quarter_label"] = "T" + periods["quarter"].astype(str) + " " + periods["year"].astype(str)
    periods = periods.sort_values("period_start").reset_index(drop=True)
    periods["period_order"] = periods.index + 1
    return periods[["period_id", "period_start", "year", "quarter", "quarter_label", "period_order"]]


def build_market_quarterly() -> pd.DataFrame:
    dep = _read_raw("deposits_withdrawals")
    acc = _read_raw("accounts")
    mkt = _read_raw("marketing")
    ggr = _read_raw("ggr_turnover")

    dep_q = dep.groupby("period_id", as_index=False).agg(
        deposits_eur=("Depósitos", "sum"),
        withdrawals_eur=("Retiradas", "sum"),
        num_deposits_reported=("Nº de depósitos", "sum"),
    )

    acc_q = acc.groupby("period_id", as_index=False).agg(
        active_accounts_avg=("Cuentas activas", "mean"),
        new_accounts=("Cuentas nuevas", "sum"),
    )

    mkt_q = mkt.groupby("period_id", as_index=False).agg(
        marketing_publicidad_eur=("Publicidad", "sum"),
        marketing_bonos_eur=("Bonos", "sum"),
        marketing_afiliados_eur=("Afiliados", "sum"),
        marketing_patrocinio_eur=("Patrocinio", "sum"),
        marketing_total_eur=("Total Gastos", "sum"),
    )

    ggr_q = ggr.groupby("period_id", as_index=False).agg(
        amounts_played_total_eur=("Cantidades jugadas", "sum"),
        ggr_total_eur=("GGR", "sum"),
    )

    market = dep_q.merge(acc_q, on="period_id").merge(mkt_q, on="period_id").merge(ggr_q, on="period_id")

    # Nº de depositos no es fiable desde 2018-01 (ver profiling); se marca
    # explicitamente en vez de dejar que un consumidor lo use por error.
    market["num_deposits_reliable"] = ~market["period_id"].isin(
        dep.loc[dep["Año"] >= 2018, "period_id"].unique()
    )

    # --- Metricas derivadas, solo con denominadores validados (Fase 3: sin
    # ceros en depositos, cuentas activas ni cuentas nuevas) ---
    market["deposits_per_active_account_eur"] = market["deposits_eur"] / market["active_accounts_avg"]
    market["ggr_per_active_account_eur"] = market["ggr_total_eur"] / market["active_accounts_avg"]
    market["withdrawal_deposit_ratio"] = market["withdrawals_eur"] / market["deposits_eur"]
    market["marketing_per_new_account_eur"] = market["marketing_total_eur"] / market["new_accounts"]
    market["new_account_rate"] = market["new_accounts"] / market["active_accounts_avg"]

    return market.sort_values("period_id").reset_index(drop=True)


def build_game_quarterly(market: pd.DataFrame) -> pd.DataFrame:
    ggr = _read_raw("ggr_turnover")
    game_q = ggr.groupby(["period_id", "Juego"], as_index=False).agg(
        cantidades_jugadas_eur=("Cantidades jugadas", "sum"),
        ggr_eur=("GGR", "sum"),
    ).rename(columns={"Juego": "juego"})

    game_q = game_q.merge(
        market[["period_id", "ggr_total_eur"]], on="period_id", how="left"
    )
    # cuota recalculada desde importes compatibles del mismo periodo, no
    # sumando cuotas de distintos periodos.
    game_q["ggr_share"] = game_q["ggr_eur"] / game_q["ggr_total_eur"]
    return game_q.drop(columns=["ggr_total_eur"]).sort_values(["period_id", "juego"]).reset_index(drop=True)


def _assert_schema(dim_period: pd.DataFrame, market: pd.DataFrame, game: pd.DataFrame) -> list[str]:
    problems = []

    if dim_period["period_id"].isna().any():
        problems.append("dim_period: hay period_id nulos.")
    if dim_period["period_id"].duplicated().any():
        problems.append("dim_period: period_id no es unico.")

    if market["period_id"].duplicated().any():
        problems.append("market_quarterly: period_id no es unico.")
    if not set(market["period_id"]).issubset(set(dim_period["period_id"])):
        problems.append("market_quarterly: hay period_id que no existen en dim_period.")

    if game.duplicated(subset=["period_id", "juego"]).any():
        problems.append("game_quarterly: la clave (period_id, juego) no es unica.")
    if not set(game["period_id"]).issubset(set(dim_period["period_id"])):
        problems.append("game_quarterly: hay period_id que no existen en dim_period.")

    share_sum = game.groupby("period_id")["ggr_share"].sum()
    bad_shares = share_sum[(share_sum - 1.0).abs() > 0.01]
    if not bad_shares.empty:
        problems.append(
            f"game_quarterly: {len(bad_shares)} periodos con ggr_share que no suma ~1 "
            f"(tolerancia 0.01): {bad_shares.index.tolist()[:5]}"
        )

    for col in ["deposits_eur", "active_accounts_avg", "new_accounts"]:
        if (market[col] <= 0).any():
            problems.append(f"market_quarterly: '{col}' tiene valores <= 0 (denominador invalido).")

    return problems


def run_transform() -> dict:
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    dim_period = build_dim_period()
    market = build_market_quarterly()
    game = build_game_quarterly(market)

    problems = _assert_schema(dim_period, market, game)
    if problems:
        raise AssertionError(
            "Fallaron las aserciones de calidad del modelo canonico:\n"
            + "\n".join(f"  - {p}" for p in problems)
        )

    dim_period.to_csv(DIM_PERIOD_PATH, index=False, encoding="utf-8")
    market.to_csv(MARKET_QUARTERLY_PATH, index=False, encoding="utf-8")
    game.to_csv(GAME_QUARTERLY_PATH, index=False, encoding="utf-8")

    before_after = {
        "dim_period": {"rows": len(dim_period), "cols": dim_period.shape[1]},
        "market_quarterly": {
            "rows": len(market), "cols": market.shape[1],
            "nulls": int(market.isna().sum().sum()),
        },
        "game_quarterly": {
            "rows": len(game), "cols": game.shape[1],
            "nulls": int(game.isna().sum().sum()),
        },
        "raw_months_ggr_turnover": 2601,
        "raw_months_market_sources": 153,
    }
    return before_after


def main() -> int:
    summary = run_transform()
    print("Modelo canonico construido sin errores de aserciones.")
    for table, stats in summary.items():
        print(f"  {table}: {stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
