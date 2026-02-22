"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "../lib/api";

export default function DemoPage() {
    const router = useRouter();
    const [loadingLtW, setLoadingLtW] = useState(false);
    const [loadingSetcover, setLoadingSetcover] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const startDemo = async (paradigm: "adaptive" | "setcover") => {
        if (paradigm === "adaptive") setLoadingLtW(true);
        else setLoadingSetcover(true);
        setError(null);

        try {
            const res = await fetch("/api/videos");
            const data = await res.json();
            const allVideos: any[] = data.videos || [];
            const demoVideos = allVideos.slice(0, 16);

            const session = await apiFetch<any>(`/api/v1/public/demo/start`, {
                method: "POST",
                body: JSON.stringify({ paradigm, n_stimuli: 16 }),
            });

            // Build a lookup from filename → preset so we can match by name
            const presetByFilename: Record<string, any> = {};
            const presetByOrdinal: Record<number, any> = {};
            demoVideos.forEach((v, i) => {
                if (v.filename) presetByFilename[v.filename] = v;
                presetByOrdinal[i] = v;
            });

            // Reconcile server stimuli with frontend preset URLs
            const stimuliForClient = session.stimuli.map((s: any, i: number) => {
                // Try to match by filename first, then fall back to ordinal position
                const preset = presetByFilename[s.filename] || presetByOrdinal[i] || {};
                return {
                    id: s.id || `stim-${s.ordinal}`,
                    ordinal: s.ordinal,
                    label: preset.label || preset.filename || s.filename,
                    mediaUrl: preset.url || s.media_url || "",
                    mediaType: (preset.mediaType || s.media_type || "video") as "video" | "audio" | "image",
                    thumbnail: preset.thumbnail || s.thumbnail_url || undefined,
                };
            });

            sessionStorage.setItem("experimentStimuli", JSON.stringify(stimuliForClient));
            sessionStorage.setItem("experimentSessionId", session.session_id);
            sessionStorage.setItem("experimentStudyId", session.study_id);
            sessionStorage.setItem("experimentConfig", JSON.stringify({
                ...session.config,
                paradigm: session.paradigm,
                language: "en",
            }));
            sessionStorage.setItem("experimentInstructions", JSON.stringify([
                "Arrange the stimuli based on their perceived similarity.",
                "Place similar stimuli closer together inside the circle.",
                "Double-click a stimulus to play it.",
                "All stimuli must be inside the circle before you can submit.",
            ]));

            router.push(`/experiment?session=${session.session_id}`);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to start demo";
            setError(msg);
        } finally {
            if (paradigm === "adaptive") setLoadingLtW(false);
            else setLoadingSetcover(false);
        }
    };

    const busy = loadingLtW || loadingSetcover;

    return (
        <div style={{
            minHeight: "calc(100vh - 56px)",
            background: "#000",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "'Inter', -apple-system, sans-serif",
            padding: "40px 24px",
        }}>
            <div style={{ maxWidth: 560, width: "100%" }}>
                {/* Header */}
                <div style={{ marginBottom: 40 }}>
                    <h1 style={{ fontSize: 32, fontWeight: 700, marginBottom: 8, letterSpacing: "-0.5px", margin: 0 }}>Demo</h1>
                    <p style={{ color: "#666", fontSize: 15, marginTop: 8, lineHeight: 1.6, margin: "8px 0 0" }}>
                        Try the experiment with 16 pre-loaded video stimuli. Results stay local and can be downloaded when you&apos;re done.
                    </p>
                </div>

                {error && (
                    <div style={{ marginBottom: 24, padding: "12px 16px", background: "rgba(255,68,68,0.08)", border: "1px solid rgba(255,68,68,0.3)", borderRadius: 10, color: "#ff6666", fontSize: 14 }}>
                        {error}
                    </div>
                )}

                {/* Mode cards */}
                <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 32 }}>
                    {/* LtW */}
                    <button
                        onClick={() => startDemo("adaptive")}
                        disabled={busy}
                        style={{
                            padding: "20px 24px",
                            borderRadius: 12,
                            border: "1px solid #1e3d2a",
                            background: busy && loadingLtW ? "rgba(0,255,136,0.1)" : "linear-gradient(145deg, #0d1f15 0%, #0a1a10 100%)",
                            color: "#fff",
                            fontSize: 15,
                            fontWeight: 600,
                            cursor: busy ? "not-allowed" : "pointer",
                            transition: "all 0.2s ease",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "flex-start",
                            textAlign: "left",
                            opacity: busy && !loadingLtW ? 0.5 : 1,
                        }}
                    >
                        <div>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#00ff88", display: "inline-block", flexShrink: 0 }} />
                                <span>Lift-the-Weakest</span>
                                <span style={{ padding: "2px 8px", borderRadius: 4, background: "rgba(0,255,136,0.12)", color: "#00ff88", fontSize: 11, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.5px" }}>Adaptive</span>
                            </div>
                            <div style={{ fontSize: 13, color: "#666", fontWeight: 400 }}>Targets uncertain stimulus pairs adaptively.</div>
                        </div>
                        <span style={{ fontSize: 18, color: "#00ff88", marginLeft: 16, flexShrink: 0, marginTop: 2 }}>
                            {loadingLtW ? "..." : "→"}
                        </span>
                    </button>

                    {/* Setcover */}
                    <button
                        onClick={() => startDemo("setcover")}
                        disabled={busy}
                        style={{
                            padding: "20px 24px",
                            borderRadius: 12,
                            border: "1px solid #1a2a3d",
                            background: busy && loadingSetcover ? "rgba(0,204,255,0.1)" : "linear-gradient(145deg, #0d1a2a 0%, #0a1520 100%)",
                            color: "#fff",
                            fontSize: 15,
                            fontWeight: 600,
                            cursor: busy ? "not-allowed" : "pointer",
                            transition: "all 0.2s ease",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "flex-start",
                            textAlign: "left",
                            opacity: busy && !loadingSetcover ? 0.5 : 1,
                        }}
                    >
                        <div>
                            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                                <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#00ccff", display: "inline-block", flexShrink: 0 }} />
                                <span>Setcover Optimization</span>
                                <span style={{ padding: "2px 8px", borderRadius: 4, background: "rgba(0,204,255,0.12)", color: "#00ccff", fontSize: 11, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.5px" }}>Batch</span>
                            </div>
                            <div style={{ fontSize: 13, color: "#666", fontWeight: 400 }}>Covers all stimuli in efficient batches.</div>
                        </div>
                        <span style={{ fontSize: 18, color: "#00ccff", marginLeft: 16, flexShrink: 0, marginTop: 2 }}>
                            {loadingSetcover ? "..." : "→"}
                        </span>
                    </button>
                </div>

                {/* Info callout */}
                <div style={{ padding: "14px 18px", borderRadius: 10, background: "#111", border: "1px solid #1a1a1a", fontSize: 13, color: "#555", lineHeight: 1.6, marginBottom: 32 }}>
                    <span style={{ color: "#00ff88", fontWeight: 600 }}>16 stimuli</span> · drag into the circle · double-click to play · submit when complete
                </div>

                {/* Back link */}
                <Link href="/" style={{ color: "#444", fontSize: 13, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 6 }}>
                    ← Back to Home
                </Link>
            </div>
        </div>
    );
}
