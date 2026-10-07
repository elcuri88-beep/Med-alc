export type Mode = 'CPAP' | 'S/T' | 'PCV' | 'AVAPS';

export interface VentSettings {
  mode: Mode;
  ipap: number; // cmH2O
  epap: number; // cmH2O (en CPAP es el nivel CPAP)
  tins: number; // s
  rate: number; // rpm
  rise: number; // 1 (más rápida) a 5
  fio2: number; // %
  vt: number; // ml (AVAPS)
  pmin: number; // cmH2O (AVAPS)
  pmax: number; // cmH2O (AVAPS)
}

export interface AlarmSettings {
  frecAlta: number; // rpm
  frecBaja: number; // rpm
  vtAlto: number; // ml
  vtBajo: number; // ml, 0 = OFF
  pia: number; // cmH2O
  pib: number; // cmH2O, 0 = OFF
  pibT: number; // s
  veBaja: number; // L/min, 0 = OFF
}

export interface PatientModel {
  id: string;
  nombre: string;
  compliance: number; // ml/cmH2O
  resistencia: number; // cmH2O/L/s
  frecuenciaEspontanea: number; // rpm, 0 = apnea
  esfuerzo: number; // cmH2O pico de presión muscular
  tiempoNeuralInsp: number; // s
  fuga10: number; // L/min de fuga no intencional a 10 cmH2O
  ocluido: boolean;
}

export type AlarmPriority = 'alta' | 'baja' | 'informacion';

export interface ActiveAlarm {
  id: string;
  mensaje: string;
  prioridad: AlarmPriority;
  desde: number; // s de simulación
}

export interface Sample {
  t: number;
  paw: number; // cmH2O
  flow: number; // L/min (flujo del paciente, sin fuga)
  vol: number; // ml
}

export interface Metrics {
  ppico: number;
  vte: number; // ml
  fr: number; // rpm
  ve: number; // L/min
  ie: string;
  fuga: number; // L/min, fuga no intencional estimada
  ipapAplicada: number; // cmH2O (relevante en AVAPS)
  tipo: 'Esp' | 'Prog' | '-';
}
