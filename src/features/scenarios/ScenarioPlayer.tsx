import { useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useApp } from '../../store/useApp';
import { SCENARIOS, buildOptions } from './logic';

const BAR = {
  alta: 'bg-alarm-high text-white',
  baja: 'bg-alarm-medium text-slate-900',
  informacion: 'bg-alarm-low text-white',
  ninguna: 'bg-slate-900 text-slate-300',
} as const;
const LABEL = { alta: 'ALTA PRIORIDAD', baja: 'BAJA PRIORIDAD', informacion: 'INFORMACIÓN', ninguna: 'SIN ALIMENTACIÓN' } as const;

export default function ScenarioPlayer() {
  const { id } = useParams();
  const nav = useNavigate();
  const sc = SCENARIOS.find((s) => s.id === id);
  const setResult = useApp((s) => s.setScenarioResult);

  const [stage, setStage] = useState(0);
  const [errors, setErrors] = useState(0);
  const [wrong, setWrong] = useState<{ key: string; porque: string }[]>([]);
  const options = useMemo(() => (sc && stage < sc.pasos.length ? buildOptions(sc, stage) : []), [sc, stage]);

  if (!sc) return <p>Escenario no encontrado. <Link to="/escenarios" className="underline">Volver</Link></p>;
  const finished = stage >= sc.pasos.length;
  const idx = SCENARIOS.findIndex((s) => s.id === sc.id);
  const next = SCENARIOS[idx + 1];

  const choose = (o: (typeof options)[number]) => {
    if (o.correcta) {
      const nextStage = stage + 1;
      setStage(nextStage);
      setWrong([]);
      if (nextStage >= sc.pasos.length) setResult(sc.id, errors);
    } else if (!wrong.some((w) => w.key === o.key)) {
      setErrors((e) => e + 1);
      setWrong((w) => [...w, { key: o.key, porque: o.porque ?? '' }]);
    }
  };

  const restart = () => {
    setStage(0);
    setErrors(0);
    setWrong([]);
  };

  return (
    <div className="space-y-4">
      <Link to="/escenarios" className="inline-block min-h-[48px] py-3 text-sm underline">← Escenarios</Link>
      <div className={`rounded-lg p-3 ${BAR[sc.alarma.prioridad]}`} role="status">
        <div className="text-xs font-bold tracking-wide">{LABEL[sc.alarma.prioridad]}</div>
        <div className="text-lg font-bold">{sc.alarma.mensaje}</div>
      </div>
      <p className="card">{sc.situacion}</p>
      <p className="text-xs text-slate-500">Situación y paciente ficticios, con fines docentes.</p>

      {!finished && (
        <section aria-live="polite" className="space-y-3">
          <h2 className="font-semibold">Paso {stage + 1} de {sc.pasos.length}: ¿qué haces ahora?</h2>
          <ul className="space-y-2">
            {options.map((o) => {
              const w = wrong.find((x) => x.key === o.key);
              return (
                <li key={o.key}>
                  <button
                    onClick={() => choose(o)}
                    aria-disabled={!!w}
                    className={`min-h-[56px] w-full rounded-lg border p-3 text-left ${w ? 'border-alarm-high bg-red-50 dark:bg-red-950' : 'border-slate-300 bg-white active:bg-slate-100 dark:border-slate-600 dark:bg-slate-800'}`}
                  >
                    {o.texto}
                  </button>
                  {w && <p role="alert" className="mt-1 px-1 text-sm text-red-700 dark:text-red-300">✗ {w.porque}</p>}
                </li>
              );
            })}
          </ul>
          {stage > 0 && (
            <div className="card text-sm">
              <b>Hecho hasta ahora:</b>
              <ol className="list-decimal pl-5">
                {sc.pasos.slice(0, stage).map((p) => <li key={p.id}>{p.texto}</li>)}
              </ol>
            </div>
          )}
        </section>
      )}

      {finished && (
        <section className="space-y-3" aria-live="polite">
          <div className="card border-emerald-500">
            <h2 className="font-bold">{errors === 0 ? '✓ Sin errores' : `✓ Completado con ${errors} ${errors === 1 ? 'error' : 'errores'}`}</h2>
            <p className="mt-2 text-sm">{sc.explicacion}</p>
          </div>
          <div className="card text-sm">
            <b>Secuencia según el manual V60/V60 Plus:</b>
            <ol className="list-decimal pl-5">
              {sc.pasos.map((p) => <li key={p.id}>{p.texto} <span className="text-slate-500">(p. {p.pagina})</span></li>)}
            </ol>
          </div>
          <div className="flex gap-2">
            <button className="btn flex-1 bg-slate-600" onClick={restart}>Repetir</button>
            {next ? <button className="btn flex-1" onClick={() => { nav(`/escenarios/${next.id}`); restart(); }}>Siguiente</button> : <button className="btn flex-1" onClick={() => nav('/escenarios')}>Terminar</button>}
          </div>
        </section>
      )}

      <footer className="border-t border-slate-200 pt-3 text-xs text-slate-500 dark:border-slate-700">
        Herramienta educativa. No sustituye el manual del fabricante, la formación oficial ni el criterio clínico. Compruebe siempre el manual de su equipo.
      </footer>
    </div>
  );
}
