"""
Cálculo de scores para evaluar utilidad de cada fuente para construir un Elo.

  - historical_depth_score : 'alto' (>20 años), 'medio' (8-20), 'bajo' (<8)
  - cleanliness_score      : 'alto' (CSV/JSON estructurado), 'medio' (parseo
                              simple), 'bajo' (scraping HTML / limpieza fuerte)
  - elo_readiness_score    : 0-100 según presencia de variables clave, con
                              penalizaciones por faltantes/formato difícil.

Los scores se calculan a partir de un perfil (profiler.profile) y de la
metadata estática de la fuente/dataset.
"""

from __future__ import annotations

from typing import Optional

from sources import Source, Dataset


# Cleanliness según formato (mapeo declarativo).
_FORMAT_CLEANLINESS = {
    "openfootball_json": "alto",
    "footballcsv": "alto",
    "csv": "alto",
    "openfootball_txt": "medio",   # requiere parseo simple
    "html": "bajo",                # requiere scraping / limpieza fuerte
}


def historical_depth_score(season_start: Optional[int],
                           season_end: Optional[int]) -> tuple[str, int]:
    """Devuelve (etiqueta, años). Etiqueta: alto/medio/bajo/desconocido."""
    if season_start is None or season_end is None:
        return "desconocido", 0
    years = max(0, season_end - season_start) + 1
    if years > 20:
        return "alto", years
    if years >= 8:
        return "medio", years
    return "bajo", years


def cleanliness_score(fmt: str) -> str:
    return _FORMAT_CLEANLINESS.get(fmt, "medio")


def elo_readiness_score(profile: dict, depth_label: str,
                        clean_label: str) -> tuple[int, list[str]]:
    """
    Calcula el puntaje 0-100 de aptitud para Elo y devuelve también
    las razones (desglose) para transparencia.
    """
    score = 0
    reasons: list[str] = []

    elo_min = profile.get("elo_minimum_present", {})
    schema_missing = profile.get("schema_missing_values", {})
    n = max(1, profile.get("number_of_matches", 0))

    # +30 fecha clara
    if profile.get("first_date"):
        score += 30
        reasons.append("+30 fecha clara")
    else:
        reasons.append("+0 sin fecha parseable")

    # +20 local y visitante
    if elo_min.get("home_team") and elo_min.get("away_team"):
        score += 20
        reasons.append("+20 equipos local/visitante")

    # +20 goles local y visitante
    if elo_min.get("home_goals") and elo_min.get("away_goals"):
        score += 20
        reasons.append("+20 goles local/visitante")

    # +10 competición
    if schema_missing.get("competition", n) < n:
        score += 10
        reasons.append("+10 competición")

    # +10 temporada
    if schema_missing.get("season", n) < n:
        score += 10
        reasons.append("+10 temporada")

    # +5 neutral/localía clara
    if schema_missing.get("neutral", n) < n:
        score += 5
        reasons.append("+5 cancha neutral marcada")

    # +5 buena cobertura histórica
    if depth_label == "alto":
        score += 5
        reasons.append("+5 cobertura histórica alta")
    elif depth_label == "medio":
        score += 3
        reasons.append("+3 cobertura histórica media")

    # --- Penalizaciones ----------------------------------------------- #
    # Faltantes de goles/equipos (clave para Elo)
    for col in ("home_goals", "away_goals", "home_team", "away_team"):
        miss = schema_missing.get(col, 0)
        if miss > 0:
            ratio = miss / n
            if ratio > 0.05:
                pen = int(round(min(10, ratio * 20)))
                score -= pen
                reasons.append(f"-{pen} faltantes en {col} ({ratio:.0%})")

    # Formato difícil
    if clean_label == "bajo":
        score -= 15
        reasons.append("-15 formato difícil (HTML/scraping)")
    elif clean_label == "medio":
        score -= 3
        reasons.append("-3 requiere parseo")

    # Duplicados / encoding
    if profile.get("duplicate_rows", 0) > 0:
        score -= 3
        reasons.append("-3 duplicados detectados")
    if profile.get("encoding_problem"):
        score -= 3
        reasons.append("-3 problemas de encoding")

    score = max(0, min(100, score))
    return score, reasons


def boolean_flags(profile: dict) -> dict:
    """Flags has_* para el inventario, a partir del perfil normalizado."""
    sm = profile.get("schema_missing_values", {})
    n = max(1, profile.get("number_of_matches", 0))

    def has(col: str) -> bool:
        return sm.get(col, n) < n

    return {
        "has_date": bool(profile.get("first_date")),
        "has_home_team": has("home_team"),
        "has_away_team": has("away_team"),
        "has_home_goals": has("home_goals"),
        "has_away_goals": has("away_goals"),
        "has_neutral": has("neutral"),
        "has_round": has("round"),
        "has_stage": has("stage"),
        "has_xg": False,  # ninguna fuente normalizada expone xG en esta etapa
    }
