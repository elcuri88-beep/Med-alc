from pathlib import Path

import pytest

from medguia.domain.models import Ambito, EstadoDocumento, MetaDocumento
from medguia.ingestion.service import Biblioteca
from medguia.persistence.store import DocumentoDuplicado, IndiceNoValido, Store

META = MetaDocumento(
    titulo="Guía HTA",
    sociedad="ESC",
    anio=2024,
    ambito=Ambito.EUROPEO,
    especialidad="Cardiología",
)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    tienda = Store(tmp_path / "bd" / "biblioteca.sqlite")
    yield tienda
    tienda.cerrar()


@pytest.fixture
def biblioteca(store: Store) -> Biblioteca:
    return Biblioteca(store)


def test_importar_deja_el_documento_pendiente(biblioteca: Biblioteca, pdf_guia: Path) -> None:
    doc_id = biblioteca.importar(pdf_guia, META)

    documento = biblioteca.documento(doc_id)
    assert documento is not None
    assert documento.estado is EstadoDocumento.PENDIENTE
    assert documento.meta == META


def test_importar_el_mismo_pdf_dos_veces_se_rechaza(
    biblioteca: Biblioteca, pdf_guia: Path
) -> None:
    biblioteca.importar(pdf_guia, META)

    with pytest.raises(DocumentoDuplicado):
        biblioteca.importar(pdf_guia, META)


def test_indexar_guarda_fragmentos_y_busqueda_los_encuentra(
    biblioteca: Biblioteca, store: Store, pdf_guia: Path
) -> None:
    doc_id = biblioteca.importar(pdf_guia, META)

    estadisticas = biblioteca.indexar(doc_id)

    documento = biblioteca.documento(doc_id)
    assert documento is not None
    assert documento.estado is EstadoDocumento.LISTO
    assert documento.paginas == 2
    assert estadisticas.paginas == 2
    assert estadisticas.fragmentos >= 2
    assert estadisticas.segundos_por_pagina >= 0

    encontrados = store.buscar_texto("130 mmHg")
    assert encontrados
    assert encontrados[0].pagina_inicio == 1
    assert "[Guía HTA · ESC · 2024 · europeo" in encontrados[0].texto_indexado


def test_tabla_de_dosis_queda_como_fragmento_atomico(
    biblioteca: Biblioteca, store: Store, pdf_guia: Path
) -> None:
    doc_id = biblioteca.importar(pdf_guia, META)
    biblioteca.indexar(doc_id)

    tablas = [f for f in store.fragmentos(doc_id) if f.es_tabla]

    assert len(tablas) == 1
    assert "Losartán | 50 mg | 24 h" in tablas[0].texto


def test_paginas_escaneadas_se_registran(
    biblioteca: Biblioteca, store: Store, pdf_escaneado: Path
) -> None:
    doc_id = biblioteca.importar(pdf_escaneado, META)

    biblioteca.indexar(doc_id)

    documento = biblioteca.documento(doc_id)
    assert documento is not None
    assert documento.paginas_sin_texto == (1,)


def test_editar_metadatos_reescribe_la_cabecera_y_la_busqueda(
    biblioteca: Biblioteca, store: Store, pdf_guia: Path
) -> None:
    doc_id = biblioteca.importar(pdf_guia, META)
    biblioteca.indexar(doc_id)
    nuevo = MetaDocumento(
        titulo="Protocolo HTA Centro",
        sociedad="Local",
        anio=2025,
        ambito=Ambito.LOCAL,
        especialidad="Atención Primaria",
    )

    biblioteca.editar(doc_id, nuevo)

    encontrados = store.buscar_texto("Protocolo")
    assert encontrados
    assert "[Protocolo HTA Centro · Local · 2025 · local" in encontrados[0].texto_indexado
    assert store.buscar_texto("ESC") == []


def test_borrar_elimina_fragmentos_y_busqueda(
    biblioteca: Biblioteca, store: Store, pdf_guia: Path
) -> None:
    doc_id = biblioteca.importar(pdf_guia, META)
    biblioteca.indexar(doc_id)

    biblioteca.borrar(doc_id)

    assert biblioteca.documento(doc_id) is None
    assert store.fragmentos(doc_id) == []
    assert store.buscar_texto("130 mmHg") == []


def test_reindexar_no_duplica_fragmentos(
    biblioteca: Biblioteca, store: Store, pdf_guia: Path
) -> None:
    doc_id = biblioteca.importar(pdf_guia, META)
    primera = biblioteca.indexar(doc_id)

    biblioteca.reindexar(doc_id)

    assert len(store.fragmentos(doc_id)) == primera.fragmentos
    assert len(store.buscar_texto("130 mmHg")) == 1


def test_error_al_indexar_queda_registrado(biblioteca: Biblioteca, store: Store, tmp_path: Path) -> None:
    ruta = tmp_path / "corrupto.pdf"
    ruta.write_bytes(b"no es un pdf")
    doc_id = biblioteca.importar(ruta, META)

    with pytest.raises(Exception):
        biblioteca.indexar(doc_id)

    documento = biblioteca.documento(doc_id)
    assert documento is not None
    assert documento.estado is EstadoDocumento.ERROR
    assert documento.error


def test_interrupcion_vuelve_a_pendiente(biblioteca: Biblioteca, store: Store, pdf_guia: Path) -> None:
    doc_id = biblioteca.importar(pdf_guia, META)
    store.fijar_estado(doc_id, EstadoDocumento.INDEXANDO)

    reparados = biblioteca.reparar_estados()

    assert reparados == 1
    documento = biblioteca.documento(doc_id)
    assert documento is not None
    assert documento.estado is EstadoDocumento.PENDIENTE


def test_exportar_e_importar_en_otra_biblioteca(
    biblioteca: Biblioteca, store: Store, pdf_guia: Path, tmp_path: Path
) -> None:
    doc_id = biblioteca.importar(pdf_guia, META)
    biblioteca.indexar(doc_id)
    indice = tmp_path / "exportado" / "guias.medidx"
    store.exportar(indice)

    otra = Store(tmp_path / "otra" / "biblioteca.sqlite")
    try:
        importados, omitidos = otra.importar(indice)
        assert (importados, omitidos) == (1, 0)
        copia = otra.documentos()[0]
        assert copia.estado is EstadoDocumento.LISTO
        assert otra.buscar_texto("130 mmHg")

        assert otra.importar(indice) == (0, 1)
    finally:
        otra.cerrar()


def test_importar_rechaza_archivos_que_no_son_indices(store: Store, tmp_path: Path) -> None:
    falso = tmp_path / "falso.medidx"
    falso.write_bytes(b"x" * 100)

    with pytest.raises(IndiceNoValido):
        store.importar(falso)
