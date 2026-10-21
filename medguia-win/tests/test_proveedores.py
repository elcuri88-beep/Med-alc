import json
from pathlib import Path

import httpx
import pytest

from medguia.domain.puertos import Mensaje
from medguia.providers.embedding_local import PREFIJO_CONSULTA, PREFIJO_DOCUMENTO, EmbeddingGemmaLocal
from medguia.providers.gemma_local import GemmaLocal
from medguia.providers.openai_compatible import ApiCompatibleOpenAI, ErrorApi
from medguia.persistence.store import DimensionesIncompatibles


class _FlujoFalso:
    def __init__(self) -> None:
        self.kwargs: dict = {}

    def create_chat_completion(self, **kwargs):
        self.kwargs = kwargs
        for trozo in ["**Respuesta", " breve:**", " ok"]:
            yield {"choices": [{"delta": {"content": trozo}}]}


def test_gemma_fusiona_el_sistema_y_streamea() -> None:
    llm = _FlujoFalso()
    gemma = GemmaLocal(Path("modelo.gguf"), fabrica=lambda _ruta: llm)
    tokens: list[str] = []

    texto = gemma.generar(
        [Mensaje("system", "REGLAS"), Mensaje("user", "PREGUNTA")], al_recibir_token=tokens.append
    )

    assert texto == "**Respuesta breve:** ok"
    assert tokens == ["**Respuesta", " breve:**", " ok"]
    assert llm.kwargs["temperature"] == 0.1
    assert llm.kwargs["messages"] == [{"role": "user", "content": "REGLAS\n\nPREGUNTA"}]


def test_gemma_liberar_descarga_el_modelo() -> None:
    cargas: list[int] = []

    def fabrica(_ruta):
        cargas.append(1)
        return _FlujoFalso()

    gemma = GemmaLocal(Path("modelo.gguf"), fabrica=fabrica)
    gemma.generar([Mensaje("user", "x")])
    gemma.liberar()
    gemma.generar([Mensaje("user", "x")])

    assert len(cargas) == 2


class _EmbeddingFalso:
    def __init__(self, dimensiones: int) -> None:
        self.dimensiones = dimensiones
        self.entradas: list[str] = []

    def create_embedding(self, texto: str):
        self.entradas.append(texto)
        return {"data": [{"embedding": [3.0] + [0.0] * (self.dimensiones - 1)}]}


def test_embeddings_usan_prefijos_oficiales_y_normalizan() -> None:
    llm = _EmbeddingFalso(4)
    emb = EmbeddingGemmaLocal(Path("e.gguf"), dimensiones=4, fabrica=lambda _r: llm)

    vector = emb.consulta("aspirina")
    documento = emb.documentos([("Guía HTA", "texto")])

    assert llm.entradas[0] == PREFIJO_CONSULTA + "aspirina"
    assert llm.entradas[1] == PREFIJO_DOCUMENTO.format(titulo="Guía HTA", texto="texto")
    assert vector == pytest.approx([1.0, 0.0, 0.0, 0.0])
    assert documento[0] == pytest.approx([1.0, 0.0, 0.0, 0.0])


def test_embeddings_con_dimension_inesperada_fallan() -> None:
    emb = EmbeddingGemmaLocal(Path("e.gguf"), dimensiones=8, fabrica=lambda _r: _EmbeddingFalso(4))

    with pytest.raises(DimensionesIncompatibles):
        emb.consulta("x")


def _transporte_sse(recibidos: list[httpx.Request]) -> httpx.MockTransport:
    def manejador(request: httpx.Request) -> httpx.Response:
        recibidos.append(request)
        eventos = [
            {"choices": [{"delta": {"content": "Hola"}}]},
            {"choices": [{"delta": {"content": " mundo"}}]},
        ]
        cuerpo = "".join(f"data: {json.dumps(e)}\n\n" for e in eventos) + "data: [DONE]\n\n"
        return httpx.Response(200, text=cuerpo, headers={"content-type": "text/event-stream"})

    return httpx.MockTransport(manejador)


def test_api_compatible_envia_la_clave_y_streamea() -> None:
    recibidos: list[httpx.Request] = []
    cliente = httpx.Client(transport=_transporte_sse(recibidos))
    api = ApiCompatibleOpenAI("modelo", lambda: "sk-test", cliente=cliente)
    tokens: list[str] = []

    texto = api.generar([Mensaje("user", "pregunta")], al_recibir_token=tokens.append)

    assert texto == "Hola mundo"
    assert tokens == ["Hola", " mundo"]
    assert recibidos[0].headers["Authorization"] == "Bearer sk-test"
    assert json.loads(recibidos[0].content)["temperature"] == 0.1


def test_api_compatible_sin_clave_falla_antes_de_enviar() -> None:
    recibidos: list[httpx.Request] = []
    api = ApiCompatibleOpenAI("modelo", lambda: "", cliente=httpx.Client(transport=_transporte_sse(recibidos)))

    with pytest.raises(ErrorApi):
        api.generar([Mensaje("user", "x")])
    assert recibidos == []
