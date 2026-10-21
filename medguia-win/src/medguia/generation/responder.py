"""Pipeline de respuesta: pregunta → recuperación → presupuesto → LLM en streaming → verificación."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from medguia.domain.puertos import AlRecibirToken, LLMProvider
from medguia.generation.prompt import SYSTEM_PROMPT, construir_mensajes, formatear_fragmento
from medguia.generation.presupuesto import PerfilContexto, presupuesto_fragmentos, seleccionar
from medguia.generation.verificador import Problema, verificar
from medguia.ingestion.tokens import ContadorTokens
from medguia.retrieval.busqueda import Candidato, FiltroBusqueda, Recuperador

RESPUESTA_NO_CUBIERTA = "Las guías disponibles no cubren esta pregunta."
RESPUESTA_SIN_CONTEXTO = "Hay fragmentos relevantes, pero no caben en el contexto del modelo activo."


@dataclass(frozen=True)
class Respuesta:
    texto: str
    candidatos: list[Candidato]  # fragmentos realmente enviados al LLM
    cubierta: bool
    problemas: list[Problema]
    segundos_primer_token: float | None
    segundos_total: float


class Responder:
    def __init__(
        self,
        recuperador: Recuperador,
        llm: LLMProvider,
        contar: ContadorTokens,
        perfil: PerfilContexto,
        anio_actual: Callable[[], int] = lambda: date.today().year,
    ) -> None:
        self._recuperador = recuperador
        self._llm = llm
        self._contar = contar
        self._perfil = perfil
        self._anio_actual = anio_actual

    def responder(
        self,
        pregunta: str,
        filtro: FiltroBusqueda | None = None,
        al_recibir_token: AlRecibirToken | None = None,
    ) -> Respuesta:
        inicio = time.perf_counter()
        recuperacion = self._recuperador.buscar(pregunta, filtro)

        if not recuperacion.cubierta:
            return Respuesta(
                texto=RESPUESTA_NO_CUBIERTA,
                candidatos=[],
                cubierta=False,
                problemas=[],
                segundos_primer_token=None,
                segundos_total=time.perf_counter() - inicio,
            )

        anio = self._anio_actual()
        fijo = SYSTEM_PROMPT + pregunta
        presupuesto = presupuesto_fragmentos(self._perfil, self._contar, fijo)
        seleccion = seleccionar(
            recuperacion.candidatos,
            coste=lambda c: self._contar(formatear_fragmento(c, anio)),
            presupuesto=presupuesto,
        )
        if not seleccion:
            return Respuesta(
                texto=RESPUESTA_SIN_CONTEXTO,
                candidatos=[],
                cubierta=True,
                problemas=[],
                segundos_primer_token=None,
                segundos_total=time.perf_counter() - inicio,
            )

        primer_token: float | None = None

        def al_token(texto: str) -> None:
            nonlocal primer_token
            if primer_token is None:
                primer_token = time.perf_counter() - inicio
            if al_recibir_token:
                al_recibir_token(texto)

        mensajes = construir_mensajes(pregunta, seleccion, anio)
        texto = self._llm.generar(mensajes, al_token)
        problemas = verificar(texto, seleccion)

        return Respuesta(
            texto=texto,
            candidatos=seleccion,
            cubierta=True,
            problemas=problemas,
            segundos_primer_token=primer_token,
            segundos_total=time.perf_counter() - inicio,
        )
