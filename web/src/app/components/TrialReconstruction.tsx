"use client";

import { useEffect, useMemo, useRef, useState } from "react";

export interface MovementTrace {
  version: number;
  /** rows: [t_ms, ordinal, x, y, phase] with phase 0=pickup 1=move 2=drop */
  samples: number[][];
}

export interface TrialDetail {
  id: string;
  trial_index: number;
  subset_indices: number[];
  positions?: Record<string, [number, number] | { x: number; y: number }> | null;
  rating?: number | null;
  duration_seconds?: number | null;
  arena_size?: number | null;
  movement_trace?: MovementTrace | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ReconstructionStimulus {
  ordinal: number;
  filename: string;
}

interface TrialReconstructionProps {
  trials: TrialDetail[];
  stimuli: ReconstructionStimulus[];
}

function formatSeconds(value?: number | null): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return `${value.toFixed(value % 1 === 0 ? 0 : 2)}s`;
}

function formatDate(value?: string | null): string {
  if (!value) return "n/a";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function stimulusLabel(stimuli: ReconstructionStimulus[], ordinal: number): string {
  return stimuli.find((stimulus) => stimulus.ordinal === ordinal)?.filename ?? `Stimulus ${ordinal + 1}`;
}

function readPoint(value: [number, number] | { x: number; y: number } | undefined): [number, number] | null {
  if (!value) return null;
  if (Array.isArray(value)) return [Number(value[0]), Number(value[1])];
  return [Number(value.x), Number(value.y)];
}

function formatPoint(value: [number, number] | null): string {
  if (!value) return "missing";
  return `${value[0].toFixed(2)}, ${value[1].toFixed(2)}`;
}

const SVG_WIDTH = 220;
const SVG_HEIGHT = 180;
const SVG_CENTER_X = SVG_WIDTH / 2;
const SVG_CENTER_Y = SVG_HEIGHT / 2;
const SVG_ARENA_RADIUS = 74;
const SOURCE_ARENA_PADDING = 20;
const MIN_SOURCE_ARENA_SIZE = 260;
const MAX_SOURCE_ARENA_SIZE = 760;
const INFERRED_ARENA_ROUNDING = 20;
const MAX_TRAIL_POINTS = 120;

const TOKEN_COLORS = [
  "#00ff88",
  "#ff8800",
  "#44aaff",
  "#ff44aa",
  "#ffee44",
  "#aa66ff",
  "#66ffee",
  "#ff5555",
  "#99cc33",
  "#ff99cc",
];

function inferArenaSize(points: { x: number; y: number }[], submittedArenaSize?: number | null): number {
  if (submittedArenaSize && Number.isFinite(submittedArenaSize) && submittedArenaSize > 0) {
    return submittedArenaSize;
  }
  if (points.length === 0) return 600;

  const maxCoordinate = Math.max(...points.flatMap((point) => [point.x, point.y]));
  const minCandidate = Math.max(MIN_SOURCE_ARENA_SIZE, Math.ceil(maxCoordinate));
  for (let size = minCandidate; size <= MAX_SOURCE_ARENA_SIZE; size += 1) {
    const center = size / 2;
    const radius = center - SOURCE_ARENA_PADDING;
    const containsAll = points.every((point) => {
      const dx = point.x - center;
      const dy = point.y - center;
      return Math.sqrt(dx * dx + dy * dy) <= radius + 2;
    });
    if (containsAll) {
      return Math.min(MAX_SOURCE_ARENA_SIZE, Math.ceil(size / INFERRED_ARENA_ROUNDING) * INFERRED_ARENA_ROUNDING);
    }
  }

  return Math.min(
    MAX_SOURCE_ARENA_SIZE,
    Math.max(MIN_SOURCE_ARENA_SIZE, Math.ceil(maxCoordinate / INFERRED_ARENA_ROUNDING) * INFERRED_ARENA_ROUNDING)
  );
}

interface SvgTransform {
  arenaSize: number;
  toSvg: (x: number, y: number) => { sx: number; sy: number };
}

function buildSvgTransform(trial: TrialDetail): SvgTransform {
  const points = trial.subset_indices
    .map((ordinal) => {
      const point = readPoint(trial.positions?.[String(ordinal)]);
      return point ? { x: point[0], y: point[1] } : null;
    })
    .filter(Boolean) as { x: number; y: number }[];

  const arenaSize = inferArenaSize(points, trial.arena_size);
  const sourceCenter = arenaSize / 2;
  const sourceRadius = Math.max(1, sourceCenter - SOURCE_ARENA_PADDING);
  const scale = SVG_ARENA_RADIUS / sourceRadius;
  return {
    arenaSize,
    toSvg: (x: number, y: number) => ({
      sx: SVG_CENTER_X + (x - sourceCenter) * scale,
      sy: SVG_CENTER_Y + (y - sourceCenter) * scale,
    }),
  };
}

interface TraceTrack {
  ordinal: number;
  samples: { t: number; x: number; y: number }[];
}

function traceTracks(trace: MovementTrace | null | undefined): TraceTrack[] {
  if (!trace || !Array.isArray(trace.samples) || trace.samples.length === 0) return [];
  const byOrdinal = new Map<number, { t: number; x: number; y: number }[]>();
  for (const row of trace.samples) {
    if (!Array.isArray(row) || row.length < 5) continue;
    const [t, ordinal, x, y] = row;
    if (![t, ordinal, x, y].every((v) => Number.isFinite(Number(v)))) continue;
    const list = byOrdinal.get(Number(ordinal)) ?? [];
    list.push({ t: Number(t), x: Number(x), y: Number(y) });
    byOrdinal.set(Number(ordinal), list);
  }
  return Array.from(byOrdinal.entries())
    .map(([ordinal, samples]) => ({ ordinal, samples: samples.sort((a, b) => a.t - b.t) }))
    .sort((a, b) => a.ordinal - b.ordinal);
}

function downsample<T>(values: T[], maxCount: number): T[] {
  if (values.length <= maxCount) return values;
  const step = (values.length - 1) / (maxCount - 1);
  return Array.from({ length: maxCount }, (_, i) => values[Math.round(i * step)]);
}

function positionAt(track: TraceTrack, t: number): { x: number; y: number } {
  const samples = track.samples;
  if (t <= samples[0].t) return samples[0];
  const last = samples[samples.length - 1];
  if (t >= last.t) return last;
  let lo = 0;
  let hi = samples.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (samples[mid].t <= t) lo = mid;
    else hi = mid;
  }
  const a = samples[lo];
  const b = samples[hi];
  const span = b.t - a.t;
  const f = span > 0 ? (t - a.t) / span : 0;
  return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
}

function colorForSubsetIndex(index: number): string {
  return TOKEN_COLORS[index % TOKEN_COLORS.length];
}

function TrialCard({ trial, stimuli }: { trial: TrialDetail; stimuli: ReconstructionStimulus[] }) {
  const transform = useMemo(() => buildSvgTransform(trial), [trial]);
  const tracks = useMemo(() => traceTracks(trial.movement_trace), [trial.movement_trace]);
  const maxT = useMemo(
    () => tracks.reduce((acc, track) => Math.max(acc, track.samples[track.samples.length - 1]?.t ?? 0), 0),
    [tracks]
  );
  const hasTrace = tracks.length > 0 && maxT > 0;

  const [clockMs, setClockMs] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<1 | 4>(1);
  const frameRef = useRef<number | null>(null);
  const lastTickRef = useRef<number | null>(null);

  useEffect(() => {
    if (!playing) {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
      lastTickRef.current = null;
      return;
    }
    const tick = (now: number) => {
      const last = lastTickRef.current ?? now;
      lastTickRef.current = now;
      setClockMs((prev) => {
        const next = prev + (now - last) * speed;
        if (next >= maxT) {
          setPlaying(false);
          return maxT;
        }
        return next;
      });
      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
      lastTickRef.current = null;
    };
  }, [playing, speed, maxT]);

  const subsetColor = useMemo(() => {
    const map = new Map<number, string>();
    trial.subset_indices.forEach((ordinal, index) => map.set(ordinal, colorForSubsetIndex(index)));
    return map;
  }, [trial.subset_indices]);

  const finalPoints = trial.subset_indices
    .map((ordinal) => {
      const point = readPoint(trial.positions?.[String(ordinal)]);
      return point ? { ordinal, ...transform.toSvg(point[0], point[1]) } : null;
    })
    .filter(Boolean) as { ordinal: number; sx: number; sy: number }[];

  const replayActive = hasTrace && (playing || clockMs > 0);

  return (
    <section
      style={{
        border: "1px solid #242424",
        background: "#050505",
        borderRadius: 10,
        padding: 12,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginBottom: 10 }}>
        <div>
          <div style={{ color: "#fff", fontSize: 13, fontWeight: 700 }}>Trial {trial.trial_index + 1}</div>
          <div style={{ color: "#666", fontSize: 11 }}>
            Started {formatDate(trial.started_at)} | Completed {formatDate(trial.completed_at)}
          </div>
        </div>
        <div style={{ color: "#00ff88", fontSize: 13, fontWeight: 700 }}>
          {formatSeconds(trial.duration_seconds)}
        </div>
      </div>

      {trial.positions ? (
        <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: 14, alignItems: "start" }}>
          <div>
            <svg
              role="img"
              aria-label={`Trial ${trial.trial_index + 1} submitted arrangement`}
              viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
              data-arena-size={transform.arenaSize ?? undefined}
              style={{
                width: SVG_WIDTH,
                height: SVG_HEIGHT,
                background: "radial-gradient(circle at 50% 50%, #111 0%, #050505 72%)",
                border: "1px solid #222",
                borderRadius: 10,
              }}
            >
              <circle
                data-testid={`trial-${trial.trial_index}-arena-circle`}
                cx={SVG_CENTER_X}
                cy={SVG_CENTER_Y}
                r={SVG_ARENA_RADIUS}
                fill="none"
                stroke="#333"
                strokeWidth="1.5"
              />

              {/* Movement trails */}
              {tracks.map((track) => {
                const color = subsetColor.get(track.ordinal) ?? "#888";
                const pts = downsample(track.samples, MAX_TRAIL_POINTS)
                  .map((sample) => {
                    const { sx, sy } = transform.toSvg(sample.x, sample.y);
                    return `${sx.toFixed(1)},${sy.toFixed(1)}`;
                  })
                  .join(" ");
                return (
                  <polyline
                    key={`trail-${track.ordinal}`}
                    data-testid={`trial-${trial.trial_index}-trail-${track.ordinal}`}
                    points={pts}
                    fill="none"
                    stroke={color}
                    strokeWidth="1.4"
                    strokeOpacity="0.45"
                    strokeLinejoin="round"
                    strokeLinecap="round"
                  />
                );
              })}

              {/* Final submitted positions */}
              {finalPoints.map((point) => (
                <g key={point.ordinal} opacity={replayActive ? 0.35 : 1}>
                  <circle
                    data-testid={`trial-${trial.trial_index}-point-${point.ordinal}`}
                    cx={point.sx.toFixed(2)}
                    cy={point.sy.toFixed(2)}
                    r="10"
                    fill={subsetColor.get(point.ordinal) ?? "#00ff88"}
                    fillOpacity="0.18"
                    stroke={subsetColor.get(point.ordinal) ?? "#00ff88"}
                  />
                  <text x={point.sx} y={point.sy + 3} textAnchor="middle" fontSize="9" fill="#fff">
                    {point.ordinal + 1}
                  </text>
                </g>
              ))}

              {/* Replay tokens */}
              {replayActive &&
                tracks.map((track) => {
                  const pos = positionAt(track, clockMs);
                  const { sx, sy } = transform.toSvg(pos.x, pos.y);
                  const color = subsetColor.get(track.ordinal) ?? "#fff";
                  return (
                    <g key={`replay-${track.ordinal}`}>
                      <circle
                        data-testid={`trial-${trial.trial_index}-replay-${track.ordinal}`}
                        cx={sx.toFixed(2)}
                        cy={sy.toFixed(2)}
                        r="7"
                        fill={color}
                        fillOpacity="0.85"
                        stroke="#000"
                        strokeWidth="1"
                      />
                      <text x={sx} y={sy + 3} textAnchor="middle" fontSize="8" fill="#000" fontWeight={700}>
                        {track.ordinal + 1}
                      </text>
                    </g>
                  );
                })}
            </svg>

            {hasTrace && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  aria-label={playing ? "Pause replay" : "Play replay"}
                  onClick={() => {
                    if (!playing && clockMs >= maxT) setClockMs(0);
                    setPlaying((prev) => !prev);
                  }}
                  style={{
                    width: 30,
                    height: 24,
                    borderRadius: 5,
                    border: "1px solid #333",
                    background: "#111",
                    color: "#00ff88",
                    cursor: "pointer",
                    fontSize: 11,
                    lineHeight: 1,
                  }}
                >
                  {playing ? "❚❚" : "▶"}
                </button>
                <input
                  type="range"
                  aria-label="Replay position"
                  min={0}
                  max={Math.max(1, Math.ceil(maxT))}
                  value={Math.round(clockMs)}
                  onChange={(e) => {
                    setPlaying(false);
                    setClockMs(Number(e.target.value));
                  }}
                  style={{ flex: 1 }}
                />
                <button
                  type="button"
                  aria-label="Replay speed"
                  onClick={() => setSpeed((prev) => (prev === 1 ? 4 : 1))}
                  style={{
                    width: 32,
                    height: 24,
                    borderRadius: 5,
                    border: "1px solid #333",
                    background: "#111",
                    color: "#aaa",
                    cursor: "pointer",
                    fontSize: 10,
                  }}
                >
                  {speed}x
                </button>
                <span style={{ color: "#666", fontSize: 10, fontFamily: "monospace", minWidth: 52 }}>
                  {(clockMs / 1000).toFixed(1)}s/{(maxT / 1000).toFixed(1)}s
                </span>
              </div>
            )}
          </div>

          <div style={{ display: "grid", gap: 6 }}>
            {trial.subset_indices.map((ordinal) => {
              const point = readPoint(trial.positions?.[String(ordinal)]);
              return (
                <div
                  key={ordinal}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "26px minmax(0, 1fr) 112px",
                    gap: 8,
                    alignItems: "center",
                    fontSize: 11,
                    color: "#aaa",
                  }}
                >
                  <span style={{ color: subsetColor.get(ordinal) ?? "#00ff88", fontFamily: "monospace" }}>
                    {ordinal + 1}
                  </span>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {stimulusLabel(stimuli, ordinal)}
                  </span>
                  <span style={{ color: "#ddd", fontFamily: "monospace", textAlign: "right" }}>
                    {formatPoint(point)}
                  </span>
                </div>
              );
            })}
            {!hasTrace && (
              <div style={{ color: "#555", fontSize: 10, marginTop: 4 }}>
                No movement recording for this trial.
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{ color: "#aaa", fontSize: 12 }}>
          Pairwise rating: {trial.rating ?? "n/a"} for stimuli {trial.subset_indices.map((idx) => idx + 1).join(", ")}
        </div>
      )}
    </section>
  );
}

export default function TrialReconstruction({ trials, stimuli }: TrialReconstructionProps) {
  if (trials.length === 0) {
    return <div style={{ color: "#666", fontSize: 12 }}>No submitted trials yet.</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {trials.map((trial) => (
        <TrialCard key={trial.id} trial={trial} stimuli={stimuli} />
      ))}
    </div>
  );
}
