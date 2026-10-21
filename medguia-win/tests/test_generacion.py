from pathlib import Path

import pytest

from medguia.domain.models import Ambito, FragmentoNuevo, MetaDocumento
from medguia.generation.prompt import SYSTEM_PROMPT, construir_mensajes, formatear_fragmento
from medguia.generation.presupuesto import PerfilContexto, presupuesto_fragmentos, seleccionar
from medguia.generation.responder import RESPUESTA_NO_CUBIERTA, Responder
from medguia.generation.verificador import verificar
from medguia.ingestion.tokens import ContadorAproximado
from medguia.persistence.store import DocumentoRegistrado, FilaFragmento, Store
from medguia.retrieval.busqueda import Candidato, Recuperador
from tests.fakes import EmbedderFalso, LLMFalso

CONTAR = ContadorAproximado()
META = MetaDocumento("Guía HTA", "ESC", 2024, Ambito.EUROPEO, "Cardiología")


def _candidato(texto: str, pagina: int = 3, impresas: dict[int, str] | None = None) -> Candidato:
    documento = DocumentoRegistrado(
        id=1, meta=META, ruta=Path("g.pdf"), sha256="x", paginas=10, paginas_sin_texto=(),
        paginas_impresas=impresas or {}, estado=None, error=None, importado_en="",
    )
    fragmento = FilaFragmento(
        id=1, documento_id=1, orden=0, seccion="Diagnóstico", pagina_inicio=pagina, pagina_fin=pagina,
        es_tabla=False, texto=texto, texto_indexado=texto,
    )
    return Candidato(fragmento=fragmento, documento=documento, puntuacion=0.1, similitud=0.9)


# --- verificador -----------------------------------------------------------

def test_respuesta_correcta_pasa_la_verificacion() -> None:
    candidatos = [_candidato("La presión objetivo es menor de 130 mmHg.")]
    respuesta = "**Detalle:**\nLa presión objetivo es menor de 130 mmHg [Guía HTA, 2024, p. 3]."

    assert verificar(respuesta, candidatos) == []


def test_cifra_inventada_se_marca() -> None:
    candidatos = [_candidato("La presión objetivo es menor de 130 mmHg.")]
    respuesta = "La presión objetivo es menor de 120 mmHg [Guía HTA, 2024, p. 3]."

    problemas = verificar(respuesta, candidatos)

    assert [p.tipo for p in problemas] == ["cifra_no_verificada"]
    assert problemas[0].detalle == "120"


def test_afirmacion_sin_cita_se_marca() -> None:
    candidatos = [_candidato("La presión objetivo es menor de 130 mmHg.")]
    respuesta = "La presión objetivo debe mantenerse por debajo de los valores habituales."

    assert [p.tipo for p in verificar(respuesta, candidatos)] == ["sin_cita"]


def test_cita_a_documento_inexistente_se_marca() -> None:
    candidatos = [_candidato("La presión objetivo es menor de 130 mmHg.")]
    respuesta = "La presión objetivo es menor de 130 mmHg [Otra guía, 2020, p. 3]."

    assert "cita_no_encontrada" in [p.tipo for p in verificar(respuesta, candidatos)]


def test_cita_con_pagina_fuera_del_fragmento_se_marca() -> None:
    candidatos = [_candidato("La presión objetivo es menor de 130 mmHg.", pagina=3)]
    respuesta = "La presión objetivo es menor de 130 mmHg [Guía HTA, 2024, p. 9]."

    assert "cita_no_encontrada" in [p.tipo for p in verificar(respuesta, candidatos)]


def test_se_cita_la_pagina_impresa_si_existe() -> None:
    candidatos = [_candidato("La presión objetivo es menor de 130 mmHg.", pagina=5, impresas={5: "41"})]
    respuesta = "La presión objetivo es menor de 130 mmHg [Guía HTA, 2024, p. 41]."

    assert verificar(respuesta, candidatos) == []


def test_respuesta_de_no_cobertura_no_exige_citas() -> None:
    assert verificar(f"**Respuesta breve:** {RESPUESTA_NO_CUBIERTA}", []) == []


# --- prompt y presupuesto ---------------------------------------------------

def test_reglas_del_prompt_son_literales() -> None:
    for linea in [
        "1. Usa solo la información de <contexto>. No completes con conocimiento propio.",
        "7. Copia dosis, umbrales y puntos de corte EXACTAMENTE como aparecen. No calcules, redondees ni extrapoles a otras poblaciones (pediatría, embarazo, insuficiencia renal o hepática).",
        "8. Si la pregunta sugiere una situación grave o urgente, empieza con ⚠️.",
        "**Respuesta breve:** 1-3 frases.",
        "Responde siempre en español.",
    ]:
        assert linea in SYSTEM_PROMPT


def test_mensajes_contienen_contexto_fuentes_y_pregunta() -> None:
    mensajes = construir_mensajes("¿Objetivo de PA?", [_candidato("Texto de la guía.")], anio_actual=2026)

    assert [m.rol for m in mensajes] == ["system", "user"]
    assert mensajes[0].texto == SYSTEM_PROMPT
    usuario = mensajes[1].texto
    assert "<contexto>" in usuario and "</contexto>" in usuario
    assert "<pregunta>\n¿Objetivo de PA?\n</pregunta>" in usuario
    assert 'documento="Guía HTA"' in usuario
    assert 'anios_desde_publicacion="2"' in usuario


def test_presupuesto_no_supera_la_ventana() -> None:
    perfil = PerfilContexto(n_ctx=2048, reserva_respuesta=512, margen=128)
    presupuesto = presupuesto_fragmentos(perfil, CONTAR, SYSTEM_PROMPT)

    assert 0 < presupuesto < 2048


def test_seleccion_respeta_el_presupuesto_en_orden() -> None:
    candidatos = [_candidato("a" * 400), _candidato("b" * 400), _candidato("c" * 400)]
    coste = lambda c: CONTAR(c.fragmento.texto)  # noqa: E731

    elegidos = seleccionar(candidatos, coste, presupuesto=220)

    assert [c.fragmento.texto[0] for c in elegidos] == ["a", "b"]


def test_formatear_fragmento_incluye_metadatos() -> None:
    texto = formatear_fragmento(_candidato("Texto."), anio_actual=2026)

    assert texto.startswith("<fuente ")
    assert 'página="3"' in texto and 'página_pdf="3"' in texto


# --- responder --------------------------------------------------------------

@pytest.fixture
def responder_de_prueba(tmp_path: Path):
    store = Store(tmp_path / "b.sqlite", dimensiones=256)
    emb = EmbedderFalso()

    def _responder(respuesta_llm: str, umbral: float = 0.2):  # el embedder falso da similitudes bajas
        llm = LLMFalso(respuesta_llm)
        recuperador = Recuperador(store, emb, umbral_similitud=umbral)
        return Responder(recuperador, llm, CONTAR, PerfilContexto(n_ctx=8192), lambda: 2026), llm

    doc = store.insertar_documento(META, tmp_path / "g.pdf", "sha")
    fragmentos = [
        FragmentoNuevo(0, "Diagnóstico", 3, 3, False,
                       "La presión objetivo es menor de 130 mmHg.",
                       "[Guía HTA · ESC · 2024 · europeo · Diagnóstico · p. 3]\nLa presión objetivo es menor de 130 mmHg."),
    ]
    store.reemplazar_fragmentos(doc, fragmentos, 3, [])
    frags = store.fragmentos(doc)
    store.guardar_vectores([(f.id, emb.documentos([("Guía HTA", f.texto_indexado)])[0]) for f in frags])
    yield _responder
    store.cerrar()


def test_sin_cobertura_no_se_llama_al_llm(responder_de_prueba) -> None:
    responder, llm = responder_de_prueba("cualquier cosa", umbral=0.99)

    respuesta = responder.responder("tratamiento de fractura de tibia")

    assert not respuesta.cubierta
    assert respuesta.texto == RESPUESTA_NO_CUBIERTA
    assert llm.llamadas == []


def test_con_cobertura_se_streamea_y_se_verifica(responder_de_prueba) -> None:
    texto_llm = "**Respuesta breve:** La presión objetivo es menor de 130 mmHg [Guía HTA, 2024, p. 3]."
    responder, llm = responder_de_prueba(texto_llm)
    tokens: list[str] = []

    respuesta = responder.responder("presión objetivo en hipertensos", al_recibir_token=tokens.append)

    assert respuesta.cubierta
    assert "".join(tokens).strip() == texto_llm
    assert len(llm.llamadas) == 1
    assert respuesta.segundos_primer_token is not None
    assert respuesta.problemas == []
    assert respuesta.candidatos


def test_respuesta_con_cifra_falsa_lleva_problemas(responder_de_prueba) -> None:
    responder, _ = responder_de_prueba("La presión objetivo es menor de 120 mmHg [Guía HTA, 2024, p. 3].")

    respuesta = responder.responder("presión objetivo en hipertensos")

    assert [p.tipo for p in respuesta.problemas] == ["cifra_no_verificada"]
