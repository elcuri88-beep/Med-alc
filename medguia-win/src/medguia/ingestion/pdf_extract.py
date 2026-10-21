"""Extracción de texto y tablas por página con PyMuPDF.

Las tablas se devuelven como bloques atómicos para que el troceado nunca las parta.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

# Encabezados multinivel ("4.2 Tratamiento") o numerados seguidos de mayúscula ("3. Diagnóstico").
ENCABEZADO_NUMERADO = re.compile(r"^\d+(\.\d+)+\.?\s+\S|^\d+\.\s+[A-ZÁÉÍÓÚÑ]")
NUMERO_SUELTO = re.compile(r"^\d{1,4}$")
MAX_LONGITUD_ENCABEZADO = 160
FLAG_NEGRITA = 16  # bit de negrita en los flags de span de PyMuPDF


@dataclass(frozen=True)
class Bloque:
    pagina: int
    texto: str
    es_tabla: bool = False
    encabezado: bool = False


@dataclass
class Extraccion:
    paginas_total: int
    bloques: list[Bloque] = field(default_factory=list)
    paginas_sin_texto: list[int] = field(default_factory=list)
    paginas_impresas: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _Linea:
    texto: str
    tamano: float
    negrita: bool
    caja: pymupdf.Rect


def extraer(
    ruta: Path,
    progreso: Callable[[int, int], None] | None = None,
) -> Extraccion:
    with pymupdf.open(ruta) as pdf:
        tamano_cuerpo = _tamano_cuerpo(pdf)
        resultado = Extraccion(paginas_total=pdf.page_count)
        for indice, pagina in enumerate(pdf, start=1):
            _extraer_pagina(pagina, indice, tamano_cuerpo, resultado)
            if progreso:
                progreso(indice, pdf.page_count)
    return resultado


def _tamano_cuerpo(pdf: pymupdf.Document) -> float:
    """Tamaño de letra más frecuente, ponderado por número de caracteres."""
    contador: Counter[float] = Counter()
    for pagina in pdf:
        for linea in _lineas(pagina):
            contador[round(linea.tamano, 1)] += len(linea.texto)
    return contador.most_common(1)[0][0] if contador else 10.0


def _extraer_pagina(
    pagina: pymupdf.Page,
    numero: int,
    tamano_cuerpo: float,
    resultado: Extraccion,
) -> None:
    tablas = pagina.find_tables().tables
    cajas_tabla = [pymupdf.Rect(t.bbox) for t in tablas]
    lineas = [
        linea
        for linea in _lineas(pagina)
        if not any(_dentro(linea.caja, caja) for caja in cajas_tabla)
    ]

    alto = pagina.rect.height
    elementos: list[tuple[float, Bloque | _Linea]] = []
    for tabla, caja in zip(tablas, cajas_tabla):
        elementos.append((caja.y0, Bloque(numero, _texto_tabla(pagina, tabla), es_tabla=True)))
    for linea in lineas:
        if linea.caja.y0 > alto * 0.9 and NUMERO_SUELTO.match(linea.texto):
            resultado.paginas_impresas[numero] = linea.texto
            continue
        elementos.append((linea.caja.y0, linea))
    elementos.sort(key=lambda par: par[0])

    parrafo: list[str] = []
    ultima_caja: pymupdf.Rect | None = None
    ultimo_tamano = tamano_cuerpo

    def vaciar() -> None:
        if parrafo:
            resultado.bloques.append(Bloque(numero, " ".join(parrafo)))
            parrafo.clear()

    for _, elemento in elementos:
        if isinstance(elemento, Bloque):
            vaciar()
            ultima_caja = None
            resultado.bloques.append(elemento)
            continue

        if _es_encabezado(elemento, tamano_cuerpo):
            vaciar()
            resultado.bloques.append(Bloque(numero, elemento.texto, encabezado=True))
            ultima_caja = elemento.caja
            ultimo_tamano = elemento.tamano
            continue

        separacion_grande = (
            ultima_caja is not None
            and elemento.caja.y0 - ultima_caja.y1 > ultimo_tamano * 1.8
        )
        if separacion_grande:
            vaciar()
        parrafo.append(elemento.texto)
        ultima_caja = elemento.caja
        ultimo_tamano = elemento.tamano
    vaciar()

    if not resultado.bloques or all(b.pagina != numero for b in resultado.bloques):
        resultado.paginas_sin_texto.append(numero)


def _lineas(pagina: pymupdf.Page) -> list[_Linea]:
    lineas: list[_Linea] = []
    datos = pagina.get_text("dict")
    for bloque in datos["blocks"]:
        if bloque.get("type") != 0:
            continue
        for linea in bloque["lines"]:
            spans = [s for s in linea["spans"] if s["text"].strip()]
            if not spans:
                continue
            texto = " ".join("".join(s["text"] for s in spans).split())
            tamano = max(s["size"] for s in spans)
            negrita = all(s["flags"] & FLAG_NEGRITA for s in spans)
            lineas.append(_Linea(texto, tamano, negrita, pymupdf.Rect(linea["bbox"])))
    return lineas


def _es_encabezado(linea: _Linea, tamano_cuerpo: float) -> bool:
    texto = linea.texto
    if len(texto) > MAX_LONGITUD_ENCABEZADO:
        return False
    if ENCABEZADO_NUMERADO.match(texto):
        return True
    if linea.tamano >= tamano_cuerpo + 1.5:
        return True
    return linea.negrita and len(texto) <= 80 and not texto.endswith(".")


def _texto_tabla(pagina: pymupdf.Page, tabla: pymupdf.table.Table) -> str:
    """Texto por celda leído con get_text(clip). table.extract() pierde espacios ("5 mg" -> "5mg")."""
    filas = []
    for fila in tabla.rows:
        celdas = []
        for caja in fila.cells:
            if caja is None:
                celdas.append("")
                continue
            celdas.append(" ".join(pagina.get_text("text", clip=pymupdf.Rect(caja)).split()))
        filas.append(" | ".join(celdas))
    return "\n".join(filas)


def _dentro(caja: pymupdf.Rect, contenedor: pymupdf.Rect) -> bool:
    centro = caja.tl + (caja.br - caja.tl) * 0.5
    return contenedor.contains(centro)
