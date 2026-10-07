import { describe, expect, it } from 'vitest';
import { cmH2OToMbar, mbarToCmH2O, minuteVentilation, pressureSupport, tiFromRatio, timing } from './index';

describe('presión de soporte', () => {
  it('es IPAP − EPAP', () => {
    expect(pressureSupport(18, 6)).toBe(12);
    expect(pressureSupport(10, 10)).toBe(0);
  });
  it('rechaza valores no numéricos', () => {
    expect(() => pressureSupport(NaN, 5)).toThrow();
  });
});

describe('tiempos respiratorios', () => {
  it('calcula Te y relación I:E', () => {
    const t = timing(1, 15); // ciclo de 4 s
    expect(t.cycle).toBeCloseTo(4);
    expect(t.te).toBeCloseTo(3);
    expect(t.ie).toBe('1:3.0');
    expect(t.inverse).toBe(false);
    expect(t.fraction).toBeCloseTo(0.25);
  });
  it('detecta la relación invertida', () => {
    expect(timing(2.5, 20).inverse).toBe(true); // ciclo 3 s, Ti 2,5 s
  });
  it('rechaza Ti mayor que el ciclo y valores no positivos', () => {
    expect(() => timing(4, 15)).toThrow(RangeError);
    expect(() => timing(0, 15)).toThrow(RangeError);
    expect(() => timing(1, 0)).toThrow(RangeError);
  });
  it('obtiene Ti a partir de la relación', () => {
    expect(tiFromRatio(2, 20)).toBeCloseTo(1); // ciclo 3 s, 1:2
    expect(timing(tiFromRatio(3, 15), 15).ratio).toBeCloseTo(3);
  });
});

describe('ventilación minuto', () => {
  it('es VT × FR en L/min', () => {
    expect(minuteVentilation(500, 12)).toBeCloseTo(6);
    expect(minuteVentilation(0, 12)).toBe(0);
  });
  it('rechaza negativos', () => {
    expect(() => minuteVentilation(-1, 12)).toThrow(RangeError);
  });
});

describe('conversión de unidades', () => {
  it('1 cmH2O = 0,980665 mbar', () => {
    expect(cmH2OToMbar(1)).toBeCloseTo(0.980665, 6);
    expect(cmH2OToMbar(20)).toBeCloseTo(19.6133, 4);
  });
  it('es reversible', () => {
    expect(mbarToCmH2O(cmH2OToMbar(15))).toBeCloseTo(15, 9);
  });
});
