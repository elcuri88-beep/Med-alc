// Genera CLAIMS.md con todas las afirmaciones clínicas para validación experta.
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';

const dir = new URL('../content/modules/', import.meta.url);
const sources = Object.fromEntries(
  JSON.parse(readFileSync(new URL('../content/sources.json', import.meta.url), 'utf8')).map((s) => [s.id, s.titulo]),
);
let out = '# Afirmaciones clínicas para validación\n\n| ID | Módulo | Afirmación | Fuentes | Estado | Notas |\n|---|---|---|---|---|---|\n';
let n = 0;
for (const f of readdirSync(dir).filter((x) => x.endsWith('.json')).sort()) {
  const m = JSON.parse(readFileSync(new URL(f, dir), 'utf8'));
  for (const s of m.secciones)
    for (const c of s.afirmaciones) {
      n++;
      out += `| ${c.id} | ${m.titulo} › ${s.titulo} | ${c.texto} | ${c.fuentes.join(', ')} | ${c.pendienteRevision ? 'PENDIENTE' : (c.verificacion === 'directa' ? 'verificado en manual' : c.verificacion === 'secundaria' ? 'contrastado (fuente secundaria)' : 'fuente identificada')} | ${c.notas ?? ''} |\n`;
    }
}
const lim = JSON.parse(readFileSync(new URL('../content/simulator/limits.json', import.meta.url), 'utf8'));
out += '\n## Parámetros del simulador (verificados con el manual V60/V60 Plus)\n\n| Parámetro | Mín | Máx | Unidad | Manual |\n|---|---|---|---|---|\n';
for (const grupo of ['ajustes', 'alarmas']) for (const [k, v] of Object.entries(lim[grupo])) out += `| ${v.etiqueta} (${k}) | ${v.min} | ${v.max} | ${v.unidad} | p. ${v.pagina} |\n`;
const ap = JSON.parse(readFileSync(new URL('../content/simulator/approximations.json', import.meta.url), 'utf8'));
out += '\n## Aproximaciones del simulador (NO proceden del manual; PENDIENTE de revisión)\n\n' + ap.aproximaciones.map((a) => `- **${a.id}**: ${a.texto}`).join('\n') + '\n';
const esc = JSON.parse(readFileSync(new URL('../content/scenarios/alarm-scenarios.json', import.meta.url), 'utf8'));
out += '\n## Escenarios de alarma\n\nPasos correctos: verificados en el manual (página indicada). Acciones incorrectas y explicaciones: PENDIENTE de revisión clínica.\n\n';
for (const e of esc.escenarios) {
  out += `### ${e.alarma.mensaje} (${e.id})\n` + e.pasos.map((p, i) => `${i + 1}. ${p.texto} _(manual p. ${p.pagina})_`).join('\n') + '\n';
  out += e.distractores.map((d) => `- ✗ ${d.texto} — ${d.porque} _(PENDIENTE)_`).join('\n') + '\n\n';
}
out += `\nTotal: ${n}\n\n## Fuentes\n` + Object.entries(sources).map(([k, v]) => `- **${k}**: ${v}`).join('\n') + '\n';
writeFileSync(new URL('../CLAIMS.md', import.meta.url), out);
console.log(`CLAIMS.md generado con ${n} afirmaciones`);
