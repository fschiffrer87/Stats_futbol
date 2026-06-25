# Control de espacio (Voronoi) — Final Mundial 2022 · Argentina vs Francia

Análisis del **espacio controlado** por cada equipo con **datos StatsBomb 360** de la final del
Mundial Qatar 2022 (`match_id = 3869685`), usando diagramas de **Voronoi** (enfoque *Soccermatics*).

Se calcula el control de espacio en los **10 minutos previos a cada gol, hasta el gol**, y **solo
para el primer tiempo**. Los dos goles del 1er tiempo (ambos de Argentina):

| # | Minuto | Jugador | Tipo | Control medio en la ventana |
|---|--------|---------|------|------------------------------|
| 1 | 22:24 | Messi | Penal | Argentina 46.6% · Francia 53.4% |
| 2 | 35:22 | Di María | Jugada | Argentina 44.6% · Francia 55.4% |

## Cómo correrlo

```bash
pip install -r requirements.txt
jupyter notebook voronoi_final_2022.ipynb     # o: jupyter nbconvert --to notebook --execute --inplace voronoi_final_2022.ipynb
```

El notebook descarga los datos (con caché en `data/`) y regenera las figuras en `output/`.

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
