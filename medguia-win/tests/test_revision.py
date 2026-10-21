"""Regresiones de la revisión: cada test reproduce un fallo real encontrado antes de corregirlo."""

import sys
import types
from pathlib import Path

import pymupdf
import pytest

from medguia.domain.models import Ambito, FragmentoNuevo, MetaDocumento
from medguia.generation.verificador import verificar
from medguia.ingestion.pdf_extract import extraer
from medguia.persistence.store import DocumentoRegistrado, FilaFragmento, Store
from medguia.providers.embedding_local import EmbeddingGemmaLocal
from medguia.retrieval.busqueda import Candidato, FiltroBusqueda, Recuperador, terminos_de_busqueda
from medguia.ui.servicios import Ajustes
from tests.fakes import EmbedderFalso

META = MetaDocumento("Guía HTA", "ESC", 2024, Ambito.EUROPEO, "Cardiología")


# --- extracción -------------------------------------------------------------

@pytest.fixture
def pdf_dos_columnas(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    for n in range(1, 6):
        pagina = doc.new_page()
        pagina.insert_text((72, 40), "Guia ESC 2024 - Hipertension", fontsize=8)  # cabecera repetida
        pagina.insert_text((72, 100), f"IZQ-{n}-A primera linea izquierda.", fontsize=10)
        pagina.insert_text((72, 114), f"IZQ-{n}-B segunda linea izquierda.", fontsize=10)
        pagina.insert_text((330, 100), f"DER-{n}-A primera linea derecha.", fontsize=10)
        pagina.insert_text((330, 114), f"DER-{n}-B segunda linea derecha.", fontsize=10)
        pagina.insert_text((72, 128), "la hiper-", fontsize=10)
        pagina.insert_text((72, 142), "tension se define", fontsize=10)
    ruta = tmp_path / "dos_columnas.pdf"
    doc.save(ruta)
    return ruta


def test_dos_columnas_se_leen_una_detras_de_otra(pdf_dos_columnas: Path) -> None:
    textos = [b.texto for b in extraer(pdf_dos_columnas).bloques if b.pagina == 1]

    izquierda = next(t for t in textos if "IZQ-1-A" in t)
    derecha = next(t for t in textos if "DER-1-A" in t)
    assert "DER" not in izquierda and "IZQ" not in derecha
    assert izquierda.index("IZQ-1-A") < izquierda.index("IZQ-1-B")


def test_cabecera_repetida_se_descarta(pdf_dos_columnas: Path) -> None:
    textos = " ".join(b.texto for b in extraer(pdf_dos_columnas).bloques)

    assert "Guia ESC 2024" not in textos


def test_palabra_partida_por_guion_se_une(pdf_dos_columnas: Path) -> None:
    textos = " ".join(b.texto for b in extraer(pdf_dos_columnas).bloques if b.pagina == 1)

    assert "hipertension se define" in textos and "hiper- " not in textos


# --- verificador ------------------------------------------------------------

def _candidatos(texto: str) -> list[Candidato]:
    documento = DocumentoRegistrado(1, META, Path("g.pdf"), "x", 10, (), {}, None, None, "")
    fragmento = FilaFragmento(1, 1, 0, "S", 3, 3, False, texto, texto)
    return [Candidato(fragmento, documento, 0.1, 0.9)]


def test_linea_de_fuentes_no_es_un_falso_positivo() -> None:
    respuesta = (
        "La PA objetivo es 130/80 mmHg [Guía HTA, 2024, p. 3].\n"
        "**Fuentes:** Guía HTA de la Sociedad Europea de Cardiología (2024)"
    )

    assert verificar(respuesta, _candidatos("Objetivo 130/80 mmHg en la mayoría de pacientes.")) == []


def test_decir_que_no_cubren_no_desactiva_la_verificacion_de_cifras() -> None:
    respuesta = (
        "La dosis es 999 mg [Guía HTA, 2024, p. 3].\n"
        "Las guías disponibles no cubren el embarazo."
    )

    problemas = verificar(respuesta, _candidatos("Dosis de 50 mg al día."))

    assert [(p.tipo, p.detalle) for p in problemas] == [("cifra_no_verificada", "999")]


def test_laguna_sin_cifras_no_pide_cita() -> None:
    respuesta = "Las guías disponibles no cubren el ajuste de dosis en insuficiencia renal grave."

    assert verificar(respuesta, _candidatos("Dosis de 50 mg al día.")) == []


@pytest.mark.parametrize(
    ("respuesta", "esperadas"),
    [
        ("Objetivo 130/80 mmHg [Guía HTA, 2024, p. 3].", []),
        ("Objetivo 140/90 mmHg [Guía HTA, 2024, p. 3].", ["140", "90"]),
        ("Dosis 5-10 mg [Guía HTA, 2024, p. 3].", ["10"]),
    ],
)
def test_se_comprueban_todos_los_numeros_de_presiones_y_rangos(respuesta: str, esperadas: list[str]) -> None:
    problemas = verificar(respuesta, _candidatos("Objetivo 130/80 mmHg. Dosis de 5 mg."))

    assert [p.detalle for p in problemas if p.tipo == "cifra_no_verificada"] == esperadas


# --- recuperación -----------------------------------------------------------

def test_un_filtro_no_deja_sin_resultados_por_estar_fuera_del_top_k(tmp_path: Path) -> None:
    store = Store(tmp_path / "b.sqlite", dimensiones=256)
    emb = EmbedderFalso()
    textos_a = ["presión objetivo hipertensos tratamiento"] * 50
    doc_a = store.insertar_documento(META, tmp_path / "a.pdf", "a")
    meta_b = MetaDocumento("Protocolo local", "Local", 2025, Ambito.LOCAL, "Atención Primaria")
    doc_b = store.insertar_documento(meta_b, tmp_path / "b.pdf", "b")
    for doc, titulo, textos in ((doc_a, "HTA", textos_a), (doc_b, "Local", ["presión objetivo"])):
        store.reemplazar_fragmentos(
            doc, [FragmentoNuevo(i, "S", 1, 1, False, t, t) for i, t in enumerate(textos)], 1, []
        )
        store.guardar_vectores([(f.id, emb.consulta(f.texto)) for f in store.fragmentos(doc)])
    recuperador = Recuperador(store, emb, umbral_similitud=0.0, k_candidatos=5, max_por_documento=50)

    sin_filtro = recuperador.buscar("presión objetivo hipertensos tratamiento")
    con_filtro = recuperador.buscar(
        "presión objetivo hipertensos tratamiento", FiltroBusqueda(sociedades=frozenset({"Local"}))
    )

    assert all(c.documento.meta.sociedad == "ESC" for c in sin_filtro.candidatos)
    assert [c.documento.meta.sociedad for c in con_filtro.candidatos] == ["Local"]
    store.cerrar()


def test_palabras_vacias_se_quitan_de_la_busqueda_lexica() -> None:
    assert terminos_de_busqueda("¿Cuál es el objetivo de la presión en los diabéticos?") == "objetivo presión diabéticos?"
    assert terminos_de_busqueda("de la en") == "de la en"


# --- embeddings con llama.cpp ------------------------------------------------

def test_embedder_configura_lotes_de_la_ventana_y_trunca_entradas_enormes(monkeypatch) -> None:
    creados: list[dict] = []
    entradas: list[str] = []

    class LlamaFalso:
        def __init__(self, **kwargs) -> None:
            creados.append(kwargs)

        def create_embedding(self, texto: str):
            entradas.append(texto)
            return {"data": [{"embedding": [1.0, 0.0]}]}

    monkeypatch.setitem(sys.modules, "llama_cpp", types.SimpleNamespace(Llama=LlamaFalso))
    embedder = EmbeddingGemmaLocal(Path("modelos/emb-q8.gguf"), dimensiones=2, n_ctx=100)

    embedder.documentos([("Guía", "x" * 10_000)])

    assert creados[0]["n_batch"] == 100 and creados[0]["n_ubatch"] == 100
    assert len(entradas[0]) == 300
    assert embedder.nombre == "embeddinggemma:emb-q8.gguf"


# --- diagnóstico de cobertura -----------------------------------------------

def test_respuesta_sin_cobertura_explica_la_similitud_y_el_umbral(tmp_path: Path) -> None:
    from medguia.generation.presupuesto import PerfilContexto
    from medguia.generation.responder import Responder
    from medguia.ingestion.tokens import ContadorAproximado
    from tests.fakes import LLMFalso

    store = Store(tmp_path / "b.sqlite", dimensiones=256)
    emb = EmbedderFalso()
    doc = store.insertar_documento(META, tmp_path / "a.pdf", "a")
    store.reemplazar_fragmentos(doc, [FragmentoNuevo(0, "S", 1, 1, False, "dieta baja en sal", "dieta baja en sal")], 1, [])
    store.guardar_vectores([(f.id, emb.consulta(f.texto)) for f in store.fragmentos(doc)])
    llm = LLMFalso("no debería llamarse")
    responder = Responder(Recuperador(store, emb, umbral_similitud=0.9), llm, ContadorAproximado(), PerfilContexto(8192))

    respuesta = responder.responder("dieta con sal")

    assert not respuesta.cubierta and llm.llamadas == []
    assert respuesta.umbral == 0.9
    assert respuesta.mejor_similitud is not None and respuesta.mejor_similitud < 0.9
    store.cerrar()


def test_umbral_se_guarda_en_los_ajustes(tmp_path: Path) -> None:
    ruta = tmp_path / "ajustes.json"
    Ajustes(umbral_similitud=0.42).guardar(ruta)

    assert Ajustes.cargar(ruta, 32, 16).umbral_similitud == 0.42
