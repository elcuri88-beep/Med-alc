import type { Meta, Module, Source } from '../types';
import meta from '../../content/meta.json';
import sources from '../../content/sources.json';

const files = import.meta.glob('../../content/modules/*.json', { eager: true, import: 'default' });

export const MODEL_META = meta as Meta;
export const SOURCES = sources as Source[];
export const MODULES: Module[] = (Object.values(files) as Module[]).sort((a, b) => a.orden - b.orden);

export const sourceById = (id: string) => SOURCES.find((s) => s.id === id);
export const moduleById = (id: string) => MODULES.find((m) => m.id === id);

export interface SearchHit {
  moduleId: string;
  moduleTitle: string;
  sectionTitle: string;
  claimId: string;
  texto: string;
}

export function searchContent(query: string): SearchHit[] {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return [];
  const hits: SearchHit[] = [];
  for (const m of MODULES)
    for (const s of m.secciones)
      for (const c of s.afirmaciones)
        if (c.texto.toLowerCase().includes(q) || s.titulo.toLowerCase().includes(q))
          hits.push({ moduleId: m.id, moduleTitle: m.titulo, sectionTitle: s.titulo, claimId: c.id, texto: c.texto });
  return hits;
}
