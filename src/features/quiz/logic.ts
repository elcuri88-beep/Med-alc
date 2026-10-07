import type { Claim } from '../../types';

export interface RawQuestion {
  id: string;
  enunciado: string;
  correcta: string;
  incorrectas: string[];
  explicacion: string;
  afirmaciones: string[];
}

export interface PreparedQuestion {
  id: string;
  modulo: string;
  enunciado: string;
  opciones: string[];
  correcta: number; // índice en opciones
  explicacion: string;
  afirmaciones: string[];
  /** Pendiente de revisión si alguna afirmación en la que se apoya lo está. */
  pendienteRevision: boolean;
  verificacion: 'directa' | 'secundaria' | 'ninguna';
  fuentes: string[];
  referencia: string;
}

export const EXAM_SECONDS_PER_QUESTION = 60;

function hash(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function shuffle<T>(items: T[], seed: number): T[] {
  const out = [...items];
  const r = rng(seed);
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** Página citada en las notas de una afirmación verificada con el manual (p. ej. "pp. 4-8 y 4-9"). */
export function pageFromNotes(notas?: string): string | null {
  const m = notas?.match(/\b(pp?\.\s[^.]*\d[^.]*)\./);
  return m ? m[1] : null;
}

export function describeReference(claims: Claim[], sourceTitle: (id: string) => string | undefined): { fuentes: string[]; referencia: string } {
  const fuentes = Array.from(new Set(claims.flatMap((c) => c.fuentes)));
  const parts = fuentes.map((f) => {
    const title = sourceTitle(f) ?? f;
    const short = title.length > 90 ? `${title.slice(0, 87)}…` : title;
    const pages = claims.filter((c) => c.fuentes.includes(f) && f === 'manual-v60').map((c) => pageFromNotes(c.notas)).filter(Boolean);
    return pages.length ? `${short} — ${Array.from(new Set(pages)).join('; ')}` : short;
  });
  return { fuentes, referencia: parts.join(' | ') };
}

export function prepare(
  q: RawQuestion,
  modulo: string,
  claimById: (id: string) => Claim | undefined,
  sourceTitle: (id: string) => string | undefined,
): PreparedQuestion {
  const claims = q.afirmaciones.map((id) => claimById(id));
  if (claims.some((c) => !c)) throw new Error(`Pregunta ${q.id}: afirmación inexistente`);
  const cs = claims as Claim[];
  const todas = [q.correcta, ...q.incorrectas];
  const opciones = shuffle(todas, hash(q.id));
  const pend = cs.some((c) => c.pendienteRevision);
  const verificacion = pend ? 'ninguna' : cs.every((c) => c.verificacion === 'directa') ? 'directa' : cs.every((c) => c.verificacion) ? 'secundaria' : 'ninguna';
  const ref = describeReference(cs, sourceTitle);
  return {
    id: q.id,
    modulo,
    enunciado: q.enunciado,
    opciones,
    correcta: opciones.indexOf(q.correcta),
    explicacion: q.explicacion,
    afirmaciones: q.afirmaciones,
    pendienteRevision: pend,
    verificacion: pend ? 'ninguna' : verificacion,
    fuentes: ref.fuentes,
    referencia: ref.referencia,
  };
}

export interface PickOptions {
  modulo?: string; // 'todos' o id de módulo
  count?: number;
  seed: number;
  ids?: string[]; // restringir a estos ids (p. ej. errores)
}

export function pickQuestions(all: PreparedQuestion[], opts: PickOptions): PreparedQuestion[] {
  let pool = all.filter((q) => (!opts.modulo || opts.modulo === 'todos' ? true : q.modulo === opts.modulo));
  if (opts.ids) pool = pool.filter((q) => opts.ids!.includes(q.id));
  const mixed = shuffle(pool, opts.seed);
  return opts.count ? mixed.slice(0, opts.count) : mixed;
}

export function examSeconds(n: number): number {
  return n * EXAM_SECONDS_PER_QUESTION;
}

export interface Grade {
  total: number;
  correctas: number;
  incorrectas: number;
  sinResponder: number;
  porcentaje: number;
  falladas: string[];
}

/** answers[i] = índice elegido o null si no se respondió. */
export function grade(questions: PreparedQuestion[], answers: (number | null)[]): Grade {
  let correctas = 0;
  let sinResponder = 0;
  const falladas: string[] = [];
  questions.forEach((q, i) => {
    const a = answers[i] ?? null;
    if (a === null) {
      sinResponder++;
      falladas.push(q.id);
    } else if (a === q.correcta) correctas++;
    else falladas.push(q.id);
  });
  const total = questions.length;
  return {
    total,
    correctas,
    incorrectas: total - correctas - sinResponder,
    sinResponder,
    porcentaje: total ? Math.round((correctas / total) * 100) : 0,
    falladas,
  };
}
