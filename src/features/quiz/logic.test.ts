import { describe, expect, it } from 'vitest';
import { QUESTIONS, QUIZ_MODULES } from './data';
import { examSeconds, grade, pageFromNotes, pickQuestions, shuffle } from './logic';

describe('banco de preguntas', () => {
  it('tiene más de 100 preguntas con ids únicos', () => {
    expect(QUESTIONS.length).toBeGreaterThanOrEqual(100);
    expect(new Set(QUESTIONS.map((q) => q.id)).size).toBe(QUESTIONS.length);
  });
  it('todos los módulos tienen preguntas', () => {
    for (const m of QUIZ_MODULES) expect(m.preguntas.length).toBeGreaterThanOrEqual(8);
  });
  it.each(QUESTIONS.map((q) => [q.id, q] as const))('%s está bien formada', (_id, q) => {
    expect(q.opciones).toHaveLength(4);
    expect(new Set(q.opciones).size).toBe(4);
    expect(q.correcta).toBeGreaterThanOrEqual(0);
    expect(q.correcta).toBeLessThan(4);
    expect(q.explicacion.length).toBeGreaterThan(15);
    expect(q.afirmaciones.length).toBeGreaterThan(0);
    expect(q.referencia.length).toBeGreaterThan(5);
  });
  it('las preguntas verificadas con el manual citan página', () => {
    const directas = QUESTIONS.filter((q) => q.verificacion === 'directa' && q.fuentes.includes('manual-v60'));
    expect(directas.length).toBeGreaterThan(50);
    for (const q of directas) expect(q.referencia, q.id).toMatch(/pp?\./);
  });
  it('la posición de la respuesta correcta está repartida', () => {
    const counts = [0, 0, 0, 0];
    for (const q of QUESTIONS) counts[q.correcta]++;
    for (const c of counts) expect(c / QUESTIONS.length).toBeGreaterThan(0.12);
  });
  it('la barajado es estable por pregunta', () => {
    expect(QUESTIONS[0].opciones).toEqual(QUESTIONS[0].opciones);
    expect(shuffle([1, 2, 3, 4, 5], 7)).toEqual(shuffle([1, 2, 3, 4, 5], 7));
  });
});

describe('selección y nota', () => {
  it('filtra por módulo y limita el número', () => {
    const sel = pickQuestions(QUESTIONS, { modulo: 'alarmas', count: 5, seed: 1 });
    expect(sel).toHaveLength(5);
    expect(sel.every((q) => q.modulo === 'alarmas')).toBe(true);
  });
  it('misma semilla, mismo orden; distinta semilla, distinto orden', () => {
    const a = pickQuestions(QUESTIONS, { modulo: 'todos', count: 20, seed: 3 }).map((q) => q.id);
    const b = pickQuestions(QUESTIONS, { modulo: 'todos', count: 20, seed: 3 }).map((q) => q.id);
    const c = pickQuestions(QUESTIONS, { modulo: 'todos', count: 20, seed: 4 }).map((q) => q.id);
    expect(a).toEqual(b);
    expect(a).not.toEqual(c);
  });
  it('restringe a una lista de ids (errores)', () => {
    const ids = [QUESTIONS[0].id, QUESTIONS[5].id];
    expect(pickQuestions(QUESTIONS, { seed: 1, ids }).map((q) => q.id).sort()).toEqual([...ids].sort());
  });
  it('calcula la nota, las no respondidas y las falladas', () => {
    const qs = QUESTIONS.slice(0, 4);
    const g = grade(qs, [qs[0].correcta, (qs[1].correcta + 1) % 4, null, qs[3].correcta]);
    expect(g).toMatchObject({ total: 4, correctas: 2, incorrectas: 1, sinResponder: 1, porcentaje: 50 });
    expect(g.falladas).toEqual([qs[1].id, qs[2].id]);
  });
  it('el tiempo del examen es proporcional al número de preguntas', () => {
    expect(examSeconds(20)).toBe(20 * 60);
  });
});

describe('referencias', () => {
  it('extrae la página de las notas', () => {
    expect(pageFromNotes('Manual de usuario V60/V60 Plus (ref. 1152841_ES), pp. 4-8 y 4-9.')).toBe('pp. 4-8 y 4-9');
    expect(pageFromNotes('Manual de usuario V60/V60 Plus (ref. 1152841_ES), p. 3-2.')).toBe('p. 3-2');
    expect(pageFromNotes(undefined)).toBeNull();
  });
});
