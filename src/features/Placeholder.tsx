export default function Placeholder({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="card">
      <h2 className="text-xl font-bold">{title}</h2>
      <p className="mt-2 text-slate-600 dark:text-slate-300">Disponible en la fase {phase} del desarrollo.</p>
    </div>
  );
}
