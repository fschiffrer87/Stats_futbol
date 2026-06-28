"""
Lectores de archivos por formato.

Cada lector recibe bytes crudos (de fetcher.fetch) y devuelve un
pandas.DataFrame con la representación tabular MÁS CERCANA a la fuente
original (columnas "crudas"). La normalización al esquema común se hace
aparte en normalizer.py.

Formatos:
    - footballcsv  : CSV "Date,Team 1,FT,HT,Team 2"
    - csv          : CSV genérico (football-data.co.uk, etc.)
    - openfootball_json : JSON {name, matches:[{round,date,time,team1,team2,score}]}
    - openfootball_txt  : formato de texto legible de openfootball
    - html         : se devuelve metadata mínima (parseo opcional/liviano)
"""

from __future__ import annotations

import io
import json
import re
from typing import Optional

import pandas as pd


# --------------------------------------------------------------------------- #
#  CSV (footballcsv y genérico)
# --------------------------------------------------------------------------- #
def read_csv_bytes(data: bytes) -> pd.DataFrame:
    """Lee CSV genérico, tolerante a encoding."""
    for enc in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except UnicodeDecodeError:
            continue
        except Exception:
            # reintentar con motor python y separador flexible
            try:
                return pd.read_csv(io.BytesIO(data), encoding=enc,
                                   engine="python", sep=None)
            except Exception:
                continue
    # último recurso
    return pd.read_csv(io.BytesIO(data), encoding="latin-1",
                       engine="python", on_bad_lines="skip")


# --------------------------------------------------------------------------- #
#  openfootball JSON
# --------------------------------------------------------------------------- #
def read_openfootball_json(data: bytes) -> pd.DataFrame:
    doc = json.loads(data.decode("utf-8"))
    league_name = doc.get("name", "")
    rows = []
    for m in doc.get("matches", []):
        if not isinstance(m, dict):
            continue
        score = m.get("score") or {}
        if not isinstance(score, dict):
            score = {}
        ft = score.get("ft")
        ht = score.get("ht")
        # Algunos archivos guardan los goles directamente en score1/score2
        if ft is None and "score1" in m and "score2" in m:
            ft = [m.get("score1"), m.get("score2")]
        rows.append({
            "league": league_name,
            "round": m.get("round"),
            "date": m.get("date"),
            "time": m.get("time"),
            "team1": m.get("team1"),
            "team2": m.get("team2"),
            "ft": "-".join(str(x) for x in ft) if isinstance(ft, list) else None,
            "ht": "-".join(str(x) for x in ht) if isinstance(ht, list) else None,
            "ft_home": ft[0] if isinstance(ft, list) and len(ft) == 2 else None,
            "ft_away": ft[1] if isinstance(ft, list) and len(ft) == 2 else None,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
#  openfootball TXT  (formato de texto legible)
# --------------------------------------------------------------------------- #
# Ejemplo de líneas:
#   = Argentina Primera Division 2024
#   ▪ Matchday 1
#     Fri May 10 2024
#       19:00  Sarmiento de Junín   v Instituto de Córdoba   1-2 (0-1)
#              Newell's Old Boys     v Platense               2-0 (0-0)
_RE_HEADER = re.compile(r"^=\s+(.*)$")
_RE_ROUND = re.compile(r"^[»▪•]\s*(.+)$")
_RE_ROUND2 = re.compile(r"^\s*(Matchday|Round|Fecha|Group|Grupo|Final|Semi|Quarter|Round of)\b.*$", re.I)
# Línea de fecha: empieza con día de semana (con o sin año)
_RE_DATE = re.compile(
    r"^\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$"
)
# Línea de partido: (hora opcional) Local v Visitante  goles (ht)
_RE_MATCH = re.compile(
    r"^\s*(?:(\d{1,2}:\d{2})\s+)?"          # hora opcional
    r"(.+?)\s+v\s+(.+?)\s+"                  # local v visitante
    r"(\d+)\s*-\s*(\d+)"                     # goles FT
    r"(?:\s*\((\d+)\s*-\s*(\d+)\))?"        # goles HT opcional
    r"\s*(?:[a-zA-Z.\s]*)?$"                 # sufijos (aet, pen., etc.)
)
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def read_openfootball_txt(data: bytes, default_year: Optional[int] = None) -> pd.DataFrame:
    """Parsea el formato de texto de openfootball a filas de partidos."""
    text = data.decode("utf-8", errors="replace")
    competition = ""
    current_round = ""
    current_date = None  # (year, month, day)
    rows = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        m = _RE_HEADER.match(line.strip())
        if m:
            competition = m.group(1).strip()
            continue

        m = _RE_ROUND.match(line.strip())
        if m:
            current_round = m.group(1).strip()
            continue
        if _RE_ROUND2.match(line.strip()) and " v " not in line:
            current_round = line.strip()
            continue

        m = _RE_DATE.match(line)
        if m:
            mon, day, year = m.group(2), int(m.group(3)), m.group(4)
            yr = int(year) if year else (default_year or (current_date[0] if current_date else None))
            current_date = (yr, _MONTHS.get(mon), day)
            continue

        m = _RE_MATCH.match(line)
        if m:
            time_s, home, away, fh, fa, hh, ha = m.groups()
            date_iso = None
            if current_date and all(current_date):
                y, mo, d = current_date
                date_iso = f"{y:04d}-{mo:02d}-{d:02d}"
            rows.append({
                "competition": competition,
                "round": current_round,
                "date": date_iso,
                "time": time_s,
                "team1": home.strip(),
                "team2": away.strip(),
                "ft": f"{fh}-{fa}",
                "ht": f"{hh}-{ha}" if hh is not None else None,
                "ft_home": int(fh),
                "ft_away": int(fa),
            })

    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
#  HTML (solo inspección liviana)
# --------------------------------------------------------------------------- #
def read_html_tables(data: bytes) -> pd.DataFrame:
    """Intento liviano de leer la primera tabla HTML. Opcional."""
    try:
        tables = pd.read_html(io.BytesIO(data))
        if tables:
            return tables[0]
    except Exception:
        pass
    return pd.DataFrame()


# --------------------------------------------------------------------------- #
#  Despachador
# --------------------------------------------------------------------------- #
def read_by_format(fmt: str, data: bytes,
                   default_year: Optional[int] = None) -> pd.DataFrame:
    if fmt == "openfootball_json":
        return read_openfootball_json(data)
    if fmt == "openfootball_txt":
        return read_openfootball_txt(data, default_year=default_year)
    if fmt in ("footballcsv", "csv"):
        return read_csv_bytes(data)
    if fmt == "html":
        return read_html_tables(data)
    raise ValueError(f"Formato no soportado: {fmt}")
