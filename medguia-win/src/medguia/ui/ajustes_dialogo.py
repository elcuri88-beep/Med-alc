"""Ajustes: proveedor, modelo, descarga con progreso y borrado, y API externa con aviso."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from medguia.models import gestor
from medguia.models.gestor import ram_total_gb, vram_total_gb
from medguia.ui.servicios import PROVEEDOR_API, PROVEEDOR_LOCAL, Ajustes, Servicios
from medguia.ui.trabajadores_ia import TrabajadorDescarga

AVISO_API = (
    "Con la API externa, cada pregunta y los fragmentos de las guías que la acompañen se envían "
    "a un servidor de terceros. Acepta esto solo si lo tienes permitido en tu entorno."
)


class AjustesDialogo(QDialog):
    def __init__(self, servicios: Servicios, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ajustes")
        self.setMinimumWidth(560)
        self._servicios = servicios
        self._descarga: TrabajadorDescarga | None = None
        ajustes = servicios.ajustes

        self._proveedor = QComboBox()
        self._proveedor.addItem("Gemma 4 local (recomendado, sin datos fuera del equipo)", PROVEEDOR_LOCAL)
        self._proveedor.addItem("API externa compatible con OpenAI (OpenRouter)", PROVEEDOR_API)
        self._proveedor.setCurrentIndex(0 if ajustes.proveedor == PROVEEDOR_LOCAL else 1)

        self._modelo = QComboBox()
        for clave in (gestor.GEMMA_E4B, gestor.GEMMA_E2B):
            self._modelo.addItem(servicios.catalogo[clave].nombre, clave)
        self._modelo.setCurrentIndex(self._modelo.findData(ajustes.modelo_llm))
        self._estado_modelo = QLabel()

        self._n_ctx = QSpinBox()
        self._n_ctx.setRange(2048, 32768)
        self._n_ctx.setSingleStep(1024)
        self._n_ctx.setValue(ajustes.n_ctx)

        self._boton_descargar = QPushButton("Descargar modelos…")
        self._boton_borrar = QPushButton("Borrar modelo LLM seleccionado")
        self._boton_descargar.clicked.connect(self._descargar)
        self._boton_borrar.clicked.connect(self._borrar)
        self._progreso = QProgressBar()
        self._progreso.setVisible(False)

        self._api_modelo = QLineEdit(ajustes.openrouter_modelo)
        self._api_modelo.setPlaceholderText("identificador del modelo en OpenRouter")
        self._api_clave = QLineEdit(servicios.clave_api())
        self._api_clave.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_clave.setPlaceholderText("se guarda en el Administrador de credenciales de Windows")
        self._api_aceptada = QCheckBox("Entiendo que la consulta sale del dispositivo")
        self._api_aceptada.setChecked(ajustes.api_aceptada)
        aviso = QLabel(AVISO_API)
        aviso.setWordWrap(True)
        aviso.setStyleSheet("color: #b00020;")

        local = QFormLayout()
        local.addRow("Proveedor", self._proveedor)
        local.addRow("Modelo LLM", self._modelo)
        local.addRow("Ventana de contexto", self._n_ctx)
        botones_modelo = QHBoxLayout()
        botones_modelo.addWidget(self._boton_descargar)
        botones_modelo.addWidget(self._boton_borrar)
        api = QFormLayout()
        api.addRow("Modelo OpenRouter", self._api_modelo)
        api.addRow("Clave de API", self._api_clave)
        api.addRow(self._api_aceptada)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self._guardar)
        botones.rejected.connect(self.reject)

        diseno = QVBoxLayout(self)
        diseno.addLayout(local)
        diseno.addWidget(self._estado_modelo)
        diseno.addLayout(botones_modelo)
        diseno.addWidget(self._progreso)
        diseno.addWidget(QLabel("<b>API externa (opcional)</b>"))
        diseno.addWidget(aviso)
        diseno.addLayout(api)
        diseno.addWidget(botones)

        self._modelo.currentIndexChanged.connect(self._actualizar_estado)
        self._actualizar_estado()

    def _actualizar_estado(self) -> None:
        instalados = []
        for clave in (gestor.GEMMA_E4B, gestor.GEMMA_E2B, gestor.EMBEDDING_GEMMA):
            if self._servicios.instalado(clave):
                instalados.append(self._servicios.catalogo[clave].nombre)
        recomendado = self._servicios.catalogo[gestor.recomendar_llm(ram_total_gb(), vram_total_gb())].nombre
        self._estado_modelo.setText(
            f"Instalados: {', '.join(instalados) or 'ninguno'}. Recomendado para este equipo: {recomendado}."
        )

    def _descargar(self) -> None:
        if self._descarga is not None and self._descarga.isRunning():
            return
        claves = [self._modelo.currentData(), gestor.EMBEDDING_GEMMA]
        self._progreso.setVisible(True)
        self._progreso.setRange(0, 0)
        self._descarga = TrabajadorDescarga(self._servicios, claves)
        self._descarga.progreso.connect(self._al_progresar)
        self._descarga.terminado.connect(lambda nombre: self._estado_modelo.setText(f"Listo: {nombre}"))
        self._descarga.fallo.connect(lambda error: QMessageBox.warning(self, "Descarga fallida", error))
        self._descarga.finished.connect(self._fin_descarga)
        self._descarga.start()

    def _al_progresar(self, nombre: str, recibido: int, total: int) -> None:
        self._progreso.setRange(0, max(total, 1))
        self._progreso.setValue(recibido)
        self._progreso.setFormat(f"{nombre}: %p%")

    def _fin_descarga(self) -> None:
        self._progreso.setVisible(False)
        self._actualizar_estado()

    def _borrar(self) -> None:
        clave = self._modelo.currentData()
        modelo = self._servicios.catalogo[clave]
        if QMessageBox.question(self, "Borrar modelo", f"¿Borrar «{modelo.nombre}» del disco?") != QMessageBox.StandardButton.Yes:
            return
        gestor.borrar(modelo, self._servicios.carpeta_modelos)
        self._actualizar_estado()

    def _guardar(self) -> None:
        proveedor = self._proveedor.currentData()
        if proveedor == PROVEEDOR_API and not self._api_aceptada.isChecked():
            QMessageBox.warning(self, "Falta confirmar", "Marca la casilla de envío de datos fuera del equipo.")
            return
        self._servicios.guardar_clave_api(self._api_clave.text().strip())
        self._servicios.guardar_ajustes(
            Ajustes(
                proveedor=proveedor,
                modelo_llm=self._modelo.currentData(),
                n_ctx=self._n_ctx.value(),
                openrouter_modelo=self._api_modelo.text().strip(),
                api_aceptada=self._api_aceptada.isChecked(),
            )
        )
        self.accept()
