-- Consultas de negocio sobre responsible_gambling.duckdb (Fase 5).
-- Cada consulta va precedida de: pregunta respondida, grano del resultado,
-- metricas y unidades, interpretacion permitida, limitacion principal.


-- =====================================================================
-- Consulta 1 — Evolucion anual del mercado (GROUP BY)
-- Pregunta: como evolucionan GGR, depositos y gasto promocional por anio.
-- Grano: una fila por anio.
-- Metricas: GGR, depositos y gasto promocional en EUR (suma anual, son
--   flujos aditivos); cuentas activas como PROMEDIO anual de las medias
--   trimestrales (NO se suma, es una foto, no una cantidad acumulable).
-- Interpretacion permitida: tendencia de intensidad de mercado agregada,
--   no evolucion de personas concretas.
-- Limitacion: 2025 esta incompleto (solo hasta T3). Comparar 2025 con anios
--   completos subestima el total anual real.
-- =====================================================================
SELECT
    dp.year,
    COUNT(*) AS quarters_available,
    SUM(mq.ggr_total_eur) AS ggr_total_eur,
    SUM(mq.deposits_eur) AS deposits_total_eur,
    SUM(mq.marketing_total_eur) AS marketing_total_eur,
    AVG(mq.active_accounts_avg) AS active_accounts_avg_yearly
FROM market_quarterly mq
JOIN dim_period dp ON dp.period_id = mq.period_id
GROUP BY dp.year
ORDER BY dp.year;


-- =====================================================================
-- Consulta 2 — Intensidad por cuenta activa, con dim_period (JOIN + ORDER
--   BY + LIMIT)
-- Pregunta: en que trimestres fue mayor el deposito y el GGR por cuenta
--   activa.
-- Grano: una fila por trimestre.
-- Metricas: deposits_per_active_account_eur, ggr_per_active_account_eur
--   (EUR por cuenta activa promedio del trimestre).
-- Interpretacion permitida: intensidad de gasto normalizada por tamano de
--   la base de cuentas; util para detectar trimestres de mayor exposicion
--   media por cuenta, no gasto de un individuo concreto.
-- Limitacion: "cuenta activa" no es "persona unica" (una persona puede
--   tener mas de una cuenta); el JOIN con dim_period aporta year/quarter
--   legibles, no cambia el grano.
-- =====================================================================
SELECT
    dp.quarter_label,
    dp.year,
    dp.quarter,
    mq.deposits_per_active_account_eur,
    mq.ggr_per_active_account_eur
FROM market_quarterly mq
JOIN dim_period dp ON dp.period_id = mq.period_id
ORDER BY mq.ggr_per_active_account_eur DESC
LIMIT 10;


-- =====================================================================
-- Consulta 3 — Concentracion de GGR por modalidad en el ultimo trimestre
--   disponible (WHERE + ORDER BY + LIMIT)
-- Pregunta: que modalidades concentran mayor GGR y que cuota representan.
-- Grano: una fila por modalidad, para el trimestre mas reciente.
-- Metricas: ggr_eur (EUR), ggr_share (cuota del GGR total de ESE trimestre,
--   recalculada desde importes compatibles, no sumada entre periodos).
-- Interpretacion permitida: composicion del mercado por modalidad en un
--   momento dado.
-- Limitacion: un trimestre no revela tendencia; ver notebook para la serie
--   completa de composicion.
-- =====================================================================
SELECT
    gq.juego,
    gq.ggr_eur,
    ROUND(gq.ggr_share * 100, 2) AS ggr_share_pct
FROM game_quarterly gq
WHERE gq.period_id = (SELECT period_id FROM dim_period ORDER BY period_order DESC LIMIT 1)
ORDER BY gq.ggr_eur DESC
LIMIT 5;


-- =====================================================================
-- Consulta 4 — Marketing, nuevas cuentas y depositos por trimestre
--   (WHERE/HAVING + JOIN funcional con dim_period)
-- Pregunta: que trimestres combinan alto gasto promocional y crecimiento de
--   actividad (nuevas cuentas, depositos).
-- Grano: una fila por trimestre, filtrado a trimestres con gasto
--   promocional por encima de la mediana historica.
-- Metricas: marketing_total_eur, new_accounts, deposits_eur,
--   marketing_per_new_account_eur.
-- Interpretacion permitida: descriptiva. Estos trimestres muestran
--   coincidencia temporal entre gasto y actividad, NO se demuestra que el
--   marketing cause las nuevas cuentas o los depositos.
-- Limitacion: no hay diseno experimental ni control de otras variables;
--   cualquier lectura causal aqui seria un error metodologico.
-- =====================================================================
SELECT
    dp.quarter_label,
    mq.marketing_total_eur,
    mq.new_accounts,
    mq.deposits_eur,
    ROUND(mq.marketing_per_new_account_eur, 2) AS marketing_per_new_account_eur
FROM market_quarterly mq
JOIN dim_period dp ON dp.period_id = mq.period_id
WHERE mq.marketing_total_eur > (SELECT MEDIAN(marketing_total_eur) FROM market_quarterly)
ORDER BY dp.period_order;
