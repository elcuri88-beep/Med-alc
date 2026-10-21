import json
from pathlib import Path

from medguia.evaluation.cli import main as cli_main
from medguia.evaluation.preguntas import cargar


def test_plantilla_del_repositorio_es_valida() -> None:
    preguntas = cargar(Path(__file__).parent.parent / "evaluacion" / "plantilla_preguntas.json")

    assert len(preguntas) == 2
    assert preguntas[0].cubierta and not preguntas[1].cubierta


def test_cli_sin_modelos_falla_con_mensaje(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MEDGUIA_HOME", str(tmp_path / "datos"))
    preguntas = tmp_path / "p.json"
    preguntas.write_text(json.dumps([{"pregunta": "x", "cubierta": False}]), encoding="utf-8")

    assert cli_main([str(preguntas), "--modelos", "gemma-e4b"]) == 1
