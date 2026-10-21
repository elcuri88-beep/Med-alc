import hashlib
from pathlib import Path

import httpx
import pytest

from medguia.models.gestor import (
    CATALOGO,
    GEMMA_E2B,
    GEMMA_E4B,
    IntegridadFallida,
    ModeloDescargable,
    ModeloNoConfigurado,
    borrar,
    cargar_catalogo,
    descargar,
    instalado,
    recomendar_llm,
    verificar,
)

CONTENIDO = b"pesos-falsos" * 1000


def _modelo(sha: str | None) -> ModeloDescargable:
    return ModeloDescargable("prueba", "Prueba", "usuario/repo", "m.gguf", sha, 0.0)


def _cliente(contenido: bytes) -> httpx.Client:
    def manejador(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=contenido, headers={"content-length": str(len(contenido))})

    return httpx.Client(transport=httpx.MockTransport(manejador))


def test_descarga_verifica_hash_publicado_y_renombra(tmp_path: Path) -> None:
    sha = hashlib.sha256(CONTENIDO).hexdigest()
    progreso: list[tuple[int, int]] = []

    destino = descargar(_modelo(sha), tmp_path, progreso=lambda r, t: progreso.append((r, t)), cliente=_cliente(CONTENIDO))

    assert destino.read_bytes() == CONTENIDO
    assert not list(tmp_path.glob("*.part"))
    assert progreso and progreso[-1][0] == len(CONTENIDO)
    assert verificar(_modelo(sha), tmp_path)


def test_hash_incorrecto_no_deja_archivo(tmp_path: Path) -> None:
    with pytest.raises(IntegridadFallida):
        descargar(_modelo("0" * 64), tmp_path, cliente=_cliente(CONTENIDO))

    assert not instalado(tmp_path, _modelo("0" * 64))
    assert not list(tmp_path.glob("*.part"))


def test_sin_hash_publicado_se_guarda_el_propio_para_comprobaciones_posteriores(tmp_path: Path) -> None:
    modelo = _modelo(None)
    descargar(modelo, tmp_path, cliente=_cliente(CONTENIDO))
    assert verificar(modelo, tmp_path)

    (tmp_path / "m.gguf").write_bytes(b"corrupto")

    assert not verificar(modelo, tmp_path)


def test_borrar_elimina_modelo_y_hash_local(tmp_path: Path) -> None:
    modelo = _modelo(None)
    descargar(modelo, tmp_path, cliente=_cliente(CONTENIDO))

    assert borrar(modelo, tmp_path)
    assert not instalado(tmp_path, modelo)
    assert not list(tmp_path.glob("*.sha256"))


def test_modelo_sin_repositorio_avisa_con_claridad(tmp_path: Path) -> None:
    modelo = CATALOGO[GEMMA_E4B]

    with pytest.raises(ModeloNoConfigurado):
        descargar(modelo, tmp_path, cliente=_cliente(CONTENIDO))


def test_modelos_json_sobrescribe_el_repositorio(tmp_path: Path) -> None:
    (tmp_path / "modelos.json").write_text(
        '{"gemma-e4b": {"repo": "usuario/gemma", "archivo": "e4b.gguf"}}', encoding="utf-8"
    )

    catalogo = cargar_catalogo(tmp_path)

    assert catalogo[GEMMA_E4B].repo == "usuario/gemma"
    assert catalogo[GEMMA_E4B].url == "https://huggingface.co/usuario/gemma/resolve/main/e4b.gguf"
    assert catalogo[GEMMA_E2B].repo is None


@pytest.mark.parametrize(
    ("ram", "vram", "esperado"),
    [
        (32, 16, GEMMA_E4B),   # este equipo
        (32, None, GEMMA_E4B),
        (8, 16, GEMMA_E2B),
        (32, 6, GEMMA_E2B),
    ],
)
def test_recomendacion_por_ram_y_vram(ram: float, vram: float | None, esperado: str) -> None:
    assert recomendar_llm(ram, vram) == esperado
