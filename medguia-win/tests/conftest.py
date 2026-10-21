from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest


@pytest.fixture
def pdf_guia(tmp_path: Path) -> Path:
    """Guía mínima de dos páginas: encabezados, párrafo, número de página y una tabla de dosis."""
    ruta = tmp_path / "guia.pdf"
    doc = pymupdf.open()

    pagina1 = doc.new_page()
    pagina1.insert_text((72, 80), "1. Hipertensión arterial", fontsize=14)
    pagina1.insert_text(
        (72, 110),
        "La presión objetivo es menor de 130 mmHg en la mayoría de pacientes.",
        fontsize=10,
    )
    pagina1.insert_text((300, 800), "1", fontsize=9)

    pagina2 = doc.new_page()
    pagina2.insert_text((72, 80), "1.1 Fármacos de primera línea", fontsize=11)
    filas = [
        ["Fármaco", "Dosis", "Frecuencia"],
        ["Amlodipino", "5 mg", "24 h"],
        ["Losartán", "50 mg", "24 h"],
    ]
    for i in range(len(filas) + 1):
        pagina2.draw_line((72, 150 + i * 30), (372, 150 + i * 30))
    for j in range(4):
        pagina2.draw_line((72 + j * 100, 150), (72 + j * 100, 150 + len(filas) * 30))
    for i, fila in enumerate(filas):
        for j, celda in enumerate(fila):
            pagina2.insert_text((80 + j * 100, 170 + i * 30), celda, fontsize=10)
    pagina2.insert_text((300, 800), "2", fontsize=9)

    doc.save(ruta)
    doc.close()
    return ruta


@pytest.fixture
def pdf_escaneado(tmp_path: Path) -> Path:
    """Página sin capa de texto, como un escaneo."""
    ruta = tmp_path / "escaneo.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(ruta)
    doc.close()
    return ruta
