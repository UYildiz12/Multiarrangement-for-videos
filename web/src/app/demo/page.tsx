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
            const allVideos = data.videos || [];
            const demoVideos = allVideos.slice(0, 16); // take 16 presets

            const session = await apiFetch<any>(`/api/v1/public/demo/start`, {
                method: "POST",
                body: JSON.stringify({ paradigm, n_stimuli: 16 }),
            });

            // Reconcile URLs from demo config with frontend preset URLs
            const stimuliForClient = session.stimuli.map((s: any, i: number) => {
                const preset = demoVideos[i] || {};
                return {
                    id: s.id || `stim-${s.ordinal}`,
                    ordinal: s.ordinal,
                    label: preset.label || preset.filename || s.filename,
                    mediaUrl: preset.url || s.media_url || "",
                    mediaType: preset.mediaType || "video",
                    thumbnail: preset.thumbnail || s.thumbnail_url || undefined,
                };
            });

            sessionStorage.setItem("experimentStimuli", JSON.stringify(stimuliForClient));
            sessionStorage.setItem("experimentSessionId", session.session_id);
            sessionStorage.setItem("experimentStudyId", session.study_id);
            sessionStorage.setItem("experimentConfig", JSON.stringify({
                ...session.config,
                paradigm: session.paradigm,
                language: "en"
            }));
            sessionStorage.setItem("experimentInstructions", JSON.stringify([
                "This is a local demonstration. You can download your results at the end.",
                "Have fun exploring the interface!"
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

    return (
        <div style={{
            minHeight: "100vh",
            background: "#000",
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "'Inter', -apple-system, sans-serif",
            padding: 24,
        }}>
            <div style={{ maxWidth: 600, width: "100%", background: "#111", padding: 40, borderRadius: 16, border: "1px solid #1a1a1a", textAlign: "center" }}>
                <h1 style={{ fontSize: 32, fontWeight: 700, marginBottom: 12, letterSpacing: "-0.5px" }}>Multiarrangement Demo</h1>
                <p style={{ color: "#888", fontSize: 15, marginBottom: 40, lineHeight: 1.6 }}>
                    Welcome to the interactive demonstration. Experience both of our clustering paradigms using 16 pre-selected video stimuli. 
                    <br/><br/>
                    <span style={{ color: "#00ff88" }}>All data is local and you can download your results at the end.</span>
                </p>

                {error && (
                    <div style={{ marginBottom: 24, padding: 12, background: "rgba(255,0,0,0.1)", border: "1px solid #ff4444", borderRadius: 8, color: "#ff4444", fontSize: 14 }}>
                        {error}
                    </div>
                )}

                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    <button
                        onClick={() => startDemo("adaptive")}
                        disabled={loadingLtW || loadingSetcover}
                        style={{
                            padding: "16px 24px",
                            borderRadius: 12,
                            border: "1px solid #00ff88",
                            background: "rgba(0, 255, 136, 0.05)",
                            color: "#00ff88",
                            fontSize: 16,
                            fontWeight: 600,
                            cursor: loadingLtW || loadingSetcover ? "not-allowed" : "pointer",
                            transition: "all 0.2s ease",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center"
                        }}
                    >
                        <span>Lift-the-Weak (LtW)</span>
                        {loadingLtW ? <span style={{ opacity: 0.7 }}>Starting...</span> : <span>→</span>}
                    </button>
                    <p style={{ color: "#666", fontSize: 13, marginTop: -8, marginBottom: 8, textAlign: "left", paddingLeft: 16 }}>
                        Adaptive pairwise selection targeting uncertain areas.
                    </p>

                    <button
                        onClick={() => startDemo("setcover")}
                        disabled={loadingLtW || loadingSetcover}
                        style={{
                            padding: "16px 24px",
                            borderRadius: 12,
                            border: "1px solid #00ccff",
                            background: "rgba(0, 204, 255, 0.05)",
                            color: "#00ccff",
                            fontSize: 16,
                            fontWeight: 600,
                            cursor: loadingLtW || loadingSetcover ? "not-allowed" : "pointer",
                            transition: "all 0.2s ease",
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center"
                        }}
                    >
                        <span>Setcover Optimization</span>
                        {loadingSetcover ? <span style={{ opacity: 0.7 }}>Starting...</span> : <span>→</span>}
                    </button>
                    <p style={{ color: "#666", fontSize: 13, marginTop: -8, marginBottom: 8, textAlign: "left", paddingLeft: 16 }}>
                        Batch arrangement covering the entire stimulus set.
                    </p>
                </div>

                <div style={{ marginTop: 40, borderTop: "1px solid #222", paddingTop: 24 }}>
                    <Link href="/" style={{ color: "#555", fontSize: 14, textDecoration: "none" }}>
                        ← Back to Home
                    </Link>
                </div>
            </div>
        </div>
    );
}
