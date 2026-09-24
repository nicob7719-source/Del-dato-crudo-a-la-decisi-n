-- Esquema del modelo canonico (Fase 5).
-- Las columnas y su orden coinciden exactamente con data/processed/*.csv,
-- generado por src/transform.py. Las claves foraneas documentan la relacion
-- conceptual con dim_period aunque DuckDB no bloquea escrituras por ellas
-- del mismo modo que un RDBMS transaccional.

-- Orden de DROP importa: las tablas hijas (FK) deben caer antes que
-- dim_period, o DuckDB rechaza el CREATE OR REPLACE de la tabla padre.
DROP TABLE IF EXISTS market_quarterly;
DROP TABLE IF EXISTS game_quarterly;
DROP TABLE IF EXISTS dim_period;

CREATE TABLE dim_period (
    period_id       VARCHAR PRIMARY KEY,   -- p.ej. '2025-T3'
    period_start    DATE NOT NULL,         -- primer dia del trimestre
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,      -- 1..4
    quarter_label   VARCHAR NOT NULL,      -- p.ej. 'T3 2025'
    period_order    INTEGER NOT NULL       -- orden cronologico 1..n
);

CREATE TABLE market_quarterly (
    period_id                          VARCHAR PRIMARY KEY REFERENCES dim_period(period_id),
    deposits_eur                       DOUBLE,   -- suma trimestral, euros
    withdrawals_eur                    DOUBLE,   -- suma trimestral, euros
    num_deposits_reported               BIGINT,   -- ver num_deposits_reliable
    active_accounts_avg                DOUBLE,   -- PROMEDIO mensual (foto, no acumulable)
    new_accounts                       BIGINT,   -- suma trimestral
    marketing_publicidad_eur           DOUBLE,
    marketing_bonos_eur                DOUBLE,
    marketing_afiliados_eur            DOUBLE,
    marketing_patrocinio_eur           DOUBLE,
    marketing_total_eur                DOUBLE,
    amounts_played_total_eur           DOUBLE,   -- suma de las 17 modalidades
    ggr_total_eur                      DOUBLE,   -- suma de las 17 modalidades
    num_deposits_reliable               BOOLEAN,  -- FALSE desde 2018-01 (ver profiling)
    deposits_per_active_account_eur    DOUBLE,
    ggr_per_active_account_eur         DOUBLE,
    withdrawal_deposit_ratio           DOUBLE,
    marketing_per_new_account_eur      DOUBLE,
    new_account_rate                   DOUBLE
);

CREATE TABLE game_quarterly (
    period_id               VARCHAR REFERENCES dim_period(period_id),
    juego                   VARCHAR,
    cantidades_jugadas_eur  DOUBLE,
    ggr_eur                 DOUBLE,
    ggr_share                DOUBLE,  -- ggr_eur / ggr_total_eur del mismo periodo
    PRIMARY KEY (period_id, juego)
);
