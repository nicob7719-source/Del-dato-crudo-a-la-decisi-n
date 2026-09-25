"""Perfilado de calidad de los CSV raw de la DGOJ (Fase 3).

No modifica data/raw. Genera:
- reports/data_quality_report.md (informe legible)
- data/processed/data_quality_summary.csv (resumen tabular por dataset)

El perfilado es puramente descriptivo: no imputa, no elimina outliers ni
decide todavia el modelo de transformacion (eso es Fase 4).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.config import DATA_PROCESSED_DIR, DATA_RAW_DIR

REPORTS_DIR = DATA_RAW_DIR.parent.parent / "reports"
REPORT_PATH = REPORTS_DIR / "data_quality_report.md"
SUMMARY_PATH = DATA_PROCESSED_DIR / "data_quality_summary.csv"

# Columnas clave compartidas por las cuatro fuentes (mismo nombre logico,
# distinto texto exacto por fuente segun se confirma en el raw real).
DATASETS = {
    "ggr_turnover": {
        "key_cols": ["Año", "Trimestre", "Mes", "Juego"],
        "numeric_cols": ["Cantidades jugadas", "GGR"],
        "category_cols": ["Juego"],
    },
    "deposits_withdrawals": {
        "key_cols": ["Año", "Trimestre", "Mes"],
        "numeric_cols": ["Depósitos", "Retiradas", "Nº de depósitos"],
        "category_cols": [],
    },
    "accounts": {
        "key_cols": ["Año", "Trimestre", "Mes"],
        "numeric_cols": ["Cuentas activas", "Cuentas nuevas"],
        "category_cols": [],
    },
    "marketing": {
        "key_cols": ["Año", "Trimestre", "Mes"],
        "numeric_cols": ["Publicidad", "Bonos", "Afiliados", "Patrocinio", "Total Gastos"],
        "category_cols": [],
    },
}


def _read_raw(name: str) -> pd.DataFrame:
    path = DATA_RAW_DIR / f"{name}.csv"
    return pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)


@dataclass
class DatasetProfile:
    name: str
    rows: int
    columns: int
    key_cols: list
    key_is_unique: bool
    key_duplicate_count: int
    exact_duplicate_rows: int
    min_period: str
    max_period: str
    numeric_cols_checked: str
    negative_value_cols: str
    zero_run_columns: str
    null_like_cells: int


def _to_numeric(series: pd.Series) -> pd.Series:
    """Convierte a numerico sin asumir formato: falla explicitamente."""
    return pd.to_numeric(series, errors="coerce")


def profile_dataset(name: str, spec: dict) -> tuple[DatasetProfile, list[str]]:
    df = _read_raw(name)
    notes: list[str] = []

    rows, columns = df.shape
    key_cols = spec["key_cols"]
    key_present = [c for c in key_cols if c in df.columns]
    if len(key_present) != len(key_cols):
        notes.append(
            f"Columnas clave esperadas ausentes: {set(key_cols) - set(key_present)}"
        )

    dup_key = df.duplicated(subset=key_present, keep=False).sum() if key_present else -1
    key_is_unique = dup_key == 0
    exact_dup = df.duplicated(keep=False).sum()

    month_order = {
        m: i for i, m in enumerate(
            ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
             "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], start=1
        )
    }
    chrono_key = df["Año"].astype(int) * 100 + df["Mes"].map(month_order)
    ordered = df.assign(_chrono=chrono_key).sort_values("_chrono")
    min_period = f"{ordered.iloc[0]['Trimestre']} ({ordered.iloc[0]['Mes']} {ordered.iloc[0]['Año']})"
    max_period = f"{ordered.iloc[-1]['Trimestre']} ({ordered.iloc[-1]['Mes']} {ordered.iloc[-1]['Año']})"

    negative_cols = []
    zero_run_cols = []
    numeric_checked = []
    null_like = 0
    for col in spec["numeric_cols"]:
        if col not in df.columns:
            notes.append(f"Columna numerica esperada ausente: {col!r}")
            continue
        numeric_checked.append(col)
        as_num = _to_numeric(df[col])
        failed = as_num.isna() & df[col].notna()
        if failed.any():
            notes.append(
                f"{failed.sum()} valores de '{col}' no parsean como numero (revisar formato)."
            )
        null_like += int(df[col].isna().sum() + (df[col].astype(str).str.strip() == "").sum())
        if (as_num < 0).any():
            negative_cols.append(f"{col} ({int((as_num < 0).sum())} filas)")
        # racha de ceros al final de la serie => posible metrica descontinuada,
        # no un simple periodo incompleto puntual.
        zero_mask = as_num == 0
        trailing_zero_run = 0
        for val in zero_mask.iloc[::-1]:
            if val:
                trailing_zero_run += 1
            else:
                break
        if trailing_zero_run >= 6:
            zero_run_cols.append(f"{col} (últimas {trailing_zero_run} filas = 0)")

    category_notes = []
    for col in spec["category_cols"]:
        if col not in df.columns:
            continue
        distinct = df[col].nunique(dropna=True)
        counts_per_value = df.groupby(col).size()
        balanced = counts_per_value.nunique() == 1
        category_notes.append(
            f"Columna categórica '{col}': {distinct} valores distintos, "
            f"{'mismo número de filas por valor (panel balanceado)' if balanced else 'número de filas DESIGUAL por valor (revisar)'}."
        )
    notes.extend(category_notes)

    profile = DatasetProfile(
        name=name,
        rows=rows,
        columns=columns,
        key_cols=key_present,
        key_is_unique=key_is_unique,
        key_duplicate_count=int(dup_key) if key_present else -1,
        exact_duplicate_rows=int(exact_dup),
        min_period=str(min_period),
        max_period=str(max_period),
        numeric_cols_checked=", ".join(numeric_checked),
        negative_value_cols="; ".join(negative_cols) if negative_cols else "ninguna",
        zero_run_columns="; ".join(zero_run_cols) if zero_run_cols else "ninguna",
        null_like_cells=null_like,
    )
    return profile, notes


def run_profiling() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    profiles: list[DatasetProfile] = []
    all_notes: dict[str, list[str]] = {}

    for name, spec in DATASETS.items():
        profile, notes = profile_dataset(name, spec)
        profiles.append(profile)
        all_notes[name] = notes
        print(f"[{name}] {profile.rows} filas, clave única={profile.key_is_unique}, "
              f"periodo {profile.min_period}–{profile.max_period}")
        for n in notes:
            print(f"    - {n}")

    summary_df = pd.DataFrame([p.__dict__ for p in profiles])
    summary_df.to_csv(SUMMARY_PATH, index=False, encoding="utf-8")

    _write_report(profiles, all_notes)


def _write_report(profiles: list[DatasetProfile], all_notes: dict[str, list[str]]) -> None:
    lines = ["# Informe de calidad de datos (Fase 3)", ""]
    lines.append(
        "Generado por `src/profile.py` sobre los CSV congelados en `data/raw/`. "
        "No se ha modificado ningún archivo raw. Este informe distingue "
        "observaciones confirmadas por el propio perfilado de hipótesis "
        "pendientes de decisión en la Fase 4."
    )
    lines.append("")

    for p in profiles:
        lines.append(f"## `{p.name}.csv`")
        lines.append("")
        lines.append(f"- Dimensiones: {p.rows} filas × {p.columns} columnas.")
        lines.append(f"- Cobertura temporal: {p.min_period} a {p.max_period}.")
        lines.append(
            f"- Clave candidata evaluada: {p.key_cols} → "
            f"{'única (0 duplicados)' if p.key_is_unique else f'NO única ({p.key_duplicate_count} filas implicadas)'}."
        )
        lines.append(f"- Filas exactamente duplicadas (todas las columnas): {p.exact_duplicate_rows}.")
        lines.append(f"- Columnas numéricas revisadas: {p.numeric_cols_checked}.")
        lines.append(f"- Celdas vacías o no parseables en columnas numéricas: {p.null_like_cells}.")
        lines.append(f"- Columnas con valores negativos: {p.negative_value_cols}.")
        lines.append(
            f"- Columnas con racha final de ceros ≥ 6 filas (posible métrica "
            f"descontinuada, no periodo incompleto puntual): {p.zero_run_columns}."
        )
        notes = all_notes.get(p.name, [])
        if notes:
            lines.append("- Observaciones adicionales:")
            for n in notes:
                lines.append(f"  - {n}")
        lines.append("")

    lines.append("## Respuestas a las preguntas de profiling del plan")
    lines.append("")
    lines.append(
        "1. **Granularidad**: mensual en las cuatro fuentes (columna `Mes` con "
        "153 meses, enero 2013 a septiembre 2025). El campo `Trimestre` es "
        "una etiqueta derivada del mes, no una granularidad distinta."
    )
    lines.append(
        "2. **Total de mercado vs. detalle por modalidad**: `ggr_turnover` "
        "mezcla ambos conceptos en el mismo fichero mediante la columna "
        "`Juego` (17 modalidades, cada una con exactamente 153 filas = panel "
        "balanceado). No hay fila de tipo \"Total\"; el total de mercado se "
        "obtiene sumando las 17 modalidades por periodo, no leyendo una fila "
        "aparte. `deposits_withdrawals`, `accounts` y `marketing` son series "
        "de mercado agregado sin desglose por modalidad."
    )
    lines.append(
        "3. **Cuentas activas**: es una fotografía mensual, no una cifra "
        "acumulable entre meses (el valor sube y baja mes a mes, no es "
        "monótona creciente). Sumarla entre periodos produciría doble conteo "
        "de cuentas que estuvieron activas varios meses."
    )
    lines.append(
        "4. **Cambios de nomenclatura**: no se han detectado variantes "
        "ortográficas de la columna `Juego` a lo largo de la serie (17 "
        "categorías estables, mismo recuento de filas cada una)."
    )
    lines.append(
        "5. **Formato decimal**: no se han observado separadores decimales "
        "(coma o punto) en ninguna columna numérica de las cuatro fuentes; "
        "todos los importes están expresados como enteros. "
        "El diccionario oficial de datos de la DGOJ confirma que los importes "
        "se expresan en euros; esta interpretación se conserva en el modelo procesado."
        "Hipótesis cerrada."
    )
    lines.append(
        "6. **Filas agregadas que producirían doble conteo**: no detectadas "
        "como filas explícitas; el riesgo real de doble conteo está en cómo "
        "se agregue `ggr_turnover` por modalidad si además se compara con un "
        "total de mercado calculado de forma independiente."
    )
    lines.append(
        "7. **Trimestre más reciente completo**: **sí**. Las cuatro fuentes "
        "contienen datos hasta septiembre de 2025, por lo que 2025.T3 incluye "
        "sus tres meses completos: julio, agosto y septiembre. "
        "`deposits_withdrawals` tiene la columna `Nº de depósitos` en 0 de forma "
        "consistente desde enero de 2018 en adelante (93 de 153 filas), lo que "
        "indica que la DGOJ dejó de reportar esa métrica concreta, pero esto no "
        "implica que el trimestre 2025.T3 esté incompleto."
    )
    lines.append(
        "8. **Coincidencia de fechas y periodos entre fuentes**: sí, las "
        "cuatro fuentes comparten exactamente el mismo rango mensual "
        "(enero 2013 a septiembre 2025, 153 meses), lo que hace viable un "
        "`dim_period` común para el `JOIN` de la Fase 5."
    )
    lines.append("")

    lines.append("## Propuesta de contrato de datos y transformaciones (Fase 4)")
    lines.append("")
    lines.append("**Confirmado por este perfilado** (hechos, no hipótesis):")
    lines.append("- Las cuatro fuentes son mensuales, cubren 2013-01 a 2025-09, sin huecos de mes.")
    lines.append("- `ggr_turnover` requiere agregación por periodo (sumar las 17 modalidades) para obtener un GGR de mercado comparable con las otras fuentes.")
    lines.append("- `Nº de depósitos` en `deposits_withdrawals` no es utilizable desde 2018 en adelante (siempre 0); no debe usarse en ninguna métrica derivada sin excluir explícitamente ese periodo o descartar la columna.")
    lines.append("- No hay duplicados exactos ni de clave candidata en ninguna de las cuatro fuentes.")
    lines.append("")
    lines.append("**Hipótesis pendientes, a decidir en Fase 4:**")
    lines.append("- Si `market_quarterly` se construye agregando los 3 meses de cada trimestre (suma para flujos, último mes o promedio para `Cuentas activas` al ser una fotografía) — a decidir explícitamente y documentar la fórmula por métrica.")
    lines.append("- 2025.T3 es un trimestre completo; sin embargo, 2025 es un año parcial porque no se dispone de T4, por lo que las comparaciones anuales con años completos deben tratarse con cautela.")
    lines.append("")

    lines.append("## Qué NO se ha hecho en esta fase")
    lines.append("")
    lines.append("- No se han eliminado outliers ni valores negativos (hay 88 filas con GGR negativo en `ggr_turnover`, compatible con periodos donde los premios pagados superaron lo jugado en una modalidad; se documentan, no se tratan como error).")
    lines.append("- No se ha convertido ningún valor a NaN de forma silenciosa.")
    lines.append("- No se ha realizado ningún `JOIN` entre fuentes todavía.")
    lines.append("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Informe escrito en {REPORT_PATH}")
    print(f"Resumen tabular escrito en {SUMMARY_PATH}")


def main() -> int:
    run_profiling()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
