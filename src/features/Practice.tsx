import { Link } from 'react-router-dom';
import { SCENARIOS } from './scenarios/logic';
import { useApp } from '../store/useApp';

export default function Practice() {
  const progress = useApp((s) => s.scenarioProgress);
  const done = SCENARIOS.filter((s) => progress[s.id]?.done).length;
  return (
    <div className="space-y-3">
      <h2 className="text-xl font-bold">Practicar</h2>
      <Link to="/escenarios" className="card block min-h-[64px]">
        <div className="flex items-center justify-between">
          <span className="font-semibold">Escenarios de alarma</span>
          <span className="text-sm text-slate-500">{done}/{SCENARIOS.length}</span>
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-300">«Suena esta alarma, ¿qué haces?» con respuesta paso a paso.</p>
      </Link>
      <div className="card opacity-70">
        <div className="font-semibold">Quiz por módulo y modo examen</div>
        <p className="text-sm text-slate-600 dark:text-slate-300">Próximamente (fase C).</p>
      </div>
    </div>
  );
}
