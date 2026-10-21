"""Troceado por secciones con solape y metadatos antepuestos al texto indexado.

- Cada sección se trocea por separado: un fragmento nunca cruza un encabezado.
- Las tablas son fragmentos atómicos, aunque superen el máximo.
- El solape (~12 % del objetivo) solo se aplica entre fragmentos de texto de una misma sección.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from medguia.domain.models import Ambito, FragmentoNuevo, MetaDocumento
from medguia.ingestion.pdf_extract import Bloque
from medguia.ingestion.tokens import ContadorTokens

# Presupuesto del texto del fragmento. La cabecera de metadatos (~60 tokens) queda fuera:
# el fragmento completo indexado queda en 400-600 tokens.
TOKENS_OBJETIVO = 450
TOKENS_MAXIMO = 540
FRACCION_SOLAPE = 0.12

ETIQUETA_AMBITO = {
    Ambito.LOCAL: "local",
    Ambito.NACIONAL: "nacional",
    Ambito.EUROPEO: "europeo",
}
SECCION_INICIAL = "Inicio"
SEPARADOR_FRASES = re.compile(r"(?<=[.;:!?])\s+")


@dataclass
class _Acumulador:
    """Párrafos de texto pendientes de emitir dentro de la sección actual."""

    bloques: list[Bloque]
    tokens: int = 0


def cabecera(meta: MetaDocumento, seccion: str, pagina_inicio: int, pagina_fin: int) -> str:
    referencia = (
        f"p. {pagina_inicio}"
        if pagina_inicio == pagina_fin
        else f"pp. {pagina_inicio}-{pagina_fin}"
    )
    return (
        f"[{meta.titulo} · {meta.sociedad} · {meta.anio} · "
        f"{ETIQUETA_AMBITO[meta.ambito]} · {seccion} · {referencia}]"
    )


def trocear(
    bloques: list[Bloque],
    meta: MetaDocumento,
    contar: ContadorTokens,
) -> list[FragmentoNuevo]:
    fragmentos: list[FragmentoNuevo] = []
    seccion = SECCION_INICIAL
    acumulado = _Acumulador(bloques=[])

    def emitir(texto: str, paginas: tuple[int, int], es_tabla: bool) -> None:
        orden = len(fragmentos)
        pagina_inicio, pagina_fin = paginas
        indexado = f"{cabecera(meta, seccion, pagina_inicio, pagina_fin)}\n{texto}"
        fragmentos.append(
            FragmentoNuevo(
                orden=orden,
                seccion=seccion,
                pagina_inicio=pagina_inicio,
                pagina_fin=pagina_fin,
                es_tabla=es_tabla,
                texto=texto,
                texto_indexado=indexado,
            )
        )

    def vaciar(conservar_solape: bool) -> None:
        if not acumulado.bloques:
            return
        texto = "\n".join(b.texto for b in acumulado.bloques)
        paginas = (acumulado.bloques[0].pagina, acumulado.bloques[-1].pagina)
        emitir(texto, paginas, es_tabla=False)
        if not conservar_solape:
            acumulado.bloques.clear()
            acumulado.tokens = 0
            return
        limite = int(TOKENS_OBJETIVO * FRACCION_SOLAPE)
        solape: list[Bloque] = []
        total = 0
        for bloque in reversed(acumulado.bloques):
            coste = contar(bloque.texto)
            if total + coste > limite:
                break
            solape.insert(0, bloque)
            total += coste
        acumulado.bloques = solape
        acumulado.tokens = total

    for bloque in bloques:
        if bloque.encabezado:
            vaciar(conservar_solape=False)
            seccion = bloque.texto
            continue

        if bloque.es_tabla:
            vaciar(conservar_solape=False)
            emitir(bloque.texto, (bloque.pagina, bloque.pagina), es_tabla=True)
            continue

        for trozo in _partir(bloque, contar):
            coste = contar(trozo.texto)
            if acumulado.tokens + coste > TOKENS_MAXIMO:
                vaciar(conservar_solape=True)
            acumulado.bloques.append(trozo)
            acumulado.tokens += coste
            if acumulado.tokens >= TOKENS_OBJETIVO:
                vaciar(conservar_solape=True)

    vaciar(conservar_solape=False)
    return fragmentos


def _partir(bloque: Bloque, contar: ContadorTokens) -> list[Bloque]:
    """Divide un párrafo que por sí solo supera el máximo, primero por frases y luego por palabras."""
    if contar(bloque.texto) <= TOKENS_MAXIMO:
        return [bloque]

    trozos: list[Bloque] = []
    actual = ""
    for frase in SEPARADOR_FRASES.split(bloque.texto):
        for pieza in _limitar(frase, contar):
            candidato = f"{actual} {pieza}".strip()
            if contar(candidato) > TOKENS_MAXIMO and actual:
                trozos.append(Bloque(bloque.pagina, actual))
                actual = pieza
            else:
                actual = candidato
    if actual:
        trozos.append(Bloque(bloque.pagina, actual))
    return trozos


def _limitar(frase: str, contar: ContadorTokens) -> list[str]:
    if contar(frase) <= TOKENS_MAXIMO:
        return [frase]
    palabras = frase.split()
    piezas: list[str] = []
    actual: list[str] = []
    for palabra in palabras:
        if actual and contar(" ".join(actual + [palabra])) > TOKENS_MAXIMO:
            piezas.append(" ".join(actual))
            actual = []
        actual.append(palabra)
    if actual:
        piezas.append(" ".join(actual))
    return piezas
