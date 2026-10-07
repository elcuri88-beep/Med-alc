import { Link } from 'react-router-dom';
import { MODULES } from '../content/loader';
import { useApp } from '../store/useApp';

export default function Learn() {
  const readClaims = useApp((s) => s.readClaims);
  const favorites = useApp((s) => s.favorites);
  return (
    <div className="space-y-3">
      <h2 className="text-xl font-bold">Módulos</h2>
      {MODULES.map((m) => {
        const ids = m.secciones.flatMap((s) => s.afirmaciones.map((c) => c.id));
        const done = ids.filter((id) => readClaims.includes(id)).length;
        const pct = ids.length ? Math.round((done / ids.length) * 100) : 0;
        return (
          <Link key={m.id} to={`/aprender/${m.id}`} className="card block min-h-[64px]">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{m.orden}. {m.titulo}</span>
              <span className="text-sm text-slate-500">{pct}%</span>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-300">{m.resumen}</p>
            <div className="mt-2 h-2 rounded bg-slate-200 dark:bg-slate-700" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`Progreso ${m.titulo}`}>
              <div className="h-2 rounded bg-brand" style={{ width: `${pct}%` }} />
            </div>
          </Link>
        );
      })}
      {favorites.length > 0 && <p className="text-sm text-slate-500">Favoritos guardados: {favorites.length}</p>}
    </div>
  );
}
