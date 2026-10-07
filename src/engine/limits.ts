import limitsJson from '../../content/simulator/limits.json';
import type { AlarmSettings, VentSettings } from './types';

interface Range {
  etiqueta: string;
  unidad: string;
  min: number;
  max: number;
  paso: number;
  pagina: string;
  nota?: string;
}

export const LIMITS = limitsJson as unknown as {
  ajustes: Record<keyof Omit<VentSettings, 'mode'>, Range>;
  alarmas: Record<keyof AlarmSettings, Range>;
  tiempos: Record<string, { valor: number; pagina: string; nota?: string }>;
  ventanasOnda: { segundos: number[] };
};

export const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

export const DEFAULT_SETTINGS: VentSettings = {
  mode: 'S/T', ipap: 12, epap: 5, tins: 1.0, rate: 12, rise: 2, fio2: 40, vt: 500, pmin: 8, pmax: 25,
};

export function defaultAlarms(s: VentSettings): AlarmSettings {
  return {
    frecAlta: 35,
    frecBaja: 8,
    vtAlto: 1200,
    vtBajo: 200,
    pia: clamp(s.ipap + 10, LIMITS.alarmas.pia.min, LIMITS.alarmas.pia.max),
    pib: s.mode === 'CPAP' ? 0 : clamp(s.ipap - 4, 0, LIMITS.alarmas.pib.max),
    pibT: 10,
    veBaja: 0,
  };
}

/** Relación I:E inversa: no permitida por el manual (pp. 6-25 y 6-26). */
export function isInverseIE(tins: number, rate: number): boolean {
  return tins > 60 / rate - tins + 1e-9;
}

/** Ajusta un conjunto de ajustes a los intervalos del manual y a sus restricciones cruzadas. */
export function sanitizeSettings(s: VentSettings): VentSettings {
  const a = LIMITS.ajustes;
  const out: VentSettings = { ...s };
  out.ipap = clamp(Math.round(s.ipap), a.ipap.min, a.ipap.max);
  out.epap = clamp(Math.round(s.epap), a.epap.min, a.epap.max);
  if (out.epap > out.ipap) out.epap = out.ipap;
  out.rate = clamp(Math.round(s.rate), a.rate.min, a.rate.max);
  out.tins = clamp(Math.round(s.tins * 10) / 10, a.tins.min, a.tins.max);
  // Sin relación I:E invertida: Ti <= Te
  const maxTi = Math.max(a.tins.min, Math.floor((30 / out.rate) * 10) / 10);
  if (out.tins > maxTi) out.tins = maxTi;
  out.rise = clamp(Math.round(s.rise), a.rise.min, a.rise.max);
  out.fio2 = clamp(Math.round(s.fio2), a.fio2.min, a.fio2.max);
  out.vt = clamp(Math.round(s.vt / 10) * 10, a.vt.min, a.vt.max);
  out.pmin = clamp(Math.round(s.pmin), a.pmin.min, a.pmin.max);
  out.pmax = clamp(Math.round(s.pmax), a.pmax.min, a.pmax.max);
  if (out.pmax < out.pmin) out.pmax = out.pmin;
  return out;
}
