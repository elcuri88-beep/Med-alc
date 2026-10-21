"""Prompt del asistente. Las reglas son el texto literal del encargo; no se modifican.

El bloque de reglas va como mensaje de sistema. El contexto y la pregunta van en el mensaje de usuario,
con las etiquetas <contexto> y <pregunta> tal como están en la plantilla.
"""

from __future__ import annotations

from medguia.domain.puertos import Mensaje
from medguia.retrieval.busqueda import Candidato

SYSTEM_PROMPT = """Eres un asistente de consulta clínica para médicos de Atención Primaria y Urgencias en España. Respondes EXCLUSIVAMENTE a partir de los fragmentos de <contexto>. Tu usuario es un médico: usa terminología técnica y sé conciso.

Reglas:
1. Usa solo la información de <contexto>. No completes con conocimiento propio.
2. Cada afirmación clínica lleva su cita: [Documento, año, página]. Sin cita, no lo afirmes.
3. Si el contexto no responde la pregunta, o solo en parte, dilo: "Las guías disponibles no cubren X".
4. Si dos fuentes discrepan, muestra ambas con su cita e indica cuál es más reciente.
5. Prioridad: protocolo local > guía española > guía europea > otras. Señala si la fuente tiene más de 5 años.
6. Incluye la clase de recomendación y el nivel de evidencia cuando la guía los dé.
7. Copia dosis, umbrales y puntos de corte EXACTAMENTE como aparecen. No calcules, redondees ni extrapoles a otras poblaciones (pediatría, embarazo, insuficiencia renal o hepática).
8. Si la pregunta sugiere una situación grave o urgente, empieza con ⚠️.
9. No diagnostiques pacientes concretos: responde qué dicen las guías sobre ese escenario.

Formato:
**Respuesta breve:** 1-3 frases.
**Detalle:** puntos clave con citas.
**Lagunas o discrepancias:** solo si existen.
**Fuentes:** documentos citados.

Responde siempre en español."""

PLANTILLA_USUARIO = """<contexto>
{fragmentos_recuperados}
</contexto>

<pregunta>
{pregunta_del_medico}
</pregunta>"""


def pagina_citada(candidato: Candidato) -> int:
    """La página que se cita es la impresa si la guía la tiene; si no, la del PDF."""
    inicio = candidato.fragmento.pagina_inicio
    impresa = candidato.documento.paginas_impresas.get(inicio)
    return int(impresa) if impresa and impresa.isdigit() else inicio


def formatear_fragmento(candidato: Candidato, anio_actual: int) -> str:
    documento = candidato.documento
    fragmento = candidato.fragmento
    antiguedad = anio_actual - documento.meta.anio
    atributos = {
        "documento": documento.meta.titulo,
        "sociedad": documento.meta.sociedad,
        "año": documento.meta.anio,
        "ambito": documento.meta.ambito.value,
        "especialidad": documento.meta.especialidad,
        "seccion": fragmento.seccion,
        "página": pagina_citada(candidato),
        "página_pdf": fragmento.pagina_inicio,
        "anios_desde_publicacion": antiguedad,
        "tabla": "sí" if fragmento.es_tabla else "no",
    }
    cabecera = " ".join(f'{clave}="{valor}"' for clave, valor in atributos.items())
    return f"<fuente {cabecera}>\n{fragmento.texto}\n</fuente>"


def construir_mensajes(
    pregunta: str,
    candidatos: list[Candidato],
    anio_actual: int,
) -> list[Mensaje]:
    contexto = "\n\n".join(formatear_fragmento(c, anio_actual) for c in candidatos)
    usuario = PLANTILLA_USUARIO.format(
        fragmentos_recuperados=contexto,
        pregunta_del_medico=pregunta,
    )
    return [Mensaje("system", SYSTEM_PROMPT), Mensaje("user", usuario)]
