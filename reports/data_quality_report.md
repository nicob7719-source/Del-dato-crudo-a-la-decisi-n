# Informe de calidad de datos (Fase 3)

Generado por `src/profile.py` sobre los CSV congelados en `data/raw/`. No se ha modificado ningún archivo raw. Este informe distingue observaciones confirmadas por el propio perfilado de hipótesis pendientes de decisión en la Fase 4.

## `ggr_turnover.csv`

- Dimensiones: 2601 filas × 6 columnas.
- Cobertura temporal: 2013.T1 (Enero 2013) a 2025.T3 (Septiembre 2025).
- Clave candidata evaluada: ['Año', 'Trimestre', 'Mes', 'Juego'] → única (0 duplicados).
- Filas exactamente duplicadas (todas las columnas): 0.
- Columnas numéricas revisadas: Cantidades jugadas, GGR.
- Celdas vacías o no parseables en columnas numéricas: 0.
- Columnas con valores negativos: GGR (88 filas).
- Columnas con racha final de ceros ≥ 6 filas (posible métrica descontinuada, no periodo incompleto puntual): ninguna.
- Observaciones adicionales:
  - Columna categórica 'Juego': 17 valores distintos, mismo número de filas por valor (panel balanceado).

## `deposits_withdrawals.csv`

- Dimensiones: 153 filas × 6 columnas.
- Cobertura temporal: 2013.T1 (Enero 2013) a 2025.T3 (Septiembre 2025).
- Clave candidata evaluada: ['Año', 'Trimestre', 'Mes'] → única (0 duplicados).
- Filas exactamente duplicadas (todas las columnas): 0.
- Columnas numéricas revisadas: Depósitos, Retiradas, Nº de depósitos.
- Celdas vacías o no parseables en columnas numéricas: 0.
- Columnas con valores negativos: ninguna.
- Columnas con racha final de ceros ≥ 6 filas (posible métrica descontinuada, no periodo incompleto puntual): Nº de depósitos (últimas 93 filas = 0).

## `accounts.csv`

- Dimensiones: 153 filas × 5 columnas.
- Cobertura temporal: 2013.T1 (Enero 2013) a 2025.T3 (Septiembre 2025).
- Clave candidata evaluada: ['Año', 'Trimestre', 'Mes'] → única (0 duplicados).
- Filas exactamente duplicadas (todas las columnas): 0.
- Columnas numéricas revisadas: Cuentas activas, Cuentas nuevas.
- Celdas vacías o no parseables en columnas numéricas: 0.
- Columnas con valores negativos: ninguna.
- Columnas con racha final de ceros ≥ 6 filas (posible métrica descontinuada, no periodo incompleto puntual): ninguna.

## `marketing.csv`

- Dimensiones: 153 filas × 8 columnas.
- Cobertura temporal: 2013.T1 (Enero 2013) a 2025.T3 (Septiembre 2025).
- Clave candidata evaluada: ['Año', 'Trimestre', 'Mes'] → única (0 duplicados).
- Filas exactamente duplicadas (todas las columnas): 0.
- Columnas numéricas revisadas: Publicidad, Bonos, Afiliados, Patrocinio, Total Gastos.
- Celdas vacías o no parseables en columnas numéricas: 0.
- Columnas con valores negativos: ninguna.
- Columnas con racha final de ceros ≥ 6 filas (posible métrica descontinuada, no periodo incompleto puntual): ninguna.

## Respuestas a las preguntas de profiling del plan

1. **Granularidad**: mensual en las cuatro fuentes (columna `Mes` con 153 meses, enero 2013 a septiembre 2025). El campo `Trimestre` es una etiqueta derivada del mes, no una granularidad distinta.
2. **Total de mercado vs. detalle por modalidad**: `ggr_turnover` mezcla ambos conceptos en el mismo fichero mediante la columna `Juego` (17 modalidades, cada una con exactamente 153 filas = panel balanceado). No hay fila de tipo "Total"; el total de mercado se obtiene sumando las 17 modalidades por periodo, no leyendo una fila aparte. `deposits_withdrawals`, `accounts` y `marketing` son series de mercado agregado sin desglose por modalidad.
3. **Cuentas activas**: es una fotografía mensual, no una cifra acumulable entre meses (el valor sube y baja mes a mes, no es monótona creciente). Sumarla entre periodos produciría doble conteo de cuentas que estuvieron activas varios meses.
4. **Cambios de nomenclatura**: no se han detectado variantes ortográficas de la columna `Juego` a lo largo de la serie (17 categorías estables, mismo recuento de filas cada una).
5. **Formato decimal**: no se han observado separadores decimales (coma o punto) en ninguna columna numérica de las cuatro fuentes; todos los importes están expresados como enteros. El diccionario oficial de datos de la DGOJ confirma que los importes se expresan en euros; esta interpretación se conserva en el modelo procesado.Hipótesis cerrada.
6. **Filas agregadas que producirían doble conteo**: no detectadas como filas explícitas; el riesgo real de doble conteo está en cómo se agregue `ggr_turnover` por modalidad si además se compara con un total de mercado calculado de forma independiente.
7. **Trimestre más reciente completo**: **sí**. Las cuatro fuentes contienen datos hasta septiembre de 2025, por lo que 2025.T3 incluye sus tres meses completos: julio, agosto y septiembre. `deposits_withdrawals` tiene la columna `Nº de depósitos` en 0 de forma consistente desde enero de 2018 en adelante (93 de 153 filas), lo que indica que la DGOJ dejó de reportar esa métrica concreta, pero esto no implica que el trimestre 2025.T3 esté incompleto.
8. **Coincidencia de fechas y periodos entre fuentes**: sí, las cuatro fuentes comparten exactamente el mismo rango mensual (enero 2013 a septiembre 2025, 153 meses), lo que hace viable un `dim_period` común para el `JOIN` de la Fase 5.

## Propuesta de contrato de datos y transformaciones (Fase 4)

**Confirmado por este perfilado** (hechos, no hipótesis):
- Las cuatro fuentes son mensuales, cubren 2013-01 a 2025-09, sin huecos de mes.
- `ggr_turnover` requiere agregación por periodo (sumar las 17 modalidades) para obtener un GGR de mercado comparable con las otras fuentes.
- `Nº de depósitos` en `deposits_withdrawals` no es utilizable desde 2018 en adelante (siempre 0); no debe usarse en ninguna métrica derivada sin excluir explícitamente ese periodo o descartar la columna.
- No hay duplicados exactos ni de clave candidata en ninguna de las cuatro fuentes.

**Hipótesis pendientes, a decidir en Fase 4:**
- Si `market_quarterly` se construye agregando los 3 meses de cada trimestre (suma para flujos, último mes o promedio para `Cuentas activas` al ser una fotografía) — a decidir explícitamente y documentar la fórmula por métrica.
- 2025.T3 es un trimestre completo; sin embargo, 2025 es un año parcial porque no se dispone de T4, por lo que las comparaciones anuales con años completos deben tratarse con cautela.

## Qué NO se ha hecho en esta fase

- No se han eliminado outliers ni valores negativos (hay 88 filas con GGR negativo en `ggr_turnover`, compatible con periodos donde los premios pagados superaron lo jugado en una modalidad; se documentan, no se tratan como error).
- No se ha convertido ningún valor a NaN de forma silenciosa.
- No se ha realizado ningún `JOIN` entre fuentes todavía.
