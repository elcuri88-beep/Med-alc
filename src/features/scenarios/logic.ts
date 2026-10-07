import data from '../../../content/scenarios/alarm-scenarios.json';

export interface ScenarioStep {
  id: string;
  texto: string;
  pagina: string;
}
export interface Distractor {
  texto: string;
  porque: string;
  pendienteRevision: boolean;
}
export interface Scenario {
  id: string;
  titulo: string;
  alarma: { mensaje: string; prioridad: 'alta' | 'baja' | 'informacion' | 'ninguna' };
  situacion: string;
  pasos: ScenarioStep[];
  distractores: Distractor[];
  explicacion: string;
}
export interface Option {
  key: string;
  texto: string;
  correcta: boolean;
  porque?: string;
}

export const SCENARIOS = data.escenarios as unknown as Scenario[];

function hash(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function rng(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Opciones de una etapa: el paso correcto, hasta 2 acciones incorrectas y el paso siguiente (fuera de orden). Orden estable. */
export function buildOptions(sc: Scenario, stage: number): Option[] {
  const correct = sc.pasos[stage];
  const opts: Option[] = [{ key: `${sc.id}-${stage}-ok`, texto: correct.texto, correcta: true }];

  const n = sc.distractores.length;
  for (let i = 0; i < Math.min(2, n); i++) {
    const d = sc.distractores[(stage + i) % n];
    opts.push({ key: `${sc.id}-${stage}-d${(stage + i) % n}`, texto: d.texto, correcta: false, porque: d.porque });
  }
  const later = sc.pasos[stage + 1];
  if (later) {
    opts.push({
      key: `${sc.id}-${stage}-later`,
      texto: later.texto,
      correcta: false,
      porque: `Es un paso correcto, pero va más adelante. Ahora toca: «${correct.texto}»`,
    });
  }

  const rand = rng(hash(`${sc.id}:${stage}`));
  for (let i = opts.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [opts[i], opts[j]] = [opts[j], opts[i]];
  }
  return opts;
}
