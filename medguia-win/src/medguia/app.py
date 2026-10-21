from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from medguia.config import carpeta_datos
from medguia.ui.servicios import Servicios
from medguia.ui.ventana import VentanaPrincipal


def main() -> int:
    aplicacion = QApplication(sys.argv)
    servicios = Servicios(carpeta_datos())
    ventana = VentanaPrincipal(servicios)
    ventana.show()
    return aplicacion.exec()
