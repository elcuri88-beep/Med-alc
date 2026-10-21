"""Verificación determinista de la respuesta del LLM. No confía en el modelo para las reglas 2 y 7.

- Cada párrafo con contenido clínico debe llevar una cita [Documento, año, página] que
  corresponda a un fragmento recuperado.
- Cada cifra con unidad o símbolo de comparación debe aparecer literalmente en los fragmentos citados.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from medguia.retrieval.busqueda import Candidato

CITA = re.compile(r"\[([^\[\]]+)\]")
ANIO = re.compile(r"\b(?:19|20)\d{2}\b")
PAGINA = re.compile(r"\bp(?:p)?\.?\s*(\d+)(?:\s*[-–]\s*(\d+))?", re.IGNORECASE)
CIFRA_CON_UNIDAD = re.compile(
    r"(?:(?:[<>≤≥]=?|≥|≤)\s*)?(\d+(?:[.,]\d+)?)\s*"
    r"(?:mg/dl|mmol/l|mmhg|mcg|µg|mg|ml|%|kg|g|h|min|minutos?|horas?|días?|semanas?|meses|años|ui|u\b|lpm|bpm|/min)",
    re.IGNORECASE,
)
FRASE_NO_CUBIERTA = "Las guías disponibles no cubren"
MINIMO_CARACTERES_CLINICOS = 30
CABECERA = re.compile(r"^\*\*[^*]+:\*\*\s*$")


@dataclass(frozen=True)
class Problema:
    tipo: str  # "sin_cita" | "cita_no_encontrada" | "cifra_no_verificada"
    detalle: str


def verificar(respuesta: str, candidatos: list[Candidato]) -> list[Problema]:
    if FRASE_NO_CUBIERTA in respuesta:
        return []

    problemas: list[Problema] = []
    for linea in _lineas_de_contenido(respuesta):
        sin_citas = CITA.sub("", linea)
        citados = _fragmentos_citados(linea, candidatos, problemas)

        if not CITA.search(linea) and len(sin_citas.strip()) >= MINIMO_CARACTERES_CLINICOS:
            problemas.append(Problema("sin_cita", linea[:120]))

        textos = " ".join(c.fragmento.texto for c in citados)
        for cifra in _cifras(sin_citas):
            if not _aparece(cifra, textos):
                problemas.append(Problema("cifra_no_verificada", cifra))
    return problemas


def _lineas_de_contenido(respuesta: str) -> list[str]:
    lineas = []
    for bruta in respuesta.splitlines():
        linea = bruta.strip().lstrip("-*•").strip()
        if not linea or CABECERA.match(linea):
            continue
        lineas.append(linea)
    return lineas


def _fragmentos_citados(
    linea: str,
    candidatos: list[Candidato],
    problemas: list[Problema],
) -> list[Candidato]:
    encontrados: list[Candidato] = []
    for cita in CITA.findall(linea):
        anio = ANIO.search(cita)
        pagina = PAGINA.search(cita)
        coincidencias = [
            c
            for c in candidatos
            if c.documento.meta.titulo.lower() in cita.lower()
            and (anio is None or int(anio.group(0)) == c.documento.meta.anio)
            and _pagina_en_rango(c, cita, pagina)
        ]
        if not coincidencias:
            problemas.append(Problema("cita_no_encontrada", f"[{cita}]"))
        encontrados.extend(coincidencias)
    return encontrados


def _pagina_en_rango(candidato: Candidato, cita: str, pagina: re.Match[str] | None) -> bool:
    if pagina is None:
        return False
    inicio = int(pagina.group(1))
    fin = int(pagina.group(2) or inicio)
    impresa = candidato.documento.paginas_impresas.get(candidato.fragmento.pagina_inicio)
    pagina_citada = int(impresa) if impresa and impresa.isdigit() else candidato.fragmento.pagina_inicio
    paginas_pdf = range(candidato.fragmento.pagina_inicio, candidato.fragmento.pagina_fin + 1)
    cubiertas = set(paginas_pdf) | {pagina_citada}
    return any(p in cubiertas for p in range(min(inicio, fin), max(inicio, fin) + 1))


def _cifras(texto: str) -> list[str]:
    return [m.group(1) for m in CIFRA_CON_UNIDAD.finditer(texto)]


def _aparece(cifra: str, texto: str) -> bool:
    normalizada = cifra.replace(",", ".")
    patron = r"(?<![\d.,])" + re.escape(normalizada) + r"(?![\d])"
    texto_normalizado = texto.replace(",", ".")
    return re.search(patron, texto_normalizado) is not None
