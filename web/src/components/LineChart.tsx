import { useRef } from "react";

export interface LineSeries {
  name: string;
  color: string;
  x: number[];
  y: (number | null)[];
}

export interface Marker {
  x: number;
  label: string;
  color: string;
}

interface Props {
  title: string;
  unit?: string;
  series: LineSeries[];
  height?: number;
  cursor?: number | null;
  onCursor?: (x: number) => void;
  markers?: Marker[];
}

const W = 600;
const PAD = { l: 48, r: 10, t: 14, b: 22 };

/** Round tick values covering [min, max], about `count` of them. */
export function ticks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
  if (min === max) return [min];
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const out: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

/** SVG path for one series, broken wherever y is null (e.g. no lead vehicle). */
export function pathFor(x: number[], y: (number | null)[], sx: (v: number) => number, sy: (v: number) => number) {
  let d = "";
  let pen = false;
  for (let i = 0; i < x.length; i++) {
    const v = y[i];
    if (v === null || v === undefined || !Number.isFinite(v)) {
      pen = false;
      continue;
    }
    d += `${pen ? "L" : "M"}${sx(x[i]).toFixed(1)},${sy(v).toFixed(1)}`;
    pen = true;
  }
  return d;
}

export default function LineChart({ title, unit, series, height = 150, cursor, onCursor, markers = [] }: Props) {
  const ref = useRef<SVGSVGElement>(null);
  const xs = series.flatMap((s) => s.x);
  const ys = series.flatMap((s) => s.y).filter((v): v is number => v !== null && Number.isFinite(v));
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  let y0 = Math.min(...ys);
  let y1 = Math.max(...ys);
  if (y0 === y1) {
    y0 -= 1;
    y1 += 1;
  }
  const pad = 0.06 * (y1 - y0);
  y0 -= pad;
  y1 += pad;
  const sx = (v: number) => PAD.l + ((v - x0) / (x1 - x0 || 1)) * (W - PAD.l - PAD.r);
  const sy = (v: number) => height - PAD.b - ((v - y0) / (y1 - y0)) * (height - PAD.t - PAD.b);

  function move(e: React.MouseEvent<SVGSVGElement>) {
    if (!onCursor || !ref.current) return;
    const box = ref.current.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * W;
    const v = x0 + ((px - PAD.l) / (W - PAD.l - PAD.r)) * (x1 - x0);
    onCursor(Math.min(x1, Math.max(x0, v)));
  }

  if (ys.length === 0) {
    return (
      <div className="panel">
        <div className="muted">{title}: no data</div>
      </div>
    );
  }

  return (
    <div className="panel" style={{ padding: 10 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong style={{ fontSize: 13 }}>
          {title}
          {unit ? <span className="muted"> ({unit})</span> : null}
        </strong>
        <div className="legend">
          {series.map((s) => (
            <span key={s.name}>
              <i style={{ background: s.color }} />
              {s.name}
            </span>
          ))}
        </div>
      </div>
      <svg ref={ref} viewBox={`0 0 ${W} ${height}`} width="100%" role="img" aria-label={title} onMouseMove={move}
        style={{ cursor: onCursor ? "crosshair" : "default", display: "block" }}>
        {ticks(y0, y1, 4).map((t) => (
          <g key={`y${t}`}>
            <line x1={PAD.l} x2={W - PAD.r} y1={sy(t)} y2={sy(t)} stroke="var(--line)" />
            <text x={PAD.l - 6} y={sy(t) + 4} textAnchor="end" fontSize="10" fill="var(--muted)">
              {Math.abs(t) < 1e-9 ? 0 : t}
            </text>
          </g>
        ))}
        {ticks(x0, x1, 8).map((t) => (
          <text key={`x${t}`} x={sx(t)} y={height - 6} textAnchor="middle" fontSize="10" fill="var(--muted)">
            {t}s
          </text>
        ))}
        {markers.map((m, i) => (
          <g key={`m${i}`}>
            <line x1={sx(m.x)} x2={sx(m.x)} y1={PAD.t} y2={height - PAD.b} stroke={m.color} strokeDasharray="2 3"
              opacity={0.7} />
            <title>{m.label}</title>
          </g>
        ))}
        {series.map((s) => (
          <path key={s.name} d={pathFor(s.x, s.y, sx, sy)} fill="none" stroke={s.color} strokeWidth={1.6}
            data-series={s.name} />
        ))}
        {cursor !== null && cursor !== undefined && (
          <line x1={sx(cursor)} x2={sx(cursor)} y1={PAD.t} y2={height - PAD.b} stroke="var(--text)" opacity={0.5}
            data-testid="cursor" />
        )}
      </svg>
    </div>
  );
}
