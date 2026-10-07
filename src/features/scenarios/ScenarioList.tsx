import { Link } from 'react-router-dom';
import { useApp } from '../../store/useApp';
import { SCENARIOS } from './logic';

const DOT = { alta: 'bg-alarm-high', baja: 'bg-alarm-medium', informacion: 'bg-alarm-low', ninguna: 'bg-slate-700' } as const;

export default function ScenarioList() {
  const progress = useApp((s) => s.scenarioProgress);
  const done = SCENARIOS.filter((s) => progress[s.id]?.done).length;
  return (
    <div className="space-y-3">
      <Link to="/quiz" className="inline-block min-h-[48px] py-3 text-sm underline">← Practicar</Link>
      <h2 className="text-xl font-bold">Escenarios de alarma</h2>
      <p className="text-sm text-slate-600 dark:text-slate-300">«Suena esta alarma, ¿qué haces?». Elige cada paso en orden. Las respuestas siguen el manual del V60/V60 Plus. Completados: {done}/{SCENARIOS.length}.</p>
      <ul className="space-y-2">
        {SCENARIOS.map((s) => {
          const r = progress[s.id];
          return (
            <li key={s.id}>
              <Link to={`/escenarios/${s.id}`} className="card flex min-h-[64px] items-center gap-3">
                <span aria-hidden className={`h-4 w-4 shrink-0 rounded-full ${DOT[s.alarma.prioridad]}`} />
                <span className="flex-1 font-semibold">{s.alarma.mensaje}</span>
                <span className="text-sm text-slate-500">{r?.done ? (r.errors === 0 ? '✓ perfecto' : `✓ ${r.errors} err.`) : ''}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
