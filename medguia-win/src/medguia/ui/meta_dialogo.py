from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
)

from medguia.domain.models import Ambito, MetaDocumento

ETIQUETAS_AMBITO = {
    Ambito.LOCAL: "Local",
    Ambito.NACIONAL: "Nacional",
    Ambito.EUROPEO: "Europeo",
}


class MetaDialogo(QDialog):
    """Formulario de metadatos. Se usa al importar y al editar."""

    def __init__(
        self,
        titulo_ventana: str,
        meta: MetaDocumento | None,
        parent=None,
        titulo_sugerido: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo_ventana)
        self.setMinimumWidth(420)

        self._titulo = QLineEdit(meta.titulo if meta else titulo_sugerido)
        self._sociedad = QLineEdit(meta.sociedad if meta else "")
        self._anio = QSpinBox()
        self._anio.setRange(1900, 2100)
        self._anio.setValue(meta.anio if meta else 2024)
        self._ambito = QComboBox()
        for ambito, etiqueta in ETIQUETAS_AMBITO.items():
            self._ambito.addItem(etiqueta, ambito)
        if meta:
            self._ambito.setCurrentIndex(list(Ambito).index(meta.ambito))
        self._especialidad = QLineEdit(meta.especialidad if meta else "")

        formulario = QFormLayout()
        formulario.addRow("Título", self._titulo)
        formulario.addRow("Sociedad / origen", self._sociedad)
        formulario.addRow("Año", self._anio)
        formulario.addRow("Ámbito", self._ambito)
        formulario.addRow("Especialidad", self._especialidad)

        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)

        diseno = QVBoxLayout(self)
        diseno.addLayout(formulario)
        diseno.addWidget(botones)

    def meta(self) -> MetaDocumento:
        return MetaDocumento(
            titulo=self._titulo.text().strip(),
            sociedad=self._sociedad.text().strip(),
            anio=self._anio.value(),
            ambito=self._ambito.currentData(),
            especialidad=self._especialidad.text().strip(),
        )

    def accept(self) -> None:
        try:
            self.meta()
        except ValueError as error:
            QMessageBox.warning(self, "Metadatos no válidos", str(error))
            return
        super().accept()
