import json
from pathlib import Path

import pytest

from medguia.domain.models import Ambito, FragmentoNuevo, MetaDocumento
from medguia.evaluation.informe import csv_texto, tabla_markdown
from medguia.evaluation.memoria import MedidorMemoria
from medguia.evaluation.metricas import evaluar_modelo
from medguia.evaluation.preguntas import PreguntasNoValidas, cargar
from medguia.generation.presupuesto import PerfilContexto
from medguia.generation.responder import Responder
from medguia.ingestion.tokens import ContadorAproximado
from medguia.persistence.store import Store
from medguia.retrieval.busqueda import Recuperador
from tests.fakes import EmbedderFalso, LLMFalso


def _escribir(tmp_path: Path, datos) -> Path:
    ruta = tmp_path / "preguntas.json"
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return ruta


def test_carga_valida_preguntas_cubiertas_y_no_cubiertas(tmp_path: Path) -> None:
    ruta = _escribir(tmp_path, [
        {"id": "a", "pregunta": "¿Objetivo?", "documento": "Guía HTA", "pagina": 3},
        {"id": "b", "pregunta": "¿Fuera de tema?", "cubierta": False},
    ])

    preguntas = cargar(ruta)

    assert [p.cubierta for p in preguntas] == [True, False]
    assert preguntas[1].documento is None


@pytest.mark.parametrize("entrada", [
    {"pregunta": "x", "cubierta": True},  # falta documento y página
    {"documento": "G", "pagina": 1},  # falta la pregunta
    {"pregunta": "x", "cubierta": "sí", "documento": "G", "pagina": 1},
])
def test_preguntas_mal_formadas_se_rechazan(tmp_path: Path, entrada: dict) -> None:
    with pytest.raises(PreguntasNoValidas):
        cargar(_escribir(tmp_path, [entrada]))


def test_lista_vacia_se_rechaza(tmp_path: Path) -> None:
    with pytest.raises(PreguntasNoValidas):
        cargar(_escribir(tmp_path, []))


def test_evaluacion_mide_recuperacion_cita_y_cobertura(tmp_path: Path) -> None:
    store = Store(tmp_path / "b.sqlite", dimensiones=256)
    emb = EmbedderFalso()
    meta = MetaDocumento("Guía HTA", "ESC", 2024, Ambito.EUROPEO, "Cardiología")
    doc = store.insertar_documento(meta, tmp_path / "g.pdf", "sha")
    store.reemplazar_fragmentos(doc, [
        FragmentoNuevo(0, "Diagnóstico", 3, 3, False,
                       "La presión objetivo es menor de 130 mmHg.",
                       "[Guía HTA]\nLa presión objetivo es menor de 130 mmHg."),
    ], 3, [])
    frags = store.fragmentos(doc)
    store.guardar_vectores([(f.id, emb.documentos([("Guía HTA", f.texto_indexado)])[0]) for f in frags])
    ruta = _escribir(tmp_path, [
        {"id": "ok", "pregunta": "presión objetivo", "documento": "Guía HTA", "pagina": 3},
        {"id": "fuera", "pregunta": "fractura de tibia", "cubierta": False},
    ])
    llm = LLMFalso("La presión objetivo es menor de 130 mmHg [Guía HTA, 2024, p. 3].")
    recuperador = Recuperador(store, emb, umbral_similitud=0.2)
    responder = Responder(recuperador, llm, ContadorAproximado(), PerfilContexto(n_ctx=8192), lambda: 2026)

    resumen = evaluar_modelo("prueba", cargar(ruta), recuperador, responder)

    assert resumen.recuperacion_top5 == 1.0
    assert resumen.acierto_cita == 1.0
    assert resumen.no_cubiertas_acertadas == 1.0
    assert resumen.pico.ram_gb > 0
    store.cerrar()


def test_informe_markdown_y_csv_contienen_cada_modelo() -> None:
    from medguia.evaluation.memoria import PicoMemoria
    from medguia.evaluation.metricas import resumir

    resumenes = [
        resumir("E2B", [], PicoMemoria(ram_gb=2.0, vram_gb=3.5)),
        resumir("E4B", [], PicoMemoria(ram_gb=2.5, vram_gb=5.0)),
    ]

    markdown = tabla_markdown(resumenes)
    assert "| E2B |" in markdown and "| E4B |" in markdown
    assert csv_texto(resumenes).splitlines()[0].startswith("modelo,")


def test_medidor_registra_pico_de_ram() -> None:
    with MedidorMemoria(intervalo_s=0.01) as medidor:
        _ = bytearray(20 * 1024 * 1024)
    assert medidor.pico().ram_gb > 0
