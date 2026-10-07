import alarmsJson from '../../content/simulator/alarms.json';
import { LIMITS, clamp, defaultAlarms, sanitizeSettings } from './limits';
import type { ActiveAlarm, AlarmPriority, AlarmSettings, Metrics, PatientModel, Sample, VentSettings } from './types';

/**
 * Motor del simulador del V60. Aproximación DIDÁCTICA de un compartimento; no reproduce el firmware.
 * Las simplificaciones están listadas en content/simulator/approximations.json.
 */

const ALARM_TEXT: Record<string, string> = Object.fromEntries(
  (alarmsJson.alarmas as { id: string; mensaje: string }[]).map((a) => [a.id, a.mensaje]),
);
const ESCALATING = new Set(['frecAlta', 'frecBaja', 'vtBajo', 'vtAlto', 'veBaja']);
const BUFFER_SECONDS = 30;
const WARMUP_SECONDS = 10;
const OCCLUSION_SECONDS = 5; // aproximación (ap-ocluido)
const DISCONNECT_LEAK = 100; // L/min, aproximación (ap-desconexion)

export class VentSim {
  settings: VentSettings;
  alarmSettings: AlarmSettings;
  patient: PatientModel;

  t = 0;
  buffer: Sample[] = [];
  metrics: Metrics = { ppico: 0, vte: 0, fr: 0, ve: 0, ie: '-', fuga: 0, ipapAplicada: 0, tipo: '-' };

  private phase: 'I' | 'E' = 'E';
  private tPhase = 0;
  private tSinceStart = 0;
  private paw: number;
  private vol = 0; // L por encima del equilibrio a EPAP
  private q = 0; // L/s
  private tipo: 'Esp' | 'Prog' = 'Esp';
  private ipapTarget: number;
  private tNeural = 0;
  private pmus = 0;
  private peakFlow = 0;
  private ppicoBreath = 0;
  private breathStarts: number[] = [];
  private vtes: number[] = [];
  private lastTi = 0;
  private leakNow = 0;
  private alarms = new Map<string, ActiveAlarm>();
  private silenceUntil = 0;
  private pibSince: number | null = null;
  private disconnectSince: number | null = null;
  private occlusionSince: number | null = null;
  private lastPpico = 0;
  readonly counts = { total: 0, spontaneous: 0, mandatory: 0 };

  constructor(settings: VentSettings, patient: PatientModel, alarmSettings?: AlarmSettings) {
    this.settings = sanitizeSettings(settings);
    this.patient = { ...patient };
    this.alarmSettings = alarmSettings ?? defaultAlarms(this.settings);
    this.paw = this.settings.epap;
    this.ipapTarget = this.initialAvapsPressure();
    this.tNeural = -0.5; // primer esfuerzo a los 0,5 s, de forma determinista
  }

  /** Presión inicial de AVAPS: la mayor de EPAP + VT/60, EPAP + 8 y P Mín (manual, p. 4-11). */
  initialAvapsPressure(): number {
    const s = this.settings;
    const p = Math.max(s.epap + s.vt / 60, s.epap + 8, s.pmin);
    return clamp(p, s.pmin, Math.max(s.pmin, s.pmax));
  }

  applySettings(next: VentSettings) {
    const prev = this.settings;
    this.settings = sanitizeSettings(next);
    if (prev.mode !== this.settings.mode || prev.vt !== this.settings.vt || prev.pmin !== this.settings.pmin || prev.pmax !== this.settings.pmax || prev.epap !== this.settings.epap) {
      this.ipapTarget = this.initialAvapsPressure();
    }
  }

  setAlarmSettings(a: AlarmSettings) {
    this.alarmSettings = { ...a };
  }

  setPatient(p: PatientModel) {
    this.patient = { ...p };
  }

  // ---------------------------------------------------------------- alarmas

  getAlarms(): ActiveAlarm[] {
    const order: Record<AlarmPriority, number> = { alta: 0, baja: 1, informacion: 2 };
    return [...this.alarms.values()].sort((a, b) => order[a.prioridad] - order[b.prioridad] || a.desde - b.desde);
  }

  isSilenced(): boolean {
    return this.t < this.silenceUntil;
  }

  silenceRemaining(): number {
    return Math.max(0, this.silenceUntil - this.t);
  }

  silence() {
    this.silenceUntil = this.t + LIMITS.tiempos.silencioAlarmaSeg.valor;
  }

  resetAlarms() {
    this.alarms.clear();
    this.silenceUntil = 0;
  }

  private raise(id: string, prioridad: AlarmPriority) {
    const cur = this.alarms.get(id);
    if (!cur) {
      this.alarms.set(id, { id, mensaje: ALARM_TEXT[id] ?? id, prioridad, desde: this.t });
    } else if (cur.prioridad !== 'alta' && prioridad === 'alta') {
      cur.prioridad = 'alta';
    }
  }

  private clear(id: string) {
    this.alarms.delete(id);
  }

  private escalate() {
    const limit = LIMITS.tiempos.escaladaPrioridadSeg.valor;
    for (const a of this.alarms.values()) {
      if (ESCALATING.has(a.id) && a.prioridad === 'baja' && this.t - a.desde > limit) a.prioridad = 'alta';
    }
  }

  // ------------------------------------------------------------------- paso

  private tau(): number {
    return 0.02 * this.settings.rise + 0.03; // ap-subida
  }

  private startBreath(tipo: 'Esp' | 'Prog') {
    this.phase = 'I';
    this.tPhase = 0;
    this.tSinceStart = 0;
    this.tipo = tipo;
    this.peakFlow = 0;
    this.ppicoBreath = this.paw;
    this.breathStarts.push(this.t);
    this.counts.total++;
    if (tipo === 'Esp') this.counts.spontaneous++;
    else this.counts.mandatory++;
    if (this.breathStarts.length > 8) this.breathStarts.shift();
  }

  private endBreath() {
    const s = this.settings;
    const vte = this.vol * 1000;
    this.lastTi = this.tPhase;
    this.lastPpico = this.ppicoBreath;
    this.vtes.push(vte);
    if (this.vtes.length > 4) this.vtes.shift();
    this.phase = 'E';
    this.tPhase = 0;

    // alarmas por respiración
    const al = this.alarmSettings;
    if (al.vtBajo > 0 && vte < al.vtBajo) this.raise('vtBajo', 'baja');
    else this.clear('vtBajo');
    if (vte > al.vtAlto) this.raise('vtAlto', 'baja');
    else this.clear('vtAlto');
    if (this.ppicoBreath > al.pia) this.raise('pia', 'alta');
    else this.clear('pia');
    if (al.pib > 0 && this.ppicoBreath < al.pib) {
      if (this.pibSince === null) this.pibSince = this.t;
    } else {
      this.pibSince = null;
      this.clear('pib');
    }

    // AVAPS: ajuste de presión hacia el VT objetivo (ap-avaps)
    if (s.mode === 'AVAPS') {
      const dp = this.ipapTarget - s.epap;
      if (dp > 0.5 && vte > 0) {
        const gain = vte / dp; // ml/cmH2O
        const need = s.epap + s.vt / gain;
        if (need > this.ipapTarget + 0.25) this.ipapTarget += 0.5;
        else if (need < this.ipapTarget - 0.25) this.ipapTarget -= 0.5;
        if (need > s.pmax + 0.25) this.raise('avapsMax', 'informacion');
        else this.clear('avapsMax');
        if (need < s.pmin - 0.25) this.raise('avapsMin', 'informacion');
        else this.clear('avapsMin');
        this.ipapTarget = clamp(this.ipapTarget, s.pmin, Math.max(s.pmin, s.pmax));
      }
    }
  }

  private updateMetrics() {
    const s = this.settings;
    const starts = this.breathStarts;
    let fr = 0;
    if (starts.length >= 2) {
      const n = Math.min(4, starts.length - 1);
      let sum = 0;
      for (let i = starts.length - n; i < starts.length; i++) sum += starts[i] - starts[i - 1];
      const mean = sum / n;
      const since = this.t - starts[starts.length - 1];
      fr = 60 / Math.max(mean, since);
    } else if (starts.length === 1) {
      fr = 60 / Math.max(5, this.t - starts[0]);
    }
    const vteAvg = this.vtes.length ? this.vtes.reduce((a, b) => a + b, 0) / this.vtes.length : 0;
    const period = starts.length >= 2 ? Math.max(0.1, starts[starts.length - 1] - starts[starts.length - 2]) : 0;
    const te = period - this.lastTi;
    this.metrics = {
      ppico: Math.round(Math.max(this.lastPpico, this.phase === 'I' ? this.ppicoBreath : 0) * 10) / 10,
      vte: Math.round(vteAvg),
      fr: Math.round(fr * 10) / 10,
      ve: Math.round(((fr * vteAvg) / 1000) * 10) / 10,
      ie: period > 0 && this.lastTi > 0 && te > 0 ? `1:${(te / this.lastTi).toFixed(1)}` : '-',
      fuga: Math.round(this.leakNow),
      ipapAplicada: s.mode === 'AVAPS' ? Math.round(this.ipapTarget * 10) / 10 : s.ipap,
      tipo: this.phase === 'I' ? this.tipo : this.metrics.tipo,
    };
  }

  private evaluateContinuousAlarms() {
    const al = this.alarmSettings;
    const lim = LIMITS.tiempos;

    if (this.t >= WARMUP_SECONDS) {
      // Frec. baja
      const sinceBreath = this.breathStarts.length ? this.t - this.breathStarts[this.breathStarts.length - 1] : this.t;
      const fr = this.metrics.fr;
      if (fr < al.frecBaja) {
        const highNow = al.frecBaja <= 4 ? sinceBreath > 60 / al.frecBaja : sinceBreath > lim.frecBajaSinRespiracionSeg.valor;
        this.raise('frecBaja', highNow ? 'alta' : 'baja');
      } else {
        this.clear('frecBaja');
      }
      // Frec. alta
      if (this.breathStarts.length >= 4 && fr > al.frecAlta) this.raise('frecAlta', 'baja');
      else this.clear('frecAlta');
      // Ventilación minuto baja
      if (al.veBaja > 0 && this.vtes.length >= 3 && this.metrics.ve < al.veBaja) this.raise('veBaja', 'baja');
      else this.clear('veBaja');
    }

    // PIB con demora PIB T
    if (this.pibSince !== null && this.t - this.pibSince >= al.pibT) this.raise('pib', 'alta');

    // Desconexión paciente: fuga mantenida 11 s
    if (this.leakNow >= DISCONNECT_LEAK) {
      if (this.disconnectSince === null) this.disconnectSince = this.t;
      if (this.t - this.disconnectSince >= lim.desconexionPacienteSeg.valor) this.raise('desconexion', 'alta');
    } else {
      this.disconnectSince = null;
      this.clear('desconexion');
    }

    // Circuito ocluido
    if (this.patient.ocluido) {
      if (this.occlusionSince === null) this.occlusionSince = this.t;
      if (this.t - this.occlusionSince >= OCCLUSION_SECONDS) this.raise('ocluido', 'alta');
    } else {
      this.occlusionSince = null;
      this.clear('ocluido');
    }

    this.escalate();
  }

  step(dt = 0.02) {
    const s = this.settings;
    const p = this.patient;
    this.t += dt;
    this.tPhase += dt;
    this.tSinceStart += dt;

    // Esfuerzo neural del paciente (media sinusoide)
    if (p.frecuenciaEspontanea > 0 && p.esfuerzo > 0) {
      this.tNeural += dt;
      const period = 60 / p.frecuenciaEspontanea;
      if (this.tNeural >= period) this.tNeural -= period;
      this.pmus = this.tNeural >= 0 && this.tNeural < p.tiempoNeuralInsp ? -p.esfuerzo * Math.sin((Math.PI * this.tNeural) / p.tiempoNeuralInsp) : 0;
    } else {
      this.pmus = 0;
    }
    const neuralActive = this.pmus < -0.05;

    // Disparo y ciclado
    if (this.phase === 'E') {
      const threshold = 0.5 + Math.max(0, this.leakNow - 10) / 40; // ap-trigger
      if (this.tSinceStart > 0.3 && -this.pmus > threshold) {
        this.startBreath('Esp');
      } else if (s.mode !== 'CPAP' && this.tSinceStart >= 60 / s.rate) {
        this.startBreath('Prog');
      }
    } else {
      const timed = this.tipo === 'Prog' || s.mode === 'PCV';
      let cycle = false;
      if (s.mode === 'CPAP') cycle = !neuralActive && this.tPhase > 0.2;
      else if (timed) cycle = this.tPhase >= s.tins;
      else cycle = this.tPhase >= LIMITS.tiempos.cicloMaxIpapSeg.valor || (this.tPhase >= 0.3 && this.q < 0.25 * this.peakFlow);
      if (cycle) this.endBreath();
    }

    // Presión en la vía aérea
    const ipapEff = s.mode === 'AVAPS' ? this.ipapTarget : s.ipap;
    const loss = clamp((this.leakNow - 30) / 150, 0, 0.6); // ap-fuga
    if (s.mode === 'CPAP') {
      this.paw = s.epap;
    } else if (this.phase === 'I') {
      const target = s.epap + (ipapEff - s.epap) * (1 - loss);
      this.paw = s.epap + (target - s.epap) * (1 - Math.exp(-this.tPhase / this.tau()));
    } else {
      this.paw = s.epap + (this.paw - s.epap) * Math.exp(-dt / 0.05);
    }
    if (this.phase === 'I') this.ppicoBreath = Math.max(this.ppicoBreath, this.paw);

    // Mecánica: flujo = (Paw − EPAP − Pmus − V/C) / R
    const C = p.compliance / 1000;
    const drive = this.paw - s.epap - this.pmus - this.vol / C;
    this.q = p.ocluido ? 0 : drive / p.resistencia;
    this.vol = Math.max(0, this.vol + this.q * dt);
    if (this.vol === 0 && this.q < 0) this.q = 0;
    if (this.phase === 'I') this.peakFlow = Math.max(this.peakFlow, this.q);

    // Fuga no intencional: Q = k·√P (ap-fuga)
    this.leakNow = (p.fuga10 / Math.sqrt(10)) * Math.sqrt(Math.max(this.paw, 0));

    this.updateMetrics();
    this.evaluateContinuousAlarms();

    this.buffer.push({ t: this.t, paw: this.paw, flow: this.q * 60, vol: this.vol * 1000 });
    const cutoff = this.t - BUFFER_SECONDS;
    while (this.buffer.length && this.buffer[0].t < cutoff) this.buffer.shift();
  }

  run(seconds: number, dt = 0.02) {
    const n = Math.round(seconds / dt);
    for (let i = 0; i < n; i++) this.step(dt);
  }
}
