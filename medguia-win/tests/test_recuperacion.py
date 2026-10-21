from pathlib import Path

import pytest

from medguia.domain.models import Ambito, FragmentoNuevo, MetaDocumento
from medguia.persistence.store import Store
from medguia.retrieval.busqueda import FiltroBusqueda, Recuperador
from tests.fakes import EmbedderFalso


@pytest.fixture
def biblioteca_de_prueba(tmp_path: Path) -> Store:
    store = Store(tmp_path / "b.sqlite", dimensiones=256)
    emb = EmbedderFalso()
    documentos = [
        ("HTA", "ESC", 2024, Ambito.EUROPEO, "Cardiología",
         ["presión objetivo menor de 130 mmHg", "tratamiento antihipertensivo inicial", "dieta baja en sal"]),
        ("Protocolo local", "Local", 2025, Ambito.LOCAL, "Atención Primaria",
         ["protocolo presión arterial en consulta", "control de presión a los 3 meses"]),
        ("Diabetes", "semFYC", 2019, Ambito.NACIONAL, "Atención Primaria",
         ["hemoglobina glicosilada objetivo 7 por ciento"]),
    ]
    for indice, (titulo, sociedad, anio, ambito, especialidad, textos) in enumerate(documentos):
        meta = MetaDocumento(titulo, sociedad, anio, ambito, especialidad)
        doc_id = store.insertar_documento(meta, tmp_path / f"{indice}.pdf", f"sha{indice}")
        fragmentos = [
            FragmentoNuevo(i, "Sección", 1, 1, False, t, f"[{titulo}]\n{t}") for i, t in enumerate(textos)
        ]
        store.reemplazar_fragmentos(doc_id, fragmentos, 1, [])
        store.guardar_vectores(
            [(f.id, emb.documentos([(titulo, f.texto_indexado)])[0]) for f in store.fragmentos(doc_id)]
        )
    yield store
    store.cerrar()


def test_pregunta_con_respuesta_en_las_guias_esta_cubierta(biblioteca_de_prueba: Store) -> None:
    recuperador = Recuperador(biblioteca_de_prueba, EmbedderFalso(dimensiones=256), umbral_similitud=0.3)

    recuperacion = recuperador.buscar("presión objetivo en hipertensos")

    assert recuperacion.cubierta
    assert recuperacion.candidatos[0].fragmento.texto.startswith("presión objetivo")


def test_pregunta_fuera_de_las_guias_no_esta_cubierta(biblioteca_de_prueba: Store) -> None:
    recuperador = Recuperador(biblioteca_de_prueba, EmbedderFalso(dimensiones=256), umbral_similitud=0.55)

    recuperacion = recuperador.buscar("tratamiento de fractura de tibia en niños")

    assert not recuperacion.cubierta


def test_diversidad_limita_fragmentos_por_documento(biblioteca_de_prueba: Store) -> None:
    recuperador = Recuperador(
        biblioteca_de_prueba, EmbedderFalso(dimensiones=256), umbral_similitud=0.0, max_por_documento=1
    )

    recuperacion = recuperador.buscar("presión")

    documentos = [c.documento.id for c in recuperacion.candidatos]
    assert len(documentos) == len(set(documentos))


def test_filtro_por_especialidad_excluye_otras(biblioteca_de_prueba: Store) -> None:
    recuperador = Recuperador(biblioteca_de_prueba, EmbedderFalso(dimensiones=256), umbral_similitud=0.0)
    filtro = FiltroBusqueda(especialidades=frozenset({"Atención Primaria"}))

    recuperacion = recuperador.buscar("presión", filtro)

    assert recuperacion.candidatos
    assert all(c.documento.meta.especialidad == "Atención Primaria" for c in recuperacion.candidatos)


def test_filtro_por_antiguedad(biblioteca_de_prueba: Store) -> None:
    recuperador = Recuperador(biblioteca_de_prueba, EmbedderFalso(dimensiones=256), umbral_similitud=0.0)

    recuperacion = recuperador.buscar("hemoglobina glicosilada", FiltroBusqueda(anio_minimo=2020))

    assert all(c.documento.meta.anio >= 2020 for c in recuperacion.candidatos)


def test_el_filtro_puede_dejar_la_pregunta_sin_cubrir(biblioteca_de_prueba: Store) -> None:
    recuperador = Recuperador(biblioteca_de_prueba, EmbedderFalso(dimensiones=256), umbral_similitud=0.3)
    filtro = FiltroBusqueda(sociedades=frozenset({"semFYC"}))

    recuperacion = recuperador.buscar("presión objetivo", filtro)

    assert not recuperacion.cubierta
