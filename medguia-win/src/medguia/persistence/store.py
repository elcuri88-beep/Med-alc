"""Persistencia SQLite: documentos, fragmentos, FTS5 (BM25), vectores (sqlite-vec) y exportación del índice."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import sqlite_vec

from medguia.domain.models import (
    Ambito,
    EstadoDocumento,
    FragmentoNuevo,
    MetaDocumento,
)

VERSION_ESQUEMA = 2
DIMENSIONES_POR_DEFECTO = 768  # EmbeddingGemma
FORMATO_INDICE = "medguia-indice"
VERSION_FORMATO_INDICE = 1

ESQUEMA = """
CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documentos (
    id INTEGER PRIMARY KEY,
    titulo TEXT NOT NULL,
    sociedad TEXT NOT NULL,
    anio INTEGER NOT NULL,
    ambito TEXT NOT NULL CHECK (ambito IN ('local', 'nacional', 'europeo')),
    especialidad TEXT NOT NULL,
    ruta TEXT NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    paginas INTEGER NOT NULL DEFAULT 0,
    paginas_sin_texto TEXT NOT NULL DEFAULT '[]',
    paginas_impresas TEXT NOT NULL DEFAULT '{}',
    estado TEXT NOT NULL,
    error TEXT,
    importado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fragmentos (
    id INTEGER PRIMARY KEY,
    documento_id INTEGER NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    orden INTEGER NOT NULL,
    seccion TEXT NOT NULL,
    pagina_inicio INTEGER NOT NULL,
    pagina_fin INTEGER NOT NULL,
    es_tabla INTEGER NOT NULL,
    texto TEXT NOT NULL,
    texto_indexado TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS fragmentos_documento ON fragmentos(documento_id, orden);
-- Tabla FTS5 independiente; rowid = fragmentos.id.
CREATE VIRTUAL TABLE IF NOT EXISTS fragmentos_fts USING fts5(
    texto_indexado,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


class DocumentoDuplicado(Exception):
    """Ya existe un documento con el mismo contenido (mismo SHA-256)."""


class IndiceNoValido(Exception):
    """El archivo no es un índice de MedGuía compatible."""


class DimensionesIncompatibles(Exception):
    """La base de datos guarda vectores de otra dimensión."""


@dataclass(frozen=True)
class DocumentoRegistrado:
    id: int
    meta: MetaDocumento
    ruta: Path
    sha256: str
    paginas: int
    paginas_sin_texto: tuple[int, ...]
    paginas_impresas: dict[int, str]
    estado: EstadoDocumento
    error: str | None
    importado_en: str


@dataclass(frozen=True)
class FilaFragmento:
    id: int
    documento_id: int
    orden: int
    seccion: str
    pagina_inicio: int
    pagina_fin: int
    es_tabla: bool
    texto: str
    texto_indexado: str


class Store:
    def __init__(self, ruta_bd: Path, dimensiones: int = DIMENSIONES_POR_DEFECTO) -> None:
        ruta_bd.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(ruta_bd, isolation_level=None)
        self._con.row_factory = sqlite3.Row
        _cargar_vec(self._con)
        self._con.execute("PRAGMA foreign_keys = ON")
        self._con.execute("PRAGMA journal_mode = WAL")
        self._con.executescript(ESQUEMA)
        _migrar(self._con)
        self._con.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS vectores USING vec0("
            f"embedding float[{dimensiones}] distance_metric=cosine)"
        )
        self._con.execute(
            "INSERT OR IGNORE INTO meta(clave, valor) VALUES ('version_esquema', ?)",
            (str(VERSION_ESQUEMA),),
        )
        guardadas = self.meta_valor("dimensiones")
        if guardadas is None:
            self.fijar_meta_valor("dimensiones", str(dimensiones))
        elif int(guardadas) != dimensiones:
            raise DimensionesIncompatibles(
                f"El índice tiene vectores de {guardadas} dimensiones, no de {dimensiones}"
            )
        self.dimensiones = dimensiones

    def cerrar(self) -> None:
        self._con.close()

    def _transaccion(self):
        return _Transaccion(self._con)

    # --- meta ----------------------------------------------------------------

    def meta_valor(self, clave: str) -> str | None:
        fila = self._con.execute("SELECT valor FROM meta WHERE clave = ?", (clave,)).fetchone()
        return fila["valor"] if fila else None

    def fijar_meta_valor(self, clave: str, valor: str) -> None:
        self._con.execute(
            "INSERT INTO meta(clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
            (clave, valor),
        )

    # --- documentos ----------------------------------------------------------

    def insertar_documento(self, meta: MetaDocumento, ruta: Path, sha256: str) -> int:
        existente = self._con.execute(
            "SELECT id FROM documentos WHERE sha256 = ?", (sha256,)
        ).fetchone()
        if existente:
            raise DocumentoDuplicado(str(existente["id"]))
        cursor = self._con.execute(
            """
            INSERT INTO documentos
                (titulo, sociedad, anio, ambito, especialidad, ruta, sha256, estado, importado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meta.titulo,
                meta.sociedad,
                meta.anio,
                meta.ambito.value,
                meta.especialidad,
                str(ruta),
                sha256,
                EstadoDocumento.PENDIENTE.value,
                _ahora(),
            ),
        )
        return int(cursor.lastrowid)

    def documento(self, documento_id: int) -> DocumentoRegistrado | None:
        fila = self._con.execute("SELECT * FROM documentos WHERE id = ?", (documento_id,)).fetchone()
        return _a_documento(fila) if fila else None

    def documentos(self) -> list[DocumentoRegistrado]:
        filas = self._con.execute(
            "SELECT * FROM documentos ORDER BY anio DESC, titulo COLLATE NOCASE"
        ).fetchall()
        return [_a_documento(f) for f in filas]

    def documentos_por_sha256(self, sha256: str) -> DocumentoRegistrado | None:
        fila = self._con.execute("SELECT * FROM documentos WHERE sha256 = ?", (sha256,)).fetchone()
        return _a_documento(fila) if fila else None

    def actualizar_meta(self, documento_id: int, meta: MetaDocumento) -> None:
        self._con.execute(
            """
            UPDATE documentos
               SET titulo = ?, sociedad = ?, anio = ?, ambito = ?, especialidad = ?
             WHERE id = ?
            """,
            (
                meta.titulo,
                meta.sociedad,
                meta.anio,
                meta.ambito.value,
                meta.especialidad,
                documento_id,
            ),
        )

    def fijar_estado(
        self,
        documento_id: int,
        estado: EstadoDocumento,
        error: str | None = None,
    ) -> None:
        self._con.execute(
            "UPDATE documentos SET estado = ?, error = ? WHERE id = ?",
            (estado.value, error, documento_id),
        )

    def recuperar_interrumpidos(self) -> int:
        """Tras un cierre inesperado, los documentos a medio indexar vuelven a pendientes."""
        cursor = self._con.execute(
            "UPDATE documentos SET estado = ? WHERE estado = ?",
            (EstadoDocumento.PENDIENTE.value, EstadoDocumento.INDEXANDO.value),
        )
        return cursor.rowcount

    def borrar_documento(self, documento_id: int) -> None:
        with self._transaccion():
            self._borrar_vectores_y_texto(documento_id)
            self._con.execute("DELETE FROM documentos WHERE id = ?", (documento_id,))

    # --- fragmentos ----------------------------------------------------------

    def reemplazar_fragmentos(
        self,
        documento_id: int,
        fragmentos: list[FragmentoNuevo],
        paginas: int,
        paginas_sin_texto: list[int],
        paginas_impresas: dict[int, str] | None = None,
    ) -> None:
        """Sustituye fragmentos (y sus vectores) y marca el documento como listo, en una transacción."""
        with self._transaccion():
            self._borrar_vectores_y_texto(documento_id)
            for fragmento in fragmentos:
                cursor = self._con.execute(
                    """
                    INSERT INTO fragmentos
                        (documento_id, orden, seccion, pagina_inicio, pagina_fin,
                         es_tabla, texto, texto_indexado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        documento_id,
                        fragmento.orden,
                        fragmento.seccion,
                        fragmento.pagina_inicio,
                        fragmento.pagina_fin,
                        int(fragmento.es_tabla),
                        fragmento.texto,
                        fragmento.texto_indexado,
                    ),
                )
                self._con.execute(
                    "INSERT INTO fragmentos_fts(rowid, texto_indexado) VALUES (?, ?)",
                    (cursor.lastrowid, fragmento.texto_indexado),
                )
            self._con.execute(
                """
                UPDATE documentos
                   SET paginas = ?, paginas_sin_texto = ?, paginas_impresas = ?,
                       estado = ?, error = NULL
                 WHERE id = ?
                """,
                (
                    paginas,
                    json.dumps(paginas_sin_texto),
                    json.dumps(paginas_impresas or {}),
                    EstadoDocumento.LISTO.value,
                    documento_id,
                ),
            )

    def fragmentos_por_ids(self, ids: set[int]) -> dict[int, FilaFragmento]:
        if not ids:
            return {}
        marcas = ",".join("?" for _ in ids)
        filas = self._con.execute(
            f"SELECT * FROM fragmentos WHERE id IN ({marcas})", tuple(ids)
        ).fetchall()
        return {f["id"]: _a_fragmento(f) for f in filas}

    def fragmentos(self, documento_id: int) -> list[FilaFragmento]:
        filas = self._con.execute(
            "SELECT * FROM fragmentos WHERE documento_id = ? ORDER BY orden",
            (documento_id,),
        ).fetchall()
        return [_a_fragmento(f) for f in filas]

    def reescribir_cabeceras(self, documento_id: int, nuevos_indexados: dict[int, str]) -> None:
        """Cambia el texto indexado y descarta sus vectores: deben recalcularse."""
        with self._transaccion():
            for fragmento_id, indexado in nuevos_indexados.items():
                self._con.execute(
                    "UPDATE fragmentos SET texto_indexado = ? WHERE id = ?",
                    (indexado, fragmento_id),
                )
                self._con.execute(
                    "UPDATE fragmentos_fts SET texto_indexado = ? WHERE rowid = ?",
                    (indexado, fragmento_id),
                )
            self._con.execute(
                "DELETE FROM vectores WHERE rowid IN (SELECT id FROM fragmentos WHERE documento_id = ?)",
                (documento_id,),
            )

    def buscar_texto(self, consulta: str, limite: int = 10) -> list[FilaFragmento]:
        """BM25 sobre el texto indexado, en orden de relevancia."""
        terminos = [t for t in consulta.replace('"', " ").split() if t]
        if not terminos:
            return []
        expresion = " OR ".join(f'"{t}"' for t in terminos)
        filas = self._con.execute(
            """
            SELECT f.* FROM fragmentos_fts
              JOIN fragmentos f ON f.id = fragmentos_fts.rowid
             WHERE fragmentos_fts MATCH ?
             ORDER BY bm25(fragmentos_fts)
             LIMIT ?
            """,
            (expresion, limite),
        ).fetchall()
        return [_a_fragmento(f) for f in filas]

    # --- vectores ------------------------------------------------------------

    def fragmentos_sin_vector(self, documento_id: int) -> list[FilaFragmento]:
        filas = self._con.execute(
            """
            SELECT * FROM fragmentos
             WHERE documento_id = ?
               AND id NOT IN (SELECT rowid FROM vectores)
             ORDER BY orden
            """,
            (documento_id,),
        ).fetchall()
        return [_a_fragmento(f) for f in filas]

    def documentos_con_fragmentos_sin_vector(self) -> list[int]:
        filas = self._con.execute(
            """
            SELECT DISTINCT documento_id FROM fragmentos
             WHERE id NOT IN (SELECT rowid FROM vectores)
             ORDER BY documento_id
            """
        ).fetchall()
        return [int(f["documento_id"]) for f in filas]

    def guardar_vectores(self, pares: list[tuple[int, list[float]]]) -> None:
        with self._transaccion():
            for fragmento_id, vector in pares:
                self._validar_dimension(vector)
                self._con.execute("DELETE FROM vectores WHERE rowid = ?", (fragmento_id,))
                self._con.execute(
                    "INSERT INTO vectores(rowid, embedding) VALUES (?, ?)",
                    (fragmento_id, sqlite_vec.serialize_float32(vector)),
                )

    def vecinos(self, vector: list[float], k: int) -> list[tuple[int, float]]:
        """Fragmentos más parecidos: (id, similitud coseno), de mayor a menor similitud."""
        self._validar_dimension(vector)
        filas = self._con.execute(
            """
            SELECT rowid, distance FROM vectores
             WHERE embedding MATCH ? AND k = ?
             ORDER BY distance
            """,
            (sqlite_vec.serialize_float32(vector), k),
        ).fetchall()
        return [(int(f["rowid"]), 1.0 - float(f["distance"])) for f in filas]

    def _validar_dimension(self, vector: list[float]) -> None:
        if len(vector) != self.dimensiones:
            raise DimensionesIncompatibles(
                f"Vector de {len(vector)} dimensiones; el índice usa {self.dimensiones}"
            )

    def _borrar_vectores_y_texto(self, documento_id: int) -> None:
        self._con.execute(
            "DELETE FROM vectores WHERE rowid IN (SELECT id FROM fragmentos WHERE documento_id = ?)",
            (documento_id,),
        )
        self._con.execute(
            "DELETE FROM fragmentos_fts WHERE rowid IN (SELECT id FROM fragmentos WHERE documento_id = ?)",
            (documento_id,),
        )
        self._con.execute("DELETE FROM fragmentos WHERE documento_id = ?", (documento_id,))

    # --- exportar / importar -------------------------------------------------

    def exportar(self, destino: Path) -> None:
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            destino.unlink()
        self._con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        self._con.execute("VACUUM INTO ?", (str(destino),))
        origen = sqlite3.connect(destino)
        try:
            origen.executemany(
                "INSERT OR REPLACE INTO meta(clave, valor) VALUES (?, ?)",
                [
                    ("formato", FORMATO_INDICE),
                    ("version_formato", str(VERSION_FORMATO_INDICE)),
                    ("exportado_en", _ahora()),
                ],
            )
            origen.commit()
        finally:
            origen.close()

    def importar(self, origen_ruta: Path, modelo_activo: str | None = None) -> tuple[int, int]:
        """Añade los documentos que no estén ya presentes (por SHA-256), con sus vectores si el modelo coincide.

        Solo se copian vectores si el índice y la base local usan `modelo_activo`. Si no,
        los fragmentos llegan sin vectores y `Biblioteca.vectorizar_faltantes` los calcula después.
        Devuelve (importados, omitidos).
        """
        origen = sqlite3.connect(f"file:{origen_ruta}?mode=ro", uri=True)
        origen.row_factory = sqlite3.Row
        _cargar_vec(origen)
        try:
            self._validar_indice(origen)
            vectores_compatibles = self._vectores_compatibles(origen, modelo_activo)
            importados = omitidos = 0
            with self._transaccion():
                for doc in origen.execute("SELECT * FROM documentos").fetchall():
                    if self.documentos_por_sha256(doc["sha256"]):
                        omitidos += 1
                        continue
                    nuevo_id = self._copiar_documento(doc)
                    mapa = self._copiar_fragmentos(origen, doc["id"], nuevo_id)
                    if vectores_compatibles:
                        self._copiar_vectores(origen, mapa)
                    importados += 1
            return importados, omitidos
        finally:
            origen.close()

    def _validar_indice(self, origen: sqlite3.Connection) -> None:
        try:
            filas = dict(origen.execute("SELECT clave, valor FROM meta").fetchall())
        except sqlite3.DatabaseError as error:
            raise IndiceNoValido(str(error)) from error
        if filas.get("formato") != FORMATO_INDICE:
            raise IndiceNoValido("No es un índice de MedGuía")
        if int(filas.get("version_formato", 0)) > VERSION_FORMATO_INDICE:
            raise IndiceNoValido("El índice es de una versión más reciente de la app")

    def _vectores_compatibles(self, origen: sqlite3.Connection, modelo_activo: str | None) -> bool:
        if modelo_activo is None:
            return False
        modelo_origen = origen.execute(
            "SELECT valor FROM meta WHERE clave = 'modelo_embedding'"
        ).fetchone()
        dimensiones_origen = origen.execute(
            "SELECT valor FROM meta WHERE clave = 'dimensiones'"
        ).fetchone()
        if modelo_origen is None or dimensiones_origen is None:
            return False
        modelo_local = self.meta_valor("modelo_embedding")
        if modelo_local is not None and modelo_local != modelo_activo:
            return False
        compatible = (
            modelo_origen["valor"] == modelo_activo
            and int(dimensiones_origen["valor"]) == self.dimensiones
        )
        if compatible and modelo_local is None:
            self.fijar_meta_valor("modelo_embedding", modelo_activo)
        return compatible

    def _copiar_documento(self, doc: sqlite3.Row) -> int:
        cursor = self._con.execute(
            """
            INSERT INTO documentos
                (titulo, sociedad, anio, ambito, especialidad, ruta, sha256,
                 paginas, paginas_sin_texto, paginas_impresas, estado, error, importado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                doc["titulo"],
                doc["sociedad"],
                doc["anio"],
                doc["ambito"],
                doc["especialidad"],
                doc["ruta"],
                doc["sha256"],
                doc["paginas"],
                doc["paginas_sin_texto"],
                doc["paginas_impresas"],
                EstadoDocumento.LISTO.value,
                _ahora(),
            ),
        )
        return int(cursor.lastrowid)

    def _copiar_fragmentos(
        self,
        origen: sqlite3.Connection,
        origen_id: int,
        destino_id: int,
    ) -> dict[int, int]:
        """Copia fragmentos y devuelve el mapa id de origen -> id nuevo."""
        mapa: dict[int, int] = {}
        filas = origen.execute(
            "SELECT * FROM fragmentos WHERE documento_id = ? ORDER BY orden",
            (origen_id,),
        ).fetchall()
        for fila in filas:
            cursor = self._con.execute(
                """
                INSERT INTO fragmentos
                    (documento_id, orden, seccion, pagina_inicio, pagina_fin,
                     es_tabla, texto, texto_indexado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    destino_id,
                    fila["orden"],
                    fila["seccion"],
                    fila["pagina_inicio"],
                    fila["pagina_fin"],
                    fila["es_tabla"],
                    fila["texto"],
                    fila["texto_indexado"],
                ),
            )
            nuevo_id = int(cursor.lastrowid)
            mapa[int(fila["id"])] = nuevo_id
            self._con.execute(
                "INSERT INTO fragmentos_fts(rowid, texto_indexado) VALUES (?, ?)",
                (nuevo_id, fila["texto_indexado"]),
            )
        return mapa

    def _copiar_vectores(self, origen: sqlite3.Connection, mapa: dict[int, int]) -> None:
        """Copia los vectores ya serializados. Requiere la extensión cargada en la conexión de origen."""
        if not _existe_tabla_vectores(origen):
            return
        for fila in origen.execute("SELECT rowid, embedding FROM vectores").fetchall():
            nuevo_id = mapa.get(int(fila["rowid"]))
            if nuevo_id is not None:
                self._con.execute(
                    "INSERT INTO vectores(rowid, embedding) VALUES (?, ?)",
                    (nuevo_id, fila["embedding"]),
                )


def _cargar_vec(con: sqlite3.Connection) -> None:
    con.enable_load_extension(True)
    try:
        sqlite_vec.load(con)
    finally:
        con.enable_load_extension(False)


def _migrar(con: sqlite3.Connection) -> None:
    """Añade columnas nuevas a bases creadas en versiones anteriores."""
    columnas = {f["name"] for f in con.execute("PRAGMA table_info(documentos)").fetchall()}
    if "paginas_impresas" not in columnas:
        con.execute("ALTER TABLE documentos ADD COLUMN paginas_impresas TEXT NOT NULL DEFAULT '{}'")


def _existe_tabla_vectores(con: sqlite3.Connection) -> bool:
    fila = con.execute("SELECT 1 FROM sqlite_master WHERE name = 'vectores'").fetchone()
    return fila is not None


class _Transaccion:
    def __init__(self, con: sqlite3.Connection) -> None:
        self._con = con

    def __enter__(self) -> None:
        self._con.execute("BEGIN IMMEDIATE")

    def __exit__(self, tipo, valor, traza) -> None:
        self._con.execute("COMMIT" if tipo is None else "ROLLBACK")


def _ahora() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _a_documento(fila: sqlite3.Row) -> DocumentoRegistrado:
    return DocumentoRegistrado(
        id=int(fila["id"]),
        meta=MetaDocumento(
            titulo=fila["titulo"],
            sociedad=fila["sociedad"],
            anio=int(fila["anio"]),
            ambito=Ambito(fila["ambito"]),
            especialidad=fila["especialidad"],
        ),
        ruta=Path(fila["ruta"]),
        sha256=fila["sha256"],
        paginas=int(fila["paginas"]),
        paginas_sin_texto=tuple(json.loads(fila["paginas_sin_texto"])),
        paginas_impresas={int(k): v for k, v in json.loads(fila["paginas_impresas"]).items()},
        estado=EstadoDocumento(fila["estado"]),
        error=fila["error"],
        importado_en=fila["importado_en"],
    )


def _a_fragmento(fila: sqlite3.Row) -> FilaFragmento:
    return FilaFragmento(
        id=int(fila["id"]),
        documento_id=int(fila["documento_id"]),
        orden=int(fila["orden"]),
        seccion=fila["seccion"],
        pagina_inicio=int(fila["pagina_inicio"]),
        pagina_fin=int(fila["pagina_fin"]),
        es_tabla=bool(fila["es_tabla"]),
        texto=fila["texto"],
        texto_indexado=fila["texto_indexado"],
    )
