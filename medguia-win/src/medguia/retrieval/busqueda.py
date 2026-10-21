"""Búsqueda híbrida: BM25 + vectores, fusión RRF, diversidad por documento y umbral de cobertura.

Cobertura: la pregunta está cubierta si el mejor fragmento por vectores supera el umbral de similitud.
Si no lo supera, el responder contesta «las guías no cubren» sin llamar al LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from medguia.domain.models import MetaDocumento
from medguia.domain.puertos import Embedder
from medguia.persistence.store import DocumentoRegistrado, FilaFragmento, Store

UMBRAL_SIMILITUD_POR_DEFECTO = 0.55  # calibrar con el conjunto de evaluación (Fase 4)
K_CANDIDATOS = 40
K_RRF = 60
MAX_POR_DOCUMENTO = 3
POOL_FINAL = 20
FACTOR_K_CON_FILTRO = 12  # con filtros activos se miran más candidatos: los filtros se aplican después
PALABRAS_VACIAS = frozenset(
    "de la el los las un una unos unas y o u a en con por para del al que se es son como cual cuál "
    "cuando cuándo qué cuáles sobre entre desde hasta sin más muy ser está están hay tiene tienen".split()
)


def terminos_de_busqueda(pregunta: str) -> str:
    """Quita palabras vacías para que el BM25 no premie «de», «la», «en»… Si no queda nada, usa la pregunta."""
    palabras = [p for p in pregunta.replace('"', " ").split() if p.lower().strip("¿?¡!.,;:()") not in PALABRAS_VACIAS]
    return " ".join(palabras) or pregunta


@dataclass(frozen=True)
class FiltroBusqueda:
    especialidades: frozenset[str] = field(default_factory=frozenset)
    sociedades: frozenset[str] = field(default_factory=frozenset)
    anio_minimo: int | None = None

    @property
    def activo(self) -> bool:
        return bool(self.especialidades or self.sociedades or self.anio_minimo is not None)

    def admite(self, meta: MetaDocumento) -> bool:
        if self.especialidades and meta.especialidad not in self.especialidades:
            return False
        if self.sociedades and meta.sociedad not in self.sociedades:
            return False
        if self.anio_minimo is not None and meta.anio < self.anio_minimo:
            return False
        return True


@dataclass(frozen=True)
class Candidato:
    fragmento: FilaFragmento
    documento: DocumentoRegistrado
    puntuacion: float  # RRF
    similitud: float | None  # coseno, si el fragmento apareció en la búsqueda vectorial


@dataclass(frozen=True)
class Recuperacion:
    candidatos: list[Candidato]
    cubierta: bool
    mejor_similitud: float | None


class Recuperador:
    def __init__(
        self,
        store: Store,
        embedder: Embedder,
        umbral_similitud: float = UMBRAL_SIMILITUD_POR_DEFECTO,
        k_candidatos: int = K_CANDIDATOS,
        max_por_documento: int = MAX_POR_DOCUMENTO,
        pool: int = POOL_FINAL,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._umbral = umbral_similitud
        self.umbral = umbral_similitud
        self._k = k_candidatos
        self._max_por_documento = max_por_documento
        self._pool = pool

    def buscar(self, pregunta: str, filtro: FiltroBusqueda | None = None) -> Recuperacion:
        filtro = filtro or FiltroBusqueda()
        documentos = {d.id: d for d in self._store.documentos()}

        k = self._k * FACTOR_K_CON_FILTRO if filtro.activo else self._k
        vector = self._embedder.consulta(pregunta)
        vecinos = self._store.vecinos(vector, k)
        lexicos = self._store.buscar_texto(terminos_de_busqueda(pregunta), k)

        filas = self._store.fragmentos_por_ids({fid for fid, _ in vecinos} | {f.id for f in lexicos})

        def admite(fid: int) -> bool:
            fila = filas.get(fid)
            documento = documentos.get(fila.documento_id) if fila else None
            return documento is not None and filtro.admite(documento.meta)

        vecinos_admitidos = [(fid, sim) for fid, sim in vecinos if admite(fid)]
        similitud_por_id = dict(vecinos_admitidos)
        mejor = max((sim for _, sim in vecinos_admitidos), default=None)
        cubierta = mejor is not None and mejor >= self._umbral

        ranking_vectores = [fid for fid, _ in vecinos_admitidos]
        ranking_lexico = [f.id for f in lexicos if admite(f.id)]
        puntuacion = _rrf([ranking_vectores, ranking_lexico], K_RRF)
        ordenados = sorted(puntuacion, key=lambda fid: puntuacion[fid], reverse=True)

        candidatos: list[Candidato] = []
        por_documento: dict[int, int] = {}
        for fid in ordenados:
            fila = filas[fid]
            documento = documentos[fila.documento_id]
            if por_documento.get(documento.id, 0) >= self._max_por_documento:
                continue
            por_documento[documento.id] = por_documento.get(documento.id, 0) + 1
            candidatos.append(
                Candidato(
                    fragmento=fila,
                    documento=documento,
                    puntuacion=puntuacion[fid],
                    similitud=similitud_por_id.get(fid),
                )
            )
            if len(candidatos) >= self._pool:
                break

        return Recuperacion(candidatos=candidatos, cubierta=cubierta, mejor_similitud=mejor)


def _rrf(rankings: list[list[int]], k: int) -> dict[int, float]:
    puntuacion: dict[int, float] = {}
    for ranking in rankings:
        for posicion, fid in enumerate(ranking, start=1):
            puntuacion[fid] = puntuacion.get(fid, 0.0) + 1.0 / (k + posicion)
    return puntuacion
