"""Tema claro/oscuro y tamaño de texto. Equivalente en Windows a modo oscuro y Dynamic Type."""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from medguia.ui.servicios import Ajustes

_TAMANO_BASE_PT: float | None = None


def aplicar(aplicacion: QApplication, ajustes: Ajustes) -> None:
    global _TAMANO_BASE_PT
    if _TAMANO_BASE_PT is None:
        _TAMANO_BASE_PT = aplicacion.font().pointSizeF() or 10.0

    fuente = QFont(aplicacion.font())
    fuente.setPointSizeF(_TAMANO_BASE_PT * max(1.0, min(ajustes.escala_texto, 1.6)))
    aplicacion.setFont(fuente)

    if ajustes.tema == "oscuro":
        aplicacion.setStyle("Fusion")
        aplicacion.setPalette(_paleta_oscura())
    elif ajustes.tema == "claro":
        aplicacion.setStyle("Fusion")
        aplicacion.setPalette(aplicacion.style().standardPalette())
    else:
        aplicacion.setPalette(aplicacion.style().standardPalette())


def _paleta_oscura() -> QPalette:
    paleta = QPalette()
    colores = {
        QPalette.ColorRole.Window: "#1e1f22",
        QPalette.ColorRole.WindowText: "#e6e6e6",
        QPalette.ColorRole.Base: "#2b2d31",
        QPalette.ColorRole.AlternateBase: "#25272b",
        QPalette.ColorRole.Text: "#e6e6e6",
        QPalette.ColorRole.Button: "#2b2d31",
        QPalette.ColorRole.ButtonText: "#e6e6e6",
        QPalette.ColorRole.Highlight: "#3a7bd5",
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.ToolTipBase: "#2b2d31",
        QPalette.ColorRole.ToolTipText: "#e6e6e6",
    }
    for rol, color in colores.items():
        paleta.setColor(rol, QColor(color))
    return paleta
