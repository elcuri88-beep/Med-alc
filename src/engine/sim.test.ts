import { describe, expect, it } from 'vitest';
import patients from '../../content/simulator/patients.json';
import { DEFAULT_SETTINGS, defaultAlarms, isInverseIE, sanitizeSettings } from './limits';
import { VentSim } from './sim';
import type { PatientModel, VentSettings } from './types';

const P = Object.fromEntries(
  (patients.perfiles as { id: string; nombre: string; compliance: number; resistencia: number; frecuenciaEspontanea: number; esfuerzo: number; tiempoNeuralInsp: number; fuga10: number; ocluido: boolean }[]).map((x) => [x.id, x as PatientModel]),
);
const make = (over: Partial<VentSettings>, patient: PatientModel, alarmOver = {}) => {
  const s = sanitizeSettings({ ...DEFAULT_SETTINGS, ...over });
  return new VentSim(s, patient, { ...defaultAlarms(s), ...alarmOver });
};
const ids = (sim: VentSim) => sim.getAlarms().map((a) => a.id);

describe('límites del manual', () => {
  it('ajusta los valores a los intervalos', () => {
    const s = sanitizeSettings({ ...DEFAULT_SETTINGS, ipap: 99, epap: 1, rate: 200, rise: 9, fio2: 5, vt: 5000 });
    expect(s.ipap).toBe(40);
    expect(s.epap).toBe(4);
    expect(s.rate).toBe(60);
    expect(s.rise).toBe(5);
    expect(s.fio2).toBe(21);
    expect(s.vt).toBe(2000);
  });
  it('EPAP no puede superar IPAP', () => {
    const s = sanitizeSettings({ ...DEFAULT_SETTINGS, ipap: 8, epap: 20 });
    expect(s.epap).toBeLessThanOrEqual(s.ipap);
  });
  it('no permite relación I:E invertida', () => {
    const s = sanitizeSettings({ ...DEFAULT_SETTINGS, rate: 30, tins: 3 }); // ciclo 2 s
    expect(isInverseIE(s.tins, s.rate)).toBe(false);
    expect(s.tins).toBeLessThanOrEqual(1);
  });
});

describe('S/T con paciente en apnea', () => {
  it('administra respiraciones obligatorias a la frecuencia programada', () => {
    const sim = make({ mode: 'S/T', rate: 12, ipap: 14, epap: 5 }, P.apnea);
    sim.run(60);
    expect(sim.counts.spontaneous).toBe(0);
    expect(sim.counts.mandatory).toBeGreaterThanOrEqual(11);
    expect(sim.counts.mandatory).toBeLessThanOrEqual(13);
  });
  it('alcanza la IPAP programada y un VT coherente con la distensibilidad', () => {
    const sim = make({ mode: 'S/T', rate: 12, ipap: 14, epap: 5, tins: 1.5, rise: 1 }, { ...P.apnea, fuga10: 0 });
    sim.run(40);
    expect(sim.metrics.ppico).toBeGreaterThan(13.5);
    expect(sim.metrics.ppico).toBeLessThanOrEqual(14.01);
    // C = 70 ml/cmH2O, ΔP = 9 cmH2O, constante de tiempo R·C = 0,42 s, Ti = 1,5 s → ~97 % de C·ΔP
    expect(sim.metrics.vte).toBeGreaterThan(560);
    expect(sim.metrics.vte).toBeLessThan(640);
    expect(sim.metrics.fr).toBeCloseTo(12, 0);
  });
  it('es determinista', () => {
    const a = make({}, P.epoc);
    const b = make({}, P.epoc);
    a.run(30);
    b.run(30);
    expect(a.metrics).toEqual(b.metrics);
    expect(a.counts).toEqual(b.counts);
  });
});

describe('disparo por el paciente', () => {
  it('con esfuerzo suficiente casi todas las respiraciones son espontáneas', () => {
    const sim = make({ mode: 'S/T', rate: 8 }, P.normal);
    sim.run(60);
    expect(sim.counts.spontaneous).toBeGreaterThan(10);
    expect(sim.counts.spontaneous).toBeGreaterThan(sim.counts.mandatory * 5);
  });
  it('con esfuerzos muy débiles solo hay respiraciones obligatorias', () => {
    const sim = make({ mode: 'S/T', rate: 12 }, P.debil);
    sim.run(60);
    expect(sim.counts.spontaneous).toBe(0);
    expect(sim.counts.mandatory).toBeGreaterThan(10);
  });
});

describe('CPAP', () => {
  it('no administra respiraciones obligatorias y avisa de frecuencia baja en apnea', () => {
    const sim = make({ mode: 'CPAP', epap: 8 }, P.apnea);
    sim.run(40);
    expect(sim.counts.total).toBe(0);
    expect(ids(sim)).toContain('frecBaja');
    expect(sim.getAlarms().find((a) => a.id === 'frecBaja')?.prioridad).toBe('alta'); // > 15 s sin respiraciones (manual p. 9-10)
  });
  it('mantiene la presión en el nivel CPAP', () => {
    const sim = make({ mode: 'CPAP', epap: 8 }, P.normal);
    sim.run(20);
    expect(Math.max(...sim.buffer.map((x) => x.paw))).toBeCloseTo(8, 5);
    expect(sim.counts.spontaneous).toBeGreaterThan(3);
  });
});

describe('PCV', () => {
  it('cicla por tiempo también las respiraciones espontáneas', () => {
    const sim = make({ mode: 'PCV', rate: 10, tins: 1.2, ipap: 14 }, P.normal);
    sim.run(40);
    expect(sim.metrics.ie).toMatch(/^1:/);
    expect(sim.counts.spontaneous).toBeGreaterThan(0);
  });
});

describe('AVAPS', () => {
  it('parte de la presión inicial del manual', () => {
    const sim = make({ mode: 'AVAPS', epap: 5, vt: 500, pmin: 8, pmax: 25 }, P.apnea);
    // máx(5 + 500/60 = 13,33; 5 + 8 = 13; 8) = 13,33
    expect(sim.initialAvapsPressure()).toBeCloseTo(13.33, 1);
  });
  it('converge al VT objetivo dentro de P Mín–P Máx', () => {
    const sim = make({ mode: 'AVAPS', epap: 5, vt: 500, pmin: 8, pmax: 30, tins: 1.5, rate: 12, rise: 1 }, { ...P.apnea, compliance: 40, fuga10: 0 });
    sim.run(240);
    expect(sim.metrics.vte).toBeGreaterThan(450);
    expect(sim.metrics.vte).toBeLessThan(550);
    expect(sim.metrics.ipapAplicada).toBeLessThanOrEqual(30);
  });
  it('avisa si P Máx es insuficiente para el objetivo', () => {
    const sim = make({ mode: 'AVAPS', epap: 5, vt: 800, pmin: 8, pmax: 12, tins: 1.5, rate: 12 }, { ...P.apnea, compliance: 40, fuga10: 0 });
    sim.run(120);
    expect(ids(sim)).toContain('avapsMax');
    expect(sim.metrics.ipapAplicada).toBeLessThanOrEqual(12);
  });
});

describe('alarmas', () => {
  it('PIA se dispara cuando el límite queda por debajo de la presión alcanzada', () => {
    const sim = make({ mode: 'S/T', ipap: 20, rate: 12 }, P.apnea, { pia: 15 });
    sim.run(20);
    expect(ids(sim)).toContain('pia');
    expect(sim.getAlarms().find((a) => a.id === 'pia')?.prioridad).toBe('alta');
  });
  it('PIB se dispara tras la demora PIB T con una fuga muy grande', () => {
    const sim = make({ mode: 'S/T', ipap: 16, epap: 5, rate: 12 }, { ...P.apnea, fuga10: 120 }, { pib: 12, pibT: 5 });
    sim.run(30);
    expect(ids(sim)).toContain('pib');
  });
  it('Desconexión paciente tarda 11 s en saltar (manual p. 9-10)', () => {
    const sim = make({ mode: 'S/T' }, { ...P.apnea, fuga10: 250 });
    sim.run(8);
    expect(ids(sim)).not.toContain('desconexion');
    sim.run(8);
    expect(ids(sim)).toContain('desconexion');
  });
  it('Circuito ocluido', () => {
    const sim = make({ mode: 'S/T' }, { ...P.normal, ocluido: true });
    sim.run(12);
    expect(ids(sim)).toContain('ocluido');
  });
  it('las alarmas de baja prioridad escalan a alta tras 60 s', () => {
    const sim = make({ mode: 'S/T', rate: 12, ipap: 12 }, { ...P.apnea, compliance: 20, fuga10: 0 }, { vtBajo: 400 });
    sim.run(30);
    expect(sim.getAlarms().find((a) => a.id === 'vtBajo')?.prioridad).toBe('baja');
    sim.run(40);
    expect(sim.getAlarms().find((a) => a.id === 'vtBajo')?.prioridad).toBe('alta');
  });
  it('silenciar dura 2 minutos y restablecer limpia la lista', () => {
    const sim = make({ mode: 'S/T', ipap: 20 }, P.apnea, { pia: 15 });
    sim.run(20);
    sim.silence();
    expect(sim.isSilenced()).toBe(true);
    sim.run(121);
    expect(sim.isSilenced()).toBe(false);
    sim.resetAlarms();
    expect(sim.getAlarms().length).toBe(0);
  });
  it('Frec. alta con taquipnea', () => {
    const sim = make({ mode: 'S/T', rate: 10 }, { ...P.normal, frecuenciaEspontanea: 40 }, { frecAlta: 30 });
    sim.run(40);
    expect(ids(sim)).toContain('frecAlta');
  });
});
