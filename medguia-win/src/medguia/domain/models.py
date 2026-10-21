"""Entidades del dominio. Sin dependencias de PDF, SQLite ni UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Ambito(StrEnum):
    LOCAL = "local"
    NACIONAL = "nacional"
    EUROPEO = "europeo"


class EstadoDocumento(StrEnum):
    PENDIENTE = "pendiente"
    INDEXANDO = "indexando"
    LISTO = "listo"
    ERROR = "error"


@dataclass(frozen=True)
class MetaDocumento:
    """Metadatos editables por el usuario."""

    titulo: str
    sociedad: str
    anio: int
    ambito: Ambito
    especialidad: str

    def __post_init__(self) -> None:
        if not self.titulo.strip():
            raise ValueError("El título no puede estar vacío")
        if not 1900 <= self.anio <= 2100:
            raise ValueError(f"Año no válido: {self.anio}")


@dataclass(frozen=True)
class FragmentoNuevo:
    """Fragmento antes de persistir. `texto_indexado` antepone los metadatos al texto."""

    orden: int
    seccion: str
    pagina_inicio: int
    pagina_fin: int
    es_tabla: bool
    texto: str
    texto_indexado: str


@dataclass(frozen=True)
class EstadisticasIndexado:
    paginas: int
    fragmentos: int
    segundos: float

    @property
    def segundos_por_pagina(self) -> float:
        return self.segundos / self.paginas if self.paginas else 0.0
