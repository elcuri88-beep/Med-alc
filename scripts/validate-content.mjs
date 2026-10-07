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
if (errors) { console.error(`${errors} errores`); process.exit(1); }
console.log(`Contenido válido (${seen.size} afirmaciones)`);
