"""Tabla comparativa en Markdown y CSV."""

from __future__ import annotations

import csv
import io

from medguia.evaluation.metricas import ResumenModelo


def _porcentaje(valor: float | None) -> str:
    return "n/a" if valor is None else f"{valor * 100:.0f} %"


def _segundos(valor: float | None) -> str:
    return "n/a" if valor is None else f"{valor:.2f} s"


def tabla_markdown(resumenes: list[ResumenModelo]) -> str:
    cabecera = (
        "| Modelo | Recuperación top 5 | Acierto de cita | No cubiertas acertadas | "
        "Primer token (mediana) | Total (mediana) | Pico RAM | Pico VRAM |\n"
        "|---|---|---|---|---|---|---|---|\n"
    )
    filas = [
        f"| {r.modelo} | {_porcentaje(r.recuperacion_top5)} | {_porcentaje(r.acierto_cita)} | "
        f"{_porcentaje(r.no_cubiertas_acertadas)} | {_segundos(r.primer_token_mediana_s)} | "
        f"{_segundos(r.total_mediana_s)} | {r.pico.ram_gb:.1f} GB | "
        f"{'n/a' if r.pico.vram_gb is None else f'{r.pico.vram_gb:.1f} GB'} |"
        for r in resumenes
    ]
    return cabecera + "\n".join(filas) + "\n"


def csv_texto(resumenes: list[ResumenModelo]) -> str:
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(
        ["modelo", "recuperacion_top5", "acierto_cita", "no_cubiertas_acertadas",
         "primer_token_mediana_s", "total_mediana_s", "pico_ram_gb", "pico_vram_gb"]
    )
    for r in resumenes:
        escritor.writerow(
            [r.modelo, r.recuperacion_top5, r.acierto_cita, r.no_cubiertas_acertadas,
             r.primer_token_mediana_s, r.total_mediana_s, round(r.pico.ram_gb, 2), r.pico.vram_gb]
        )
    return salida.getvalue()
