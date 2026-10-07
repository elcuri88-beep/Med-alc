import { MODULES, sourceById } from '../../content/loader';
import type { Claim } from '../../types';
import { prepare, type PreparedQuestion, type RawQuestion } from './logic';

const files = import.meta.glob('../../../content/quiz/*.json', { eager: true, import: 'default' }) as Record<string, { modulo: string; preguntas: RawQuestion[] }>;

const claimIndex = new Map<string, Claim>();
for (const m of MODULES) for (const s of m.secciones) for (const c of s.afirmaciones) claimIndex.set(c.id, c);

export const QUESTIONS: PreparedQuestion[] = Object.values(files)
  .flatMap((f) => f.preguntas.map((q) => prepare(q, f.modulo, (id) => claimIndex.get(id), (id) => sourceById(id)?.titulo)))
  .sort((a, b) => a.id.localeCompare(b.id));

export const QUIZ_MODULES = MODULES.map((m) => ({ id: m.id, titulo: m.titulo, orden: m.orden, preguntas: QUESTIONS.filter((q) => q.modulo === m.id) }));
