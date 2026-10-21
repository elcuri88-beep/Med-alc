"""Conversión de la respuesta a texto plano, para pegarla en la historia clínica."""

from __future__ import annotations

import re

_MARCAS = re.compile(r"\*\*|__|`|^#+\s*", re.MULTILINE)


def a_texto_plano(respuesta_markdown: str, lineas_fuentes: list[str]) -> str:
    cuerpo = _MARCAS.sub("", respuesta_markdown).strip()
    if not lineas_fuentes:
        return cuerpo
    fuentes = "\n".join(f"- {linea}" for linea in lineas_fuentes)
    return f"{cuerpo}\n\nFuentes:\n{fuentes}"
