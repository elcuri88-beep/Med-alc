"""Pestaña de evaluación: carga el JSON de preguntas, evalúa los modelos elegidos y muestra la tabla."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from medguia.evaluation import informe
from medguia.evaluation.ejecucion import evaluar_configuraciones
from medguia.evaluation.preguntas import PreguntaEvaluacion, PreguntasNoValidas, cargar
from medguia.models import gestor
from medguia.ui.servicios import ModeloNoInstalado, Servicios


class TrabajadorEvaluacion(QThread):
    progreso = Signal(str, int, int)
    terminado = Signal(object)  # list[ResumenModelo]
    fallo = Signal(str)

    def __init__(self, servicios: Servicios, preguntas: list[PreguntaEvaluacion], claves: list[str]) -> None:
        super().__init__()
        self._servicios = servicios
        self._preguntas = preguntas
        self._claves = claves

    def run(self) -> None:
        try:
            resumenes = evaluar_configuraciones(
                self._servicios, self._preguntas, self._claves, al_progresar=self.progreso.emit
            )
            self.terminado.emit(resumenes)
        except (ModeloNoInstalado, RuntimeError) as error:
            self.fallo.emit(str(error))
        except Exception as error:
            self.fallo.emit(f"Error inesperado: {error}")


class EvaluacionVista(QWidget):
    def __init__(self, servicios: Servicios, parent=None) -> None:
        super().__init__(parent)
        self._servicios = servicios
        self._preguntas: list[PreguntaEvaluacion] = []
        self._resumenes = []
        self._trabajador: TrabajadorEvaluacion | None = None

        self._boton_cargar = QPushButton("Cargar preguntas (JSON)…")
        self._e4b = QCheckBox(servicios.catalogo[gestor.GEMMA_E4B].nombre)
        self._e2b = QCheckBox(servicios.catalogo[gestor.GEMMA_E2B].nombre)
        self._e4b.setChecked(True)
        self._e2b.setChecked(True)
        self._boton_evaluar = QPushButton("Evaluar")
        self._boton_guardar = QPushButton("Guardar informe…")
        self._boton_guardar.setEnabled(False)
        self._boton_cargar.clicked.connect(self._cargar)
        self._boton_evaluar.clicked.connect(self._evaluar)
        self._boton_guardar.clicked.connect(self._guardar)

        self._estado = QLabel("Carga un JSON con preguntas (ver evaluacion/plantilla_preguntas.json).")
        self._estado.setWordWrap(True)
        self._progreso = QProgressBar()
        self._progreso.setVisible(False)
        self._resultado = QTextBrowser()

        barra = QHBoxLayout()
        for control in (self._boton_cargar, self._e4b, self._e2b, self._boton_evaluar, self._boton_guardar):
            barra.addWidget(control)
        barra.addStretch()

        diseno = QVBoxLayout(self)
        diseno.addLayout(barra)
        diseno.addWidget(self._estado)
        diseno.addWidget(self._progreso)
        diseno.addWidget(self._resultado)

    def _cargar(self) -> None:
        ruta, _ = QFileDialog.getOpenFileName(self, "Preguntas de evaluación", "", "JSON (*.json)")
        if not ruta:
            return
        try:
            self._preguntas = cargar(Path(ruta))
        except (PreguntasNoValidas, ValueError) as error:
            QMessageBox.warning(self, "Preguntas no válidas", str(error))
            return
        cubiertas = sum(p.cubierta for p in self._preguntas)
        self._estado.setText(
            f"{len(self._preguntas)} preguntas cargadas ({cubiertas} cubiertas, "
            f"{len(self._preguntas) - cubiertas} sin cobertura)."
        )

    def _evaluar(self) -> None:
        if not self._preguntas:
            QMessageBox.information(self, "Sin preguntas", "Carga primero un JSON de preguntas.")
            return
        claves = [k for k, casilla in ((gestor.GEMMA_E4B, self._e4b), (gestor.GEMMA_E2B, self._e2b)) if casilla.isChecked()]
        if not claves:
            QMessageBox.information(self, "Sin modelos", "Marca al menos un modelo.")
            return
        self._boton_evaluar.setEnabled(False)
        self._progreso.setVisible(True)
        self._progreso.setRange(0, len(self._preguntas))
        self._trabajador = TrabajadorEvaluacion(self._servicios, self._preguntas, claves)
        self._trabajador.progreso.connect(lambda nombre, i, n: (self._progreso.setValue(i), self._estado.setText(f"{nombre}: {i}/{n}")))
        self._trabajador.terminado.connect(self._mostrar)
        self._trabajador.fallo.connect(lambda e: QMessageBox.warning(self, "Evaluación fallida", e))
        self._trabajador.finished.connect(self._fin)
        self._trabajador.start()

    def _fin(self) -> None:
        self._boton_evaluar.setEnabled(True)
        self._progreso.setVisible(False)

    def _mostrar(self, resumenes) -> None:
        self._resumenes = resumenes
        self._resultado.setMarkdown(informe.tabla_markdown(resumenes))
        self._boton_guardar.setEnabled(True)
        self._estado.setText("Evaluación terminada.")

    def _guardar(self) -> None:
        destino, _ = QFileDialog.getSaveFileName(self, "Guardar informe", "informe.md", "Markdown (*.md)")
        if not destino:
            return
        ruta = Path(destino)
        ruta.write_text(informe.tabla_markdown(self._resumenes), encoding="utf-8")
        ruta.with_suffix(".csv").write_text(informe.csv_texto(self._resumenes), encoding="utf-8")
        self._estado.setText(f"Informe guardado en {ruta} y {ruta.with_suffix('.csv')}.")
