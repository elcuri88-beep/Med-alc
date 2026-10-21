"""Ventana principal: pestañas de Biblioteca y Consulta. Libera los modelos cuando la app pasa a segundo plano."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMainWindow, QPushButton, QTabWidget

from medguia.ui.ajustes_dialogo import AjustesDialogo
from medguia.ui.biblioteca_vista import BibliotecaVista
from medguia.ui.chat_vista import ChatVista
from medguia.ui.servicios import Servicios

SEGUNDOS_ANTES_DE_LIBERAR = 60


class VentanaPrincipal(QMainWindow):
    def __init__(self, servicios: Servicios) -> None:
        super().__init__()
        self.setWindowTitle("MedGuía")
        self.resize(1150, 720)
        self._servicios = servicios

        self._biblioteca = BibliotecaVista(servicios)
        self._chat = ChatVista(servicios)
        self._pestanas = QTabWidget()
        self._pestanas.addTab(self._chat, "Consulta")
        self._pestanas.addTab(self._biblioteca, "Biblioteca")
        self.setCentralWidget(self._pestanas)

        boton_ajustes = QPushButton("Ajustes…")
        boton_ajustes.clicked.connect(self._abrir_ajustes)
        self._pestanas.setCornerWidget(boton_ajustes, Qt.Corner.TopRightCorner)

        self._temporizador = QTimer(self)
        self._temporizador.setSingleShot(True)
        self._temporizador.timeout.connect(self._liberar)
        QGuiApplication.instance().applicationStateChanged.connect(self._cambio_de_estado)

    def _cambio_de_estado(self, estado: Qt.ApplicationState) -> None:
        if estado == Qt.ApplicationState.ApplicationActive:
            self._temporizador.stop()
        else:
            self._temporizador.start(SEGUNDOS_ANTES_DE_LIBERAR * 1000)

    def _liberar(self) -> None:
        self._servicios.liberar_modelos()

    def _abrir_ajustes(self) -> None:
        dialogo = AjustesDialogo(self._servicios, self)
        if dialogo.exec():
            self._chat.actualizar_proveedor()
            self._chat.recargar_filtros()

    def closeEvent(self, evento) -> None:
        self._chat.cerrar()
        self._biblioteca.cerrar()
        self._servicios.liberar_modelos()
        super().closeEvent(evento)
