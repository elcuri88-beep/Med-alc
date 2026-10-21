"""EmbeddingGemma local vía llama-cpp-python. Usa los prefijos de tarea oficiales para consulta y documento."""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from pathlib import Path

from medguia.persistence.store import DimensionesIncompatibles

PREFIJO_CONSULTA = "task: search result | query: "
PREFIJO_DOCUMENTO = "title: {titulo} | text: {texto}"
TITULO_SIN_DATO = "none"
CARACTERES_POR_TOKEN_MINIMO = 3  # estimación conservadora para español


class EmbeddingGemmaLocal:
    def __init__(
        self,
        ruta_gguf: Path,
        dimensiones: int = 768,
        n_ctx: int = 2048,
        n_gpu_capas: int = -1,
        fabrica: Callable[..., object] | None = None,
    ) -> None:
        self.dimensiones = dimensiones
        # El nombre incluye el archivo: otro GGUF (otra cuantización) da vectores incompatibles.
        self.nombre = f"embeddinggemma:{ruta_gguf.name}"
        self._ruta = ruta_gguf
        self._n_ctx = n_ctx
        self._n_gpu_capas = n_gpu_capas
        self._fabrica = fabrica
        self._llm = None
        self._lock = threading.Lock()

    def _cargar(self):
        if self._llm is None:
            if self._fabrica is not None:
                self._llm = self._fabrica(self._ruta)
            else:
                from llama_cpp import Llama

                self._llm = Llama(
                    model_path=str(self._ruta),
                    embedding=True,
                    n_ctx=self._n_ctx,
                    n_batch=self._n_ctx,  # con el valor por defecto (512) falla un fragmento de >512 tokens
                    n_ubatch=self._n_ctx,
                    n_gpu_layers=self._n_gpu_capas,
                    verbose=False,
                )
        return self._llm

    def documentos(self, elementos: list[tuple[str, str]]) -> list[list[float]]:
        return [
            self._vector(PREFIJO_DOCUMENTO.format(titulo=titulo or TITULO_SIN_DATO, texto=texto))
            for titulo, texto in elementos
        ]

    def consulta(self, texto: str) -> list[float]:
        return self._vector(f"{PREFIJO_CONSULTA}{texto}")

    def _vector(self, texto: str) -> list[float]:
        # Una tabla atómica puede superar la ventana del modelo: se trunca solo lo que se embebe.
        # El BM25 y el LLM siguen viendo el texto completo.
        texto = texto[: self._n_ctx * CARACTERES_POR_TOKEN_MINIMO]
        with self._lock:
            respuesta = self._cargar().create_embedding(texto)
        valor = respuesta["data"][0]["embedding"]
        if valor and isinstance(valor[0], list):
            valor = _media(valor)
        if len(valor) != self.dimensiones:
            raise DimensionesIncompatibles(
                f"El modelo devuelve {len(valor)} dimensiones; la configuración espera {self.dimensiones}"
            )
        norma = math.sqrt(sum(x * x for x in valor)) or 1.0
        return [x / norma for x in valor]

    def liberar(self) -> None:
        with self._lock:
            self._llm = None


def _media(filas: list[list[float]]) -> list[float]:
    n = len(filas)
    return [sum(columna) / n for columna in zip(*filas)]
