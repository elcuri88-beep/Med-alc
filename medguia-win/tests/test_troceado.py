from medguia.domain.models import Ambito, MetaDocumento
from medguia.ingestion.chunker import (
    TOKENS_MAXIMO,
    trocear,
)
from medguia.ingestion.pdf_extract import Bloque
from medguia.ingestion.tokens import ContadorAproximado

META = MetaDocumento(
    titulo="Guía HTA",
    sociedad="ESC",
    anio=2024,
    ambito=Ambito.EUROPEO,
    especialidad="Cardiología",
)
CONTAR = ContadorAproximado()


def _frase(n: int) -> str:
    return f"Frase clínica número {n} sobre el tratamiento del paciente hipertenso."


def test_cada_fragmento_respeta_el_maximo_de_tokens() -> None:
    bloques = [Bloque(1, "1. Tratamiento", encabezado=True)]
    bloques += [Bloque(1, " ".join(_frase(i) for i in range(400)))]

    fragmentos = trocear(bloques, META, CONTAR)

    assert len(fragmentos) > 1
    for fragmento in fragmentos:
        assert CONTAR(fragmento.texto) <= TOKENS_MAXIMO


def test_hay_solape_entre_fragmentos_consecutivos() -> None:
    bloques = [Bloque(1, f"Párrafo {i}. " + _frase(i)) for i in range(60)]

    fragmentos = trocear(bloques, META, CONTAR)

    assert len(fragmentos) >= 2
    for anterior, siguiente in zip(fragmentos, fragmentos[1:]):
        ultimo_parrafo = anterior.texto.split("\n")[-1]
        assert ultimo_parrafo in siguiente.texto


def test_tabla_es_atomica_aunque_supere_el_maximo() -> None:
    filas = "\n".join(f"Fármaco {i} | {i * 5} mg | 24 h" for i in range(200))
    bloques = [
        Bloque(2, "Antes de la tabla."),
        Bloque(2, filas, es_tabla=True),
        Bloque(2, "Después de la tabla."),
    ]

    fragmentos = trocear(bloques, META, CONTAR)

    tablas = [f for f in fragmentos if f.es_tabla]
    assert len(tablas) == 1
    assert tablas[0].texto == filas
    assert CONTAR(tablas[0].texto) > TOKENS_MAXIMO
    assert "Antes de la tabla." in fragmentos[0].texto
    assert "Después de la tabla." in fragmentos[-1].texto


def test_los_fragmentos_no_cruzan_encabezados() -> None:
    bloques = [
        Bloque(1, "1. Diagnóstico", encabezado=True),
        Bloque(1, "Texto de diagnóstico."),
        Bloque(2, "2. Tratamiento", encabezado=True),
        Bloque(2, "Texto de tratamiento."),
    ]

    fragmentos = trocear(bloques, META, CONTAR)

    assert [(f.seccion, f.texto) for f in fragmentos] == [
        ("1. Diagnóstico", "Texto de diagnóstico."),
        ("2. Tratamiento", "Texto de tratamiento."),
    ]


def test_cabecera_de_metadatos_se_antepone_al_texto_indexado() -> None:
    bloques = [
        Bloque(3, "1. Diagnóstico", encabezado=True),
        Bloque(3, "Texto."),
    ]

    fragmento = trocear(bloques, META, CONTAR)[0]

    assert fragmento.texto_indexado.startswith(
        "[Guía HTA · ESC · 2024 · europeo · 1. Diagnóstico · p. 3]\n"
    )
    assert fragmento.texto_indexado.endswith("Texto.")


def test_rango_de_paginas_en_la_cabecera() -> None:
    bloques = [
        Bloque(4, "Inicio de párrafo."),
        Bloque(5, "Continuación del párrafo."),
    ]

    fragmento = trocear(bloques, META, CONTAR)[0]

    assert (fragmento.pagina_inicio, fragmento.pagina_fin) == (4, 5)
    assert "pp. 4-5" in fragmento.texto_indexado
