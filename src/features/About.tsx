import { MODEL_META, MODULES, SOURCES } from '../content/loader';

export default function About() {
  const claims = MODULES.flatMap((m) => m.secciones.flatMap((s) => s.afirmaciones));
  const pending = claims.filter((c) => c.pendienteRevision).length;
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">Acerca de</h2>
      <div className="card space-y-1">
        <p><b>Versión del contenido:</b> {MODEL_META.contentVersion}</p>
        <p><b>Última revisión clínica:</b> {MODEL_META.lastReview ?? 'ninguna todavía'}</p>
        <p><b>Estado:</b> {MODEL_META.reviewStatus}</p>
        <p><b>Afirmaciones:</b> {claims.length} ({pending} pendientes de revisión)</p>
      </div>
      <div className="card"><h3 className="font-semibold">Aviso legal</h3><p>{MODEL_META.disclaimer}</p><p className="mt-2 text-sm">{MODEL_META.legal}</p></div>
      <div className="card"><h3 className="font-semibold">Privacidad</h3><p>{MODEL_META.privacy}</p></div>
      <div className="card">
        <h3 className="font-semibold">Fuentes</h3>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {SOURCES.map((s) => (
            <li key={s.id}><b>{s.id}</b>: {s.titulo}{s.nota ? ` (${s.nota})` : ''}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
