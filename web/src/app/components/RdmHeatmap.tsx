"use client";

import { useState } from "react";

interface RdmHeatmapProps {
    rdm: number[][];
    labels: string[];
    size?: number;
    paradigm?: "setcover" | "adaptive" | "pairwise";
    scaleMode?: "auto" | "absolute01" | "minmax";
    language?: "en" | "tr";
}

export default function RdmHeatmap({
    rdm,
    labels,
    size = 400,
    paradigm,
    scaleMode = "auto",
    language = "en",
}: RdmHeatmapProps) {
    const n = rdm.length;
    if (n === 0) return null;

    const labelWidth = 30;
    const [hoveredCell, setHoveredCell] = useState<{
        i: number;
        j: number;
        scaled01: number;
    } | null>(null);

    // Dynamic sizing based on stimulus count
    // Few stimuli: larger cells, many stimuli: smaller cells
    let targetSize: number;
    if (n <= 5) {
        targetSize = 350; // Large cells for very few items
    } else if (n <= 10) {
        targetSize = 400;
    } else if (n <= 20) {
        targetSize = 450;
    } else if (n <= 40) {
        targetSize = 500;
    } else {
        targetSize = 600; // Cap for very large matrices
    }

    const cellSize = Math.max(8, Math.min(50, Math.floor((targetSize - labelWidth) / n)));
    const gridSize = cellSize * n;


    const effectiveScaleMode = scaleMode === "auto" ? "minmax" : scaleMode;

    let minVal = 0;
    let maxVal = 1;
    if (effectiveScaleMode === "minmax") {
        const values: number[] = [];
        for (let i = 0; i < n; i += 1) {
            for (let j = 0; j < n; j += 1) {
                const v = rdm[i]?.[j];
                if (Number.isFinite(v)) values.push(v);
            }
        }
        if (values.length === 0) {
            minVal = 0;
            maxVal = 1;
        } else {
            values.sort((a, b) => a - b);
            minVal = values[0];
            maxVal = values[values.length - 1];
            if (!Number.isFinite(minVal) || !Number.isFinite(maxVal)) {
                minVal = 0;
                maxVal = 1;
            }
        }
    }

    const normalizeForColor = (value: number): number => {
        if (!Number.isFinite(value)) return 0.5;
        if (effectiveScaleMode === "absolute01") {
            return Math.max(0, Math.min(1, value));
        }
        if (maxVal <= minVal + 1e-12) return 0.5;
        const scaled = (value - minVal) / (maxVal - minVal);
        return Math.max(0, Math.min(1, scaled));
    };

    // Cold-Hot colormap: 0 (min/similar) = deep blue, 1 (max/different) = deep red
    const getColor = (value: number): string => {
        const v = Math.max(0, Math.min(1, value));
        // Cold (blue) -> Warm (white) -> Hot (red)
        if (v <= 0.5) {
            const t = v * 2;
            const r = Math.round(20 + t * 235);
            const g = Math.round(60 + t * 195);
            const b = Math.round(180 + t * 75);
            return `rgb(${r}, ${g}, ${b})`;
        } else {
            const t = (v - 0.5) * 2;
            const r = Math.round(255);
            const g = Math.round(255 - t * 200);
            const b = Math.round(255 - t * 230);
            return `rgb(${r}, ${g}, ${b})`;
        }
    };

    return (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#fff" }}>
                {language === "tr" ? "Benzerliksizlik Matrisi (RDM)" : "Dissimilarity Matrix (RDM)"}
            </h3>

            {/* Main container with row labels and grid */}
            <div style={{ display: "flex", gap: 4 }}>
                {/* Row labels (left side) */}
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "flex-start",
                        gap: 1,
                        paddingTop: labelWidth + 4,
                    }}
                >
                    {Array.from({ length: n }, (_, i) => (
                        <div
                            key={i}
                            style={{
                                height: cellSize - 1,
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "flex-end",
                                fontSize: 10,
                                color: "#888",
                                paddingRight: 4,
                                fontFamily: "monospace",
                            }}
                        >
                            {i + 1}
                        </div>
                    ))}
                </div>

                {/* Grid with column labels */}
                <div>
                    {/* Column labels (top) */}
                    <div
                        style={{
                            display: "grid",
                            gridTemplateColumns: `repeat(${n}, ${cellSize}px)`,
                            gap: 1,
                            marginBottom: 4,
                        }}
                    >
                        {Array.from({ length: n }, (_, j) => (
                            <div
                                key={j}
                                style={{
                                    height: labelWidth,
                                    display: "flex",
                                    alignItems: "flex-end",
                                    justifyContent: "center",
                                    fontSize: 10,
                                    color: "#888",
                                    fontFamily: "monospace",
                                }}
                            >
                                {j + 1}
                            </div>
                        ))}
                    </div>

                    {/* Heatmap grid */}
                    <div
                        style={{
                            display: "grid",
                            gridTemplateColumns: `repeat(${n}, ${cellSize}px)`,
                            gap: 1,
                            background: "#333",
                            padding: 1,
                            borderRadius: 4,
                            position: "relative",
                            userSelect: "none",
                        }}
                    >
                        {rdm.map((row, i) =>
                            row.map((value, j) => (
                                <div
                                    key={`${i}-${j}`}
                                    style={{
                                        width: cellSize - 1,
                                        height: cellSize - 1,
                                        background: i === j ? getColor(0) : getColor(normalizeForColor(value)),
                                    }}
                                    onMouseEnter={() => {
                                        const scaled01 = normalizeForColor(value);
                                        setHoveredCell({ i, j, scaled01 });
                                    }}
                                    onMouseLeave={() => setHoveredCell(null)}
                                    onMouseDown={(e) => e.preventDefault()}
                                />
                            ))
                        )}
                        {hoveredCell && (
                            <div
                                style={{
                                    position: "absolute",
                                    left: hoveredCell.j * cellSize + (cellSize - 1) / 2,
                                    top: hoveredCell.i * cellSize + (cellSize - 1) / 2,
                                    transform: "translate(-50%, -120%)",
                                    background: "#111",
                                    color: "#fff",
                                    border: "1px solid #333",
                                    borderRadius: 4,
                                    padding: "4px 6px",
                                    fontSize: 11,
                                    pointerEvents: "none",
                                    whiteSpace: "nowrap",
                                }}
                            >
                                Scaled: {(hoveredCell.scaled01 * 100).toFixed(1)}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* Color legend - cold to hot */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#888" }}>
                <span>0</span>
                <div
                    style={{
                        width: 120,
                        height: 14,
                        background: "linear-gradient(to right, rgb(20, 60, 180), rgb(255, 255, 255), rgb(255, 55, 25))",
                        borderRadius: 3,
                        border: "1px solid #444",
                    }}
                />
                <span>100</span>
            </div>

            {/* Label legend */}
            {labels.length <= 15 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 4, maxWidth: gridSize + labelWidth, justifyContent: "center" }}>
                    {labels.map((label, i) => (
                        <span
                            key={i}
                            style={{
                                fontSize: 10,
                                color: "#666",
                                padding: "2px 6px",
                                background: "#1a1a1a",
                                borderRadius: 3,
                                fontFamily: "monospace",
                            }}
                        >
                            {i + 1}: {label.length > 12 ? label.slice(0, 12) + "…" : label}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}
