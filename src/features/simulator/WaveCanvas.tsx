import { useEffect, useRef } from 'react';
import type { VentSim } from '../../engine/sim';
import type { Sample } from '../../engine/types';

interface Trace {
  key: keyof Pick<Sample, 'paw' | 'flow' | 'vol'>;
  label: string;
  unit: string;
  color: string;
  min: number;
  max: number;
}

interface Props {
  sim: VentSim;
  seconds: number;
  frozen: boolean;
}

export default function WaveCanvas({ sim, seconds, frozen }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  const frozenBuffer = useRef<Sample[] | null>(null);

  useEffect(() => {
    frozenBuffer.current = frozen ? [...sim.buffer] : null;
  }, [frozen, sim]);

  useEffect(() => {
    let raf = 0;
    const draw = () => {
      const canvas = ref.current;
      if (canvas) {
        const dpr = window.devicePixelRatio || 1;
        const w = canvas.clientWidth;
        const h = canvas.clientHeight;
        if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
          canvas.width = Math.round(w * dpr);
          canvas.height = Math.round(h * dpr);
        }
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
          paint(ctx, w, h, frozenBuffer.current ?? sim.buffer, seconds);
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [sim, seconds]);

  return (
    <canvas
      ref={ref}
      role="img"
      aria-label="Curvas simuladas de presión, flujo y volumen en tiempo real"
      className="h-72 w-full rounded-lg bg-slate-950"
    />
  );
}

function paint(ctx: CanvasRenderingContext2D, w: number, h: number, buf: Sample[], seconds: number) {
  ctx.clearRect(0, 0, w, h);
  const peak = (k: 'flow' | 'vol') => buf.reduce((m, s) => Math.max(m, Math.abs(s[k])), 0);
  const flowMax = Math.max(40, Math.ceil(peak('flow') / 20) * 20);
  const volMax = Math.max(400, Math.ceil(peak('vol') / 100) * 100);
  const traces: Trace[] = [
    { key: 'paw', label: 'Presión', unit: 'cmH2O', color: '#facc15', min: 0, max: Math.max(30, Math.ceil(buf.reduce((m, s) => Math.max(m, s.paw), 0) / 5) * 5) },
    { key: 'flow', label: 'Flujo', unit: 'L/min', color: '#4ade80', min: -flowMax, max: flowMax },
    { key: 'vol', label: 'Volumen', unit: 'ml', color: '#38bdf8', min: 0, max: volMax },
  ];
  const rowH = h / traces.length;
  const tEnd = buf.length ? buf[buf.length - 1].t : 0;
  const tStart = tEnd - seconds;

  traces.forEach((tr, i) => {
    const top = i * rowH + 4;
    const bottom = (i + 1) * rowH - 4;
    const y = (v: number) => bottom - ((v - tr.min) / (tr.max - tr.min)) * (bottom - top);
    // rejilla y cero
    ctx.strokeStyle = 'rgba(148,163,184,0.25)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, y(0 >= tr.min ? 0 : tr.min));
    ctx.lineTo(w, y(0 >= tr.min ? 0 : tr.min));
    ctx.stroke();
    // curva
    ctx.strokeStyle = tr.color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    let started = false;
    for (const s of buf) {
      if (s.t < tStart) continue;
      const x = ((s.t - tStart) / seconds) * w;
      const yy = y(s[tr.key]);
      if (!started) {
        ctx.moveTo(x, yy);
        started = true;
      } else ctx.lineTo(x, yy);
    }
    ctx.stroke();
    // etiqueta
    ctx.fillStyle = tr.color;
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillText(`${tr.label} (${tr.unit})  ${tr.min}…${tr.max}`, 6, top + 12);
  });
}
