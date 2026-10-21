import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from medguia.domain.models import Ambito, EstadoDocumento, MetaDocumento  # noqa: E402
from medguia.ui.biblioteca_vista import BibliotecaVista  # noqa: E402
from medguia.ui.worker import TrabajadorIndexado  # noqa: E402


@pytest.fixture(scope="module")
def aplicacion():
    return QApplication.instance() or QApplication([])


def test_indexado_en_segundo_plano_actualiza_la_tabla(
    aplicacion, pdf_guia: Path, tmp_path: Path
) -> None:
    ruta_bd = tmp_path / "bd.sqlite"
    vista = BibliotecaVista(ruta_bd)
    meta = MetaDocumento("Guía HTA", "ESC", 2024, Ambito.EUROPEO, "Cardiología")
    doc_id = vista._biblioteca.importar(pdf_guia, meta)
    vista._refrescar()

    trabajador = TrabajadorIndexado(ruta_bd, [doc_id])
    trabajador.start()
    trabajador.wait()
    aplicacion.processEvents()
    vista._refrescar()

    assert vista._tabla.item(0, 6).text() == "Listo"
    assert vista._tabla.item(0, 5).text() == "2"
    documento = vista._biblioteca.documento(doc_id)
    assert documento is not None and documento.estado is EstadoDocumento.LISTO
    vista.close()
