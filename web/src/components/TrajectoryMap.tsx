import { useEffect, useRef, useState } from "react";

import type { ScenarioGeometry, Series } from "../api";
import { num } from "../format";
import { nearest } from "./Replay";

interface Props {
  geometry: ScenarioGeometry["geometry"];
  base: Series;
  cand: Series;
  cursor: number | null;
  onCursor: (t: number) => void;
}

type Pt = [number, number];

export function bounds(sets: Pt[][]): { minX: number; minY: number; maxX: number; maxY: number } {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const s of sets) {
    for (const [x, y] of s) {
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }
  return { minX, minY, maxX, maxY };
}

function track(s: Series): Pt[] {
  const out: Pt[] = [];
  for (let i = 0; i < s.t.length; i++) {
    const x = s.x?.[i];
    const y = s.y?.[i];
    if (x !== null && x !== undefined && y !== null && y !== undefined) out.push([x, y]);
  }
  return out;
}

// world y points up, SVG y points down
const pts = (p: Pt[]) => p.map(([x, y]) => `${x.toFixed(2)},${(-y).toFixed(2)}`).join(" ");

function at(s: Series, t: number): Pt | null {
  const i = nearest(s.t, t);
  const x = s.x?.[i];
  const y = s.y?.[i];
  return x === null || x === undefined || y === null || y === undefined ? null : [x, y];
}

function Ego({ s, t, color, scale }: { s: Series; t: number; color: string; scale: number }) {
  const i = nearest(s.t, t);
  const x = s.x?.[i];
  const y = s.y?.[i];
  const yaw = s.yaw?.[i] ?? 0;
  if (x === null || x === undefined || y === null || y === undefined) return null;
  const deg = (-yaw * 180) / Math.PI;
  return (
    <g transform={`translate(${x} ${-y}) rotate(${deg}) scale(${scale})`}>
      <rect x={-2.35} y={-0.95} width={4.7} height={1.9} rx={0.4} fill={color} stroke="var(--bg)" strokeWidth={0.2} />
    </g>
  );
}

export default function TrajectoryMap({ geometry, base, cand, cursor, onCursor }: Props) {
  const route = geometry.route as Pt[];
  const mapRoute = geometry.map_route as Pt[] | undefined;
  const bt = track(base);
  const ct = track(cand);
  const tEnd = Math.max(base.t[base.t.length - 1] ?? 0, cand.t[cand.t.length - 1] ?? 0);
  const t = cursor ?? 0;
  const [follow, setFollow] = useState(false);
  const centre = follow ? at(cand, t) ?? at(base, t) : null;

  let view: string;
  let carScale = 1;
  if (centre) {
    // 50 m window around the candidate: lateral differences of a few cm become visible
    view = `${centre[0] - 25} ${-centre[1] - 12.5} 50 25`;
  } else {
    const b = bounds([route, bt, ct]);
    const pad = 8;
    const w = b.maxX - b.minX + 2 * pad;
    view = `${b.minX - pad} ${-b.maxY - pad} ${w} ${b.maxY - b.minY + 2 * pad}`;
    carScale = Math.max(1, w / 120);
  }
  const line = centre ? 0.15 : 0.5 * carScale;

  const [playing, setPlaying] = useState(false);
  const last = useRef<number | null>(null);
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const step = (now: number) => {
      const dt = last.current === null ? 0 : (now - last.current) / 1000;
      last.current = now;
      const next = t + dt;
      if (next >= tEnd) {
        onCursor(tEnd);
        setPlaying(false);
        return;
      }
      onCursor(next);
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(raf);
      last.current = null;
    };
  }, [playing, t, tEnd, onCursor]);

  return (
    <div className="panel stack" style={{ gap: 8 }}>
      <div className="row" style={{ alignItems: "center", justifyContent: "space-between" }}>
        <strong style={{ fontSize: 13 }}>Trajectories</strong>
        <div className="legend">
          <span><i style={{ background: "var(--line)", height: 6 }} />lane</span>
          {mapRoute && <span><i style={{ background: "var(--warn)" }} />prior map</span>}
          <span><i style={{ background: "var(--baseline)" }} />baseline</span>
          <span><i style={{ background: "var(--candidate)" }} />candidate</span>
        </div>
      </div>
      <svg viewBox={view} width="100%" style={{ maxHeight: 360, background: "var(--panel-2)", borderRadius: 6 }}
        role="img" aria-label="trajectories">
        <polyline points={pts(route)} fill="none" stroke="var(--line)" strokeOpacity={0.9}
          strokeWidth={geometry.lane_width} strokeLinejoin="round" strokeLinecap="round" />
        <polyline points={pts(route)} fill="none" stroke="var(--muted)" strokeOpacity={0.5}
          strokeWidth={centre ? 0.05 : 0.2 * carScale} strokeDasharray={centre ? "1 1" : undefined} />
        {mapRoute && (
          <polyline points={pts(mapRoute)} fill="none" stroke="var(--warn)" strokeWidth={line}
            strokeDasharray="2 2" />
        )}
        <polyline points={pts(bt)} fill="none" stroke="var(--baseline)" strokeWidth={line}
          data-testid="track-baseline" />
        <polyline points={pts(ct)} fill="none" stroke="var(--candidate)" strokeWidth={line}
          data-testid="track-candidate" />
        {cursor !== null && (
          <>
            <Ego s={base} t={t} color="var(--baseline)" scale={carScale} />
            <Ego s={cand} t={t} color="var(--candidate)" scale={carScale} />
          </>
        )}
      </svg>
      <div className="row" style={{ alignItems: "center" }}>
        <button onClick={() => { if (t >= tEnd) onCursor(0); setPlaying((p) => !p); }} aria-label="play">
          {playing ? "Pause" : "Play"}
        </button>
        <label className="muted" style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
          follow (50 m)
        </label>
        <input type="range" min={0} max={tEnd} step={0.1} value={t} style={{ flex: 1 }} aria-label="time"
          onChange={(e) => { setPlaying(false); onCursor(Number(e.target.value)); }} />
        <span className="mono muted" style={{ width: 90, textAlign: "right" }}>
          {num(t, 1)} / {num(tEnd, 1)} s
        </span>
      </div>
    </div>
  );
}
