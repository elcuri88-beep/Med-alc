"""Extracción de texto y tablas por página con PyMuPDF.

- Las tablas se devuelven como bloques atómicos para que el troceado nunca las parta.
- Las páginas a dos columnas se leen columna a columna, no línea a línea.
- Cabeceras y pies repetidos en las páginas se descartan, y los guiones de fin de línea se unen.
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
FRANJA_MARGEN = 0.08  # fracción superior e inferior de la página donde buscar cabeceras y pies
FRACCION_PAGINAS_REPETIDA = 0.4
MINIMO_PAGINAS_PARA_REPETIDAS = 4
ANCHO_MINIMO_COMPLETO = 0.16  # un bloque ocupa «toda la página» si cruza el centro por más de esta fracción


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


@dataclass(frozen=True)
class _Elemento:
    """Una línea de texto o una tabla, con su posición en la página."""

    caja: pymupdf.Rect
    lineas: tuple[_Linea, ...] = ()
    tabla: str | None = None


def extraer(
    ruta: Path,
    progreso: Callable[[int, int], None] | None = None,
) -> Extraccion:
    with pymupdf.open(ruta) as pdf:
        tamano_cuerpo = _tamano_cuerpo(pdf)
        repetidas = _lineas_repetidas(pdf)
        resultado = Extraccion(paginas_total=pdf.page_count)
        for indice, pagina in enumerate(pdf, start=1):
            _extraer_pagina(pagina, indice, tamano_cuerpo, repetidas, resultado)
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


def _clave_repetida(texto: str) -> str:
    return re.sub(r"\d+", "#", texto.lower())


def _en_margen(caja: pymupdf.Rect, alto: float) -> bool:
    return caja.y1 < alto * FRANJA_MARGEN or caja.y0 > alto * (1 - FRANJA_MARGEN)


def _lineas_repetidas(pdf: pymupdf.Document) -> set[str]:
    """Líneas de los márgenes que se repiten en muchas páginas (cabeceras, pies, marcas de agua)."""
    if pdf.page_count < MINIMO_PAGINAS_PARA_REPETIDAS:
        return set()
    paginas_por_clave: Counter[str] = Counter()
    for pagina in pdf:
        vistas = {
            _clave_repetida(linea.texto)
            for linea in _lineas(pagina)
            if _en_margen(linea.caja, pagina.rect.height) and not NUMERO_SUELTO.match(linea.texto)
        }
        paginas_por_clave.update(vistas)
    umbral = max(3, FRACCION_PAGINAS_REPETIDA * pdf.page_count)
    return {clave for clave, n in paginas_por_clave.items() if n >= umbral}


def _extraer_pagina(
    pagina: pymupdf.Page,
    numero: int,
    tamano_cuerpo: float,
    repetidas: set[str],
    resultado: Extraccion,
) -> None:
    alto, ancho = pagina.rect.height, pagina.rect.width
    tablas = pagina.find_tables().tables
    cajas_tabla = [pymupdf.Rect(t.bbox) for t in tablas]

    elementos = [
        _Elemento(caja, tabla=_texto_tabla(pagina, tabla)) for tabla, caja in zip(tablas, cajas_tabla)
    ]
    # Se ordena por línea, no por bloque: PyMuPDF puede agrupar en un mismo bloque líneas de columnas distintas.
    for linea in _lineas(pagina):
        if any(_dentro(linea.caja, caja) for caja in cajas_tabla):
            continue
        if NUMERO_SUELTO.match(linea.texto) and _en_margen(linea.caja, alto):
            resultado.paginas_impresas.setdefault(numero, linea.texto)
            continue
        if _en_margen(linea.caja, alto) and _clave_repetida(linea.texto) in repetidas:
            continue
        elementos.append(_Elemento(linea.caja, lineas=(linea,)))

    parrafo: list[str] = []
    ultima_caja: pymupdf.Rect | None = None
    ultimo_tamano = tamano_cuerpo

    def vaciar() -> None:
        if parrafo:
            resultado.bloques.append(Bloque(numero, _unir_lineas(parrafo)))
            parrafo.clear()

    for elemento in _ordenar(elementos, ancho):
        if elemento.tabla is not None:
            vaciar()
            ultima_caja = None
            resultado.bloques.append(Bloque(numero, elemento.tabla, es_tabla=True))
            continue
        for linea in elemento.lineas:
            if _es_encabezado(linea, tamano_cuerpo):
                vaciar()
                resultado.bloques.append(Bloque(numero, linea.texto, encabezado=True))
                ultima_caja = linea.caja
                ultimo_tamano = linea.tamano
                continue
            cambio_de_columna = ultima_caja is not None and linea.caja.x0 > ultima_caja.x1
            separacion_grande = (
                ultima_caja is not None
                and linea.caja.y0 - ultima_caja.y1 > ultimo_tamano * 1.8
            )
            if cambio_de_columna or separacion_grande:
                vaciar()
            parrafo.append(linea.texto)
            ultima_caja = linea.caja
            ultimo_tamano = linea.tamano
    vaciar()

    if not resultado.bloques or all(b.pagina != numero for b in resultado.bloques):
        resultado.paginas_sin_texto.append(numero)


def _ordenar(elementos: list[_Elemento], ancho: float) -> list[_Elemento]:
    """Orden de lectura: los elementos de ancho completo separan franjas; dentro de una franja con dos
    columnas se lee primero toda la izquierda y luego toda la derecha."""
    medio = ancho / 2
    margen = ancho * ANCHO_MINIMO_COMPLETO / 2
    ordenados: list[_Elemento] = []
    izquierda: list[_Elemento] = []
    derecha: list[_Elemento] = []

    def vaciar() -> None:
        ordenados.extend(sorted(izquierda, key=lambda e: e.caja.y0))
        ordenados.extend(sorted(derecha, key=lambda e: e.caja.y0))
        izquierda.clear()
        derecha.clear()

    for elemento in sorted(elementos, key=lambda e: (e.caja.y0, e.caja.x0)):
        caja = elemento.caja
        if caja.x0 < medio - margen and caja.x1 > medio + margen:
            vaciar()
            ordenados.append(elemento)
        elif (caja.x0 + caja.x1) / 2 < medio:
            izquierda.append(elemento)
        else:
            derecha.append(elemento)
    vaciar()
    return ordenados


def _unir_lineas(lineas: list[str]) -> str:
    """Une líneas de un párrafo. Un guion de fin de línea seguido de minúscula es una palabra partida."""
    texto = ""
    for linea in lineas:
        if texto.endswith("-") and len(texto) > 1 and texto[-2].isalpha() and linea[:1].islower():
            texto = texto[:-1] + linea
        else:
            texto = f"{texto} {linea}" if texto else linea
    return texto


def _lineas(pagina: pymupdf.Page) -> list[_Linea]:
    lineas: list[_Linea] = []
    for bloque in pagina.get_text("dict")["blocks"]:
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
