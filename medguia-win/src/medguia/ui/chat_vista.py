"""Pantalla de consulta: historial en memoria, respuesta en streaming, fuentes y copia en texto plano."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
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
from medguia.ui.texto import a_texto_plano
from medguia.ui.trabajadores_ia import TrabajadorRespuesta
from medguia.ui.visor_pdf import VisorPdf

TODOS = "(todas)"


@dataclass
class Turno:
    pregunta: str
    respuesta: Respuesta | None = None
    parcial: str = ""
    fuentes_texto: list[str] = field(default_factory=list)


class ChatVista(QWidget):
    def __init__(self, servicios: Servicios, parent=None) -> None:
        super().__init__(parent)
        self._servicios = servicios
        self._trabajador: TrabajadorRespuesta | None = None
        self._turnos: list[Turno] = []
        self._fuentes: list[Candidato] = []

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
        self._nueva = QPushButton("Nueva conversación")
        self._copiar = QPushButton("Copiar respuesta (texto plano)")
        self._enviar.clicked.connect(self._consultar)
        QShortcut(QKeySequence("Ctrl+Return"), self._pregunta, activated=self._consultar)
        self._nueva.clicked.connect(self._nueva_conversacion)
        self._copiar.clicked.connect(self._copiar_respuesta)
        self._copiar.setEnabled(False)
        botones = QHBoxLayout()
        for boton in (self._enviar, self._copiar, self._nueva):
            botones.addWidget(boton)
        botones.addStretch()

        self._historial = QTextBrowser()
        self._historial.setOpenExternalLinks(False)
        self._verificacion = QLabel()
        self._verificacion.setStyleSheet("color: #b35c00;")
        self._verificacion.setWordWrap(True)
        self._metricas = QLabel()
        self._fuentes_lista = QListWidget()
        self._fuentes_lista.setToolTip("Doble clic para abrir la página en el PDF original")
        self._fuentes_lista.itemDoubleClicked.connect(self._abrir_fuente)

        diseno = QVBoxLayout(self)
        diseno.addWidget(self._proveedor)
        diseno.addLayout(filtros)
        diseno.addWidget(self._pregunta)
        diseno.addLayout(botones)
        diseno.addWidget(self._historial, stretch=3)
        diseno.addWidget(self._verificacion)
        diseno.addWidget(QLabel("Fuentes de la última respuesta"))
        diseno.addWidget(self._fuentes_lista, stretch=1)
        diseno.addWidget(self._metricas)

        self.actualizar_proveedor()
        self.recargar_filtros()

    # --- estado -----------------------------------------------------------------

    def actualizar_proveedor(self) -> None:
        if self._servicios.ajustes.proveedor == PROVEEDOR_API:
            self._proveedor.setText("⚠ Proveedor: API externa (OpenRouter). Cada consulta SALE DEL DISPOSITIVO.")
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

    def _nueva_conversacion(self) -> None:
        if self._trabajando():
            return
        self._turnos.clear()
        self._fuentes = []
        self._fuentes_lista.clear()
        self._verificacion.clear()
        self._metricas.clear()
        self._copiar.setEnabled(False)
        self._historial.clear()

    # --- consulta ----------------------------------------------------------------

    def _filtro(self) -> FiltroBusqueda:
        especialidad = self._especialidad.currentText()
        sociedad = self._sociedad.currentText()
        return FiltroBusqueda(
            especialidades=frozenset({especialidad}) if especialidad != TODOS else frozenset(),
            sociedades=frozenset({sociedad}) if sociedad != TODOS else frozenset(),
            anio_minimo=self._anio_minimo.value() or None,
        )

    def _trabajando(self) -> bool:
        return self._trabajador is not None and self._trabajador.isRunning()

    def _consultar(self) -> None:
        pregunta = self._pregunta.toPlainText().strip()
        if not pregunta or self._trabajando():
            return
        self._turnos.append(Turno(pregunta=pregunta))
        self._fuentes_lista.clear()
        self._verificacion.clear()
        self._metricas.setText("Consultando… (la primera consulta tarda más: carga el modelo en la GPU)")
        self._enviar.setEnabled(False)
        self._copiar.setEnabled(False)
        self._pregunta.clear()

        self._trabajador = TrabajadorRespuesta(self._servicios, pregunta, self._filtro())
        self._trabajador.token.connect(self._al_token)
        self._trabajador.respondido.connect(self._mostrar)
        self._trabajador.fallo.connect(self._mostrar_fallo)
        self._trabajador.finished.connect(lambda: self._enviar.setEnabled(True))
        self._trabajador.start()
        self._renderizar()

    def _al_token(self, texto: str) -> None:
        self._turnos[-1].parcial += texto
        self._renderizar()

    def _mostrar(self, respuesta: Respuesta) -> None:
        turno = self._turnos[-1]
        turno.respuesta = respuesta
        turno.parcial = ""
        self._fuentes = respuesta.candidatos
        self._fuentes_lista.clear()
        turno.fuentes_texto = []
        for candidato in respuesta.candidatos:
            etiqueta = (
                f"{candidato.documento.meta.titulo} · {candidato.documento.meta.anio} · "
                f"p. {pagina_citada(candidato)} · {candidato.fragmento.seccion}"
            )
            turno.fuentes_texto.append(etiqueta)
            self._fuentes_lista.addItem(QListWidgetItem(etiqueta))

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
        diagnostico = ""
        if not respuesta.cubierta and respuesta.mejor_similitud is not None:
            diagnostico = (
                f" · Mejor similitud {respuesta.mejor_similitud:.2f} frente a un umbral de {respuesta.umbral:.2f}. "
                "Si crees que la guía sí lo cubre, baja el umbral en Ajustes."
            )
        elif not respuesta.cubierta:
            diagnostico = " · No hay fragmentos que cumplan los filtros activos."
        self._metricas.setText(f"{primero}Total {respuesta.segundos_total:.2f} s{diagnostico}")
        self._copiar.setEnabled(True)
        self._renderizar()

    def _mostrar_fallo(self, mensaje: str) -> None:
        turno = self._turnos[-1]
        turno.parcial = f"No se pudo responder: {mensaje}"
        turno.respuesta = None
        self._metricas.clear()
        self._renderizar()

    def _renderizar(self) -> None:
        bloques = []
        for turno in self._turnos:
            bloques.append(f"**Pregunta:** {turno.pregunta}")
            texto = turno.respuesta.texto if turno.respuesta else turno.parcial
            bloques.append(texto or "…")
        self._historial.setMarkdown("\n\n".join(bloques))
        self._historial.verticalScrollBar().setValue(self._historial.verticalScrollBar().maximum())

    def _copiar_respuesta(self) -> None:
        turno = next((t for t in reversed(self._turnos) if t.respuesta), None)
        if turno is None:
            return
        QGuiApplication.clipboard().setText(a_texto_plano(turno.respuesta.texto, turno.fuentes_texto))
        self._metricas.setText("Respuesta copiada en texto plano.")

    def _abrir_fuente(self, item: QListWidgetItem) -> None:
        indice = self._fuentes_lista.row(item)
        candidato = self._fuentes[indice]
        visor = VisorPdf(
            Path(candidato.documento.ruta),
            candidato.fragmento.pagina_inicio,
            candidato.documento.meta.titulo,
            parent=self,
        )
        visor.exec()
