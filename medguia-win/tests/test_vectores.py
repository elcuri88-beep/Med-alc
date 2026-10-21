from pathlib import Path

import pytest

from medguia.domain.models import Ambito, FragmentoNuevo, MetaDocumento
from medguia.ingestion.service import Biblioteca, ModeloDeEmbeddingsDistinto
from medguia.persistence.store import DimensionesIncompatibles, Store
from tests.fakes import EmbedderFalso

META = MetaDocumento("Guía HTA", "ESC", 2024, Ambito.EUROPEO, "Cardiología")


def _fragmento(orden: int, texto: str) -> FragmentoNuevo:
    return FragmentoNuevo(orden, "Sección", 1, 1, False, texto, f"[cab]\n{texto}")


def test_vecinos_devuelve_el_mas_parecido_primero(tmp_path: Path) -> None:
    store = Store(tmp_path / "b.sqlite", dimensiones=256)
    store.insertar_documento(META, tmp_path / "a.pdf", "h1")
    doc = store.documentos_por_sha256("h1")
    store.reemplazar_fragmentos(doc.id, [_fragmento(0, "aspirina dosis"), _fragmento(1, "dieta sal")], 1, [])
    frags = store.fragmentos(doc.id)
    emb = EmbedderFalso()
    store.guardar_vectores([(frags[0].id, emb.consulta("aspirina dosis")), (frags[1].id, emb.consulta("dieta sal"))])

    vecinos = store.vecinos(emb.consulta("dosis de aspirina"), k=2)

    assert vecinos[0][0] == frags[0].id
    assert vecinos[0][1] > vecinos[1][1]
    store.cerrar()


def test_dimension_incorrecta_se_rechaza(tmp_path: Path) -> None:
    store = Store(tmp_path / "b.sqlite", dimensiones=256)

    with pytest.raises(DimensionesIncompatibles):
        store.vecinos([0.1, 0.2], k=1)
    store.cerrar()


def test_reabrir_con_otra_dimension_falla(tmp_path: Path) -> None:
    Store(tmp_path / "b.sqlite", dimensiones=256).cerrar()

    with pytest.raises(DimensionesIncompatibles):
        Store(tmp_path / "b.sqlite", dimensiones=8)


def test_borrar_documento_elimina_sus_vectores(tmp_path: Path) -> None:
    store = Store(tmp_path / "b.sqlite", dimensiones=256)
    store.insertar_documento(META, tmp_path / "a.pdf", "h1")
    doc = store.documentos_por_sha256("h1")
    store.reemplazar_fragmentos(doc.id, [_fragmento(0, "aspirina")], 1, [])
    frag = store.fragmentos(doc.id)[0]
    store.guardar_vectores([(frag.id, EmbedderFalso().consulta("aspirina"))])

    store.borrar_documento(doc.id)

    assert store.vecinos(EmbedderFalso().consulta("aspirina"), k=5) == []
    store.cerrar()


def test_vectorizar_faltantes_calcula_solo_lo_que_falta(pdf_guia: Path, tmp_path: Path) -> None:
    store = Store(tmp_path / "b.sqlite", dimensiones=256)
    biblioteca = Biblioteca(store, embedder=EmbedderFalso())
    doc_id = biblioteca.importar(pdf_guia, META)
    biblioteca.indexar(doc_id)
    assert store.fragmentos_sin_vector(doc_id) == []
    store.reescribir_cabeceras(doc_id, {f.id: f.texto_indexado for f in store.fragmentos(doc_id)})
    assert len(store.fragmentos_sin_vector(doc_id)) == len(store.fragmentos(doc_id))

    calculados = biblioteca.vectorizar_faltantes()

    assert calculados == len(store.fragmentos(doc_id))
    assert store.fragmentos_sin_vector(doc_id) == []
    store.cerrar()


def test_modelo_distinto_al_del_indice_se_rechaza(tmp_path: Path) -> None:
    store = Store(tmp_path / "b.sqlite", dimensiones=256)
    store.fijar_meta_valor("modelo_embedding", "otro-modelo")

    with pytest.raises(ModeloDeEmbeddingsDistinto):
        Biblioteca(store, embedder=EmbedderFalso())
    store.cerrar()


def test_importar_con_mismo_modelo_copia_vectores(pdf_guia: Path, tmp_path: Path) -> None:
    origen = Store(tmp_path / "origen.sqlite", dimensiones=256)
    bib_origen = Biblioteca(origen, embedder=EmbedderFalso())
    bib_origen.indexar(bib_origen.importar(pdf_guia, META))
    indice = tmp_path / "indice.medidx"
    origen.exportar(indice)
    origen.cerrar()

    destino = Store(tmp_path / "destino.sqlite", dimensiones=256)
    importados, omitidos = destino.importar(indice, modelo_activo="embedder-falso")

    assert (importados, omitidos) == (1, 0)
    doc = destino.documentos()[0]
    assert destino.fragmentos_sin_vector(doc.id) == []
    assert destino.vecinos(EmbedderFalso().consulta("presión objetivo"), k=3)
    destino.cerrar()


def test_importar_con_otro_modelo_deja_fragmentos_sin_vector(pdf_guia: Path, tmp_path: Path) -> None:
    origen = Store(tmp_path / "origen.sqlite", dimensiones=256)
    bib_origen = Biblioteca(origen, embedder=EmbedderFalso())
    bib_origen.indexar(bib_origen.importar(pdf_guia, META))
    indice = tmp_path / "indice.medidx"
    origen.exportar(indice)
    origen.cerrar()

    destino = Store(tmp_path / "destino.sqlite", dimensiones=256)
    destino.fijar_meta_valor("modelo_embedding", "otro-modelo")
    destino.importar(indice, modelo_activo="embedder-falso")
    doc = destino.documentos()[0]

    assert destino.fragmentos_sin_vector(doc.id) != []
    destino.cerrar()
