"""Visor del PDF original, abierto en la página citada."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView

    PDF_DISPONIBLE = True
except ImportError:  # PySide6 sin el módulo QtPdf (usar el paquete PySide6 completo)
    PDF_DISPONIBLE = False


class VisorPdf(QDialog):
    def __init__(self, ruta: Path, pagina: int, titulo: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{titulo} · p. {pagina}")
        self.resize(900, 1000)
        diseno = QVBoxLayout(self)
        if not PDF_DISPONIBLE:
            diseno.addWidget(QLabel("El visor PDF requiere el paquete PySide6 completo (QtPdf)."))
            return
        if not ruta.exists():
            diseno.addWidget(QLabel(f"No se encuentra el PDF original:\n{ruta}"))
            return

        self._documento = QPdfDocument(self)
        self._documento.load(str(ruta))
        self._vista = QPdfView(self)
        self._vista.setDocument(self._documento)
        self._vista.setPageMode(QPdfView.PageMode.MultiPage)
        diseno.addWidget(self._vista)
        navegador = self._vista.pageNavigator()
        navegador.jump(max(pagina - 1, 0), QPointF(0, 0), self._vista.zoomFactor())
