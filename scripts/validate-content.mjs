// Valida que cada afirmación tenga texto, fuentes existentes e IDs únicos.
import { readdirSync, readFileSync } from 'node:fs';

const dir = new URL('../content/modules/', import.meta.url);
const ids = new Set(JSON.parse(readFileSync(new URL('../content/sources.json', import.meta.url), 'utf8')).map((s) => s.id));
const seen = new Set();
let errors = 0;
for (const f of readdirSync(dir).filter((x) => x.endsWith('.json'))) {
  const m = JSON.parse(readFileSync(new URL(f, dir), 'utf8'));
  for (const s of m.secciones)
    for (const c of s.afirmaciones) {
      const bad = (msg) => { console.error(`${f} ${c.id}: ${msg}`); errors++; };
      if (!c.texto) bad('sin texto');
      if (seen.has(c.id)) bad('ID duplicado');
      seen.add(c.id);
      if (!c.fuentes?.length) bad('sin fuentes');
      for (const src of c.fuentes ?? []) if (!ids.has(src)) bad(`fuente desconocida: ${src}`);
      if (c.fuentes?.includes('consenso-docente') && !c.pendienteRevision) bad('consenso-docente debe estar pendiente');
      if (c.verificacion && !['directa','secundaria'].includes(c.verificacion)) bad('verificacion inválida');
      if (c.verificacion && !c.notas) bad('verificacion sin nota');
      if (typeof c.pendienteRevision !== 'boolean') bad('falta pendienteRevision');
    }
}
const sc = JSON.parse(readFileSync(new URL('../content/scenarios/alarm-scenarios.json', import.meta.url), 'utf8'));
const scIds = new Set();
for (const e of sc.escenarios) {
  const bad = (m) => { console.error(`escenario ${e.id}: ${m}`); errors++; };
  if (scIds.has(e.id)) bad('ID duplicado');
  scIds.add(e.id);
  if (!e.pasos?.length || e.pasos.length < 2) bad('menos de 2 pasos');
  if (!e.distractores?.length) bad('sin acciones incorrectas');
  for (const p of e.pasos ?? []) if (!/^\d+-\d+$/.test(p.pagina ?? '')) bad(`paso sin página: ${p.id}`);
}
const claimIds = seen;
const qSeen = new Set();
for (const f of readdirSync(new URL('../content/quiz/', import.meta.url)).filter((x) => x.endsWith('.json'))) {
  const qf = JSON.parse(readFileSync(new URL('../content/quiz/' + f, import.meta.url), 'utf8'));
  for (const q of qf.preguntas) {
    const bad = (m) => { console.error(`pregunta ${q.id}: ${m}`); errors++; };
    if (qSeen.has(q.id)) bad('ID duplicado');
    qSeen.add(q.id);
    if (q.incorrectas?.length !== 3) bad('debe tener 3 respuestas incorrectas');
    if (new Set([q.correcta, ...(q.incorrectas ?? [])]).size !== 4) bad('opciones repetidas');
    if (!q.explicacion) bad('sin explicación');
    if (!q.afirmaciones?.length) bad('sin afirmaciones de referencia');
    for (const a of q.afirmaciones ?? []) if (!claimIds.has(a)) bad(`afirmación inexistente: ${a}`);
  }
}
if (qSeen.size < 100) { console.error(`Hay ${qSeen.size} preguntas; se requieren al menos 100`); errors++; }
console.log(`Preguntas válidas (${qSeen.size})`);
console.log(`Escenarios válidos (${scIds.size})`);
if (errors) { console.error(`${errors} errores`); process.exit(1); }
console.log(`Contenido válido (${seen.size} afirmaciones)`);
