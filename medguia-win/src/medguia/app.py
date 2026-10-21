from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from medguia.config import ruta_base_datos
from medguia.ui.biblioteca_vista import BibliotecaVista


def main() -> int:
    aplicacion = QApplication(sys.argv)
    ventana = BibliotecaVista(ruta_base_datos())
    ventana.show()
    return aplicacion.exec()
