"""Rutas de datos de la app. En Windows: %LOCALAPPDATA%\\MedGuia. MEDGUIA_HOME la sobrescribe."""

from __future__ import annotations

import os
from pathlib import Path


def carpeta_datos() -> Path:
    configurada = os.environ.get("MEDGUIA_HOME")
    if configurada:
        return Path(configurada)
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "MedGuia"
    return Path.home() / ".medguia"


def ruta_base_datos() -> Path:
    return carpeta_datos() / "biblioteca.sqlite"
