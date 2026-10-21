"""Ventana principal: pestañas de Biblioteca y Consulta. Libera los modelos cuando la app pasa a segundo plano."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMainWindow, QPushButton, QTabWidget, QVBoxLayout, QWidget

from medguia.ui.ajustes_dialogo import AjustesDialogo
from medguia.ui.biblioteca_vista import BibliotecaVista
from medguia.ui.chat_vista import ChatVista
from medguia.ui.evaluacion_vista import EvaluacionVista
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
        self._evaluacion = EvaluacionVista(servicios)
        self._pestanas = QTabWidget()
        self._pestanas.addTab(self._chat, "Consulta")
        self._pestanas.addTab(self._biblioteca, "Biblioteca")
        self._pestanas.addTab(self._evaluacion, "Evaluación")

        aviso = QLabel("No introduzcas datos identificativos de pacientes.")
        aviso.setStyleSheet("font-weight: bold; padding: 4px; background: #fff3cd; color: #553c00;")
        contenido = QWidget()
        diseno = QVBoxLayout(contenido)
        diseno.addWidget(aviso)
        diseno.addWidget(self._pestanas)
        self.setCentralWidget(contenido)

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
            from medguia.ui.apariencia import aplicar
            from PySide6.QtWidgets import QApplication

            aplicar(QApplication.instance(), self._servicios.ajustes)
            self._chat.actualizar_proveedor()
            self._chat.recargar_filtros()

    def closeEvent(self, evento) -> None:
        self._chat.cerrar()
        self._biblioteca.cerrar()
        self._servicios.liberar_modelos()
        super().closeEvent(evento)
