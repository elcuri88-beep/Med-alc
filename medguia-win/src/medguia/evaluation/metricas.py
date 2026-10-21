"""Métricas de evaluación: acierto de recuperación en el top 5, acierto de cita y latencias."""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass, field

from medguia.evaluation.memoria import MedidorMemoria, PicoMemoria
from medguia.evaluation.preguntas import PreguntaEvaluacion
from medguia.generation.prompt import pagina_citada
from medguia.generation.responder import Responder
from medguia.generation.verificador import citas_de
from medguia.retrieval.busqueda import Candidato, Recuperador

TOP_K = 5


@dataclass(frozen=True)
class ResultadoPregunta:
    id: str
    acierto_recuperacion: bool | None  # None si la pregunta no está cubierta
    acierto_cita: bool | None
    cubierta_respondida: bool
    segundos_primer_token: float | None
    segundos_total: float
    problemas: int


@dataclass(frozen=True)
class ResumenModelo:
    modelo: str
    recuperacion_top5: float | None
    acierto_cita: float | None
    no_cubiertas_acertadas: float | None
    primer_token_mediana_s: float | None
    total_mediana_s: float
    pico: PicoMemoria
    preguntas: list[ResultadoPregunta] = field(default_factory=list)


def _coincide(candidato: Candidato, titulo: str, pagina: int) -> bool:
    if candidato.documento.meta.titulo != titulo:
        return False
    fragmento = candidato.fragmento
    paginas_pdf = range(fragmento.pagina_inicio, fragmento.pagina_fin + 1)
    return pagina in paginas_pdf or pagina == pagina_citada(candidato)


def evaluar_pregunta(
    pregunta: PreguntaEvaluacion,
    recuperador: Recuperador,
    responder: Responder,
) -> ResultadoPregunta:
    recuperacion = recuperador.buscar(pregunta.pregunta)
    respuesta = responder.responder(pregunta.pregunta)

    if pregunta.cubierta:
        acierto_recuperacion = any(
            _coincide(c, pregunta.documento, pregunta.pagina)
            for c in recuperacion.candidatos[:TOP_K]
        )
        acierto_cita = any(
            ref.titulo == pregunta.documento and ref.pagina == pregunta.pagina
            for ref in citas_de(respuesta.texto)
        )
        cubierta_respondida = respuesta.cubierta
    else:
        acierto_recuperacion = None
        acierto_cita = None
        cubierta_respondida = respuesta.cubierta

    return ResultadoPregunta(
        id=pregunta.id,
        acierto_recuperacion=acierto_recuperacion,
        acierto_cita=acierto_cita,
        cubierta_respondida=cubierta_respondida,
        segundos_primer_token=respuesta.segundos_primer_token,
        segundos_total=respuesta.segundos_total,
        problemas=len(respuesta.problemas),
    )


def evaluar_modelo(
    nombre: str,
    preguntas: list[PreguntaEvaluacion],
    recuperador: Recuperador,
    responder: Responder,
    al_progresar: Callable[[int, int], None] | None = None,
) -> ResumenModelo:
    resultados: list[ResultadoPregunta] = []
    with MedidorMemoria() as medidor:
        for indice, pregunta in enumerate(preguntas, start=1):
            resultados.append(evaluar_pregunta(pregunta, recuperador, responder))
            if al_progresar:
                al_progresar(indice, len(preguntas))
    return resumir(nombre, resultados, medidor.pico())


def resumir(nombre: str, resultados: list[ResultadoPregunta], pico: PicoMemoria) -> ResumenModelo:
    cubiertas = [r for r in resultados if r.acierto_recuperacion is not None]
    no_cubiertas = [r for r in resultados if r.acierto_recuperacion is None]
    primeros = [r.segundos_primer_token for r in resultados if r.segundos_primer_token is not None]
    return ResumenModelo(
        modelo=nombre,
        recuperacion_top5=_proporcion(r.acierto_recuperacion for r in cubiertas),
        acierto_cita=_proporcion(r.acierto_cita for r in cubiertas),
        no_cubiertas_acertadas=_proporcion(not r.cubierta_respondida for r in no_cubiertas),
        primer_token_mediana_s=statistics.median(primeros) if primeros else None,
        total_mediana_s=statistics.median(r.segundos_total for r in resultados) if resultados else 0.0,
        pico=pico,
        preguntas=resultados,
    )


def _proporcion(valores) -> float | None:
    lista = [bool(v) for v in valores]
    return sum(lista) / len(lista) if lista else None
