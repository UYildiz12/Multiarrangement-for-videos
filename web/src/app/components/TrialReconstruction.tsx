"use client";

export interface TrialDetail {
  id: string;
  trial_index: number;
  subset_indices: number[];
  positions?: Record<string, [number, number] | { x: number; y: number }> | null;
  rating?: number | null;
  duration_seconds?: number | null;
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

function buildSvgPoints(trial: TrialDetail) {
  const points = trial.subset_indices
    .map((ordinal) => {
      const point = readPoint(trial.positions?.[String(ordinal)]);
      return point ? { ordinal, x: point[0], y: point[1] } : null;
    })
    .filter(Boolean) as { ordinal: number; x: number; y: number }[];

  if (points.length === 0) return [];

  const width = 220;
  const height = 180;
  const pad = 22;
  const minX = Math.min(...points.map((point) => point.x));
  const maxX = Math.max(...points.map((point) => point.x));
  const minY = Math.min(...points.map((point) => point.y));
  const maxY = Math.max(...points.map((point) => point.y));
  const rangeX = Math.max(1, maxX - minX);
  const rangeY = Math.max(1, maxY - minY);

  return points.map((point) => ({
    ...point,
    sx: pad + ((point.x - minX) / rangeX) * (width - pad * 2),
    sy: pad + ((point.y - minY) / rangeY) * (height - pad * 2),
  }));
}

export default function TrialReconstruction({ trials, stimuli }: TrialReconstructionProps) {
  if (trials.length === 0) {
    return <div style={{ color: "#666", fontSize: 12 }}>No submitted trials yet.</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {trials.map((trial) => {
        const svgPoints = buildSvgPoints(trial);
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
                  viewBox="0 0 220 180"
                  style={{
                    width: 220,
                    height: 180,
                    background: "radial-gradient(circle at 50% 50%, #111 0%, #050505 72%)",
                    border: "1px solid #222",
                    borderRadius: 10,
                  }}
                >
                  <circle cx="110" cy="90" r="74" fill="none" stroke="#333" strokeWidth="1.5" />
                  {svgPoints.map((point) => (
                    <g key={point.ordinal}>
                      <circle cx={point.sx} cy={point.sy} r="10" fill="#00ff88" fillOpacity="0.18" stroke="#00ff88" />
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
