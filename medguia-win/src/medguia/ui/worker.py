"""Indexado y vectorización en segundo plano. Cada hilo abre su propia conexión SQLite."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from medguia.domain.models import EstadisticasIndexado, EstadoDocumento
from medguia.domain.puertos import Embedder
from medguia.ingestion.service import Biblioteca
from medguia.persistence.store import Store


class _Cancelado(Exception):
    pass


class TrabajadorIndexado(QThread):
    progreso = Signal(int, int, int)  # documento, página o vector, total
    documento_listo = Signal(int, object)  # documento, EstadisticasIndexado | None
    documento_fallido = Signal(int, str)

    def __init__(
        self,
        ruta_bd: Path,
        documentos: list[int],
        embedder: Embedder | None = None,
        solo_vectores: bool = False,
    ) -> None:
        super().__init__()
        self._ruta_bd = ruta_bd
        self._documentos = documentos
        self._embedder = embedder
        self._solo_vectores = solo_vectores

    def run(self) -> None:
        store = Store(self._ruta_bd)
        try:
            biblioteca = Biblioteca(store, embedder=self._embedder)
            for documento_id in self._documentos:
                if self.isInterruptionRequested():
                    break
                try:
                    resultado = self._procesar(biblioteca, documento_id)
                except _Cancelado:
                    store.fijar_estado(documento_id, EstadoDocumento.PENDIENTE)
                    break
                except Exception as error:
                    self.documento_fallido.emit(documento_id, str(error))
                else:
                    self.documento_listo.emit(documento_id, resultado)
        finally:
            store.cerrar()

    def _procesar(self, biblioteca: Biblioteca, documento_id: int) -> EstadisticasIndexado | None:
        def avance(pagina: int, total: int, _mensaje: str = "") -> None:
            if self.isInterruptionRequested():
                raise _Cancelado()
            self.progreso.emit(documento_id, pagina, total)

        if self._solo_vectores:
            biblioteca.vectorizar(documento_id, avance)
            return None
        return biblioteca.indexar(documento_id, progreso=avance)
