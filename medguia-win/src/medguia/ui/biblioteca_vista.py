"""Pantalla de biblioteca: importar, indexar y vectorizar con progreso, editar, reindexar, borrar, exportar e importar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from medguia.domain.models import EstadoDocumento
from medguia.ingestion.service import Biblioteca, ModeloDeEmbeddingsDistinto
from medguia.persistence.store import DocumentoDuplicado, DocumentoRegistrado, IndiceNoValido, Store
from medguia.ui.meta_dialogo import ETIQUETAS_AMBITO, MetaDialogo
from medguia.ui.servicios import Servicios
from medguia.ui.worker import TrabajadorIndexado

COLUMNAS = ["Título", "Sociedad", "Año", "Ámbito", "Especialidad", "Páginas", "Estado", "Avisos"]
ETIQUETAS_ESTADO = {
    EstadoDocumento.PENDIENTE: "Pendiente",
    EstadoDocumento.INDEXANDO: "Indexando…",
    EstadoDocumento.LISTO: "Listo",
    EstadoDocumento.ERROR: "Error",
}
AVISO_INDICE = (
    "El índice exportado contiene el texto completo de las guías. "
    "Trátalo como uso personal o institucional permitido y no lo compartas."
)


class BibliotecaVista(QWidget):
    def __init__(self, servicios: Servicios, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        self._servicios = servicios
        self._ruta_bd = servicios.ruta_bd
        self._store = Store(self._ruta_bd)
        self._biblioteca = self._crear_biblioteca()
        self._biblioteca.reparar_estados()
        self._trabajador: TrabajadorIndexado | None = None
        self._cola: list[tuple[list[int], bool]] = []

        self._tabla = QTableWidget(0, len(COLUMNAS))
        self._tabla.setHorizontalHeaderLabels(COLUMNAS)
        self._tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tabla.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tabla.itemSelectionChanged.connect(self._actualizar_botones)

        self._boton_importar = QPushButton("Importar PDF…")
        self._boton_editar = QPushButton("Editar…")
        self._boton_reindexar = QPushButton("Reindexar")
        self._boton_borrar = QPushButton("Borrar")
        self._boton_exportar = QPushButton("Exportar índice…")
        self._boton_importar_indice = QPushButton("Importar índice…")
        self._boton_importar.clicked.connect(self._elegir_pdfs)
        self._boton_editar.clicked.connect(self._editar)
        self._boton_reindexar.clicked.connect(self._reindexar)
        self._boton_borrar.clicked.connect(self._borrar)
        self._boton_exportar.clicked.connect(self._exportar_indice)
        self._boton_importar_indice.clicked.connect(self._importar_indice)

        barra = QHBoxLayout()
        for boton in (self._boton_importar, self._boton_editar, self._boton_reindexar, self._boton_borrar):
            barra.addWidget(boton)
        barra.addStretch()
        barra.addWidget(self._boton_importar_indice)
        barra.addWidget(self._boton_exportar)

        self._progreso = QProgressBar()
        self._progreso.setVisible(False)
        self._estado = QLabel("Arrastra PDFs aquí o usa «Importar PDF…».")
        self._estado.setWordWrap(True)
        self._aviso = QLabel("No introduzcas datos identificativos de pacientes.")
        self._aviso.setStyleSheet("font-weight: bold;")

        diseno = QVBoxLayout(self)
        diseno.addWidget(self._aviso)
        diseno.addLayout(barra)
        diseno.addWidget(self._tabla)
        diseno.addWidget(self._progreso)
        diseno.addWidget(self._estado)

        self._refrescar()
        self._reanudar_pendientes()

    def _crear_biblioteca(self) -> Biblioteca:
        try:
            return Biblioteca(self._store, embedder=self._servicios.embedder())
        except ModeloDeEmbeddingsDistinto as error:
            QMessageBox.warning(self, "Modelo de embeddings distinto", f"{error}\nLos vectores no se calcularán.")
            return Biblioteca(self._store)

    # --- arrastrar y soltar -------------------------------------------------

    def dragEnterEvent(self, evento: QDragEnterEvent) -> None:
        if any(u.toLocalFile().lower().endswith(".pdf") for u in evento.mimeData().urls()):
            evento.acceptProposedAction()

    def dropEvent(self, evento: QDropEvent) -> None:
        rutas = [
            Path(u.toLocalFile())
            for u in evento.mimeData().urls()
            if u.toLocalFile().lower().endswith(".pdf")
        ]
        self._importar_rutas(rutas)

    # --- acciones -----------------------------------------------------------

    def _elegir_pdfs(self) -> None:
        rutas, _ = QFileDialog.getOpenFileNames(self, "Importar guías", "", "PDF (*.pdf)")
        self._importar_rutas([Path(r) for r in rutas])

    def _importar_rutas(self, rutas: list[Path]) -> None:
        importados: list[int] = []
        for ruta in rutas:
            dialogo = MetaDialogo(f"Metadatos: {ruta.name}", None, self, titulo_sugerido=ruta.stem)
            if dialogo.exec() != MetaDialogo.DialogCode.Accepted:
                continue
            try:
                importados.append(self._biblioteca.importar(ruta, dialogo.meta()))
            except DocumentoDuplicado:
                QMessageBox.information(self, "Ya importado", f"«{ruta.name}» ya está en la biblioteca.")
        self._refrescar()
        if importados:
            self._encolar(importados)

    def _editar(self) -> None:
        documento = self._seleccionado()
        if documento is None:
            return
        dialogo = MetaDialogo("Editar metadatos", documento.meta, self)
        if dialogo.exec() == MetaDialogo.DialogCode.Accepted:
            self._biblioteca.editar(documento.id, dialogo.meta())
            self._refrescar()

    def _reindexar(self) -> None:
        documento = self._seleccionado()
        if documento is not None:
            self._encolar([documento.id])

    def _borrar(self) -> None:
        documento = self._seleccionado()
        if documento is None or self._trabajando():
            return
        respuesta = QMessageBox.question(
            self,
            "Borrar documento",
            f"¿Borrar «{documento.meta.titulo}» y sus fragmentos y vectores del índice?\n"
            "El PDF original no se modifica.",
        )
        if respuesta == QMessageBox.StandardButton.Yes:
            self._biblioteca.borrar(documento.id)
            self._refrescar()

    def _exportar_indice(self) -> None:
        destino, _ = QFileDialog.getSaveFileName(
            self, "Exportar índice", "biblioteca.medidx", "Índice MedGuía (*.medidx)"
        )
        if not destino:
            return
        self._store.exportar(Path(destino))
        QMessageBox.information(self, "Índice exportado", f"Guardado en:\n{destino}\n\n{AVISO_INDICE}")

    def _importar_indice(self) -> None:
        origen, _ = QFileDialog.getOpenFileName(self, "Importar índice", "", "Índice MedGuía (*.medidx)")
        if not origen:
            return
        try:
            importados, omitidos = self._store.importar(
                Path(origen), modelo_activo=self._servicios.nombre_embedding()
            )
        except IndiceNoValido as error:
            QMessageBox.warning(self, "Índice no válido", str(error))
            return
        self._refrescar()
        QMessageBox.information(
            self,
            "Índice importado",
            f"Documentos nuevos: {importados}\nYa presentes (omitidos): {omitidos}",
        )
        self._reanudar_vectores()

    # --- trabajo en segundo plano ---------------------------------------------

    def _encolar(self, ids: list[int], solo_vectores: bool = False) -> None:
        if self._trabajando():
            self._cola.append((ids, solo_vectores))
            self._estado.setText("Ya hay un trabajo en curso. Este se añadirá al terminar.")
            return
        self._progreso.setVisible(True)
        self._progreso.setRange(0, 0)
        self._trabajador = TrabajadorIndexado(
            self._ruta_bd, ids, embedder=self._servicios.embedder(), solo_vectores=solo_vectores
        )
        self._trabajador.progreso.connect(self._al_progresar)
        self._trabajador.documento_listo.connect(self._al_terminar_documento)
        self._trabajador.documento_fallido.connect(self._al_fallar_documento)
        self._trabajador.finished.connect(self._al_terminar_trabajo)
        self._trabajador.start()
        self._refrescar()

    def _reanudar_pendientes(self) -> None:
        ids = [d.id for d in self._biblioteca.pendientes()]
        if ids:
            self._encolar(ids)
        else:
            self._reanudar_vectores()

    def _reanudar_vectores(self) -> None:
        if self._servicios.embedder() is None:
            return
        ids = self._store.documentos_con_fragmentos_sin_vector()
        if ids:
            self._encolar(ids, solo_vectores=True)

    def _al_progresar(self, documento_id: int, pagina: int, total: int) -> None:
        self._progreso.setRange(0, total)
        self._progreso.setValue(pagina)
        self._estado.setText(f"Procesando {pagina} de {total}…")

    def _al_terminar_documento(self, documento_id: int, estadisticas) -> None:
        if estadisticas is not None:
            self._estado.setText(
                f"Indexado: {estadisticas.paginas} páginas, {estadisticas.fragmentos} fragmentos, "
                f"{estadisticas.segundos:.1f} s ({estadisticas.segundos_por_pagina:.2f} s/página)."
            )
        self._refrescar()

    def _al_fallar_documento(self, documento_id: int, error: str) -> None:
        self._estado.setText(f"Error: {error}")
        self._refrescar()

    def _al_terminar_trabajo(self) -> None:
        self._progreso.setVisible(False)
        self._trabajador = None
        self._refrescar()
        if self._cola:
            ids, solo_vectores = self._cola.pop(0)
            self._encolar(ids, solo_vectores)

    def _trabajando(self) -> bool:
        return self._trabajador is not None and self._trabajador.isRunning()

    def cerrar(self) -> None:
        if self._trabajando():
            self._trabajador.requestInterruption()
            self._trabajador.wait()
        self._store.cerrar()

    # --- tabla --------------------------------------------------------------

    def _seleccionado(self) -> DocumentoRegistrado | None:
        filas = self._tabla.selectionModel().selectedRows()
        if not filas:
            return None
        return self._biblioteca.documento(self._tabla.item(filas[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def _actualizar_botones(self) -> None:
        hay_seleccion = bool(self._tabla.selectionModel().selectedRows())
        ocupado = self._trabajando()
        self._boton_editar.setEnabled(hay_seleccion and not ocupado)
        self._boton_reindexar.setEnabled(hay_seleccion and not ocupado)
        self._boton_borrar.setEnabled(hay_seleccion and not ocupado)

    def _refrescar(self) -> None:
        documentos = self._biblioteca.documentos()
        self._tabla.setRowCount(len(documentos))
        for fila, documento in enumerate(documentos):
            valores = [
                documento.meta.titulo,
                documento.meta.sociedad,
                str(documento.meta.anio),
                ETIQUETAS_AMBITO[documento.meta.ambito],
                documento.meta.especialidad,
                str(documento.paginas) if documento.paginas else "",
                ETIQUETAS_ESTADO[documento.estado],
                _avisos(documento),
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                if columna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, documento.id)
                self._tabla.setItem(fila, columna, item)
        self._actualizar_botones()


def _avisos(documento: DocumentoRegistrado) -> str:
    if documento.estado is EstadoDocumento.ERROR:
        return documento.error or "Error"
    if documento.paginas_sin_texto:
        paginas = ", ".join(str(p) for p in documento.paginas_sin_texto)
        return f"Sin texto (escaneo): p. {paginas}"
    return ""
