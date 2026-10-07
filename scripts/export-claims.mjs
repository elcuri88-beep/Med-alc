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
      out += `| ${c.id} | ${m.titulo} › ${s.titulo} | ${c.texto} | ${c.fuentes.join(', ')} | ${c.pendienteRevision ? 'PENDIENTE' : (c.verificacion === 'secundaria' ? 'contrastado (fuente secundaria)' : 'fuente identificada')} | ${c.notas ?? ''} |\n`;
    }
}
out += `\nTotal: ${n}\n\n## Fuentes\n` + Object.entries(sources).map(([k, v]) => `- **${k}**: ${v}`).join('\n') + '\n';
writeFileSync(new URL('../CLAIMS.md', import.meta.url), out);
console.log(`CLAIMS.md generado con ${n} afirmaciones`);
