"""Servicios compartidos por las pantallas: rutas, ajustes, proveedores activos y liberación de modelos.

La clave de OpenRouter va al Administrador de credenciales de Windows (keyring), nunca al JSON de ajustes.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

import keyring

from medguia.domain.puertos import Embedder, LLMProvider
from medguia.generation.presupuesto import PerfilContexto
from medguia.models import gestor
from medguia.providers.embedding_local import EmbeddingGemmaLocal
from medguia.providers.gemma_local import GemmaLocal
from medguia.providers.openai_compatible import ApiCompatibleOpenAI

PROVEEDOR_LOCAL = "gemma-local"
PROVEEDOR_API = "openrouter"
SERVICIO_CLAVE = "MedGuia"
USUARIO_CLAVE = "openrouter"
DIMENSIONES = 768
FICHERO_AJUSTES = "ajustes.json"


class ModeloNoInstalado(Exception):
    pass


@dataclass
class Ajustes:
    proveedor: str = PROVEEDOR_LOCAL
    modelo_llm: str = gestor.GEMMA_E4B
    n_ctx: int = 8192
    openrouter_modelo: str = ""
    api_aceptada: bool = False  # el usuario aceptó que la consulta sale del dispositivo

    @classmethod
    def cargar(cls, ruta: Path, ram_gb: float, vram_gb: float | None) -> Ajustes:
        if not ruta.exists():
            return cls(modelo_llm=gestor.recomendar_llm(ram_gb, vram_gb))
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in datos.items() if k in cls.__dataclass_fields__})

    def guardar(self, ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")


class Servicios:
    def __init__(self, carpeta: Path, ram_gb: float | None = None, vram_gb: float | None = None) -> None:
        self.carpeta = carpeta
        self.ruta_bd = carpeta / "biblioteca.sqlite"
        self.carpeta_modelos = carpeta / "modelos"
        self.catalogo = gestor.cargar_catalogo(carpeta)
        ram = ram_gb if ram_gb is not None else gestor.ram_total_gb()
        vram = vram_gb if vram_gb is not None else gestor.vram_total_gb()
        self.ajustes = Ajustes.cargar(carpeta / FICHERO_AJUSTES, ram, vram)
        self._embedder: EmbeddingGemmaLocal | None = None
        self._llm: LLMProvider | None = None
        self._lock = threading.Lock()

    # --- ajustes ----------------------------------------------------------------

    def guardar_ajustes(self, ajustes: Ajustes) -> None:
        with self._lock:
            self.ajustes = ajustes
            self._llm = None
        ajustes.guardar(self.carpeta / FICHERO_AJUSTES)

    def perfil(self) -> PerfilContexto:
        return PerfilContexto(n_ctx=self.ajustes.n_ctx)

    def clave_api(self) -> str:
        try:
            return keyring.get_password(SERVICIO_CLAVE, USUARIO_CLAVE) or ""
        except keyring.errors.KeyringError:
            return ""

    def guardar_clave_api(self, clave: str) -> None:
        if clave:
            keyring.set_password(SERVICIO_CLAVE, USUARIO_CLAVE, clave)
        else:
            try:
                keyring.delete_password(SERVICIO_CLAVE, USUARIO_CLAVE)
            except keyring.errors.PasswordDeleteError:
                pass

    # --- modelos --------------------------------------------------------------

    def ruta(self, clave: str) -> Path:
        return gestor.ruta_modelo(self.carpeta_modelos, self.catalogo[clave])

    def instalado(self, clave: str) -> bool:
        return gestor.instalado(self.carpeta_modelos, self.catalogo[clave])

    def embedder(self) -> Embedder | None:
        """EmbeddingGemma si está instalado; None si no (la indexación queda sin vectores hasta descargarlo)."""
        with self._lock:
            if self._embedder is None and self.instalado(gestor.EMBEDDING_GEMMA):
                self._embedder = EmbeddingGemmaLocal(self.ruta(gestor.EMBEDDING_GEMMA), dimensiones=DIMENSIONES)
            return self._embedder

    def nombre_embedding(self) -> str | None:
        embedder = self.embedder()
        return embedder.nombre if embedder else None

    def llm(self) -> LLMProvider:
        with self._lock:
            if self._llm is None:
                self._llm = self._crear_llm()
            return self._llm

    def _crear_llm(self) -> LLMProvider:
        if self.ajustes.proveedor == PROVEEDOR_API:
            if not self.ajustes.api_aceptada:
                raise ModeloNoInstalado("Acepta el aviso de envío de datos fuera del equipo en Ajustes.")
            return ApiCompatibleOpenAI(self.ajustes.openrouter_modelo, self.clave_api)
        clave = self.ajustes.modelo_llm
        if not self.instalado(clave):
            raise ModeloNoInstalado(f"Falta el modelo «{self.catalogo[clave].nombre}». Descárgalo en Ajustes.")
        return GemmaLocal(self.ruta(clave), n_ctx=self.ajustes.n_ctx)

    def liberar_modelos(self) -> None:
        """Llamado al pasar la app a segundo plano: libera VRAM y RAM."""
        with self._lock:
            llm, embedder = self._llm, self._embedder
        for modelo in (llm, embedder):
            if modelo is not None:
                modelo.liberar()
