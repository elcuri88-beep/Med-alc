import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { SCENARIOS } from './scenarios/logic';
import { QUESTIONS, QUIZ_MODULES } from './quiz/data';
import { examSeconds } from './quiz/logic';
import { useApp } from '../store/useApp';

const fmt = (s: number) => `${Math.floor(s / 60)} min`;

export default function Practice() {
  const nav = useNavigate();
  const progress = useApp((s) => s.scenarioProgress);
  const stats = useApp((s) => s.quizStats);
  const history = useApp((s) => s.examHistory);
  const [modulo, setModulo] = useState('todos');
  const [n, setN] = useState(20);

  const done = SCENARIOS.filter((s) => progress[s.id]?.done).length;
  const pool = modulo === 'todos' ? QUESTIONS : QUESTIONS.filter((q) => q.modulo === modulo);
  const nExam = Math.min(n, pool.length);
  const failed = Object.values(stats).filter((v) => !v.last).length;
  const go = (modo: string) => nav(`/quiz/sesion?modo=${modo}&modulo=${modulo}${modo === 'examen' ? `&n=${nExam}` : ''}`);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Practicar</h2>

      <Link to="/escenarios" className="card block min-h-[64px]">
        <div className="flex items-center justify-between">
          <span className="font-semibold">Escenarios de alarma</span>
          <span className="text-sm text-slate-500">{done}/{SCENARIOS.length}</span>
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-300">«Suena esta alarma, ¿qué haces?» con respuesta paso a paso.</p>
      </Link>

      <section className="card space-y-3" aria-labelledby="quiz-h">
        <h3 id="quiz-h" className="font-semibold">Quiz ({QUESTIONS.length} preguntas)</h3>
        <label className="block text-sm">
          Módulo
          <select value={modulo} onChange={(e) => setModulo(e.target.value)} className="mt-1 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-2 dark:border-slate-600 dark:bg-slate-800">
            <option value="todos">Todos los módulos ({QUESTIONS.length})</option>
            {QUIZ_MODULES.map((m) => <option key={m.id} value={m.id}>{m.orden}. {m.titulo} ({m.preguntas.length})</option>)}
          </select>
        </label>
        <label className="block text-sm">
          Preguntas del examen
          <select value={n} onChange={(e) => setN(Number(e.target.value))} className="mt-1 min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-2 dark:border-slate-600 dark:bg-slate-800">
            {[10, 20, 40].map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        </label>
        <div className="grid grid-cols-2 gap-2">
          <button className="btn" onClick={() => go('estudio')}>Modo estudio</button>
          <button className="btn bg-slate-700" onClick={() => go('examen')}>Examen ({nExam} · {fmt(examSeconds(nExam))})</button>
        </div>
        <p className="text-xs text-slate-500">Estudio: feedback inmediato con explicación y referencia. Examen: cronometrado (1 minuto por pregunta) y sin ayuda; la corrección se ve al final.</p>
        {failed > 0 && <button className="min-h-[48px] w-full rounded-lg border border-slate-300 dark:border-slate-600" onClick={() => go('errores')}>Repasar errores ({failed})</button>}
      </section>

      <section className="card space-y-2" aria-labelledby="dom-h">
        <h3 id="dom-h" className="font-semibold">Dominio por módulo</h3>
        {QUIZ_MODULES.map((m) => {
          const ok = m.preguntas.filter((q) => stats[q.id]?.last).length;
          const pct = m.preguntas.length ? Math.round((ok / m.preguntas.length) * 100) : 0;
          return (
            <div key={m.id}>
              <div className="flex justify-between text-sm"><span>{m.orden}. {m.titulo}</span><span>{ok}/{m.preguntas.length}</span></div>
              <div className="h-2 rounded bg-slate-200 dark:bg-slate-700" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`Dominio ${m.titulo}`}><div className="h-2 rounded bg-brand" style={{ width: `${pct}%` }} /></div>
            </div>
          );
        })}
      </section>

      {history.length > 0 && (
        <section className="card" aria-labelledby="his-h">
          <h3 id="his-h" className="mb-1 font-semibold">Últimos exámenes</h3>
          <ul className="text-sm">
            {history.slice(0, 3).map((h) => (
              <li key={h.fecha}>{new Date(h.fecha).toLocaleDateString('es-ES')} · {h.modulo === 'todos' ? 'Todos' : h.modulo} · {h.correctas}/{h.total} ({Math.round((h.correctas / h.total) * 100)} %)</li>
            ))}
          </ul>
        </section>
      )}

      <p className="text-xs text-slate-500">Cada pregunta indica si está verificada con el manual del V60/V60 Plus, contrastada en una fuente secundaria o pendiente de revisión clínica.</p>
    </div>
  );
}
