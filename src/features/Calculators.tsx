import { useState } from 'react';
import { Link } from 'react-router-dom';
import { cmH2OToMbar, mbarToCmH2O, minuteVentilation, pressureSupport, tiFromRatio, timing } from '../calculators';

const num = (s: string) => (s.trim() === '' ? NaN : Number(s.replace(',', '.')));
const fmt = (n: number, d = 1) => n.toFixed(d).replace('.', ',');

function Field({ label, value, onChange, unit }: { label: string; value: string; onChange: (v: string) => void; unit: string }) {
  return (
    <label className="block text-sm">
      {label} <span className="text-slate-500">({unit})</span>
      <input inputMode="decimal" value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-3 text-lg dark:border-slate-600 dark:bg-slate-800" />
    </label>
  );
}

function attempt<T>(fn: () => T): { ok: true; v: T } | { ok: false; e: string } {
  try {
    return { ok: true, v: fn() };
  } catch (e) {
    return { ok: false, e: e instanceof RangeError ? e.message : 'Introduzca valores numéricos' };
  }
}

export default function Calculators() {
  const [ipap, setIpap] = useState('14');
  const [epap, setEpap] = useState('6');
  const [ti, setTi] = useState('1');
  const [fr, setFr] = useState('15');
  const [ratio, setRatio] = useState('2');
  const [vt, setVt] = useState('500');
  const [frVe, setFrVe] = useState('15');
  const [cm, setCm] = useState('10');
  const [mb, setMb] = useState('');

  const ps = attempt(() => pressureSupport(num(ipap), num(epap)));
  const tm = attempt(() => timing(num(ti), num(fr)));
  const tr = attempt(() => tiFromRatio(num(ratio), num(fr)));
  const ve = attempt(() => minuteVentilation(num(vt), num(frVe)));

  return (
    <div className="space-y-4">
      <Link to="/simulador" className="inline-block min-h-[48px] py-3 text-sm underline">← Simulador</Link>
      <h2 className="text-xl font-bold">Calculadoras</h2>

      <section className="card space-y-2" aria-labelledby="c-ps">
        <h3 id="c-ps" className="font-semibold">Presión de soporte</h3>
        <div className="grid grid-cols-2 gap-2">
          <Field label="IPAP" unit="cmH2O" value={ipap} onChange={setIpap} />
          <Field label="EPAP" unit="cmH2O" value={epap} onChange={setEpap} />
        </div>
        <output className="block text-lg font-bold" aria-live="polite">{ps.ok ? `PS = ${fmt(ps.v)} cmH2O` : ps.e}</output>
        {ps.ok && ps.v < 0 && <p className="text-sm text-alarm-high">La IPAP no puede ser menor que la EPAP en el equipo (manual, p. 6-24).</p>}
        <p className="text-xs text-slate-500">PS = IPAP − EPAP.</p>
      </section>

      <section className="card space-y-2" aria-labelledby="c-ie">
        <h3 id="c-ie" className="font-semibold">Tiempo inspiratorio y relación I:E</h3>
        <div className="grid grid-cols-2 gap-2">
          <Field label="T. inspiratorio" unit="s" value={ti} onChange={setTi} />
          <Field label="Frecuencia" unit="rpm" value={fr} onChange={setFr} />
        </div>
        <output className="block" aria-live="polite">
          {tm.ok ? (
            <span>
              <b className="text-lg">I:E = {tm.v.ie.replace('.', ',')}</b> · Te {fmt(tm.v.te, 2)} s · ciclo {fmt(tm.v.cycle, 2)} s · Ti/ciclo {fmt(tm.v.fraction * 100, 0)} %
              {tm.v.inverse && <span className="block text-alarm-high">Relación invertida: el V60 no la permite (manual, pp. 6-25 y 6-26).</span>}
            </span>
          ) : tm.e}
        </output>
        <div className="grid grid-cols-2 gap-2 border-t border-slate-200 pt-2 dark:border-slate-700">
          <Field label="Relación deseada 1:x, x =" unit="Te/Ti" value={ratio} onChange={setRatio} />
          <div className="self-end text-lg font-bold" aria-live="polite">{tr.ok ? `Ti = ${fmt(tr.v, 2)} s` : tr.e}</div>
        </div>
        <p className="text-xs text-slate-500">Usa la frecuencia indicada arriba. Intervalo de T. Insp. del equipo: 0,30 a 3,00 s.</p>
      </section>

      <section className="card space-y-2" aria-labelledby="c-ve">
        <h3 id="c-ve" className="font-semibold">Ventilación minuto</h3>
        <div className="grid grid-cols-2 gap-2">
          <Field label="Volumen corriente" unit="ml" value={vt} onChange={setVt} />
          <Field label="Frecuencia" unit="rpm" value={frVe} onChange={setFrVe} />
        </div>
        <output className="block text-lg font-bold" aria-live="polite">{ve.ok ? `VE = ${fmt(ve.v)} L/min` : ve.e}</output>
        <p className="text-xs text-slate-500">VE = VT × FR.</p>
      </section>

      <section className="card space-y-2" aria-labelledby="c-un">
        <h3 id="c-un" className="font-semibold">Conversión cmH2O ↔ mbar</h3>
        <div className="grid grid-cols-2 gap-2">
          <Field label="cmH2O" unit="cmH2O" value={cm} onChange={(v) => { setCm(v); setMb(''); }} />
          <Field label="mbar" unit="mbar" value={mb} onChange={(v) => { setMb(v); setCm(''); }} />
        </div>
        <output className="block text-lg font-bold" aria-live="polite">
          {mb !== '' ? (Number.isFinite(num(mb)) ? `${fmt(num(mb), 1)} mbar = ${fmt(mbarToCmH2O(num(mb)), 2)} cmH2O` : 'Introduzca un valor numérico') : Number.isFinite(num(cm)) ? `${fmt(num(cm), 1)} cmH2O = ${fmt(cmH2OToMbar(num(cm)), 2)} mbar` : 'Introduzca un valor numérico'}
        </output>
        <p className="text-xs text-slate-500">1 cmH2O = 0,980665 mbar.</p>
      </section>

      <footer className="border-t border-slate-200 pt-3 text-xs text-slate-500 dark:border-slate-700">
        Herramienta educativa. No sustituye el manual del fabricante, la formación oficial ni el criterio clínico.
      </footer>
    </div>
  );
}
