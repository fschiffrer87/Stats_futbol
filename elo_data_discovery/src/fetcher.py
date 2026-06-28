"""
Descarga liviana y respetuosa con cache local.

Principios (según los requisitos del proyecto):
    - Cache local en data/raw/cache/.
    - No volver a descargar si el archivo ya existe (salvo --force-refresh).
    - Pausa entre requests.
    - User-agent descriptivo.
    - Captura de errores HTTP -> outputs/errors.log.
    - Sin crawling profundo; una URL = un archivo.
    - Si una fuente falla, NO se rompe el flujo (se devuelve None).
"""

from __future__ import annotations

import hashlib
import time
import datetime as _dt
from pathlib import Path
from typing import Optional

# requests es la librería preferida; si no está, caemos a urllib.
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:  # pragma: no cover
    import urllib.request
    import urllib.error
    _HAS_REQUESTS = False


USER_AGENT = (
    "elo-data-discovery/0.1 (proyecto educativo de Elo de clubes; "
    "contacto: franciscoschiffrer@gmail.com)"
)

# Pausa mínima entre requests reales (segundos) para no golpear servidores.
POLITE_DELAY_SECONDS = 1.0

_LAST_REQUEST_TS = 0.0


def _project_root() -> Path:
    # src/ -> raíz del proyecto
    return Path(__file__).resolve().parent.parent


def cache_dir() -> Path:
    d = _project_root() / "data" / "raw" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def outputs_dir() -> Path:
    d = _project_root() / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def errors_log_path() -> Path:
    return outputs_dir() / "errors.log"


def log_error(context: str, message: str) -> None:
    """Registra un error sin interrumpir el flujo."""
    ts = _dt.datetime.now().isoformat(timespec="seconds")
    line = f"[{ts}] {context}: {message}\n"
    try:
        with open(errors_log_path(), "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass  # nunca rompemos por no poder loguear
    # Eco discreto a consola para visibilidad.
    print(f"  ⚠️  {context}: {message}")


def _cache_filename(url: str) -> Path:
    """Nombre de cache estable derivado de la URL (hash + sufijo legible)."""
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    tail = url.rstrip("/").split("/")[-1] or "index"
    tail = "".join(c if c.isalnum() or c in "._-" else "_" for c in tail)[:50]
    return cache_dir() / f"{h}__{tail}"


def _respect_delay() -> None:
    global _LAST_REQUEST_TS
    now = time.time()
    wait = POLITE_DELAY_SECONDS - (now - _LAST_REQUEST_TS)
    if wait > 0:
        time.sleep(wait)
    _LAST_REQUEST_TS = time.time()


def fetch(url: Optional[str], *, force_refresh: bool = False,
          context: str = "fetch") -> Optional[bytes]:
    """
    Devuelve el contenido en bytes de `url`, usando cache local.

    - Si `url` es None -> devuelve None (fuente manual).
    - Si está cacheado y no se fuerza refresco -> lee de disco (sin request).
    - Si falla -> loguea y devuelve None (no rompe el flujo).
    """
    if not url:
        return None

    cache_file = _cache_filename(url)
    if cache_file.exists() and not force_refresh:
        try:
            return cache_file.read_bytes()
        except Exception as exc:
            log_error(context, f"no se pudo leer cache {cache_file.name}: {exc}")
            # seguimos e intentamos descargar

    _respect_delay()
    try:
        data = _http_get(url)
    except Exception as exc:
        log_error(context, f"fallo al descargar {url}: {exc}")
        return None

    try:
        cache_file.write_bytes(data)
    except Exception as exc:
        log_error(context, f"no se pudo escribir cache {cache_file.name}: {exc}")
    return data


def _http_get(url: str, timeout: int = 30) -> bytes:
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if _HAS_REQUESTS:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    else:  # pragma: no cover
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()


def is_cached(url: Optional[str]) -> bool:
    if not url:
        return False
    return _cache_filename(url).exists()
