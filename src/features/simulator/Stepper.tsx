interface Props {
  label: string;
  unit: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  hint?: string;
  offAtMin?: boolean;
}

const round = (v: number, step: number) => Math.round(v / step) * step;

/** Control +/- con objetivos táctiles amplios (≥ 48 px). */
export default function Stepper({ label, unit, value, min, max, step, onChange, hint, offAtMin }: Props) {
  const set = (v: number) => onChange(Math.min(max, Math.max(min, Number(round(v, step).toFixed(2)))));
  const shown = offAtMin && value <= min ? 'OFF' : String(value);
  return (
    <div className="rounded-lg border border-slate-200 p-2 dark:border-slate-700" role="group" aria-label={label}>
      <div className="text-xs text-slate-500 dark:text-slate-400">
        {label} {unit && <span>({unit})</span>}
      </div>
      <div className="flex items-center justify-between gap-1">
        <button className="h-12 w-12 rounded-lg bg-slate-200 text-2xl font-bold active:bg-slate-300 disabled:opacity-40 dark:bg-slate-700" aria-label={`Disminuir ${label}`} disabled={value <= min} onClick={() => set(value - step)}>−</button>
        <output className="min-w-[3.5rem] text-center text-xl font-bold tabular-nums" aria-live="polite">{shown}</output>
        <button className="h-12 w-12 rounded-lg bg-slate-200 text-2xl font-bold active:bg-slate-300 disabled:opacity-40 dark:bg-slate-700" aria-label={`Aumentar ${label}`} disabled={value >= max} onClick={() => set(value + step)}>+</button>
      </div>
      <div className="text-[10px] text-slate-400">{min}–{max}{hint ? ` · ${hint}` : ''}</div>
    </div>
  );
}
