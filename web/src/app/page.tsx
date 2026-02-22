"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useKey } from "./lib/KeyContext";
import { apiFetch } from "./lib/api";
import Logo from "./components/Logo";
import { EyeIcon, EyeOffIcon } from "./components/EyeIcon";

interface StudySummary {
    id: string;
    name: string;
    description?: string | null;
    paradigm: string;
    language: string;
    created_at: string;
    n_stimuli: number;
}

interface Chain {
    id: string;
    name: string;
    description: string | null;
    studies: { id: string; study_name: string; paradigm: string; position: number }[];
}

export default function Home() {
    const { adminKey, setAdminKey, isLocalBypass, authReady } = useKey();
    const [keyInput, setKeyInput] = useState("");
    const [studies, setStudies] = useState<StudySummary[]>([]);
    const [chains, setChains] = useState<Chain[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loaded, setLoaded] = useState(false);
    const [showKey, setShowKey] = useState(false);
    const [attemptedAutoLoad, setAttemptedAutoLoad] = useState(false);

    useEffect(() => {
        if (adminKey) setKeyInput(adminKey);
    }, [adminKey]);

    const loadData = useCallback(async (key: string) => {
        const trimmedKey = key.trim();
        setError(null);
        setLoading(true);
        try {
            if (trimmedKey) {
                setAdminKey(trimmedKey);
            }
            const headers: Record<string, string> = trimmedKey
                ? { "x-experimenter-key": trimmedKey }
                : {};
            const [studiesData, chainsData] = await Promise.all([
                apiFetch<StudySummary[]>("/api/v1/admin/studies", { headers }),
                apiFetch<Chain[]>("/api/v1/chains", { headers }).catch(() => [] as Chain[]),
            ]);
            setStudies(studiesData);
            setChains(chainsData);
            setLoaded(true);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to authenticate";
            if (!trimmedKey && msg.includes("API error 401")) {
                setError(null);
                setLoaded(false);
                return;
            }
            setError(msg);
            setLoaded(false);
        } finally {
            setLoading(false);
        }
    }, [setAdminKey]);

    // Auto-load logic removed to prevent jumpy transitions and respect user preference
    // for deliberate dashboard entry.

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        loadData(keyInput);
    };

    const totalStudies = studies.length;
    const totalChains = chains.length;
    const totalStimuli = studies.reduce((acc, s) => acc + s.n_stimuli, 0);

    return (
        <div
            style={{
                minHeight: "calc(100vh - 56px)",
                background: "#000",
                color: "#fff",
                padding: "40px 24px",
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            <div style={{ maxWidth: 1000, margin: "0 auto" }}>
                {!loaded ? (
                    <div
                        style={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            minHeight: "60vh",
                            textAlign: "center",
                        }}
                    >
                        <div style={{ marginBottom: 24 }}>
                            <Logo size={64} animated />
                        </div>
                        <h1 style={{ fontSize: 36, fontWeight: 700, marginBottom: 8, letterSpacing: "-0.5px" }}>
                            Multiarrangement
                        </h1>
                        {isLocalBypass ? (
                            <p style={{ color: "#6db59b", fontSize: 14, marginBottom: 12, maxWidth: 500 }}>
                                Local keyless mode detected. You can use the app without an experimenter key.
                            </p>
                        ) : (
                            <p style={{ color: "#666", fontSize: 15, marginBottom: 40, maxWidth: 500 }}>
                                Configure and manage perceptual similarity experiments.
                                Enter your experimenter key to view your studies and chains.
                            </p>
                        )}
                        {!authReady && (
                            <p style={{ color: "#666", fontSize: 13, marginBottom: 24 }}>
                                Checking auth mode...
                            </p>
                        )}

                        {/* Key entry form */}
                        <form
                            onSubmit={handleSubmit}
                            style={{ display: "flex", gap: 10, width: "100%", maxWidth: 460, justifyContent: adminKey ? "center" : "stretch" }}
                        >
                            {!adminKey && (
                                <>
                                    <input
                                        type={showKey ? "text" : "password"}
                                        value={keyInput}
                                        onChange={(e) => setKeyInput(e.target.value)}
                                        placeholder={isLocalBypass ? "Optional experimenter key..." : "Enter your experimenter key..."}
                                        autoFocus
                                        style={{
                                            flex: 1,
                                            padding: "14px 18px",
                                            borderRadius: 10,
                                            border: "1px solid #333",
                                            background: "#111",
                                            color: "#fff",
                                            fontSize: 15,
                                            outline: "none",
                                        }}
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowKey(!showKey)}
                                        style={{ padding: "14px 12px", borderRadius: 10, border: "1px solid #333", background: "#111", color: "#888", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}
                                        title={showKey ? "Hide key" : "Show key"}
                                    >
                                        {showKey ? <EyeOffIcon size={18} color="#888" /> : <EyeIcon size={18} color="#888" />}
                                    </button>
                                </>
                            )}
                            <button
                                type="submit"
                                disabled={loading}
                                style={{
                                    padding: "14px 28px",
                                    borderRadius: 10,
                                    border: "none",
                                    background: "linear-gradient(135deg, #00ff88 0%, #00cc66 100%)",
                                    color: "#000",
                                    fontWeight: 700,
                                    fontSize: 15,
                                    cursor: loading ? "not-allowed" : "pointer",
                                    opacity: loading ? 0.6 : 1,
                                    transition: "opacity 0.2s ease",
                                }}
                            >
                                {loading ? "Loading..." : (keyInput ? "Go to Dashboard" : "Enter")}
                            </button>
                        </form>

                        {!adminKey && (
                            <p style={{ marginTop: 24, color: "#555", fontSize: 13 }}>
                                {isLocalBypass
                                    ? "Key entry is optional in local mode."
                                    : <><span>Don&apos;t have a key? </span><Link href="/admin" style={{ color: "#00ff88", textDecoration: "none" }}>Generate one</Link><span> on the Experimenter page.</span></>}
                            </p>
                        )}

                        {error && (
                            <div style={{ marginTop: 16, color: "#ff6666", fontSize: 13 }}>{error}</div>
                        )}

                        <div style={{ marginTop: 48, display: "flex", gap: 20, flexWrap: "wrap", justifyContent: "center" }}>
                            <Link href="/setup" style={{ padding: "10px 20px", borderRadius: 8, border: "1px solid #222", color: "#888", textDecoration: "none", fontSize: 13 }}>
                                Setup Experiment →
                            </Link>
                            <Link href="/chains" style={{ padding: "10px 20px", borderRadius: 8, border: "1px solid #222", color: "#888", textDecoration: "none", fontSize: 13 }}>
                                Build Chains →
                            </Link>
                        </div>
                    </div>
                ) : (
                    <>
                        <div style={{ marginBottom: 32 }}>
                            <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 4 }}>Dashboard</h1>
                            <p style={{ color: "#666", fontSize: 14 }}>Overview of your experiments and chains</p>
                        </div>

                        {/* Stats Cards */}
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 32 }}>
                            <div style={{ background: "linear-gradient(145deg, #111 0%, #0a0a0a 100%)", borderRadius: 12, padding: "20px 24px", border: "1px solid #1a1a1a" }}>
                                <div style={{ fontSize: 32, fontWeight: 700, color: "#00ff88" }}>{totalStudies}</div>
                                <div style={{ fontSize: 13, color: "#666", marginTop: 4 }}>Studies</div>
                            </div>
                            <div style={{ background: "linear-gradient(145deg, #111 0%, #0a0a0a 100%)", borderRadius: 12, padding: "20px 24px", border: "1px solid #1a1a1a" }}>
                                <div style={{ fontSize: 32, fontWeight: 700, color: "#00cc66" }}>{totalChains}</div>
                                <div style={{ fontSize: 13, color: "#666", marginTop: 4 }}>Chains</div>
                            </div>
                            <div style={{ background: "linear-gradient(145deg, #111 0%, #0a0a0a 100%)", borderRadius: 12, padding: "20px 24px", border: "1px solid #1a1a1a" }}>
                                <div style={{ fontSize: 32, fontWeight: 700, color: "#88ffcc" }}>{totalStimuli}</div>
                                <div style={{ fontSize: 13, color: "#666", marginTop: 4 }}>Total Stimuli</div>
                            </div>
                        </div>

                        {/* Quick Actions */}
                        <div style={{ display: "flex", gap: 12, marginBottom: 32, flexWrap: "wrap" }}>
                            <Link href="/setup" style={{ padding: "12px 24px", borderRadius: 10, border: "none", background: "linear-gradient(135deg, #00ff88 0%, #00cc66 100%)", color: "#000", fontWeight: 600, fontSize: 14, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 6 }}>
                                + New Experiment
                            </Link>
                            <Link href="/chains" style={{ padding: "12px 24px", borderRadius: 10, border: "1px solid #333", background: "#111", color: "#fff", fontWeight: 500, fontSize: 14, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 6 }}>
                                ⛓ Build Chain
                            </Link>
                            <Link href="/admin" style={{ padding: "12px 24px", borderRadius: 10, border: "1px solid #333", background: "#111", color: "#fff", fontWeight: 500, fontSize: 14, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 6 }}>
                                ☸ Experimenter Panel
                            </Link>
                        </div>

                        {/* Two-column: Recent Studies + Chains */}
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                            {/* Recent Studies */}
                            <div style={{ background: "#111", borderRadius: 12, padding: 24, border: "1px solid #1a1a1a" }}>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                                    <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>Recent Studies</h2>
                                    <Link href="/admin" style={{ fontSize: 12, color: "#00ff88", textDecoration: "none" }}>View All →</Link>
                                </div>
                                {studies.length === 0 ? (
                                    <div style={{ padding: 32, border: "1px dashed #333", borderRadius: 8, textAlign: "center", color: "#555", fontSize: 13 }}>
                                        No studies yet. <Link href="/setup" style={{ color: "#00ff88" }}>Create one</Link>
                                    </div>
                                ) : (
                                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                        {studies.slice(0, 5).map((study) => (
                                            <Link key={study.id} href={`/admin?study=${study.id}`} style={{ display: "block", padding: 12, borderRadius: 8, border: "1px solid #222", background: "#0a0a0a", textDecoration: "none", color: "#fff" }}>
                                                <div style={{ fontWeight: 600, fontSize: 14 }}>{study.name}</div>
                                                <div style={{ fontSize: 12, color: "#666", marginTop: 4, display: "flex", gap: 8, alignItems: "center" }}>
                                                    <span style={{ padding: "2px 8px", borderRadius: 4, background: "#1a1a1a", fontSize: 11, textTransform: "uppercase" }}>{study.paradigm}</span>
                                                    <span>{study.n_stimuli} stimuli</span>
                                                    <span style={{ color: "#444" }}>•</span>
                                                    <span>{study.language.toUpperCase()}</span>
                                                </div>
                                                <div style={{ fontSize: 10, color: "#444", marginTop: 6, fontFamily: "monospace" }}>{study.id.slice(0, 8)}...</div>
                                            </Link>
                                        ))}
                                        {studies.length > 5 && (
                                            <Link href="/admin" style={{ padding: "8px 0", fontSize: 12, color: "#666", textAlign: "center", textDecoration: "none" }}>
                                                +{studies.length - 5} more studies
                                            </Link>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Chains */}
                            <div style={{ background: "#111", borderRadius: 12, padding: 24, border: "1px solid #1a1a1a" }}>
                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                                    <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>Experiment Chains</h2>
                                    <Link href="/chains" style={{ fontSize: 12, color: "#00ff88", textDecoration: "none" }}>Manage →</Link>
                                </div>
                                {chains.length === 0 ? (
                                    <div style={{ padding: 32, border: "1px dashed #333", borderRadius: 8, textAlign: "center", color: "#555", fontSize: 13 }}>
                                        No chains yet. <Link href="/chains" style={{ color: "#00ff88" }}>Create one</Link>
                                    </div>
                                ) : (
                                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                        {chains.slice(0, 5).map((chain) => (
                                            <Link key={chain.id} href={`/chains?selected=${chain.id}`} style={{ display: "block", padding: 12, borderRadius: 8, border: "1px solid #222", background: "#0a0a0a", textDecoration: "none", color: "#fff" }}>
                                                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                                    <div style={{ fontWeight: 600, fontSize: 14 }}>{chain.name}</div>
                                                    <span style={{ padding: "2px 8px", borderRadius: 4, background: "#1a1a1a", fontSize: 11, color: "#00ff88" }}>
                                                        {chain.studies.length} studies
                                                    </span>
                                                </div>
                                                {chain.description && (
                                                    <div style={{ fontSize: 12, color: "#666", marginTop: 4 }}>{chain.description}</div>
                                                )}
                                                {chain.studies.length > 0 && (
                                                    <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                                                        {chain.studies.sort((a, b) => a.position - b.position).map((s, i) => (
                                                            <span key={s.id} style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11, color: "#555" }}>
                                                                <span style={{ width: 16, height: 16, borderRadius: "50%", background: "#1a1a1a", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 9, color: "#00ff88" }}>
                                                                    {i + 1}
                                                                </span>
                                                                {s.study_name}
                                                                {i < chain.studies.length - 1 && <span style={{ color: "#333" }}>→</span>}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}
                                            </Link>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
