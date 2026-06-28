# Elo de clubes — Etapa 1: Descubrimiento y preparación de fuentes

Primera etapa de un proyecto para calcular un **Elo/rating histórico de clubes**,
empezando por **Argentina** y diseñado para extenderse a **Sudamérica**
(Copa Libertadores, Copa Sudamericana y ligas regionales).

> ⚠️ **Esta etapa NO calcula el Elo.** Es una herramienta de **exploración y
> preparación de fuentes gratuitas**: busca, registra, inspecciona, perfila y
> evalúa fuentes de datos de partidos, y prepara la **normalización a un esquema
> común** que alimentará el modelo Elo más adelante.

El modelo Elo posterior podrá incorporar localía, diferencia de gol, importancia
de la competición, regresión a la media, ascensos/descensos e inflación/deflación.
Nada de eso se implementa todavía.

---

## Estructura del proyecto

```
elo_data_discovery/
├── README.md
├── requirements.txt
├── src/
│   ├── discover_data.py   # CLI principal (todos los comandos)
│   ├── sources.py         # registro modular de fuentes (declarativo)
│   ├── fetcher.py         # descarga liviana + cache + errores
│   ├── readers.py         # lectores CSV / JSON / TXT / HTML
│   ├── normalizer.py      # normalización al esquema común
│   ├── profiler.py        # perfilado (columnas, cobertura, equipos, problemas)
│   └── scoring.py         # scores de aptitud para Elo
├── data/
│   ├── raw/cache/         # cache local de descargas (no se versiona)
│   └── processed/         # datos normalizados (etapas futuras)
└── outputs/               # inventarios, perfiles, muestras y reportes
```

## Instalación

```bash
cd elo_data_discovery
pip install -r requirements.txt
```

Dependencias: `pandas`, `requests`, `beautifulsoup4`, `lxml`, `tqdm`,
`python-dateutil`.

---

## Comandos (CLI)

Todos se ejecutan desde la carpeta `elo_data_discovery/`:

| # | Comando | Qué hace |
|---|---------|----------|
| 1 | `python src/discover_data.py --list-sources` | Lista las fuentes configuradas |
| 2 | `python src/discover_data.py --source openfootball --list-available` | Datasets/temporadas de una fuente |
| 3 | `python src/discover_data.py --source footballcsv --sample 20` | Muestra cruda (→ `outputs/sample_<source>.csv`) |
| 4 | `python src/discover_data.py --source footballcsv --profile` | Perfil de columnas/cobertura (→ `outputs/profile_<source>.json`) |
| 5 | `python src/discover_data.py --all --inventory` | Inventario completo (→ `outputs/source_inventory.csv`) |
| 6 | `python src/discover_data.py --source footballcsv --normalize-sample` | Muestra normalizada (→ `outputs/normalized_sample_<source>.csv`) |
| 7 | `python src/discover_data.py --all --elo-readiness` | Ranking de aptitud para Elo (→ `outputs/elo_readiness_report.csv`) |
| 8 | `python src/discover_data.py --country Argentina --historical-search` | Busca datasets históricos argentinos |
| 9 | `python src/discover_data.py --region SouthAmerica --list-available` | Datasets sudamericanos por país/competición |

Flags: `--force-refresh` (ignora cache), `--country NAME` (condiciona la
elección de dataset).

### Prueba rápida (Argentina, todo en vivo)

```bash
python src/discover_data.py --source openfootball --sample 10
python src/discover_data.py --source openfootball --profile
python src/discover_data.py --source openfootball --normalize-sample
python src/discover_data.py --all --elo-readiness
```

---

## Fuentes configuradas

| key | Fuente | Formato | Acceso | Cobertura relevante |
|-----|--------|---------|--------|---------------------|
| `openfootball` | [openfootball/football.json](https://github.com/openfootball/football.json) | JSON | libre | Argentina/Brasil/Colombia/Libertadores (reciente, **muy limpio**) |
| `openfootball_sa` | [openfootball/south-america](https://github.com/openfootball/south-america) | TXT | libre | Argentina 2018→2025, Brasil, Colombia, Ecuador, Paraguay, **Copa Libertadores y Sudamericana 2012→2026** |
| `footballcsv` | [footballcsv/cache.footballdata](https://github.com/footballcsv/cache.footballdata) | CSV | libre | Europa + México, **1993→2023** (referencia de profundidad histórica; no incluye Argentina) |
| `footballdata_uk` | [football-data.co.uk](https://www.football-data.co.uk/argentina.php) | CSV | restringido | Argentina multi-temporada con columnas ricas (⚠️ bloqueado por la política de red de este entorno) |
| `fbref` | [FBref](https://fbref.com) | HTML | opcional | Argentina con xG (solo inspección liviana; sin scraping agresivo) |
| `kaggle` | Kaggle datasets | CSV | manual | Varios (requiere `kaggle.json`; no automatizado) |

> **Nota sobre acceso de red:** en este entorno, `football-data.co.uk`, `fbref`
> y Kaggle están bloqueados (proxy 403 / login). La herramienta los registra
> igualmente, **no rompe el flujo** y deja constancia en `outputs/errors.log`.
> Las fuentes `openfootball*` y `footballcsv` sí descargan en vivo.

---

## Esquema común (objetivo para el Elo)

`date · season · competition · country · home_team · away_team · home_goals ·
away_goals · neutral · stage · round · source · source_file · notes`

Si una fuente no tiene una variable, la columna se crea con `None` y se reporta
en la metadata del perfil / inventario.

**Variables mínimas para calcular Elo:** equipo local, equipo visitante, goles
local, goles visitante (+ fecha o al menos temporada y orden del partido).

## Scoring

- **`elo_readiness_score` (0–100):** +30 fecha clara, +20 local/visitante,
  +20 goles, +10 competición, +10 temporada, +5 cancha neutral, +5 cobertura
  histórica alta; con penalizaciones por faltantes, encoding, duplicados y
  formatos difíciles. El desglose por fuente queda en
  `outputs/elo_readiness_report.csv` (columna `score_breakdown`).
- **`historical_depth_score`:** `alto` (>20 años), `medio` (8–20), `bajo` (<8).
- **`cleanliness_score`:** `alto` (CSV/JSON estructurado), `medio` (parseo
  simple, p. ej. el TXT de openfootball), `bajo` (scraping HTML).

---

## Resultados de la evaluación (resumen)

Ejecutando `--all --elo-readiness` (datos en vivo de las fuentes accesibles):

| source | país | formato | readiness | profundidad | limpieza |
|--------|------|---------|-----------|-------------|----------|
| footballcsv | Europa | csv | **95** | alto | alto |
| openfootball_sa | Argentina/SA | txt | **90** | medio | medio |
| openfootball | Argentina | json | **84** | bajo | alto |
| footballdata_uk | Argentina | csv | 0¹ | medio | alto |
| fbref | Argentina | html | 0¹ | — | bajo |
| kaggle | Argentina | csv | 0¹ | — | alto |

¹ No descargables en este entorno → puntaje 0 por falta de inspección real.

**Recomendaciones de la herramienta:**

- **Elo argentino reciente y limpio →** `openfootball` (JSON estructurado,
  240 partidos/temporada, equipos y goles completos, fechas ISO).
- **Elo histórico largo (referencia de profundidad) →** `footballcsv` (CSV
  limpio desde 1993; para *Argentina* histórica real, la vía es
  `football-data.co.uk` o Kaggle, hoy fuera de alcance por red/credenciales).
- **Extensión sudamericana →** `openfootball_sa` (ligas regionales + Copa
  Libertadores y Sudamericana 2012→2026, con detección de fase
  grupos/eliminación).

---

## Outputs generados

- `outputs/source_inventory.csv` — inventario completo de fuentes.
- `outputs/elo_readiness_report.csv` — ranking de aptitud + desglose de score.
- `outputs/sample_<source>.csv` — muestra cruda por fuente.
- `outputs/profile_<source>.json` — perfil (columnas, tipos, faltantes,
  primeras/últimas fechas, equipos, competiciones, nº de partidos, problemas de
  formato/encoding/duplicados).
- `outputs/normalized_sample_<source>.csv` — muestra en el esquema común.
- `outputs/errors.log` — errores de descarga/parseo (no interrumpen el flujo).

---

## Limitaciones conocidas

- En este entorno solo descargan en vivo `openfootball*` y `footballcsv`; el
  resto queda documentado pero sin inspección real.
- La profundidad histórica **alta** para Argentina (>20 años) requiere
  `football-data.co.uk`/Kaggle (acceso no disponible aquí). openfootball llega
  bien hasta ~2012–2018.
- Los nombres de clubes **no están unificados todavía** (p. ej. "River Plate"
  vs siglas, equipos con "(URU)"/"(BOL)" en copas). Eso es trabajo de la etapa
  siguiente (diccionario de alias).
- `neutral` no viene marcado por ninguna fuente; habrá que derivarlo (finales
  de copa en cancha neutral) más adelante.
- Las estimaciones de partidos/equipos en el inventario son aproximadas
  (extrapolan desde un dataset representativo × nº de archivos).

## Próximos pasos (de exploración a cálculo del Elo)

1. Consolidar un dataset normalizado **multi-temporada de Argentina**
   (openfootball south-america 2018→2025) en `data/processed/`.
2. Construir un **diccionario de alias de clubes** para unificar nombres entre
   fuentes y temporadas.
3. Ordenar partidos cronológicamente y **validar continuidad temporal**
   (gaps/duplicados entre temporadas).
4. Definir parámetros del **modelo Elo**: K, ventaja de localía, ajuste por
   diferencia de gol, peso por importancia de competición.
5. Tratar **ascensos/descensos**: rating inicial de equipos nuevos y regresión
   a la media entre temporadas.
6. Sumar **competiciones continentales** (Libertadores/Sudamericana) con mayor
   peso y manejo de cancha neutral en finales.
7. **Validar** el Elo contra resultados conocidos (campeones, rachas) antes de
   extender a toda Sudamérica.
8. (Opcional) Integrar `football-data.co.uk` / Kaggle para profundidad
   histórica >20 años cuando haya acceso de red/credenciales, y scraping
   liviano de tablas públicas de FBref para xG.
