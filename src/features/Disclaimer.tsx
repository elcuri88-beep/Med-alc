import { MODEL_META } from '../content/loader';
import { useApp } from '../store/useApp';

export default function Disclaimer() {
  const accept = useApp((s) => s.acceptDisclaimer);
  return (
    <div className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-bold text-brand dark:text-brand-light">V60 Academy</h1>
      <p className="text-sm text-slate-500">Aprendizaje de VMNI con el Philips Respironics BiPAP V60</p>
      <div role="alert" className="card border-alarm-medium">
        <h2 className="mb-2 font-bold">Aviso importante</h2>
        <p>{MODEL_META.disclaimer}</p>
        <p className="mt-2 text-sm">{MODEL_META.privacy}</p>
        <p className="mt-2 text-sm font-semibold">Estado del contenido: {MODEL_META.reviewStatus}</p>
      </div>
      <button className="btn" onClick={accept}>Entiendo y acepto</button>
    </div>
  );
}
