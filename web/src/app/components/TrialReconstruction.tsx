"use client";

export interface TrialDetail {
  id: string;
  trial_index: number;
  subset_indices: number[];
  positions?: Record<string, [number, number] | { x: number; y: number }> | null;
  rating?: number | null;
  duration_seconds?: number | null;
  arena_size?: number | null;
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

function buildSvgPoints(trial: TrialDetail) {
  const points = trial.subset_indices
    .map((ordinal) => {
      const point = readPoint(trial.positions?.[String(ordinal)]);
      return point ? { ordinal, x: point[0], y: point[1] } : null;
    })
    .filter(Boolean) as { ordinal: number; x: number; y: number }[];

  if (points.length === 0) return { points: [], arenaSize: trial.arena_size ?? null };

  const arenaSize = inferArenaSize(points, trial.arena_size);
  const sourceCenter = arenaSize / 2;
  const sourceRadius = Math.max(1, sourceCenter - SOURCE_ARENA_PADDING);
  const scale = SVG_ARENA_RADIUS / sourceRadius;

  return {
    arenaSize,
    points: points.map((point) => ({
      ...point,
      sx: SVG_CENTER_X + (point.x - sourceCenter) * scale,
      sy: SVG_CENTER_Y + (point.y - sourceCenter) * scale,
    })),
  };
}

export default function TrialReconstruction({ trials, stimuli }: TrialReconstructionProps) {
  if (trials.length === 0) {
    return <div style={{ color: "#666", fontSize: 12 }}>No submitted trials yet.</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {trials.map((trial) => {
        const svgReconstruction = buildSvgPoints(trial);
        return (
          <section
            key={trial.id}
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
                <svg
                  role="img"
                  aria-label={`Trial ${trial.trial_index + 1} submitted arrangement`}
                  viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
                  data-arena-size={svgReconstruction.arenaSize ?? undefined}
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
                  {svgReconstruction.points.map((point) => (
                    <g key={point.ordinal}>
                      <circle
                        data-testid={`trial-${trial.trial_index}-point-${point.ordinal}`}
                        cx={point.sx.toFixed(2)}
                        cy={point.sy.toFixed(2)}
                        r="10"
                        fill="#00ff88"
                        fillOpacity="0.18"
                        stroke="#00ff88"
                      />
                      <text x={point.sx} y={point.sy + 3} textAnchor="middle" fontSize="9" fill="#fff">
                        {point.ordinal + 1}
                      </text>
                    </g>
                  ))}
                </svg>

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
                        <span style={{ color: "#00ff88", fontFamily: "monospace" }}>{ordinal + 1}</span>
                        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {stimulusLabel(stimuli, ordinal)}
                        </span>
                        <span style={{ color: "#ddd", fontFamily: "monospace", textAlign: "right" }}>
                          {formatPoint(point)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : (
              <div style={{ color: "#aaa", fontSize: 12 }}>
                Pairwise rating: {trial.rating ?? "n/a"} for stimuli {trial.subset_indices.map((idx) => idx + 1).join(", ")}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
