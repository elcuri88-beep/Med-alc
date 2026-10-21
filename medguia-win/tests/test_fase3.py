import os
from pathlib import Path

import pytest

from medguia.ui.bloqueo import desbloqueo_necesario
from medguia.ui.servicios import Ajustes
from medguia.ui.texto import a_texto_plano


def test_texto_plano_quita_marcas_y_añade_fuentes() -> None:
    markdown = "**Respuesta breve:** Objetivo `130` mmHg [Guía, 2024, p. 3].\n\n**Detalle:**\n- punto"

    texto = a_texto_plano(markdown, ["Guía · 2024 · p. 3 · Diagnóstico"])

    assert "**" not in texto and "`" not in texto
    assert "Respuesta breve: Objetivo 130 mmHg [Guía, 2024, p. 3]." in texto
    assert texto.endswith("Fuentes:\n- Guía · 2024 · p. 3 · Diagnóstico")


class _Verificador:
    def __init__(self, disponible: bool, aprueba: bool = True) -> None:
        self._disponible = disponible
        self._aprueba = aprueba
        self.pedidos = 0

    def disponible(self) -> bool:
        return self._disponible

    def verificar(self, motivo: str) -> bool:
        self.pedidos += 1
        return self._aprueba


def test_bloqueo_solo_si_esta_activado_y_disponible() -> None:
    assert not desbloqueo_necesario(False, _Verificador(True))
    assert not desbloqueo_necesario(True, _Verificador(False))
    assert desbloqueo_necesario(True, _Verificador(True))


def test_ajustes_nuevos_se_guardan_y_se_leen(tmp_path: Path) -> None:
    ruta = tmp_path / "ajustes.json"
    Ajustes(tema="oscuro", escala_texto=1.3, bloqueo_al_abrir=True).guardar(ruta)

    cargados = Ajustes.cargar(ruta, ram_gb=32, vram_gb=16)

    assert (cargados.tema, cargados.escala_texto, cargados.bloqueo_al_abrir) == ("oscuro", 1.3, True)


def test_ajustes_por_defecto_recomiendan_e4b_con_32_gb(tmp_path: Path) -> None:
    assert Ajustes.cargar(tmp_path / "no.json", ram_gb=32, vram_gb=16).modelo_llm == "gemma-e4b"


@pytest.fixture(scope="module")
def aplicacion():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_tema_oscuro_y_escala_se_aplican_sin_error(aplicacion) -> None:
    from medguia.ui.apariencia import aplicar

    aplicar(aplicacion, Ajustes(tema="oscuro", escala_texto=1.5))
    aplicar(aplicacion, Ajustes(tema="claro", escala_texto=1.0))
    aplicar(aplicacion, Ajustes(tema="sistema", escala_texto=1.0))


def test_historial_se_mantiene_y_se_limpia(aplicacion, tmp_path: Path) -> None:
    from medguia.ui.chat_vista import ChatVista, Turno
    from medguia.ui.servicios import Servicios

    chat = ChatVista(Servicios(tmp_path / "datos", ram_gb=32, vram_gb=16))
    chat._turnos.append(Turno(pregunta="¿Objetivo de PA?"))
    chat._renderizar()
    assert "¿Objetivo de PA?" in chat._historial.toPlainText()

    chat._nueva_conversacion()

    assert chat._turnos == []
    assert chat._historial.toPlainText().strip() == ""
