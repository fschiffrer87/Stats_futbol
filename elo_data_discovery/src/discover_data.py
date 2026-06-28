#!/usr/bin/env python3
"""
discover_data.py — Herramienta de exploración y preparación de fuentes
gratuitas de datos de fútbol para un futuro Elo histórico de clubes.

ESTA ETAPA NO CALCULA EL ELO. Solo descubre, inspecciona, perfila y
evalúa fuentes, y prepara la normalización al esquema común.

Comandos principales:
    python src/discover_data.py --list-sources
    python src/discover_data.py --source openfootball --list-available
    python src/discover_data.py --source footballcsv --sample 20
    python src/discover_data.py --source footballcsv --profile
    python src/discover_data.py --all --inventory
    python src/discover_data.py --source footballcsv --normalize-sample
    python src/discover_data.py --all --elo-readiness
    python src/discover_data.py --country Argentina --historical-search
    python src/discover_data.py --region SouthAmerica --list-available

Flags útiles:
    --force-refresh   ignora la cache local y vuelve a descargar.
    --country NAME    filtra/condiciona la elección de dataset por país.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# Permitir ejecución como `python src/discover_data.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetcher
from sources import REGISTRY, get_source, Source, Dataset
from readers import read_by_format
from normalizer import normalize, COMMON_COLUMNS
from profiler import profile as profile_df
from scoring import (
    historical_depth_score, cleanliness_score, elo_readiness_score,
    boolean_flags,
)


# --------------------------------------------------------------------------- #
#  Utilidades de selección y carga
# --------------------------------------------------------------------------- #
def pick_dataset(source: Source, country: str | None = None) -> Dataset | None:
    """Elige un dataset representativo (descargable) de la fuente."""
    candidates = source.datasets
    if country:
        filt = source.datasets_for_country(country)
        if filt:
            candidates = filt
    elif source.default_country:
        filt = source.datasets_for_country(source.default_country)
        if filt:
            candidates = filt
    # Preferir datasets con URL (descargables) y la temporada más reciente.
    downloadable = [d for d in candidates if d.url]
    if downloadable:
        downloadable.sort(key=lambda d: (d.season_end or 0), reverse=True)
        return downloadable[0]
    return candidates[0] if candidates else None


def load_dataset(source: Source, dataset: Dataset, force_refresh: bool):
    """Descarga + lee un dataset. Devuelve (raw_df, source_file) o (None, file)."""
    ctx = f"{source.key}:{dataset.name}"
    data = fetcher.fetch(dataset.url, force_refresh=force_refresh, context=ctx)
    src_file = dataset.url.split("/")[-1] if dataset.url else "(sin archivo)"
    if data is None:
        return None, src_file
    try:
        raw = read_by_format(dataset.fmt, data, default_year=dataset.season_start)
    except Exception as exc:
        fetcher.log_error(ctx, f"error al leer/parsear: {exc}")
        return None, src_file
    return raw, src_file


def build_profile_bundle(source: Source, dataset: Dataset, raw_df,
                         src_file: str):
    """Normaliza y perfila. Devuelve (norm_df, profile, metadata)."""
    norm_df, meta = normalize(raw_df, dataset, source.key, src_file)
    prof = profile_df(raw_df, norm_df, source.key, dataset.name)
    return norm_df, prof, meta


# --------------------------------------------------------------------------- #
#  Comandos
# --------------------------------------------------------------------------- #
def cmd_list_sources() -> None:
    print("\n=== Fuentes configuradas ===\n")
    rows = []
    for key, s in REGISTRY.items():
        ny = len(s.datasets)
        rows.append([key, s.data_format, s.access_type, s.update_status, ny, s.name])
    df = pd.DataFrame(rows, columns=[
        "key", "formato", "acceso", "estado", "#datasets", "nombre"])
    print(df.to_string(index=False))
    print("\nAcceso: download_free=descargable | network_restricted=bloqueado en este entorno"
          " | manual_auth=requiere login | optional_scrape=HTML opcional")
    print(f"\nTotal fuentes: {len(REGISTRY)}\n")


def cmd_list_available(source_key: str) -> None:
    s = get_source(source_key)
    print(f"\n=== {s.name}  ({source_key}) ===")
    print(f"Homepage : {s.homepage}")
    print(f"Licencia : {s.license_notes}")
    print(f"Acceso   : {s.access_type}   Formato: {s.data_format}\n")
    rows = []
    for d in s.datasets:
        cached = "✓" if fetcher.is_cached(d.url) else " "
        rows.append([d.season_label or "-", d.country, d.competition,
                     d.fmt, cached, (d.url or "(manual)")])
    df = pd.DataFrame(rows, columns=[
        "temporada", "país", "competición", "formato", "cache", "url"])
    print(df.to_string(index=False))
    print(f"\nTotal datasets: {len(s.datasets)}  (✓ = ya en cache local)\n")


def cmd_sample(source_key: str, n: int, country: str | None,
               force_refresh: bool) -> None:
    s = get_source(source_key)
    d = pick_dataset(s, country)
    if not d:
        print(f"Sin datasets para {source_key}.")
        return
    print(f"\nMuestra de: {d.name}\nArchivo: {d.url}\n")
    raw, src_file = load_dataset(s, d, force_refresh)
    if raw is None:
        print(f"⚠️  No se pudo obtener datos (ver outputs/errors.log). "
              f"Acceso: {s.access_type}")
        return
    sample = raw.head(n)
    print(sample.to_string(index=False))
    out = fetcher.outputs_dir() / f"sample_{source_key}.csv"
    sample.to_csv(out, index=False)
    print(f"\n→ Guardado: {out}  ({len(sample)} filas de {len(raw)})\n")


def cmd_profile(source_key: str, country: str | None,
                force_refresh: bool) -> None:
    s = get_source(source_key)
    d = pick_dataset(s, country)
    if not d:
        print(f"Sin datasets para {source_key}.")
        return
    raw, src_file = load_dataset(s, d, force_refresh)
    if raw is None:
        print(f"⚠️  No se pudo perfilar {source_key} (acceso: {s.access_type}). "
              f"Ver outputs/errors.log")
        return
    norm_df, prof, meta = build_profile_bundle(s, d, raw, src_file)
    out = fetcher.outputs_dir() / f"profile_{source_key}.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(prof, fh, ensure_ascii=False, indent=2)

    print(f"\n=== Perfil: {s.name} / {d.name} ===")
    print(f"Columnas crudas    : {prof['columns']}")
    print(f"Partidos           : {prof['number_of_matches']}")
    print(f"Cobertura          : {prof['first_date']}  →  {prof['last_date']}")
    print(f"Equipos detectados : {prof['teams_detected_count']}")
    print(f"Competiciones      : {prof['competitions_detected']}")
    print(f"Variables Elo OK   : {prof['elo_minimum_present']}")
    if prof["format_issues"]:
        print(f"Problemas          : {prof['format_issues']}")
    else:
        print("Problemas          : ninguno detectado")
    print(f"\n→ Guardado: {out}\n")


def cmd_normalize_sample(source_key: str, n: int, country: str | None,
                         force_refresh: bool) -> None:
    s = get_source(source_key)
    d = pick_dataset(s, country)
    if not d:
        print(f"Sin datasets para {source_key}.")
        return
    raw, src_file = load_dataset(s, d, force_refresh)
    if raw is None:
        print(f"⚠️  No se pudo normalizar {source_key} (acceso: {s.access_type}).")
        return
    norm_df, meta = normalize(raw, d, s.key, src_file)
    sample = norm_df.head(n)
    out = fetcher.outputs_dir() / f"normalized_sample_{source_key}.csv"
    sample.to_csv(out, index=False)
    print(f"\n=== Muestra normalizada al esquema común: {d.name} ===\n")
    print(sample.to_string(index=False))
    print(f"\nColumnas vacías (None): {meta['empty_columns']}")
    print(f"¿Tiene variables mínimas para Elo?: {meta['has_elo_minimum']}")
    if meta["derived_notes"]:
        print(f"Notas: {meta['derived_notes']}")
    print(f"\n→ Guardado: {out}\n")


def _source_row(source: Source, force_refresh: bool) -> tuple[dict, dict | None]:
    """Calcula la fila de inventario para una fuente (con dataset representativo)."""
    d = pick_dataset(source)
    n_files = len(source.datasets)
    seasons_start = [x.season_start for x in source.datasets if x.season_start]
    seasons_end = [x.season_end for x in source.datasets if x.season_end]
    season_start = min(seasons_start) if seasons_start else None
    season_end = max(seasons_end) if seasons_end else None
    depth_label, _years = historical_depth_score(season_start, season_end)
    clean_label = cleanliness_score(d.fmt if d else source.data_format)

    row = {
        "source": source.key,
        "dataset_name": d.name if d else source.name,
        "country": d.country if d else source.default_country,
        "competition": d.competition if d else "",
        "season_start": season_start,
        "season_end": season_end,
        "number_of_files": n_files,
        "estimated_number_of_matches": None,
        "estimated_number_of_teams": None,
        "has_date": False, "has_home_team": False, "has_away_team": False,
        "has_home_goals": False, "has_away_goals": False, "has_neutral": False,
        "has_round": False, "has_stage": False, "has_xg": False,
        "access_type": source.access_type,
        "data_format": source.data_format,
        "license_notes": source.license_notes,
        "update_status": source.update_status,
        "historical_depth_score": depth_label,
        "cleanliness_score": clean_label,
        "elo_readiness_score": 0,
        "notes": d.notes if d else "",
    }

    prof = None
    if d is None:
        row["notes"] = "sin datasets configurados"
        return row, prof

    raw, src_file = load_dataset(source, d, force_refresh)
    if raw is None:
        row["notes"] = (f"No descargable en este entorno (acceso={source.access_type}). "
                        "Metadatos estáticos solamente.")
        # Igual damos un puntaje de aptitud teórico mínimo basado en formato.
        return row, prof

    norm_df, prof, meta = build_profile_bundle(source, d, raw, src_file)
    flags = boolean_flags(prof)
    row.update(flags)
    per_file_matches = prof["number_of_matches"]
    row["estimated_number_of_matches"] = per_file_matches * n_files
    row["estimated_number_of_teams"] = prof["teams_detected_count"]
    score, reasons = elo_readiness_score(prof, depth_label, clean_label)
    row["elo_readiness_score"] = score
    row["_reasons"] = "; ".join(reasons)
    if d.notes:
        row["notes"] = d.notes
    return row, prof


def cmd_inventory(force_refresh: bool) -> None:
    print("\n=== Generando inventario de todas las fuentes ===\n")
    rows = []
    for key, s in REGISTRY.items():
        print(f"• Procesando {key} ...")
        row, _prof = _source_row(s, force_refresh)
        rows.append(row)
    df = pd.DataFrame(rows)
    # quitar columna interna de razones del CSV principal
    cols = [c for c in df.columns if c != "_reasons"]
    out = fetcher.outputs_dir() / "source_inventory.csv"
    df[cols].to_csv(out, index=False)
    print(f"\n→ Guardado: {out}\n")
    show = ["source", "country", "season_start", "season_end",
            "number_of_files", "estimated_number_of_matches",
            "cleanliness_score", "historical_depth_score", "elo_readiness_score"]
    print(df[show].to_string(index=False))
    print()
    _print_recommendations(df)


def cmd_elo_readiness(force_refresh: bool) -> None:
    print("\n=== Evaluando aptitud para Elo de cada fuente ===\n")
    rows = []
    for key, s in REGISTRY.items():
        print(f"• Evaluando {key} ...")
        row, _prof = _source_row(s, force_refresh)
        rows.append(row)
    df = pd.DataFrame(rows).sort_values("elo_readiness_score", ascending=False)
    out_cols = [
        "source", "dataset_name", "country", "data_format", "access_type",
        "historical_depth_score", "cleanliness_score", "elo_readiness_score",
        "_reasons",
    ]
    out_cols = [c for c in out_cols if c in df.columns]
    rep = df[out_cols].rename(columns={"_reasons": "score_breakdown"})
    out = fetcher.outputs_dir() / "elo_readiness_report.csv"
    rep.to_csv(out, index=False)
    print(f"\n→ Guardado: {out}\n")
    print(df[["source", "country", "data_format", "elo_readiness_score",
              "historical_depth_score", "cleanliness_score"]].to_string(index=False))
    print()
    _print_recommendations(df)
    _print_next_steps()


def cmd_historical_search(country: str) -> None:
    print(f"\n=== Datasets históricos para: {country} ===\n")
    rows = []
    for key, s in REGISTRY.items():
        for d in s.datasets_for_country(country):
            label, years = historical_depth_score(d.season_start, d.season_end)
            rows.append([key, d.name, d.season_label, years, label,
                         d.fmt, s.access_type])
    # también competiciones continentales cuyo "país" es SouthAmerica
    if country.lower() in ("argentina",):
        for key, s in REGISTRY.items():
            for d in s.datasets:
                if d.region == "SouthAmerica" and d.country == "SouthAmerica":
                    label, years = historical_depth_score(d.season_start, d.season_end)
                    rows.append([key, d.name + " (continental)", d.season_label,
                                 years, label, d.fmt, s.access_type])
    if not rows:
        print(f"No hay datasets configurados para {country}.")
        return
    df = pd.DataFrame(rows, columns=[
        "source", "dataset", "season", "years", "depth", "fmt", "access"])
    # Agrupar por source para mostrar profundidad agregada
    print(df.to_string(index=False))
    print("\nResumen de profundidad por fuente (años cubiertos):")
    agg = df.groupby("source")["years"].agg(["min", "max", "sum"]).reset_index()
    print(agg.to_string(index=False))
    print("\nNota: openfootball cubre desde ~2012-2018 (profundidad media). "
          "Para profundidad ALTA (>20 años) en Argentina, football-data.co.uk "
          "y datasets de Kaggle son las vías principales, pero requieren red/login "
          "no disponibles en este entorno.\n")


def cmd_region_list(region: str) -> None:
    print(f"\n=== Datasets disponibles en la región: {region} ===\n")
    rows = []
    for key, s in REGISTRY.items():
        for d in s.datasets_for_region(region):
            rows.append([key, d.country, d.competition, d.season_label,
                         d.fmt, s.access_type])
    if not rows:
        print(f"No hay datasets para la región {region}.")
        return
    df = pd.DataFrame(rows, columns=[
        "source", "país", "competición", "temporada", "formato", "acceso"])
    print(df.to_string(index=False))
    print(f"\nPaíses cubiertos: {sorted(df['país'].unique().tolist())}")
    print(f"Competiciones   : {sorted(df['competición'].unique().tolist())}")
    print(f"Total datasets  : {len(df)}\n")


# --------------------------------------------------------------------------- #
#  Recomendaciones y próximos pasos (resumen en consola)
# --------------------------------------------------------------------------- #
def _print_recommendations(df: pd.DataFrame) -> None:
    print("─" * 70)
    print("RECOMENDACIONES DE FUENTES")
    print("─" * 70)

    def best(filter_fn, label):
        sub = df[df.apply(filter_fn, axis=1)]
        if "elo_readiness_score" in sub:
            sub = sub.sort_values("elo_readiness_score", ascending=False)
        if sub.empty:
            print(f"  {label}: (sin candidatos)")
            return
        top = sub.iloc[0]
        print(f"  {label}:")
        print(f"     → {top['source']} ({top.get('data_format','?')}) "
              f"score={top.get('elo_readiness_score','?')} "
              f"limpieza={top.get('cleanliness_score','?')} "
              f"profundidad={top.get('historical_depth_score','?')}")

    best(lambda r: r["source"] == "openfootball",
         "Elo argentino RECIENTE y limpio")
    best(lambda r: r["source"] in ("footballcsv", "footballdata_uk"),
         "Elo HISTÓRICO largo (referencia de profundidad)")
    best(lambda r: r["source"] == "openfootball_sa",
         "Extensión SUDAMERICANA (ligas + Libertadores/Sudamericana)")
    print()


def _print_next_steps() -> None:
    print("─" * 70)
    print("PRÓXIMOS PASOS: de exploración de datos a cálculo de Elo")
    print("─" * 70)
    steps = [
        "1. Consolidar un dataset normalizado multi-temporada de Argentina "
        "(openfootball south-america: 2018→2025) en data/processed/.",
        "2. Construir un diccionario de alias de clubes (River Plate, CARP, etc.) "
        "para unificar nombres entre fuentes y temporadas.",
        "3. Ordenar partidos cronológicamente y validar continuidad temporal "
        "(detectar gaps y duplicados entre temporadas).",
        "4. Definir parámetros del modelo Elo: K, ventaja de localía, ajuste por "
        "diferencia de gol, peso por importancia de competición.",
        "5. Tratar ascensos/descensos: rating inicial para equipos nuevos y "
        "regresión a la media entre temporadas.",
        "6. Sumar competiciones continentales (Libertadores/Sudamericana) con "
        "mayor peso y manejo de cancha neutral en finales.",
        "7. Validar el Elo contra resultados conocidos (campeones, rachas) antes "
        "de extender a toda Sudamérica.",
        "8. (Opcional) Integrar football-data.co.uk / Kaggle para profundidad "
        "histórica >20 años cuando haya acceso de red/credenciales.",
    ]
    for s in steps:
        print(f"  {s}")
    print()


# --------------------------------------------------------------------------- #
#  Parser de argumentos
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Exploración y preparación de fuentes de datos de fútbol "
                    "para un futuro Elo de clubes (Argentina → Sudamérica).")
    p.add_argument("--source", help="clave de la fuente (ver --list-sources)")
    p.add_argument("--all", action="store_true", help="aplicar a todas las fuentes")
    p.add_argument("--country", help="filtrar/condicionar por país (ej. Argentina)")
    p.add_argument("--region", help="filtrar por región (ej. SouthAmerica)")
    p.add_argument("--force-refresh", action="store_true",
                   help="ignorar cache y volver a descargar")

    p.add_argument("--list-sources", action="store_true")
    p.add_argument("--list-available", action="store_true")
    p.add_argument("--sample", type=int, metavar="N",
                   help="mostrar N filas crudas")
    p.add_argument("--profile", action="store_true")
    p.add_argument("--inventory", action="store_true")
    p.add_argument("--normalize-sample", action="store_true")
    p.add_argument("--elo-readiness", action="store_true")
    p.add_argument("--historical-search", action="store_true")
    p.add_argument("--summary", action="store_true",
                   help="imprimir recomendaciones y próximos pasos")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fr = args.force_refresh

    try:
        if args.list_sources:
            cmd_list_sources()
        elif args.region and args.list_available:
            cmd_region_list(args.region)
        elif args.list_available and args.source:
            cmd_list_available(args.source)
        elif args.sample is not None and args.source:
            cmd_sample(args.source, args.sample, args.country, fr)
        elif args.profile and args.source:
            cmd_profile(args.source, args.country, fr)
        elif args.normalize_sample and args.source:
            cmd_normalize_sample(args.source, 20, args.country, fr)
        elif args.inventory and (args.all or args.source):
            cmd_inventory(fr)
        elif args.elo_readiness and (args.all or args.source):
            cmd_elo_readiness(fr)
        elif args.historical_search and args.country:
            cmd_historical_search(args.country)
        elif args.summary:
            cmd_elo_readiness(fr)
        else:
            build_parser().print_help()
            print("\nEjemplo: python src/discover_data.py --list-sources")
    except KeyError as exc:
        print(f"Error: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
