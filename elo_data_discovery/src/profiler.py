"""
Perfilado de una fuente: estructura, cobertura temporal, equipos,
competiciones, faltantes y posibles problemas de formato/encoding/duplicados.

Trabaja sobre el DataFrame normalizado (esquema común) pero también recibe
el DataFrame crudo para reportar columnas/tipos originales.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from normalizer import ELO_MINIMUM


def _safe_minmax_dates(series: pd.Series) -> tuple[Optional[str], Optional[str]]:
    parsed = pd.to_datetime(series, errors="coerce")
    parsed = parsed.dropna()
    if parsed.empty:
        return None, None
    return parsed.min().strftime("%Y-%m-%d"), parsed.max().strftime("%Y-%m-%d")


def profile(raw_df: pd.DataFrame, norm_df: pd.DataFrame,
            source_key: str, dataset_name: str) -> dict:
    issues: list[str] = []

    # --- Estructura cruda --------------------------------------------- #
    raw_columns = list(raw_df.columns)
    raw_dtypes = {c: str(raw_df[c].dtype) for c in raw_df.columns}
    raw_missing = {c: int(raw_df[c].isna().sum()) for c in raw_df.columns}

    # --- Cobertura temporal (del normalizado) ------------------------- #
    first_date, last_date = (None, None)
    if "date" in norm_df:
        first_date, last_date = _safe_minmax_dates(norm_df["date"])
        if first_date is None:
            issues.append("no se pudieron parsear fechas a formato fecha")

    # --- Equipos detectados ------------------------------------------- #
    teams = set()
    for col in ("home_team", "away_team"):
        if col in norm_df:
            teams |= set(norm_df[col].dropna().astype(str).unique())
    teams = sorted(t for t in teams if t)

    # --- Competiciones detectadas ------------------------------------- #
    comps = []
    if "competition" in norm_df:
        comps = sorted(norm_df["competition"].dropna().astype(str).unique().tolist())

    # --- Número de partidos ------------------------------------------- #
    n_matches = int(len(norm_df))

    # --- Faltantes del esquema común ---------------------------------- #
    schema_missing = {}
    for c in norm_df.columns:
        nulls = int(norm_df[c].isna().sum())
        schema_missing[c] = nulls

    # --- Variables mínimas para Elo ----------------------------------- #
    elo_min_ok = {}
    for c in ELO_MINIMUM:
        elo_min_ok[c] = bool(c in norm_df.columns and norm_df[c].notna().any())

    # --- Problemas de formato / encoding / duplicados ----------------- #
    # Encoding: caracteres de reemplazo en nombres de equipo
    enc_problem = False
    for col in ("home_team", "away_team"):
        if col in norm_df:
            if norm_df[col].astype(str).str.contains("�").any():
                enc_problem = True
    if enc_problem:
        issues.append("posibles problemas de encoding (carácter de reemplazo \\ufffd)")

    # Goles no numéricos
    for col in ("home_goals", "away_goals"):
        if col in norm_df:
            non_num = pd.to_numeric(norm_df[col], errors="coerce").isna() & norm_df[col].notna()
            if int(non_num.sum()) > 0:
                issues.append(f"{int(non_num.sum())} valores de '{col}' no numéricos")

    # Duplicados (mismo partido)
    dup_keys = [c for c in ("date", "home_team", "away_team") if c in norm_df]
    n_dups = 0
    if len(dup_keys) >= 2:
        n_dups = int(norm_df.duplicated(subset=dup_keys).sum())
        if n_dups > 0:
            issues.append(f"{n_dups} filas duplicadas por {dup_keys}")

    # Fechas faltantes
    if "date" in norm_df:
        miss_dates = int(norm_df["date"].isna().sum())
        if miss_dates:
            issues.append(f"{miss_dates} partidos sin fecha")

    return {
        "source": source_key,
        "dataset": dataset_name,
        "columns": raw_columns,
        "dtypes": raw_dtypes,
        "raw_missing_values": raw_missing,
        "schema_missing_values": schema_missing,
        "first_date": first_date,
        "last_date": last_date,
        "teams_detected_count": len(teams),
        "teams_detected_sample": teams[:40],
        "competitions_detected": comps,
        "number_of_matches": n_matches,
        "elo_minimum_present": elo_min_ok,
        "has_all_elo_minimum": all(elo_min_ok.values()),
        "duplicate_rows": n_dups,
        "encoding_problem": enc_problem,
        "format_issues": issues,
    }
