"""Gemma 4 local vía llama-cpp-python (GGUF, GPU con CUDA). Carga perezosa y liberable."""

from __future__ import annotations

import gc
import threading
from collections.abc import Callable
from pathlib import Path

from medguia.domain.puertos import AlRecibirToken, Mensaje

TEMPERATURA = 0.1
MAX_TOKENS_RESPUESTA = 1024


class GemmaLocal:
    nombre = "gemma-local"

    def __init__(
        self,
        ruta_gguf: Path,
        n_ctx: int = 8192,
        n_gpu_capas: int = -1,
        fabrica: Callable[..., object] | None = None,
    ) -> None:
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
                    n_ctx=self._n_ctx,
                    n_batch=min(self._n_ctx, 2048),  # prefill más rápido con contextos largos
                    n_gpu_layers=self._n_gpu_capas,
                    flash_attn=True,
                    verbose=False,
                )
        return self._llm

    def generar(self, mensajes: list[Mensaje], al_recibir_token: AlRecibirToken | None = None) -> str:
        with self._lock:
            llm = self._cargar()
            partes: list[str] = []
            flujo = llm.create_chat_completion(
                messages=_mensajes_para_api(mensajes),
                temperature=TEMPERATURA,
                max_tokens=MAX_TOKENS_RESPUESTA,
                stream=True,
            )
            for trozo in flujo:
                texto = trozo["choices"][0].get("delta", {}).get("content")
                if texto:
                    partes.append(texto)
                    if al_recibir_token:
                        al_recibir_token(texto)
            return "".join(partes)

    def liberar(self) -> None:
        with self._lock:
            self._llm = None
        gc.collect()


def _mensajes_para_api(mensajes: list[Mensaje]) -> list[dict[str, str]]:
    """La plantilla de chat de Gemma no garantiza el rol «system»: se funde con el primer mensaje de usuario."""
    sistema = "\n\n".join(m.texto for m in mensajes if m.rol == "system")
    resto = [m for m in mensajes if m.rol != "system"]
    if sistema and resto and resto[0].rol == "user":
        resto = [Mensaje("user", f"{sistema}\n\n{resto[0].texto}"), *resto[1:]]
    return [{"role": m.rol, "content": m.texto} for m in resto]
