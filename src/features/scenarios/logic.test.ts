import { describe, expect, it } from 'vitest';
import { SCENARIOS, buildOptions } from './logic';

describe('datos de los escenarios', () => {
  it('hay al menos 10 escenarios con ids únicos', () => {
    expect(SCENARIOS.length).toBeGreaterThanOrEqual(10);
    expect(new Set(SCENARIOS.map((s) => s.id)).size).toBe(SCENARIOS.length);
  });
  it.each(SCENARIOS.map((s) => [s.id, s] as const))('%s está completo', (_id, s) => {
    expect(s.situacion.length).toBeGreaterThan(20);
    expect(s.explicacion.length).toBeGreaterThan(20);
    expect(s.pasos.length).toBeGreaterThanOrEqual(2);
    expect(s.distractores.length).toBeGreaterThanOrEqual(1);
    for (const p of s.pasos) expect(p.pagina).toMatch(/^\d+-\d+$/);
    for (const d of s.distractores) {
      expect(d.porque.length).toBeGreaterThan(10);
      expect(d.pendienteRevision).toBe(true);
    }
    // primer paso común: acercarse al paciente (manual, p. 9-1)
    expect(s.pasos[0].texto).toMatch(/^Acercarse de inmediato al paciente/);
  });
});

describe('buildOptions', () => {
  it.each(SCENARIOS.map((s) => [s.id, s] as const))('%s: una sola opción correcta por etapa, máximo 4, estable', (_id, s) => {
    for (let stage = 0; stage < s.pasos.length; stage++) {
      const a = buildOptions(s, stage);
      const b = buildOptions(s, stage);
      expect(a).toEqual(b);
      expect(a.filter((o) => o.correcta)).toHaveLength(1);
      expect(a.find((o) => o.correcta)!.texto).toBe(s.pasos[stage].texto);
      expect(a.length).toBeGreaterThanOrEqual(2);
      expect(a.length).toBeLessThanOrEqual(4);
      expect(new Set(a.map((o) => o.texto)).size).toBe(a.length);
      for (const o of a.filter((x) => !x.correcta)) expect(o.porque).toBeTruthy();
    }
  });
  it('incluye el paso siguiente como opción fuera de orden', () => {
    const s = SCENARIOS[0];
    expect(buildOptions(s, 0).some((o) => !o.correcta && o.texto === s.pasos[1].texto)).toBe(true);
    expect(buildOptions(s, s.pasos.length - 1).some((o) => o.key.endsWith('later'))).toBe(false);
  });
});
