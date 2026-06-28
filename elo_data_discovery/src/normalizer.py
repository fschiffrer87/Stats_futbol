"""
Normalización hacia el esquema común de partidos.

Esquema común (objetivo para el futuro cálculo de Elo):
    date, season, competition, country, home_team, away_team,
    home_goals, away_goals, neutral, stage, round, source, source_file, notes

Si una fuente no tiene una variable, la columna se crea con None y se
reporta en la metadata (ver `normalize` -> retorna también un dict de
columnas faltantes/derivadas).
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd

from sources import Dataset


COMMON_COLUMNS = [
    "date", "season", "competition", "country",
    "home_team", "away_team", "home_goals", "away_goals",
    "neutral", "stage", "round", "source", "source_file", "notes",
]

# Variables mínimas para poder calcular un Elo básico.
ELO_MINIMUM = ["home_team", "away_team", "home_goals", "away_goals"]


def _split_score(value) -> tuple[Optional[int], Optional[int]]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, None
    s = str(value).strip()
    m = re.match(r"^\s*(\d+)\s*[-:]\s*(\d+)", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _derive_stage(round_value) -> Optional[str]:
    """Heurística simple: detectar fase (grupos/eliminación) desde 'round'."""
    if round_value is None or (isinstance(round_value, float) and pd.isna(round_value)):
        return None
    r = str(round_value).lower()
    if any(k in r for k in ["group", "grupo", "fase de grupos"]):
        return "group"
    if any(k in r for k in ["final"]):
        return "final"
    if any(k in r for k in ["semi"]):
        return "semifinal"
    if any(k in r for k in ["quarter", "cuartos"]):
        return "quarterfinal"
    if any(k in r for k in ["round of", "octavos", "16", "knockout", "playoff", "play-off"]):
        return "knockout"
    if any(k in r for k in ["matchday", "fecha", "jornada", "round", "semestre"]):
        return "regular"
    return None


def normalize(df: pd.DataFrame, dataset: Dataset, source_key: str,
              source_file: str) -> tuple[pd.DataFrame, dict]:
    """
    Convierte un DataFrame crudo al esquema común.

    Devuelve (df_normalizado, metadata) donde metadata informa qué columnas
    del esquema quedaron vacías (None) y notas de derivación.
    """
    fmt = dataset.fmt
    n = len(df)
    out = pd.DataFrame(index=range(n))
    derived_notes: list[str] = []

    # --- Mapeo según formato ------------------------------------------ #
    if fmt in ("openfootball_json", "openfootball_txt"):
        out["date"] = df.get("date")
        comp = dataset.competition
        if fmt == "openfootball_txt" and "competition" in df:
            comp_series = df["competition"].replace("", pd.NA).dropna()
            if not comp_series.empty:
                comp = comp_series.iloc[0]
        out["competition"] = comp
        out["home_team"] = df.get("team1")
        out["away_team"] = df.get("team2")
        if "ft_home" in df:
            out["home_goals"] = df["ft_home"]
            out["away_goals"] = df["ft_away"]
        else:
            hg, ag = zip(*df.get("ft", pd.Series([None] * n)).map(_split_score)) if n else ([], [])
            out["home_goals"] = list(hg)
            out["away_goals"] = list(ag)
        out["round"] = df.get("round")
        out["stage"] = out["round"].map(_derive_stage) if "round" in out else None

    elif fmt in ("footballcsv", "csv"):
        # footballcsv: Date, Team 1, FT, HT, Team 2
        cols = {c.lower().strip(): c for c in df.columns}
        date_col = cols.get("date") or cols.get("datetime")
        out["date"] = df[date_col] if date_col else None
        # equipos
        home_col = cols.get("team 1") or cols.get("hometeam") or cols.get("home")
        away_col = cols.get("team 2") or cols.get("awayteam") or cols.get("away")
        out["home_team"] = df[home_col] if home_col else None
        out["away_team"] = df[away_col] if away_col else None
        # goles
        if "ft" in cols:  # footballcsv "2-0"
            hg, ag = zip(*df[cols["ft"]].map(_split_score)) if n else ([], [])
            out["home_goals"] = list(hg)
            out["away_goals"] = list(ag)
        else:  # football-data.co.uk: FTHG/FTAG
            fthg = cols.get("fthg") or cols.get("hg")
            ftag = cols.get("ftag") or cols.get("ag")
            out["home_goals"] = df[fthg] if fthg else None
            out["away_goals"] = df[ftag] if ftag else None
        out["competition"] = dataset.competition
        out["round"] = None
        out["stage"] = None
        derived_notes.append("competición tomada de la config del dataset")

    else:
        derived_notes.append(f"formato '{fmt}' sin normalización (solo inspección)")

    # --- Columnas comunes de contexto --------------------------------- #
    out["country"] = dataset.country
    out["season"] = dataset.season_label
    out["neutral"] = None  # ninguna fuente lo marca explícito en esta etapa
    out["source"] = source_key
    out["source_file"] = source_file
    out["notes"] = dataset.notes or None

    # --- Normalizar fecha a ISO --------------------------------------- #
    if "date" in out and out["date"].notna().any():
        parsed = pd.to_datetime(out["date"], errors="coerce", utc=False)
        if parsed.notna().any():
            out["date"] = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), out["date"])

    # --- Asegurar todas las columnas del esquema ---------------------- #
    for col in COMMON_COLUMNS:
        if col not in out.columns:
            out[col] = None
    out = out[COMMON_COLUMNS]

    # --- Metadata de faltantes ---------------------------------------- #
    missing_cols = [c for c in COMMON_COLUMNS
                    if out[c].isna().all() or (out[c] == None).all()]  # noqa: E711
    metadata = {
        "source": source_key,
        "dataset": dataset.name,
        "rows": int(n),
        "empty_columns": missing_cols,
        "has_elo_minimum": all(
            (c in out.columns) and out[c].notna().any() for c in ELO_MINIMUM
        ),
        "derived_notes": derived_notes,
    }
    return out, metadata
