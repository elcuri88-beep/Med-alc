from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from medguia.config import carpeta_datos
from medguia.ui.apariencia import aplicar
from medguia.ui.bloqueo import WindowsHello, desbloqueo_necesario
from medguia.ui.servicios import Servicios
from medguia.ui.ventana import VentanaPrincipal


def main() -> int:
    aplicacion = QApplication(sys.argv)
    servicios = Servicios(carpeta_datos())
    aplicar(aplicacion, servicios.ajustes)

    hello = WindowsHello()
    if servicios.ajustes.bloqueo_al_abrir:
        if not hello.disponible():
            QMessageBox.warning(None, "Bloqueo no disponible", "Windows Hello no está disponible. Se abre sin bloqueo.")
        elif desbloqueo_necesario(True, hello) and not hello.verificar("Abrir MedGuía"):
            return 1

    ventana = VentanaPrincipal(servicios)
    ventana.show()
    return aplicacion.exec()
