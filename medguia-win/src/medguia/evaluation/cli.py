"""Evaluación desde la línea de comandos.

    python -m medguia.evaluation.cli preguntas.json --modelos gemma-e4b gemma-e2b --salida informe.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from medguia.config import carpeta_datos
from medguia.evaluation import informe
from medguia.evaluation.ejecucion import evaluar_configuraciones
from medguia.evaluation.preguntas import cargar
from medguia.models import gestor
from medguia.ui.servicios import ModeloNoInstalado, Servicios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluación de MedGuía sobre un conjunto de preguntas.")
    parser.add_argument("preguntas", type=Path, help="JSON con las preguntas de prueba")
    parser.add_argument("--modelos", nargs="+", default=[gestor.GEMMA_E4B, gestor.GEMMA_E2B])
    parser.add_argument("--salida", type=Path, default=None, help="Informe Markdown (y CSV junto a él)")
    args = parser.parse_args(argv)

    preguntas = cargar(args.preguntas)
    servicios = Servicios(carpeta_datos())

    def progreso(nombre: str, i: int, n: int) -> None:
        print(f"\r{nombre}: {i}/{n}", end="", file=sys.stderr)

    try:
        resumenes = evaluar_configuraciones(servicios, preguntas, args.modelos, progreso)
    except ModeloNoInstalado as error:
        print(f"\nError: {error}", file=sys.stderr)
        return 1
    print(file=sys.stderr)
    markdown = informe.tabla_markdown(resumenes)
    print(markdown)
    if args.salida:
        args.salida.parent.mkdir(parents=True, exist_ok=True)
        args.salida.write_text(markdown, encoding="utf-8")
        args.salida.with_suffix(".csv").write_text(informe.csv_texto(resumenes), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
