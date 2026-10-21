from pathlib import Path

from medguia.ingestion.pdf_extract import extraer


def test_extrae_paginas_y_encabezados(pdf_guia: Path) -> None:
    resultado = extraer(pdf_guia)

    assert resultado.paginas_total == 2
    encabezados = [b for b in resultado.bloques if b.encabezado]
    assert [(b.pagina, b.texto) for b in encabezados] == [
        (1, "1. Hipertensión arterial"),
        (2, "1.1 Fármacos de primera línea"),
    ]


def test_parrafo_conserva_su_pagina(pdf_guia: Path) -> None:
    resultado = extraer(pdf_guia)

    parrafos = [b for b in resultado.bloques if not b.encabezado and not b.es_tabla]
    assert any(
        b.pagina == 1 and "130 mmHg" in b.texto for b in parrafos
    )


def test_tabla_es_un_bloque_atomico_con_sus_filas(pdf_guia: Path) -> None:
    resultado = extraer(pdf_guia)

    tablas = [b for b in resultado.bloques if b.es_tabla]
    assert len(tablas) == 1
    tabla = tablas[0]
    assert tabla.pagina == 2
    assert "Fármaco | Dosis | Frecuencia" in tabla.texto
    assert "Amlodipino | 5 mg | 24 h" in tabla.texto
    assert "Losartán | 50 mg | 24 h" in tabla.texto


def test_numero_de_pagina_impresa_se_detecta_y_no_es_contenido(pdf_guia: Path) -> None:
    resultado = extraer(pdf_guia)

    assert resultado.paginas_impresas == {1: "1", 2: "2"}
    assert all(b.texto != "1" and b.texto != "2" for b in resultado.bloques)


def test_pagina_sin_texto_se_marca_como_escaneada(pdf_escaneado: Path) -> None:
    resultado = extraer(pdf_escaneado)

    assert resultado.paginas_sin_texto == [1]
    assert resultado.bloques == []
