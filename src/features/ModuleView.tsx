import { Link, useParams } from 'react-router-dom';
import { moduleById, sourceById } from '../content/loader';
import { useApp } from '../store/useApp';

export default function ModuleView() {
  const { moduleId } = useParams();
  const mod = moduleId ? moduleById(moduleId) : undefined;
  const { favorites, toggleFavorite, readClaims, markRead } = useApp();

  if (!mod) return <p>Módulo no encontrado. <Link to="/aprender" className="underline">Volver</Link></p>;

  const allIds = mod.secciones.flatMap((s) => s.afirmaciones.map((c) => c.id));

  return (
    <div className="space-y-4">
      <Link to="/aprender" className="inline-block min-h-[48px] py-3 text-sm underline">← Módulos</Link>
      <h2 className="text-xl font-bold">{mod.titulo}</h2>
      {mod.secciones.map((s) => (
        <section key={s.id} id={s.id} className="card space-y-3">
          <h3 className="font-semibold">{s.titulo}</h3>
          {s.afirmaciones.map((c) => (
            <article key={c.id} id={c.id} className="space-y-1 border-t border-slate-100 pt-2 first:border-0 first:pt-0 dark:border-slate-700">
              <p>{c.texto}</p>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                {c.pendienteRevision && (
                  <span className="rounded bg-alarm-medium/20 px-2 py-0.5 font-semibold text-amber-700 dark:text-amber-300">Pendiente de revisión</span>
                )}
                {c.fuentes.map((f) => (
                  <span key={f} className="rounded bg-slate-100 px-2 py-0.5 dark:bg-slate-700" title={sourceById(f)?.titulo}>{f}</span>
                ))}
                <button
                  className="ml-auto h-12 min-w-[48px] text-xl"
                  aria-pressed={favorites.includes(c.id)}
                  aria-label={favorites.includes(c.id) ? 'Quitar de favoritos' : 'Añadir a favoritos'}
                  onClick={() => toggleFavorite(c.id)}
                >
                  {favorites.includes(c.id) ? '★' : '☆'}
                </button>
              </div>
              {c.notas && <p className="text-xs italic text-slate-500">Nota para el revisor: {c.notas}</p>}
            </article>
          ))}
        </section>
      ))}
      <button
        className="btn w-full"
        disabled={allIds.every((id) => readClaims.includes(id))}
        onClick={() => markRead(allIds)}
      >
        {allIds.every((id) => readClaims.includes(id)) ? 'Módulo completado ✓' : 'Marcar módulo como leído'}
      </button>
    </div>
  );
}
