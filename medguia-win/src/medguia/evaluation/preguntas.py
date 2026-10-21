"""Carga y validación del conjunto de preguntas de prueba (JSON)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class PreguntasNoValidas(ValueError):
    pass


@dataclass(frozen=True)
class PreguntaEvaluacion:
    id: str
    pregunta: str
    cubierta: bool
    documento: str | None  # título exacto del documento que responde
    pagina: int | None  # página esperada (PDF o impresa)


def cargar(ruta: Path) -> list[PreguntaEvaluacion]:
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, list) or not datos:
        raise PreguntasNoValidas("El archivo debe contener una lista no vacía de preguntas")
    return [_validar(entrada, indice) for indice, entrada in enumerate(datos, start=1)]


def _validar(entrada: dict, indice: int) -> PreguntaEvaluacion:
    etiqueta = f"pregunta {indice}"
    if not isinstance(entrada, dict):
        raise PreguntasNoValidas(f"{etiqueta}: debe ser un objeto")
    pregunta = entrada.get("pregunta")
    if not isinstance(pregunta, str) or not pregunta.strip():
        raise PreguntasNoValidas(f"{etiqueta}: falta el campo «pregunta»")
    cubierta = entrada.get("cubierta", True)
    if not isinstance(cubierta, bool):
        raise PreguntasNoValidas(f"{etiqueta}: «cubierta» debe ser true o false")
    documento = entrada.get("documento")
    pagina = entrada.get("pagina")
    if cubierta and (not isinstance(documento, str) or not isinstance(pagina, int)):
        raise PreguntasNoValidas(f"{etiqueta}: las preguntas cubiertas necesitan «documento» y «pagina»")
    return PreguntaEvaluacion(
        id=str(entrada.get("id", indice)),
        pregunta=pregunta.strip(),
        cubierta=cubierta,
        documento=documento if cubierta else None,
        pagina=pagina if cubierta else None,
    )
