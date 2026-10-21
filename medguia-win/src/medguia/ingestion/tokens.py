"""Contador de tokens. Sustituible por el tokenizador real de Gemma en la Fase 2."""

from __future__ import annotations

import math
from typing import Protocol


class ContadorTokens(Protocol):
    def __call__(self, texto: str) -> int: ...


class ContadorAproximado:
    """Estimación de ~4 caracteres por token. Suficiente para trocear; no para el presupuesto del LLM."""

    def __call__(self, texto: str) -> int:
        return max(1, math.ceil(len(texto) / 4))
