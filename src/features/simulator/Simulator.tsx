import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import alarmsJson from '../../../content/simulator/alarms.json';
import patientsJson from '../../../content/simulator/patients.json';
import approximations from '../../../content/simulator/approximations.json';
import { DEFAULT_SETTINGS, LIMITS, defaultAlarms, sanitizeSettings } from '../../engine/limits';
import { VentSim } from '../../engine/sim';
import type { AlarmSettings, Metrics, Mode, PatientModel, VentSettings } from '../../engine/types';
import { useApp } from '../../store/useApp';
import Stepper from './Stepper';
import WaveCanvas from './WaveCanvas';

const PATIENTS = patientsJson.perfiles as unknown as (PatientModel & { descripcion: string })[];
const ALARM_INFO = Object.fromEntries((alarmsJson.alarmas as { id: string; acciones: string[]; pagina: string }[]).map((a) => [a.id, a]));
const MODES: Mode[] = ['CPAP', 'S/T', 'PCV', 'AVAPS'];
const BAR: Record<string, string> = {
  alta: 'bg-alarm-high text-white',
  baja: 'bg-alarm-medium text-slate-900',
  informacion: 'bg-alarm-low text-white',
};

const R = (r: { min: number; max: number; paso: number }) => ({ min: r.min, max: r.max, step: r.paso });

interface Snapshot {
  metrics: Metrics;
  alarms: ReturnType<VentSim['getAlarms']>;
  silenced: number;
}

export default function Simulator() {
  const deviceModel = useApp((s) => s.deviceModel);
  const setDeviceModel = useApp((s) => s.setDeviceModel);

  const [settings, setSettings] = useState<VentSettings>(DEFAULT_SETTINGS);
  const [alarmSettings, setAlarmSettings] = useState<AlarmSettings>(() => defaultAlarms(DEFAULT_SETTINGS));
  const [patientId, setPatientId] = useState('epoc');
  const [leak, setLeak] = useState<number>(PATIENTS.find((p) => p.id === 'epoc')!.fuga10);
  const [occluded, setOccluded] = useState(false);
  const [seconds, setSeconds] = useState(12);
  const [frozen, setFrozen] = useState(false);
  const [showAlarmCfg, setShowAlarmCfg] = useState(false);
  const [snap, setSnap] = useState<Snapshot | null>(null);

  const basePatient = PATIENTS.find((p) => p.id === patientId)!;
  const patient = useMemo<PatientModel>(() => ({ ...basePatient, fuga10: leak, ocluido: occluded }), [basePatient, leak, occluded]);

  const simRef = useRef<VentSim | null>(null);
  if (!simRef.current) simRef.current = new VentSim(DEFAULT_SETTINGS, patient, defaultAlarms(DEFAULT_SETTINGS));
  const sim = simRef.current;

  useEffect(() => sim.setPatient(patient), [sim, patient]);
  useEffect(() => sim.setAlarmSettings(alarmSettings), [sim, alarmSettings]);

  // Bucle de simulación en tiempo real
  useEffect(() => {
    let last = performance.now();
    let raf = 0;
    let acc = 0;
    const loop = (now: number) => {
      const dt = Math.min(0.25, (now - last) / 1000);
      last = now;
      if (!frozen) {
        let remaining = dt;
        while (remaining > 1e-6) {
          const h = Math.min(0.02, remaining);
          sim.step(h);
          remaining -= h;
        }
      }
      acc += dt;
      if (acc > 0.1) {
        acc = 0;
        setSnap({ metrics: { ...sim.metrics }, alarms: sim.getAlarms().map((a) => ({ ...a })), silenced: sim.silenceRemaining() });
      }
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [sim, frozen]);

  const update = useCallback(
    (patch: Partial<VentSettings>) => {
      const next = sanitizeSettings({ ...settings, ...patch });
      setSettings(next);
      sim.applySettings(next);
      if (patch.mode && patch.mode !== settings.mode) {
        const a = defaultAlarms(next);
        setAlarmSettings(a);
        sim.setAlarmSettings(a);
      }
    },
    [settings, sim],
  );

  const updateAlarm = (patch: Partial<AlarmSettings>) => setAlarmSettings((a) => ({ ...a, ...patch }));

  const choosePatient = (id: string) => {
    const p = PATIENTS.find((x) => x.id === id)!;
    setPatientId(id);
    setLeak(p.fuga10);
    setOccluded(false);
  };

  const L = LIMITS.ajustes;
  const A = LIMITS.alarmas;
  const m = snap?.metrics;
  const top = snap?.alarms[0];
  const silenced = (snap?.silenced ?? 0) > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-xl font-bold">Simulador del panel V60</h2>
        <Link to="/calculadoras" className="min-h-[48px] py-3 text-sm underline">Calculadoras</Link>
      </div>

      <div role="alert" className="rounded-lg border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950 dark:text-amber-100">
        Simulación didáctica con pacientes ficticios. No reproduce el firmware del equipo ni sustituye el manual del fabricante.
      </div>

      <fieldset className="flex gap-2" aria-label="Modelo del equipo">
        {(['V60', 'V60 Plus'] as const).map((mdl) => (
          <button key={mdl} aria-pressed={deviceModel === mdl} onClick={() => setDeviceModel(mdl)} className={`min-h-[48px] flex-1 rounded-lg border px-3 font-semibold ${deviceModel === mdl ? 'border-brand bg-brand text-white' : 'border-slate-300 dark:border-slate-600'}`}>
            {mdl}
          </button>
        ))}
      </fieldset>
      <p className="text-xs text-slate-500">
        Ambos modelos comparten plataforma y modos (manual, p. 3-1). El V60 Plus incluye de serie la terapia de alto flujo (HFT), que este simulador no reproduce.
        {deviceModel === 'V60' && ' En el V60, HFT y PPV son opcionales.'}
      </p>

      {/* Barra de alarma */}
      <div className={`rounded-lg p-3 ${top ? BAR[top.prioridad] : 'bg-slate-200 dark:bg-slate-700'}`} role="status" aria-live={top?.prioridad === 'alta' ? 'assertive' : 'polite'}>
        {top ? (
          <>
            <div className="flex items-center justify-between gap-2">
              <b>{top.prioridad === 'alta' ? '● ALTA' : top.prioridad === 'baja' ? '● BAJA' : 'ℹ INFO'} · {top.mensaje}</b>
              <span className="text-xs">{silenced ? `Silenciada ${Math.ceil(snap!.silenced)} s` : ''}</span>
            </div>
            {snap!.alarms.length > 1 && <div className="text-xs">+{snap!.alarms.length - 1} más: {snap!.alarms.slice(1).map((a) => a.mensaje).join(' · ')}</div>}
            <ul className="mt-1 list-disc pl-5 text-sm">
              {(ALARM_INFO[top.id]?.acciones ?? []).map((t) => <li key={t}>{t}</li>)}
            </ul>
            <div className="text-[10px] opacity-80">Manual V60/V60 Plus, p. {ALARM_INFO[top.id]?.pagina}</div>
          </>
        ) : (
          <span>No hay alarmas activas</span>
        )}
      </div>
      <div className="flex gap-2">
        <button className="btn flex-1" onClick={() => sim.silence()}>Silenciar alarma (2 min)</button>
        <button className="btn flex-1 bg-slate-600" onClick={() => sim.resetAlarms()}>Restablecer alarma</button>
      </div>

      <WaveCanvas sim={sim} seconds={seconds} frozen={frozen} />
      <div className="flex flex-wrap items-center gap-2">
        <button className="min-h-[48px] rounded-lg border border-slate-300 px-4 dark:border-slate-600" aria-pressed={frozen} onClick={() => setFrozen((f) => !f)}>{frozen ? '▶ Reanudar ondas' : '⏸ Congelar ondas'}</button>
        <label className="flex items-center gap-2 text-sm">
          Ventana
          <select value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} className="min-h-[48px] rounded-lg border border-slate-300 bg-white px-2 dark:border-slate-600 dark:bg-slate-800">
            {LIMITS.ventanasOnda.segundos.map((s) => <option key={s} value={s}>{s} s</option>)}
          </select>
        </label>
      </div>

      {/* Monitorización */}
      <div className="grid grid-cols-3 gap-2 text-center" aria-label="Valores monitorizados">
        {[
          ['P pico', m?.ppico ?? 0, 'cmH2O'],
          ['VT esp.', m?.vte ?? 0, 'ml'],
          ['FR', m?.fr ?? 0, 'rpm'],
          ['VE', m?.ve ?? 0, 'L/min'],
          ['I:E', m?.ie ?? '-', ''],
          ['Fuga', m?.fuga ?? 0, 'L/min'],
        ].map(([k, v, u]) => (
          <div key={String(k)} className="rounded-lg bg-slate-900 p-2 text-white">
            <div className="text-xs text-slate-400">{k}</div>
            <div className="text-2xl font-bold tabular-nums">{v}</div>
            <div className="text-[10px] text-slate-400">{u}</div>
          </div>
        ))}
      </div>
      {settings.mode === 'AVAPS' && <p className="text-sm">IPAP aplicada por AVAPS: <b>{m?.ipapAplicada}</b> cmH2O</p>}

      {/* Modo */}
      <fieldset aria-label="Modo de ventilación">
        <legend className="mb-1 text-sm font-semibold">Modo</legend>
        <div className="grid grid-cols-4 gap-2">
          {MODES.map((md) => (
            <button key={md} aria-pressed={settings.mode === md} onClick={() => update({ mode: md })} className={`min-h-[48px] rounded-lg border font-semibold ${settings.mode === md ? 'border-brand bg-brand text-white' : 'border-slate-300 dark:border-slate-600'}`}>{md}</button>
          ))}
        </div>
      </fieldset>

      {/* Ajustes */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {settings.mode !== 'CPAP' && settings.mode !== 'AVAPS' && <Stepper label="IPAP" unit="cmH2O" value={settings.ipap} {...R(L.ipap)} onChange={(v) => update({ ipap: v })} />}
        <Stepper label={settings.mode === 'CPAP' ? 'CPAP' : 'EPAP'} unit="cmH2O" value={settings.epap} {...R(L.epap)} onChange={(v) => update({ epap: v })} />
        {settings.mode !== 'CPAP' && <Stepper label="Frecuencia" unit="rpm" value={settings.rate} {...R(L.rate)} onChange={(v) => update({ rate: v })} />}
        {settings.mode !== 'CPAP' && <Stepper label="T. Insp." unit="s" value={settings.tins} {...R(L.tins)} onChange={(v) => update({ tins: v })} hint="sin I:E invertida" />}
        {settings.mode !== 'CPAP' && <Stepper label="Subida" unit="" value={settings.rise} {...R(L.rise)} onChange={(v) => update({ rise: v })} hint="1 = rápida" />}
        {settings.mode === 'AVAPS' && (
          <>
            <Stepper label="VT objetivo" unit="ml" value={settings.vt} {...R(L.vt)} onChange={(v) => update({ vt: v })} />
            <Stepper label="P Mín" unit="cmH2O" value={settings.pmin} {...R(L.pmin)} onChange={(v) => update({ pmin: v })} />
            <Stepper label="P Máx" unit="cmH2O" value={settings.pmax} {...R(L.pmax)} onChange={(v) => update({ pmax: v })} />
          </>
        )}
        <Stepper label="O2" unit="%" value={settings.fio2} {...R(L.fio2)} onChange={(v) => update({ fio2: v })} hint="solo ajuste" />
      </div>
      <p className="text-xs text-slate-500">Intervalos de ajuste del manual del V60/V60 Plus (Tabla 6-3). La sensibilidad de disparo y ciclado la gestiona Auto-Trak (no se ajusta).</p>

      {/* Alarmas */}
      <button className="min-h-[48px] w-full rounded-lg border border-slate-300 dark:border-slate-600" aria-expanded={showAlarmCfg} onClick={() => setShowAlarmCfg((s) => !s)}>
        {showAlarmCfg ? 'Ocultar ajustes de alarma' : 'Ajustes de alarma'}
      </button>
      {showAlarmCfg && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Stepper label="PIA" unit="cmH2O" value={alarmSettings.pia} {...R(A.pia)} onChange={(v) => updateAlarm({ pia: v })} />
          <Stepper label="PIB" unit="cmH2O" value={alarmSettings.pib} {...R(A.pib)} offAtMin onChange={(v) => updateAlarm({ pib: v })} hint="3–5 bajo IPAP" />
          <Stepper label="PIB T" unit="s" value={alarmSettings.pibT} {...R(A.pibT)} onChange={(v) => updateAlarm({ pibT: v })} />
          <Stepper label="Frec. alta" unit="rpm" value={alarmSettings.frecAlta} {...R(A.frecAlta)} onChange={(v) => updateAlarm({ frecAlta: v })} />
          <Stepper label="Frec. baja" unit="rpm" value={alarmSettings.frecBaja} {...R(A.frecBaja)} onChange={(v) => updateAlarm({ frecBaja: v })} />
          <Stepper label="VT alto" unit="ml" value={alarmSettings.vtAlto} {...R(A.vtAlto)} onChange={(v) => updateAlarm({ vtAlto: v })} />
          <Stepper label="VT bajo" unit="ml" value={alarmSettings.vtBajo} {...R(A.vtBajo)} offAtMin onChange={(v) => updateAlarm({ vtBajo: v })} />
          <Stepper label="Baja VE" unit="L/min" value={alarmSettings.veBaja} {...R(A.veBaja)} offAtMin onChange={(v) => updateAlarm({ veBaja: v })} />
        </div>
      )}

      {/* Paciente simulado */}
      <section className="card space-y-3">
        <h3 className="font-semibold">Paciente simulado (ficticio)</h3>
        <label className="block text-sm">
          Perfil
          <select value={patientId} onChange={(e) => choosePatient(e.target.value)} className="mt-1 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-2 dark:border-slate-600 dark:bg-slate-800">
            {PATIENTS.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
        </label>
        <p className="text-sm text-slate-600 dark:text-slate-300">{basePatient.descripcion} (C {basePatient.compliance} ml/cmH2O, R {basePatient.resistencia} cmH2O/L/s)</p>
        <Stepper label="Fuga no intencional a 10 cmH2O" unit="L/min" value={leak} min={0} max={250} step={5} onChange={setLeak} />
        <div className="flex gap-2">
          <button className="min-h-[48px] flex-1 rounded-lg border border-slate-300 dark:border-slate-600" onClick={() => setLeak(250)}>Desconectar paciente</button>
          <button className="min-h-[48px] flex-1 rounded-lg border border-slate-300 dark:border-slate-600" aria-pressed={occluded} onClick={() => setOccluded((o) => !o)}>{occluded ? 'Desocluir circuito' : 'Ocluir circuito'}</button>
        </div>
      </section>

      <details className="card text-sm">
        <summary className="min-h-[48px] cursor-pointer py-3 font-semibold">Limitaciones del simulador ({approximations.aproximaciones.length})</summary>
        <ul className="list-disc space-y-1 pl-5">
          {approximations.aproximaciones.map((a) => <li key={a.id}>{a.texto}</li>)}
        </ul>
        <p className="mt-2">Alarmas no simuladas: {alarmsJson.noSimuladas.join(', ')}.</p>
      </details>

      <footer className="border-t border-slate-200 pt-3 text-xs text-slate-500 dark:border-slate-700">
        Herramienta educativa. No sustituye el manual del fabricante, la formación oficial ni el criterio clínico. Valores y pacientes ficticios.
      </footer>
    </div>
  );
}
