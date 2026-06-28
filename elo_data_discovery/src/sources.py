"""
Registro modular de fuentes de datos de fútbol (gratuitas).

Cada fuente se describe con metadatos estáticos (lo que ya sabemos por
inspección manual de la fuente) y una lista de "datasets" lógicos. Un dataset
apunta a uno o varios archivos descargables y declara a qué país/competición
pertenece y qué formato usa.

El objetivo de esta etapa NO es calcular el Elo, sino *descubrir* y *evaluar*
fuentes. Por eso la configuración es declarativa y fácil de extender:
para sumar un país o competición nuevo basta con agregar entradas acá.

Formatos soportados por los lectores (ver readers.py):
    - "openfootball_json": JSON estructurado de openfootball/football.json
    - "openfootball_txt":  formato de texto legible de openfootball/*
    - "footballcsv":       CSV estándar footballcsv (Date,Team 1,FT,HT,Team 2)
    - "csv":               CSV genérico (football-data.co.uk, etc.)
    - "html":              tabla HTML (solo inspección liviana, opcional)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# --------------------------------------------------------------------------- #
#  Modelos de configuración
# --------------------------------------------------------------------------- #
@dataclass
class Dataset:
    """Un archivo (o grupo de archivos homogéneos) dentro de una fuente."""

    name: str                      # nombre lógico, ej. "Argentina Primera 2025"
    country: str                   # país principal ("Argentina", "Brazil", ...)
    competition: str               # competición ("Primera Division", "Copa Libertadores")
    region: str                    # "SouthAmerica", "Europe", "International"
    fmt: str                       # formato del lector (ver arriba)
    url: Optional[str] = None      # URL directa al archivo (raw)
    season_start: Optional[int] = None   # año de inicio de cobertura
    season_end: Optional[int] = None      # año de fin de cobertura
    season_label: Optional[str] = None    # etiqueta de temporada ("2025", "2021-22")
    notes: str = ""


@dataclass
class Source:
    """Una fuente de datos (repositorio, sitio, dataset)."""

    key: str                       # identificador corto para la CLI
    name: str                      # nombre legible
    homepage: str                  # URL informativa
    license_notes: str             # licencia / términos
    access_type: str               # download_free | network_restricted | manual_auth | optional_scrape
    data_format: str               # csv | json | txt | html (formato dominante)
    update_status: str             # activo | histórico | mixto
    default_country: str = ""
    datasets: list[Dataset] = field(default_factory=list)

    def datasets_for_country(self, country: str) -> list[Dataset]:
        c = country.strip().lower()
        return [d for d in self.datasets if d.country.lower() == c]

    def datasets_for_region(self, region: str) -> list[Dataset]:
        r = region.strip().lower()
        return [d for d in self.datasets if d.region.lower() == r]


# --------------------------------------------------------------------------- #
#  Helpers para generar URLs de openfootball
# --------------------------------------------------------------------------- #
_OF_JSON_RAW = "https://raw.githubusercontent.com/openfootball/football.json/master"
_OF_SA_RAW = "https://raw.githubusercontent.com/openfootball/south-america/master"
_FCSV_RAW = "https://raw.githubusercontent.com/footballcsv/cache.footballdata/master"


def _of_sa_seasons(folder: str, code: str, years: range) -> list[Dataset]:
    """Genera datasets para temporadas de año calendario de openfootball/south-america."""
    out = []
    country_map = {
        "argentina": ("Argentina", "Primera Division"),
        "brazil": ("Brazil", "Serie A"),
        "colombia": ("Colombia", "Primera A"),
        "ecuador": ("Ecuador", "Serie A"),
        "paraguay": ("Paraguay", "Primera Division"),
    }
    country, comp = country_map[folder]
    for y in years:
        out.append(
            Dataset(
                name=f"{country} {comp} {y}",
                country=country,
                competition=comp,
                region="SouthAmerica",
                fmt="openfootball_txt",
                url=f"{_OF_SA_RAW}/{folder}/{y}_{code}.txt",
                season_start=y,
                season_end=y,
                season_label=str(y),
            )
        )
    return out


def _of_copa(folder: str, code: str, comp: str, years: range) -> list[Dataset]:
    out = []
    for y in years:
        out.append(
            Dataset(
                name=f"{comp} {y}",
                country="SouthAmerica",
                competition=comp,
                region="SouthAmerica",
                fmt="openfootball_txt",
                url=f"{_OF_SA_RAW}/{folder}/{y}_{code}.txt",
                season_start=y,
                season_end=y,
                season_label=str(y),
                notes="Competición continental (clubes de varios países).",
            )
        )
    return out


# --------------------------------------------------------------------------- #
#  Definición del registro de fuentes
# --------------------------------------------------------------------------- #
def build_registry() -> dict[str, Source]:
    registry: dict[str, Source] = {}

    # ----------------------------------------------------------------- #
    # 1) openfootball/football.json  ->  JSON limpio y estructurado
    #    Ideal para prototipar un Elo argentino RECIENTE y limpio.
    # ----------------------------------------------------------------- #
    of_json = Source(
        key="openfootball",
        name="openfootball / football.json",
        homepage="https://github.com/openfootball/football.json",
        license_notes="Public Domain (CC0-like, ver repo). Datos abiertos.",
        access_type="download_free",
        data_format="json",
        update_status="activo",
        default_country="Argentina",
        datasets=[
            Dataset("Argentina Primera Division 2025", "Argentina", "Primera Division",
                    "SouthAmerica", "openfootball_json",
                    f"{_OF_JSON_RAW}/2025/ar.1.json", 2025, 2025, "2025"),
            Dataset("Argentina Primera Division 2020", "Argentina", "Primera Division",
                    "SouthAmerica", "openfootball_json",
                    f"{_OF_JSON_RAW}/2020/ar.1.json", 2020, 2020, "2020"),
            Dataset("Brazil Serie A 2025", "Brazil", "Serie A",
                    "SouthAmerica", "openfootball_json",
                    f"{_OF_JSON_RAW}/2025/br.1.json", 2025, 2025, "2025"),
            Dataset("Colombia Primera A 2025", "Colombia", "Primera A",
                    "SouthAmerica", "openfootball_json",
                    f"{_OF_JSON_RAW}/2025/co.1.json", 2025, 2025, "2025"),
            Dataset("Copa Libertadores 2025", "SouthAmerica", "Copa Libertadores",
                    "SouthAmerica", "openfootball_json",
                    f"{_OF_JSON_RAW}/2025/copa.l.json", 2025, 2025, "2025",
                    notes="Competición continental."),
            # Una liga europea limpia, como punto de comparación estructural.
            Dataset("England Premier League 2024-25", "England", "Premier League",
                    "Europe", "openfootball_json",
                    f"{_OF_JSON_RAW}/2024-25/en.1.json", 2024, 2025, "2024-25"),
        ],
    )
    registry[of_json.key] = of_json

    # ----------------------------------------------------------------- #
    # 2) openfootball/south-america  ->  TXT legible (requiere parseo)
    #    Mejor cobertura SUDAMERICANA + Copa Libertadores/Sudamericana.
    # ----------------------------------------------------------------- #
    of_sa = Source(
        key="openfootball_sa",
        name="openfootball / south-america",
        homepage="https://github.com/openfootball/south-america",
        license_notes="Public Domain (ver LICENSE.md del repo). Datos abiertos.",
        access_type="download_free",
        data_format="txt",
        update_status="activo",
        default_country="Argentina",
        datasets=[
            *_of_sa_seasons("argentina", "ar1", range(2018, 2026)),
            *_of_sa_seasons("brazil", "br1", range(2018, 2027)),
            *_of_sa_seasons("colombia", "co1", range(2023, 2026)),
            *_of_sa_seasons("ecuador", "ec1", range(2025, 2026)),
            *_of_sa_seasons("paraguay", "py1", range(2025, 2026)),
            *_of_copa("copa-libertadores", "copal", "Copa Libertadores", range(2012, 2027)),
            *_of_copa("copa-libertadores", "copas", "Copa Sudamericana", range(2012, 2026)),
        ],
    )
    registry[of_sa.key] = of_sa

    # ----------------------------------------------------------------- #
    # 3) footballcsv / cache.footballdata  ->  CSV estándar limpio
    #    No tiene Argentina (cubre Europa + México), pero es la
    #    referencia de CSV limpio y de gran profundidad histórica
    #    (1993-94 en adelante). Útil como patrón y comparación.
    # ----------------------------------------------------------------- #
    fcsv = Source(
        key="footballcsv",
        name="footballcsv / cache.footballdata",
        homepage="https://github.com/footballcsv/cache.footballdata",
        license_notes="Mirror de football-data.co.uk en formato footballcsv. "
                      "Uso libre con atribución; revisar términos de la fuente original.",
        access_type="download_free",
        data_format="csv",
        update_status="mixto",
        default_country="England",
        datasets=[
            Dataset("England Premier League 2021-22", "England", "Premier League",
                    "Europe", "footballcsv",
                    f"{_FCSV_RAW}/2021-22/eng.1.csv", 2021, 2022, "2021-22"),
            Dataset("England Premier League 1993-94", "England", "Premier League",
                    "Europe", "footballcsv",
                    f"{_FCSV_RAW}/1993-94/eng.1.csv", 1993, 1994, "1993-94",
                    notes="Temporada más antigua disponible -> profundidad histórica."),
            Dataset("Spain La Liga 2021-22", "Spain", "La Liga",
                    "Europe", "footballcsv",
                    f"{_FCSV_RAW}/2021-22/es.1.csv", 2021, 2022, "2021-22"),
            Dataset("Mexico Liga MX 2021-22", "Mexico", "Liga MX",
                    "NorthAmerica", "footballcsv",
                    f"{_FCSV_RAW}/2021-22/mx.1.csv", 2021, 2022, "2021-22"),
        ],
    )
    registry[fcsv.key] = fcsv

    # ----------------------------------------------------------------- #
    # 4) football-data.co.uk  ->  CSV con columnas ricas (resultados,
    #    cuotas). Tiene Argentina en /new/ARG.csv. En ESTE entorno suele
    #    estar bloqueado por la política de red (403); se registra igual
    #    y el flujo no se rompe si falla.
    # ----------------------------------------------------------------- #
    fduk = Source(
        key="footballdata_uk",
        name="football-data.co.uk",
        homepage="https://www.football-data.co.uk/argentina.php",
        license_notes="Gratuito para uso personal/no comercial. Revisar términos del sitio.",
        access_type="network_restricted",
        data_format="csv",
        update_status="activo",
        default_country="Argentina",
        datasets=[
            Dataset("Argentina (extra leagues, todas las temporadas)", "Argentina",
                    "Primera Division", "SouthAmerica", "csv",
                    "https://www.football-data.co.uk/new/ARG.csv", 2012, 2025, "2012-2025",
                    notes="Archivo único multi-temporada. Puede estar bloqueado por red."),
        ],
    )
    registry[fduk.key] = fduk

    # ----------------------------------------------------------------- #
    # 5) FBref  ->  solo inspección liviana de tablas HTML públicas.
    #    NO scraping agresivo. Opcional.
    # ----------------------------------------------------------------- #
    fbref = Source(
        key="fbref",
        name="FBref (StatsBomb) — opcional, inspección liviana",
        homepage="https://fbref.com/en/comps/21/Primera-Division-Stats",
        license_notes="Datos de StatsBomb vía FBref. Uso sujeto a términos del sitio. "
                      "Solo inspección liviana de tablas públicas.",
        access_type="optional_scrape",
        data_format="html",
        update_status="activo",
        default_country="Argentina",
        datasets=[
            Dataset("Argentina Primera Division (scores & fixtures)", "Argentina",
                    "Primera Division", "SouthAmerica", "html",
                    "https://fbref.com/en/comps/21/schedule/Primera-Division-Scores-and-Fixtures",
                    notes="Incluye xG en temporadas recientes. Tabla HTML; parseo opcional."),
        ],
    )
    registry[fbref.key] = fbref

    # ----------------------------------------------------------------- #
    # 6) Kaggle  ->  opcional, requiere autenticación (API key).
    #    Se documenta como fuente manual; no se descarga automáticamente.
    # ----------------------------------------------------------------- #
    kaggle = Source(
        key="kaggle",
        name="Kaggle datasets (opcional, requiere cuenta)",
        homepage="https://www.kaggle.com/datasets?search=argentina+football",
        license_notes="Licencia variable por dataset. Requiere autenticación (kaggle.json).",
        access_type="manual_auth",
        data_format="csv",
        update_status="mixto",
        default_country="Argentina",
        datasets=[
            Dataset("Argentina football datasets (varios)", "Argentina",
                    "Varias", "SouthAmerica", "csv",
                    None, None, None, None,
                    notes="Descarga manual: kaggle datasets download <slug>. No automatizado."),
        ],
    )
    registry[kaggle.key] = kaggle

    return registry


REGISTRY = build_registry()


def get_source(key: str) -> Source:
    if key not in REGISTRY:
        raise KeyError(
            f"Fuente desconocida: '{key}'. Disponibles: {', '.join(REGISTRY)}"
        )
    return REGISTRY[key]
