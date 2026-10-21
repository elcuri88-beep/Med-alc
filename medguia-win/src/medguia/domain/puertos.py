"""Puertos: contratos que implementan los proveedores (LLM, embeddings). El dominio no conoce llama.cpp ni HTTP."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

Rol = Literal["system", "user", "assistant"]
AlRecibirToken = Callable[[str], None]


@dataclass(frozen=True)
class Mensaje:
    rol: Rol
    texto: str


class LLMProvider(Protocol):
    nombre: str

    def generar(self, mensajes: list[Mensaje], al_recibir_token: AlRecibirToken | None = None) -> str:
        """Genera la respuesta completa, notificando cada fragmento de texto en streaming."""
        ...

    def liberar(self) -> None:
        """Descarga el modelo de memoria. Debe ser seguro llamarlo varias veces."""
        ...


class Embedder(Protocol):
    nombre: str
    dimensiones: int

    def documentos(self, elementos: list[tuple[str, str]]) -> list[list[float]]:
        """Vectores de documentos. Cada elemento es (título, texto indexado)."""
        ...

    def consulta(self, texto: str) -> list[float]:
        """Vector de una pregunta del usuario."""
        ...
