"""Hilos para generar respuestas y descargar modelos. Nunca bloquean la interfaz."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from medguia.generation.responder import Responder
from medguia.ingestion.tokens import ContadorAproximado
from medguia.models import gestor
from medguia.persistence.store import Store
from medguia.retrieval.busqueda import FiltroBusqueda, Recuperador
from medguia.ui.servicios import Servicios


class TrabajadorRespuesta(QThread):
    token = Signal(str)
    respondido = Signal(object)  # Respuesta
    fallo = Signal(str)

    def __init__(self, servicios: Servicios, pregunta: str, filtro: FiltroBusqueda) -> None:
        super().__init__()
        self._servicios = servicios
        self._pregunta = pregunta
        self._filtro = filtro

    def run(self) -> None:
        store = Store(self._servicios.ruta_bd)
        try:
            embedder = self._servicios.embedder()
            if embedder is None:
                raise RuntimeError("Falta EmbeddingGemma. Descárgalo en Ajustes.")
            responder = Responder(
                Recuperador(store, embedder),
                self._servicios.llm(),
                ContadorAproximado(),
                self._servicios.perfil(),
            )
            respuesta = responder.responder(self._pregunta, self._filtro, al_recibir_token=self.token.emit)
            self.respondido.emit(respuesta)
        except Exception as error:
            self.fallo.emit(str(error))
        finally:
            store.cerrar()


class TrabajadorDescarga(QThread):
    progreso = Signal(str, int, int)  # nombre, recibido, total
    terminado = Signal(str)
    fallo = Signal(str)

    def __init__(self, servicios: Servicios, claves: list[str]) -> None:
        super().__init__()
        self._servicios = servicios
        self._claves = claves

    def run(self) -> None:
        for clave in self._claves:
            modelo = self._servicios.catalogo[clave]
            try:
                if gestor.verificar(modelo, self._servicios.carpeta_modelos):
                    self.terminado.emit(modelo.nombre)
                    continue
                gestor.descargar(
                    modelo,
                    self._servicios.carpeta_modelos,
                    progreso=lambda r, t, n=modelo.nombre: self.progreso.emit(n, r, t),
                )
                self.terminado.emit(modelo.nombre)
            except Exception as error:
                self.fallo.emit(f"{modelo.nombre}: {error}")
                return
