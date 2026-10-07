import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { MODULES, searchContent } from '../content/loader';
import { useApp } from '../store/useApp';

export default function Search() {
  const [q, setQ] = useState('');
  const favorites = useApp((s) => s.favorites);
  const hits = useMemo(() => searchContent(q), [q]);
  const favClaims = useMemo(
    () =>
      MODULES.flatMap((m) =>
        m.secciones.flatMap((s) => s.afirmaciones.filter((c) => favorites.includes(c.id)).map((c) => ({ m, c }))),
      ),
    [favorites],
  );

  return (
    <div className="space-y-4">
      <input
        type="search"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Buscar en todo el contenido…"
        aria-label="Búsqueda global"
        className="min-h-[48px] w-full rounded-lg border border-slate-300 bg-white px-3 dark:border-slate-600 dark:bg-slate-800"
      />
      {q.trim().length >= 2 && (
        <ul className="space-y-2" aria-live="polite">
          {hits.length === 0 && <li className="text-slate-500">Sin resultados.</li>}
          {hits.map((h) => (
            <li key={h.claimId} className="card">
              <Link to={`/aprender/${h.moduleId}`} className="text-xs text-brand underline dark:text-brand-light">
                {h.moduleTitle} · {h.sectionTitle}
              </Link>
              <p>{h.texto}</p>
            </li>
          ))}
        </ul>
      )}
      <h2 className="font-bold">Favoritos</h2>
      {favClaims.length === 0 && <p className="text-sm text-slate-500">Marca ★ en cualquier afirmación para guardarla aquí.</p>}
      <ul className="space-y-2">
        {favClaims.map(({ m, c }) => (
          <li key={c.id} className="card">
            <Link to={`/aprender/${m.id}`} className="text-xs text-brand underline dark:text-brand-light">{m.titulo}</Link>
            <p>{c.texto}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
