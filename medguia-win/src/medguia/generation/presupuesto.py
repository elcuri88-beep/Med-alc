"""Presupuesto de contexto: cuántos fragmentos caben en la ventana del modelo activo."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from medguia.ingestion.tokens import ContadorTokens
from medguia.retrieval.busqueda import Candidato

TOKENS_SEGURIDAD = 128


@dataclass(frozen=True)
class PerfilContexto:
    """Ventana del modelo activo. En la RTX 5080 con E4B: n_ctx de 8192 (ver ajustes del LLM)."""

    n_ctx: int
    reserva_respuesta: int = 1024
    margen: int = TOKENS_SEGURIDAD


def presupuesto_fragmentos(
    perfil: PerfilContexto,
    contar: ContadorTokens,
    texto_fijo: str,
) -> int:
    """Tokens disponibles para fragmentos. `texto_fijo` son las reglas y la pregunta."""
    return perfil.n_ctx - perfil.reserva_respuesta - perfil.margen - contar(texto_fijo)


def seleccionar(
    candidatos: list[Candidato],
    coste: Callable[[Candidato], int],
    presupuesto: int,
) -> list[Candidato]:
    """Toma candidatos en orden de relevancia mientras quepan en el presupuesto."""
    elegidos: list[Candidato] = []
    usado = 0
    for candidato in candidatos:
        tokens = coste(candidato)
        if usado + tokens > presupuesto:
            break
        elegidos.append(candidato)
        usado += tokens
    return elegidos
