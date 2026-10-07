import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useApp } from '../../store/useApp';
import { QUESTIONS } from './data';
import { examSeconds, grade, pickQuestions, type PreparedQuestion } from './logic';

type Modo = 'estudio' | 'examen' | 'errores';

const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

function Badge({ q }: { q: PreparedQuestion }) {
  if (q.pendienteRevision) return <span className="rounded bg-alarm-medium/20 px-2 py-0.5 text-xs font-semibold text-amber-700 dark:text-amber-300">Pendiente de revisión</span>;
  return <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200">{q.verificacion === 'directa' ? 'Verificada en el manual' : 'Contrastada en fuente secundaria'}</span>;
}

export default function QuizSession() {
  const [params] = useSearchParams();
  const modo = (params.get('modo') as Modo) ?? 'estudio';
  const modulo = params.get('modulo') ?? 'todos';
  const n = Number(params.get('n')) || undefined;
  const { quizStats, recordAnswers, addExam } = useApp();

  const [seed] = useState(() => Date.now() % 1_000_000);
  const questions = useMemo(() => {
    if (modo === 'errores') {
      const ids = Object.entries(quizStats).filter(([, v]) => !v.last).map(([k]) => k);
      return pickQuestions(QUESTIONS, { seed, ids });
    }
    return pickQuestions(QUESTIONS, { modulo, count: n, seed });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modo, modulo, n, seed]);

  const [i, setI] = useState(0);
  const [answers, setAnswers] = useState<(number | null)[]>(() => questions.map(() => null));
  const [revealed, setRevealed] = useState(false);
  const [finished, setFinished] = useState(false);
  const total = examSeconds(questions.length);
  const [left, setLeft] = useState(total);
  const startedAt = useRef(Date.now());
  const saved = useRef(false);

  // Cronómetro del examen
  useEffect(() => {
    if (modo !== 'examen' || finished) return;
    const t = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt.current) / 1000);
      const remaining = Math.max(0, total - elapsed);
      setLeft(remaining);
      if (remaining === 0) setFinished(true);
    }, 500);
    return () => clearInterval(t);
  }, [modo, finished, total]);

  const g = grade(questions, answers);

  useEffect(() => {
    if (!finished || saved.current) return;
    saved.current = true;
    const answered = questions.map((q, k) => ({ id: q.id, ok: answers[k] === q.correcta, answered: answers[k] !== null }));
    recordAnswers(answered.filter((a) => a.answered || modo === 'examen').map(({ id, ok }) => ({ id, ok })));
    if (modo === 'examen') addExam({ fecha: new Date().toISOString(), modulo, correctas: g.correctas, total: g.total, segundos: Math.floor((Date.now() - startedAt.current) / 1000) });
  }, [finished]); // eslint-disable-line react-hooks/exhaustive-deps

  if (questions.length === 0) {
    return (
      <div className="space-y-3">
        <p className="card">{modo === 'errores' ? 'No tienes preguntas falladas pendientes. ¡Buen trabajo!' : 'No hay preguntas para esta selección.'}</p>
        <Link to="/quiz" className="btn">Volver</Link>
      </div>
    );
  }

  if (finished) {
    const failed = questions.filter((q, k) => answers[k] !== q.correcta);
    return (
      <div className="space-y-4" aria-live="polite">
        <h2 className="text-xl font-bold">Resultado {modo === 'examen' ? 'del examen' : ''}</h2>
        <div className="card text-center">
          <div className="text-4xl font-bold">{g.correctas}/{g.total}</div>
          <div className="text-slate-500">{g.porcentaje} % de aciertos{g.sinResponder ? ` · ${g.sinResponder} sin responder` : ''}</div>
          {modo === 'examen' && <div className="text-sm text-slate-500">Tiempo: {fmt(Math.min(total, Math.floor((Date.now() - startedAt.current) / 1000)))} de {fmt(total)}</div>}
        </div>
        {failed.length > 0 && <h3 className="font-semibold">Repaso de errores ({failed.length})</h3>}
        {failed.map((q) => {
          const k = questions.indexOf(q);
          return (
            <article key={q.id} className="card space-y-2">
              <p className="font-medium">{q.enunciado}</p>
              <p className="text-sm text-red-700 dark:text-red-300">Tu respuesta: {answers[k] === null ? 'sin responder' : q.opciones[answers[k]!]}</p>
              <p className="text-sm text-emerald-700 dark:text-emerald-300">Correcta: {q.opciones[q.correcta]}</p>
              <p className="text-sm">{q.explicacion}</p>
              <p className="text-xs text-slate-500">Referencia: {q.referencia}</p>
              <Badge q={q} />
            </article>
          );
        })}
        <div className="flex gap-2">
          <Link to="/quiz" className="btn flex-1">Volver a Practicar</Link>
        </div>
        <footer className="border-t border-slate-200 pt-3 text-xs text-slate-500 dark:border-slate-700">Herramienta educativa. No sustituye el manual del fabricante, la formación oficial ni el criterio clínico.</footer>
      </div>
    );
  }

  const q = questions[i];
  const chosen = answers[i];
  const choose = (idx: number) => {
    if (modo === 'examen') setAnswers((a) => a.map((v, k) => (k === i ? idx : v)));
    else if (!revealed) {
      setAnswers((a) => a.map((v, k) => (k === i ? idx : v)));
      setRevealed(true);
    }
  };
  const next = () => {
    setRevealed(false);
    if (i + 1 >= questions.length) setFinished(true);
    else setI(i + 1);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Link to="/quiz" className="min-h-[48px] py-3 text-sm underline">← Salir</Link>
        <span className="text-sm text-slate-500">{modo === 'examen' ? 'Examen' : modo === 'errores' ? 'Repaso de errores' : 'Estudio'} · {i + 1}/{questions.length}</span>
        {modo === 'examen' && <span role="timer" aria-label={`Tiempo restante ${fmt(left)}`} className={`font-mono text-lg font-bold ${left < 60 ? 'text-alarm-high' : ''}`}>{fmt(left)}</span>}
      </div>
      <div className="h-2 rounded bg-slate-200 dark:bg-slate-700" role="progressbar" aria-valuenow={i + 1} aria-valuemin={1} aria-valuemax={questions.length} aria-label="Progreso del cuestionario">
        <div className="h-2 rounded bg-brand" style={{ width: `${((i + 1) / questions.length) * 100}%` }} />
      </div>

      <h2 className="text-lg font-semibold">{q.enunciado}</h2>
      <div role="radiogroup" aria-label="Respuestas" className="space-y-2">
        {q.opciones.map((o, idx) => {
          const sel = chosen === idx;
          const show = modo !== 'examen' && revealed;
          const cls = show ? (idx === q.correcta ? 'border-emerald-600 bg-emerald-50 dark:bg-emerald-950' : sel ? 'border-alarm-high bg-red-50 dark:bg-red-950' : 'border-slate-300 dark:border-slate-600') : sel ? 'border-brand bg-blue-50 dark:bg-slate-700' : 'border-slate-300 bg-white dark:border-slate-600 dark:bg-slate-800';
          return (
            <button key={idx} role="radio" aria-checked={sel} onClick={() => choose(idx)} className={`min-h-[56px] w-full rounded-lg border p-3 text-left ${cls}`}>
              <span className="mr-2 font-bold">{String.fromCharCode(65 + idx)}.</span>{o}
              {show && idx === q.correcta && <span className="ml-2" aria-label="respuesta correcta">✓</span>}
              {show && sel && idx !== q.correcta && <span className="ml-2" aria-label="respuesta incorrecta">✗</span>}
            </button>
          );
        })}
      </div>

      {modo !== 'examen' && revealed && (
        <div className="card space-y-2" aria-live="polite">
          <p className="font-semibold">{chosen === q.correcta ? '✓ Correcto' : '✗ Incorrecto'}</p>
          <p className="text-sm">{q.explicacion}</p>
          <p className="text-xs text-slate-500">Referencia: {q.referencia}</p>
          <Badge q={q} />
        </div>
      )}

      <div className="flex gap-2">
        {modo === 'examen' && <button className="min-h-[48px] flex-1 rounded-lg border border-slate-300 dark:border-slate-600" disabled={i === 0} onClick={() => setI(i - 1)}>Anterior</button>}
        {modo === 'examen' ? (
          i + 1 < questions.length ? <button className="btn flex-1" onClick={() => setI(i + 1)}>Siguiente</button> : <button className="btn flex-1" onClick={() => setFinished(true)}>Entregar examen</button>
        ) : (
          <button className="btn flex-1" disabled={!revealed} onClick={next}>{i + 1 >= questions.length ? 'Ver resultado' : 'Siguiente'}</button>
        )}
      </div>
      {modo === 'examen' && i + 1 < questions.length && <button className="min-h-[48px] w-full text-sm underline" onClick={() => setFinished(true)}>Entregar ahora ({answers.filter((a) => a !== null).length}/{questions.length} respondidas)</button>}
      <footer className="border-t border-slate-200 pt-3 text-xs text-slate-500 dark:border-slate-700">Herramienta educativa. No sustituye el manual del fabricante, la formación oficial ni el criterio clínico.</footer>
    </div>
  );
}
