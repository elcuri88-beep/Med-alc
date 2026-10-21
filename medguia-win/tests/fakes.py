"""Dobles de prueba: embedder determinista basado en tokens y LLM que devuelve un guion fijo."""

from __future__ import annotations

import math
import re
import zlib

from medguia.domain.puertos import AlRecibirToken, Mensaje


class EmbedderFalso:
    """Textos con palabras comunes tienen vectores parecidos. Sin palabras en común, similitud ~0."""

    nombre = "embedder-falso"

    def __init__(self, dimensiones: int = 256) -> None:
        self.dimensiones = dimensiones

    def _vector(self, texto: str) -> list[float]:
        valor = [0.0] * self.dimensiones
        for palabra in re.findall(r"\w+", texto.lower()):
            valor[zlib.crc32(palabra.encode()) % self.dimensiones] += 1.0
        norma = math.sqrt(sum(x * x for x in valor)) or 1.0
        return [x / norma for x in valor]

    def documentos(self, elementos: list[tuple[str, str]]) -> list[list[float]]:
        return [self._vector(texto) for _, texto in elementos]

    def consulta(self, texto: str) -> list[float]:
        return self._vector(texto)


class LLMFalso:
    nombre = "llm-falso"

    def __init__(self, respuesta: str) -> None:
        self.respuesta = respuesta
        self.llamadas: list[list[Mensaje]] = []
        self.liberado = 0

    def generar(self, mensajes: list[Mensaje], al_recibir_token: AlRecibirToken | None = None) -> str:
        self.llamadas.append(mensajes)
        if al_recibir_token:
            for trozo in re.findall(r"\S+\s*", self.respuesta):
                al_recibir_token(trozo)
        return self.respuesta

    def liberar(self) -> None:
        self.liberado += 1
