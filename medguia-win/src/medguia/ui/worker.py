"""Indexado en segundo plano. Abre su propia conexión SQLite: las conexiones no cruzan hilos."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from medguia.domain.models import EstadisticasIndexado, EstadoDocumento
from medguia.ingestion.service import Biblioteca
from medguia.persistence.store import Store


class _Cancelado(Exception):
    pass


class TrabajadorIndexado(QThread):
    progreso = Signal(int, int, int)  # documento, página, total
    documento_listo = Signal(int, object)  # documento, EstadisticasIndexado
    documento_fallido = Signal(int, str)

    def __init__(self, ruta_bd: Path, documentos: list[int]) -> None:
        super().__init__()
        self._ruta_bd = ruta_bd
        self._documentos = documentos

    def run(self) -> None:
        store = Store(self._ruta_bd)
        try:
            biblioteca = Biblioteca(store)
            for documento_id in self._documentos:
                if self.isInterruptionRequested():
                    break
                try:
                    estadisticas = self._indexar(biblioteca, documento_id)
                except _Cancelado:
                    store.fijar_estado(documento_id, EstadoDocumento.PENDIENTE)
                    break
                except Exception as error:
                    self.documento_fallido.emit(documento_id, str(error))
                else:
                    self.documento_listo.emit(documento_id, estadisticas)
        finally:
            store.cerrar()

    def _indexar(self, biblioteca: Biblioteca, documento_id: int) -> EstadisticasIndexado:
        def avance(pagina: int, total: int, _mensaje: str) -> None:
            if self.isInterruptionRequested():
                raise _Cancelado()
            self.progreso.emit(documento_id, pagina, total)

        return biblioteca.indexar(documento_id, progreso=avance)
