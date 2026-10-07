/** Calculadoras de la app. Funciones puras, sin dependencias. */

/** 1 cmH2O = 98,0665 Pa y 1 mbar = 100 Pa. */
const MBAR_PER_CMH2O = 0.980665;

export const cmH2OToMbar = (cmH2O: number): number => cmH2O * MBAR_PER_CMH2O;
export const mbarToCmH2O = (mbar: number): number => mbar / MBAR_PER_CMH2O;

/** Presión de soporte = IPAP − EPAP. */
export function pressureSupport(ipap: number, epap: number): number {
  assertFinite(ipap, epap);
  return ipap - epap;
}

export interface Timing {
  cycle: number; // s
  te: number; // s
  ratio: number; // Te/Ti
  ie: string; // "1:x"
  inverse: boolean; // relación I:E invertida (Ti > Te)
  fraction: number; // Ti / ciclo
}

/** Tiempos respiratorios a partir del tiempo inspiratorio (s) y la frecuencia (rpm). */
export function timing(ti: number, rate: number): Timing {
  assertFinite(ti, rate);
  if (ti <= 0 || rate <= 0) throw new RangeError('El tiempo inspiratorio y la frecuencia deben ser positivos');
  const cycle = 60 / rate;
  const te = cycle - ti;
  if (te <= 0) throw new RangeError('El tiempo inspiratorio es mayor o igual que la duración del ciclo');
  const ratio = te / ti;
  return { cycle, te, ratio, ie: `1:${ratio.toFixed(1)}`, inverse: ti > te, fraction: ti / cycle };
}

/** Tiempo inspiratorio (s) para una relación 1:x y una frecuencia dadas. */
export function tiFromRatio(ratio: number, rate: number): number {
  assertFinite(ratio, rate);
  if (ratio <= 0 || rate <= 0) throw new RangeError('La relación y la frecuencia deben ser positivas');
  return 60 / rate / (1 + ratio);
}

/** Ventilación minuto (L/min) a partir del volumen corriente (ml) y la frecuencia (rpm). */
export function minuteVentilation(vtMl: number, rate: number): number {
  assertFinite(vtMl, rate);
  if (vtMl < 0 || rate < 0) throw new RangeError('Los valores no pueden ser negativos');
  return (vtMl * rate) / 1000;
}

function assertFinite(...values: number[]) {
  for (const v of values) if (!Number.isFinite(v)) throw new TypeError('Valor no numérico');
}
