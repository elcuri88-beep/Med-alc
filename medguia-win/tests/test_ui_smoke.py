import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from medguia.domain.models import Ambito, EstadoDocumento, MetaDocumento  # noqa: E402
from medguia.persistence.store import Store  # noqa: E402
from medguia.ui.biblioteca_vista import BibliotecaVista  # noqa: E402
from medguia.ui.chat_vista import ChatVista  # noqa: E402
from medguia.ui.servicios import Servicios  # noqa: E402
from medguia.ui.trabajadores_ia import TrabajadorRespuesta  # noqa: E402
from medguia.ui.ventana import VentanaPrincipal  # noqa: E402
from medguia.ui.worker import TrabajadorIndexado  # noqa: E402

META = MetaDocumento("Guía HTA", "ESC", 2024, Ambito.EUROPEO, "Cardiología")


@pytest.fixture(scope="module")
def aplicacion():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def servicios(tmp_path: Path) -> Servicios:
    # Sin modelos instalados: la indexación debe funcionar igual, sin vectores.
    return Servicios(tmp_path / "datos", ram_gb=32, vram_gb=16)


def test_indexado_en_segundo_plano_actualiza_la_tabla(aplicacion, pdf_guia: Path, servicios: Servicios) -> None:
    vista = BibliotecaVista(servicios)
    doc_id = vista._biblioteca.importar(pdf_guia, META)
    vista._refrescar()

    trabajador = TrabajadorIndexado(servicios.ruta_bd, [doc_id])
    trabajador.start()
    trabajador.wait()
    aplicacion.processEvents()
    vista._refrescar()

    assert vista._tabla.item(0, 6).text() == "Listo"
    assert vista._tabla.item(0, 5).text() == "2"
    documento = vista._biblioteca.documento(doc_id)
    assert documento is not None and documento.estado is EstadoDocumento.LISTO
    vista.cerrar()


def test_chat_sin_modelo_muestra_el_fallo_sin_colgarse(aplicacion, pdf_guia: Path, servicios: Servicios) -> None:
    store = Store(servicios.ruta_bd)
    store.cerrar()
    chat = ChatVista(servicios)
    chat._pregunta.setPlainText("presión objetivo")

    trabajador = TrabajadorRespuesta(servicios, "presión objetivo", chat._filtro())
    trabajador.fallo.connect(chat._mostrar_fallo)
    trabajador.start()
    trabajador.wait()
    aplicacion.processEvents()

    assert "No se pudo responder" in chat._respuesta.toPlainText()


def test_ventana_principal_se_construye_con_sus_pestanas(aplicacion, servicios: Servicios) -> None:
    ventana = VentanaPrincipal(servicios)

    assert ventana._pestanas.count() == 2
    assert ventana._pestanas.tabText(0) == "Consulta"
    assert ventana._pestanas.tabText(1) == "Biblioteca"
    ventana.close()


def test_ajustes_guardan_proveedor_sin_clave_en_el_json(aplicacion, servicios: Servicios) -> None:
    from medguia.ui.servicios import Ajustes, PROVEEDOR_API

    servicios.guardar_ajustes(Ajustes(proveedor=PROVEEDOR_API, api_aceptada=True, openrouter_modelo="m"))

    contenido = (servicios.carpeta / "ajustes.json").read_text(encoding="utf-8")
    assert '"proveedor": "openrouter"' in contenido
    assert "sk-" not in contenido
