"""Descarga, verificación, borrado y recomendación de modelos GGUF.

Los repositorios de Hugging Face del catálogo están SIN CONFIGURAR a propósito: no se han podido
verificar desde el entorno de desarrollo. Se pueden fijar en `modelos.json` dentro de la carpeta de datos:

    {"gemma-e4b": {"repo": "usuario/repo", "archivo": "modelo.gguf", "sha256": "..."}}
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

import httpx

GEMMA_E4B = "gemma-e4b"
GEMMA_E2B = "gemma-e2b"
EMBEDDING_GEMMA = "embeddinggemma"
FICHERO_CONFIG = "modelos.json"
UMBRAL_RAM_E4B_GB = 16
UMBRAL_VRAM_E4B_GB = 8

Progreso = Callable[[int, int], None]


class ModeloNoConfigurado(Exception):
    pass


class IntegridadFallida(Exception):
    pass


@dataclass(frozen=True)
class ModeloDescargable:
    clave: str
    nombre: str
    repo: str | None
    archivo: str
    sha256: str | None
    tamano_aprox_gb: float

    @property
    def url(self) -> str:
        if not self.repo:
            raise ModeloNoConfigurado(
                f"«{self.nombre}» no tiene repositorio configurado. "
                f"Añádelo a {FICHERO_CONFIG} en la carpeta de datos."
            )
        return f"https://huggingface.co/{self.repo}/resolve/main/{self.archivo}"


CATALOGO: dict[str, ModeloDescargable] = {
    GEMMA_E4B: ModeloDescargable(GEMMA_E4B, "Gemma 4 E4B (por defecto)", None, "gemma-4-e4b-it-Q4_K_M.gguf", None, 5.0),
    GEMMA_E2B: ModeloDescargable(GEMMA_E2B, "Gemma 4 E2B (ligero)", None, "gemma-4-e2b-it-Q4_K_M.gguf", None, 3.0),
    EMBEDDING_GEMMA: ModeloDescargable(
        EMBEDDING_GEMMA, "EmbeddingGemma", None, "embeddinggemma-300m-Q8_0.gguf", None, 0.4
    ),
}


def cargar_catalogo(carpeta_datos: Path) -> dict[str, ModeloDescargable]:
    """Aplica las sobrescrituras de modelos.json sobre el catálogo base."""
    ruta = carpeta_datos / FICHERO_CONFIG
    if not ruta.exists():
        return dict(CATALOGO)
    sobrescrituras = json.loads(ruta.read_text(encoding="utf-8"))
    catalogo = dict(CATALOGO)
    for clave, valores in sobrescrituras.items():
        if clave in catalogo:
            catalogo[clave] = replace(catalogo[clave], **{k: v for k, v in valores.items() if k in {"repo", "archivo", "sha256"}})
    return catalogo


def ruta_modelo(carpeta: Path, modelo: ModeloDescargable) -> Path:
    return carpeta / modelo.archivo


def instalado(carpeta: Path, modelo: ModeloDescargable) -> bool:
    return ruta_modelo(carpeta, modelo).exists()


def descargar(
    modelo: ModeloDescargable,
    carpeta: Path,
    progreso: Progreso | None = None,
    cliente: httpx.Client | None = None,
) -> Path:
    """Descarga a un .part, verifica el SHA-256 y solo entonces renombra. Sin hash publicado, guarda el propio."""
    destino = ruta_modelo(carpeta, modelo)
    carpeta.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".part")
    digest = hashlib.sha256()
    propio = cliente is None
    cliente = cliente or httpx.Client(timeout=60, follow_redirects=True)
    try:
        with cliente.stream("GET", modelo.url) as respuesta:
            respuesta.raise_for_status()
            total = int(respuesta.headers.get("content-length", 0))
            recibido = 0
            with temporal.open("wb") as archivo:
                for bloque in respuesta.iter_bytes(chunk_size=1 << 20):
                    archivo.write(bloque)
                    digest.update(bloque)
                    recibido += len(bloque)
                    if progreso:
                        progreso(recibido, total)
    finally:
        if propio:
            cliente.close()

    calculado = digest.hexdigest()
    if modelo.sha256 and calculado != modelo.sha256:
        temporal.unlink(missing_ok=True)
        raise IntegridadFallida(f"SHA-256 no coincide para {modelo.archivo}")
    temporal.replace(destino)
    _guardar_hash_local(destino, calculado)
    return destino


def verificar(modelo: ModeloDescargable, carpeta: Path) -> bool:
    """Compara con el SHA-256 publicado o, si no hay, con el guardado al descargar."""
    destino = ruta_modelo(carpeta, modelo)
    if not destino.exists():
        return False
    esperado = modelo.sha256 or _leer_hash_local(destino)
    if esperado is None:
        return False
    return _sha256(destino) == esperado


def borrar(modelo: ModeloDescargable, carpeta: Path) -> bool:
    destino = ruta_modelo(carpeta, modelo)
    existia = destino.exists()
    destino.unlink(missing_ok=True)
    _hash_local(destino).unlink(missing_ok=True)
    return existia


def recomendar_llm(ram_gb: float, vram_gb: float | None) -> str:
    """E4B si hay RAM y VRAM suficientes; E2B en otro caso. Sin datos de VRAM, decide la RAM."""
    if ram_gb >= UMBRAL_RAM_E4B_GB and (vram_gb is None or vram_gb >= UMBRAL_VRAM_E4B_GB):
        return GEMMA_E4B
    return GEMMA_E2B


def ram_total_gb() -> float:
    import psutil

    return psutil.virtual_memory().total / (1024**3)


def vram_total_gb() -> float | None:
    """Memoria de la GPU NVIDIA principal, o None si no se puede leer."""
    import shutil
    import subprocess

    herramienta = shutil.which("nvidia-smi")
    if herramienta is None:
        return None
    try:
        salida = subprocess.run(
            [herramienta, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
        return float(salida.strip().splitlines()[0]) / 1024
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None


def _sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _hash_local(destino: Path) -> Path:
    return destino.with_suffix(destino.suffix + ".sha256")


def _guardar_hash_local(destino: Path, digest: str) -> None:
    _hash_local(destino).write_text(digest, encoding="utf-8")


def _leer_hash_local(destino: Path) -> str | None:
    ruta = _hash_local(destino)
    return ruta.read_text(encoding="utf-8").strip() if ruta.exists() else None
