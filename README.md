# Control de espacio (Voronoi) — Final Mundial 2022 · Argentina vs Francia

Análisis del **espacio controlado** por cada equipo con **datos StatsBomb 360** de la final del
Mundial Qatar 2022 (`match_id = 3869685`), usando diagramas de **Voronoi** (enfoque *Soccermatics*).

Se calcula el control de espacio en los **10 minutos previos a cada gol, hasta el gol**, y **solo
para el primer tiempo**. Los dos goles del 1er tiempo (ambos de Argentina):

| # | Minuto | Jugador | Tipo | Control medio en la ventana |
|---|--------|---------|------|------------------------------|
| 1 | 22:24 | Messi | Penal | Argentina 46.6% · Francia 53.4% |
| 2 | 35:22 | Di María | Jugada | Argentina 44.6% · Francia 55.4% |

## Cómo correrlo (rápido)

```bash
pip install -r requirements.txt
jupyter notebook voronoi_final_2022.ipynb     # o: jupyter nbconvert --to notebook --execute --inplace voronoi_final_2022.ipynb
```

El notebook descarga los datos (con caché en `data/`) y regenera las figuras en `output/`.

## Cómo bajarlo y ejecutarlo paso a paso (para quien no usa Python a menudo)

> No hace falta saber programar: son comandos para copiar y pegar.

### 1. Instalar Python
- **Windows:** descargá Python desde <https://www.python.org/downloads/> y, al instalar,
  **tildá la casilla "Add Python to PATH"** antes de "Install Now".
- **Mac:** ya suele venir Python, pero conviene instalar el oficial desde el mismo link.

Para comprobar que quedó instalado, abrí una terminal:
- Windows: menú Inicio → escribí `cmd` → Enter.
- Mac: Spotlight (lupa) → escribí `Terminal` → Enter.

y escribí (en Windows usá `python`, en Mac `python3`):
```bash
python --version
```
Tiene que aparecer algo como `Python 3.11.x`.

### 2. Bajar este proyecto
**Opción fácil (sin git):** entrá a la página del repositorio en GitHub, botón verde
**`Code` → `Download ZIP`**, y descomprimí el ZIP en una carpeta (p. ej. el Escritorio).

**Opción con git** (si lo tenés instalado):
```bash
git clone <URL-del-repositorio>
```

### 3. Entrar a la carpeta del proyecto
En la terminal, "entrá" a la carpeta que descargaste con `cd` (cambiar directorio):
```bash
cd Desktop/Stats_futbol        # ajustá la ruta a donde lo hayas dejado
```
Tip: en Windows podés escribir `cd ` (con espacio) y arrastrar la carpeta a la terminal.

### 4. Instalar las librerías que usa el análisis
```bash
pip install -r requirements.txt
```
(En Mac, si `pip` no funciona, probá `pip3`.) Esto baja todo lo necesario una sola vez.

### 5. Abrir el notebook
```bash
jupyter notebook
```
Se abre el navegador con una lista de archivos: hacé clic en **`voronoi_final_2022.ipynb`**.
Una vez abierto, en el menú elegí **`Run → Run All Cells`** (Ejecutar todo). Va corriendo
las celdas de arriba hacia abajo; al terminar vas a ver los GIFs dentro del notebook y los
archivos nuevos en la carpeta `output/`.

> La primera vez descarga los datos de StatsBomb (necesitás internet) y tarda 1–2 minutos.
> Las siguientes veces usa la copia guardada en `data/` y va más rápido.

### ¿No querés instalar nada?
Podés abrir el notebook directo en el navegador con **Google Colab**: entrá a
<https://colab.research.google.com>, `Archivo → Subir notebook`, elegí
`voronoi_final_2022.ipynb` y, en la primera celda, agregá una línea
`!pip install mplsoccer shapely statsbombpy` antes de ejecutar todo.

## Resultados (`output/`)

- `voronoi_gol1_messi.gif` — animación Voronoi, 10' previos al penal de Messi.
- `voronoi_gol2_dimaria.gif` — animación Voronoi, 10' previos al gol de Di María.
- `control_timeseries.png` — evolución del % de control frame a frame en cada ventana.

## Metodología

- Los datos **360 no son tracking continuo**: son *freeze frames* con las posiciones de los
  jugadores **visibles por la cámara en el instante de cada evento**. El "control durante 10
  minutos" se construye como una **secuencia de Voronoi** (uno por freeze frame) → animación.
- Cada celda de Voronoi se **recorta al `visible_area`** del frame y el % de control se mide
  **relativo a la zona efectivamente observada**, no a toda la cancha. Es la práctica recomendada
  por StatsBomb/Soccermatics para evitar inflar el control con zonas sin datos.
- Se **excluyen los arqueros**; solo jugadores de campo.
- El Voronoi se recorta a los límites de la cancha con `mplsoccer.Pitch.voronoi` y la intersección
  con el área visible se hace con `shapely`.

**Limitaciones:** Voronoi *posicional* simple (sin velocidades), no un modelo dinámico de
*pitch control*. La cobertura depende del encuadre de cámara de cada evento.

## Fuente de datos

[StatsBomb Open Data](https://github.com/statsbomb/open-data) — uso sujeto a su licencia.
