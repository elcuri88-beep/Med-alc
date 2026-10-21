"""Casos de uso de la biblioteca: importar, indexar, vectorizar, editar, reindexar y borrar."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path

from medguia.domain.models import EstadisticasIndexado, EstadoDocumento, MetaDocumento
from medguia.domain.puertos import Embedder
from medguia.ingestion import chunker
from medguia.ingestion.pdf_extract import extraer
from medguia.ingestion.tokens import ContadorAproximado, ContadorTokens
from medguia.persistence.store import DocumentoRegistrado, Store

Progreso = Callable[[int, int, str], None]
LOTE_VECTORES = 16


class ModeloDeEmbeddingsDistinto(Exception):
    """El índice se creó con otro modelo de embeddings. Hay que reindexar."""


class Biblioteca:
    def __init__(
        self,
        store: Store,
        contar: ContadorTokens | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._store = store
        self._contar = contar or ContadorAproximado()
        self._embedder = embedder
        if embedder is not None:
            guardado = store.meta_valor("modelo_embedding")
            if guardado is not None and guardado != embedder.nombre:
                raise ModeloDeEmbeddingsDistinto(
                    f"El índice usa «{guardado}»; el modelo activo es «{embedder.nombre}»."
                )

    def importar(self, ruta: Path, meta: MetaDocumento) -> int:
        """Registra el PDF como pendiente. No lo indexa todavía."""
        sha256 = _sha256(ruta)
        return self._store.insertar_documento(meta, ruta.resolve(), sha256)

    def documentos(self) -> list[DocumentoRegistrado]:
        return self._store.documentos()

    def documento(self, documento_id: int) -> DocumentoRegistrado | None:
        return self._store.documento(documento_id)

    def pendientes(self) -> list[DocumentoRegistrado]:
        return [
            d
            for d in self._store.documentos()
            if d.estado in (EstadoDocumento.PENDIENTE, EstadoDocumento.ERROR)
        ]

    def indexar(self, documento_id: int, progreso: Progreso | None = None) -> EstadisticasIndexado:
        """Extrae, trocea, guarda y vectoriza un documento. Si falla, lo deja en estado de error."""
        documento = self._store.documento(documento_id)
        if documento is None:
            raise KeyError(f"Documento {documento_id} no existe")

        inicio = time.perf_counter()
        self._store.fijar_estado(documento_id, EstadoDocumento.INDEXANDO)
        try:
            def avance(pagina: int, total: int) -> None:
                if progreso:
                    progreso(pagina, total, f"Extrayendo página {pagina} de {total}")

            extraccion = extraer(documento.ruta, progreso=avance)
            fragmentos = chunker.trocear(extraccion.bloques, documento.meta, self._contar)
            self._store.reemplazar_fragmentos(
                documento_id,
                fragmentos,
                paginas=extraccion.paginas_total,
                paginas_sin_texto=extraccion.paginas_sin_texto,
                paginas_impresas=extraccion.paginas_impresas,
            )
            self.vectorizar(documento_id, progreso)
        except Exception as error:
            self._store.fijar_estado(documento_id, EstadoDocumento.ERROR, error=str(error))
            raise

        return EstadisticasIndexado(
            paginas=extraccion.paginas_total,
            fragmentos=len(fragmentos),
            segundos=time.perf_counter() - inicio,
        )

    def vectorizar(self, documento_id: int, progreso: Progreso | None = None) -> int:
        """Calcula los vectores que falten. Cada lote se guarda por separado: se reanuda tras un fallo."""
        if self._embedder is None:
            return 0
        documento = self._store.documento(documento_id)
        if documento is None:
            raise KeyError(f"Documento {documento_id} no existe")
        self._store.fijar_meta_valor("modelo_embedding", self._embedder.nombre)
        self._store.fijar_meta_valor("dimensiones", str(self._embedder.dimensiones))

        pendientes = self._store.fragmentos_sin_vector(documento_id)
        for inicio in range(0, len(pendientes), LOTE_VECTORES):
            lote = pendientes[inicio : inicio + LOTE_VECTORES]
            vectores = self._embedder.documentos(
                [(documento.meta.titulo, f.texto_indexado) for f in lote]
            )
            self._store.guardar_vectores(list(zip([f.id for f in lote], vectores)))
            if progreso:
                progreso(inicio + len(lote), len(pendientes), "Calculando vectores")
        return len(pendientes)

    def vectorizar_faltantes(self, progreso: Progreso | None = None) -> int:
        """Al arrancar o tras importar un índice: vectoriza los documentos que lo necesiten."""
        total = 0
        for documento_id in self._store.documentos_con_fragmentos_sin_vector():
            total += self.vectorizar(documento_id, progreso)
        return total

    def reindexar(self, documento_id: int, progreso: Progreso | None = None) -> EstadisticasIndexado:
        return self.indexar(documento_id, progreso)

    def editar(self, documento_id: int, meta: MetaDocumento) -> None:
        """Cambia metadatos y reescribe cabeceras. Los vectores se recalculan después."""
        documento = self._store.documento(documento_id)
        if documento is None:
            raise KeyError(f"Documento {documento_id} no existe")
        self._store.actualizar_meta(documento_id, meta)

        nuevos: dict[int, str] = {}
        for fila in self._store.fragmentos(documento_id):
            cabecera = chunker.cabecera(meta, fila.seccion, fila.pagina_inicio, fila.pagina_fin)
            nuevos[fila.id] = f"{cabecera}\n{fila.texto}"
        self._store.reescribir_cabeceras(documento_id, nuevos)
        self.vectorizar(documento_id)

    def borrar(self, documento_id: int) -> None:
        self._store.borrar_documento(documento_id)

    def reparar_estados(self) -> int:
        """Llamar al arrancar: los documentos interrumpidos vuelven a pendientes."""
        return self._store.recuperar_interrumpidos()


def _sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            digest.update(bloque)
    return digest.hexdigest()
