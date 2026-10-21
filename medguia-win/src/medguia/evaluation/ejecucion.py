"""Ejecuta la evaluación para una lista de modelos. Lo usan la CLI y la pestaña de Evaluación."""

from __future__ import annotations

from collections.abc import Callable

from medguia.evaluation.metricas import ResumenModelo, evaluar_modelo
from medguia.evaluation.preguntas import PreguntaEvaluacion
from medguia.generation.responder import Responder
from medguia.ingestion.tokens import ContadorAproximado
from medguia.persistence.store import Store
from medguia.providers.gemma_local import GemmaLocal
from medguia.retrieval.busqueda import Recuperador
from medguia.ui.servicios import ModeloNoInstalado, Servicios

AlProgresar = Callable[[str, int, int], None]


def evaluar_configuraciones(
    servicios: Servicios,
    preguntas: list[PreguntaEvaluacion],
    claves: list[str],
    al_progresar: AlProgresar | None = None,
) -> list[ResumenModelo]:
    embedder = servicios.embedder()
    if embedder is None:
        raise ModeloNoInstalado("Falta EmbeddingGemma. Descárgalo en Ajustes antes de evaluar.")
    resumenes: list[ResumenModelo] = []
    store = Store(servicios.ruta_bd)
    try:
        recuperador = Recuperador(store, embedder, umbral_similitud=servicios.ajustes.umbral_similitud)
        for clave in claves:
            if not servicios.instalado(clave):
                raise ModeloNoInstalado(f"Falta el modelo «{servicios.catalogo[clave].nombre}».")
            nombre = servicios.catalogo[clave].nombre
            llm = GemmaLocal(servicios.ruta(clave), n_ctx=servicios.ajustes.n_ctx)
            responder = Responder(recuperador, llm, ContadorAproximado(), servicios.perfil())
            try:
                resumenes.append(
                    evaluar_modelo(
                        nombre,
                        preguntas,
                        recuperador,
                        responder,
                        al_progresar=(lambda i, n, nombre=nombre: al_progresar(nombre, i, n)) if al_progresar else None,
                    )
                )
            finally:
                llm.liberar()
    finally:
        store.cerrar()
    return resumenes
