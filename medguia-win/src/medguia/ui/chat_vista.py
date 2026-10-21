"""Pantalla de consulta: pregunta, respuesta en streaming, fuentes citadas y verificación."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from medguia.generation.prompt import pagina_citada
from medguia.generation.responder import Respuesta
from medguia.persistence.store import Store
from medguia.retrieval.busqueda import Candidato, FiltroBusqueda
from medguia.ui.servicios import PROVEEDOR_API, Servicios
from medguia.ui.trabajadores_ia import TrabajadorRespuesta
from medguia.ui.visor_pdf import VisorPdf

AVISO_PACIENTES = "No introduzcas datos identificativos de pacientes."
TODOS = "(todas)"


class ChatVista(QWidget):
    def __init__(self, servicios: Servicios, parent=None) -> None:
        super().__init__(parent)
        self._servicios = servicios
        self._trabajador: TrabajadorRespuesta | None = None
        self._fuentes: list[Candidato] = []

        self._aviso = QLabel(AVISO_PACIENTES)
        self._aviso.setStyleSheet("font-weight: bold;")
        self._proveedor = QLabel()
        self._proveedor.setWordWrap(True)

        self._especialidad = QComboBox()
        self._sociedad = QComboBox()
        self._anio_minimo = QSpinBox()
        self._anio_minimo.setRange(0, 2100)
        self._anio_minimo.setSpecialValueText("cualquier año")
        self._anio_minimo.setPrefix("desde ")
        filtros = QHBoxLayout()
        for etiqueta, control in (
            ("Especialidad", self._especialidad),
            ("Sociedad", self._sociedad),
            ("Antigüedad", self._anio_minimo),
        ):
            filtros.addWidget(QLabel(etiqueta))
            filtros.addWidget(control)
        filtros.addStretch()

        self._pregunta = QPlainTextEdit()
        self._pregunta.setPlaceholderText("Escribe la pregunta clínica…")
        self._pregunta.setMaximumHeight(90)
        self._enviar = QPushButton("Consultar")
        self._enviar.clicked.connect(self._consultar)

        self._respuesta = QTextBrowser()
        self._respuesta.setOpenExternalLinks(False)
        self._verificacion = QLabel()
        self._verificacion.setStyleSheet("color: #b35c00;")
        self._verificacion.setWordWrap(True)
        self._metricas = QLabel()
        self._fuentes_lista = QListWidget()
        self._fuentes_lista.setToolTip("Doble clic para abrir la página en el PDF original")
        self._fuentes_lista.itemDoubleClicked.connect(self._abrir_fuente)

        diseno = QVBoxLayout(self)
        diseno.addWidget(self._aviso)
        diseno.addWidget(self._proveedor)
        diseno.addLayout(filtros)
        diseno.addWidget(self._pregunta)
        diseno.addWidget(self._enviar)
        diseno.addWidget(self._respuesta, stretch=3)
        diseno.addWidget(self._verificacion)
        diseno.addWidget(QLabel("Fuentes usadas"))
        diseno.addWidget(self._fuentes_lista, stretch=1)
        diseno.addWidget(self._metricas)

        self.actualizar_proveedor()
        self.recargar_filtros()

    # --- estado -----------------------------------------------------------------

    def actualizar_proveedor(self) -> None:
        if self._servicios.ajustes.proveedor == PROVEEDOR_API:
            self._proveedor.setText(
                "⚠ Proveedor: API externa (OpenRouter). Cada consulta SALE DEL DISPOSITIVO."
            )
            self._proveedor.setStyleSheet("color: #b00020; font-weight: bold;")
        else:
            modelo = self._servicios.catalogo[self._servicios.ajustes.modelo_llm].nombre
            self._proveedor.setText(f"Proveedor: {modelo}, en local (GPU si está disponible).")
            self._proveedor.setStyleSheet("")

    def recargar_filtros(self) -> None:
        store = Store(self._servicios.ruta_bd)
        try:
            documentos = store.documentos()
        finally:
            store.cerrar()
        for combo, valores in (
            (self._especialidad, sorted({d.meta.especialidad for d in documentos})),
            (self._sociedad, sorted({d.meta.sociedad for d in documentos})),
        ):
            actual = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(TODOS)
            combo.addItems(valores)
            indice = combo.findText(actual)
            combo.setCurrentIndex(indice if indice >= 0 else 0)
            combo.blockSignals(False)

    def cerrar(self) -> None:
        if self._trabajador is not None and self._trabajador.isRunning():
            self._trabajador.wait()

    # --- consulta ----------------------------------------------------------------

    def _filtro(self) -> FiltroBusqueda:
        especialidad = self._especialidad.currentText()
        sociedad = self._sociedad.currentText()
        return FiltroBusqueda(
            especialidades=frozenset({especialidad}) if especialidad != TODOS else frozenset(),
            sociedades=frozenset({sociedad}) if sociedad != TODOS else frozenset(),
            anio_minimo=self._anio_minimo.value() or None,
        )

    def _consultar(self) -> None:
        pregunta = self._pregunta.toPlainText().strip()
        if not pregunta or (self._trabajador and self._trabajador.isRunning()):
            return
        self._respuesta.clear()
        self._verificacion.clear()
        self._fuentes_lista.clear()
        self._metricas.setText("Consultando…")
        self._enviar.setEnabled(False)

        self._trabajador = TrabajadorRespuesta(self._servicios, pregunta, self._filtro())
        self._trabajador.token.connect(self._respuesta.insertPlainText)
        self._trabajador.respondido.connect(self._mostrar)
        self._trabajador.fallo.connect(self._mostrar_fallo)
        self._trabajador.finished.connect(lambda: self._enviar.setEnabled(True))
        self._trabajador.start()

    def _mostrar(self, respuesta: Respuesta) -> None:
        self._respuesta.setMarkdown(respuesta.texto)
        self._fuentes = respuesta.candidatos
        for candidato in respuesta.candidatos:
            etiqueta = (
                f"{candidato.documento.meta.titulo} · {candidato.documento.meta.anio} · "
                f"p. {pagina_citada(candidato)} · {candidato.fragmento.seccion}"
            )
            item = QListWidgetItem(etiqueta)
            item.setData(Qt.ItemDataRole.UserRole, len(self._fuentes_lista))
            self._fuentes_lista.addItem(item)

        if respuesta.problemas:
            resumen = "; ".join(f"{p.tipo}: {p.detalle}" for p in respuesta.problemas[:4])
            self._verificacion.setText(
                f"⚠ Verificación: {len(respuesta.problemas)} aviso(s). Revisa las citas. {resumen}"
            )
        primero = (
            f"Primer token {respuesta.segundos_primer_token:.2f} s · "
            if respuesta.segundos_primer_token is not None
            else ""
        )
        self._metricas.setText(f"{primero}Total {respuesta.segundos_total:.2f} s")

    def _mostrar_fallo(self, mensaje: str) -> None:
        self._respuesta.setPlainText(f"No se pudo responder: {mensaje}")
        self._metricas.clear()

    def _abrir_fuente(self, item: QListWidgetItem) -> None:
        candidato = self._fuentes[item.data(Qt.ItemDataRole.UserRole)]
        ruta = Path(candidato.documento.ruta)
        visor = VisorPdf(
            ruta,
            candidato.fragmento.pagina_inicio,
            candidato.documento.meta.titulo,
            parent=self,
        )
        visor.exec()
