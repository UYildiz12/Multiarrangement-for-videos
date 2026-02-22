"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useKey } from "./lib/KeyContext";
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
    const router = useRouter();
    const { adminKey, setAdminKey, isLocalBypass } = useKey();
    const [keyInput, setKeyInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showKey, setShowKey] = useState(false);

    useEffect(() => {
        if (adminKey) setKeyInput(adminKey);
    }, [adminKey]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const trimmedKey = keyInput.trim();
        setError(null);
        setLoading(true);
        try {
            setAdminKey(trimmedKey);
            router.push("/dashboard");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to set key");
        } finally {
            setLoading(false);
        }
    };

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

                    {/* Key entry form */}
                    <form
                        onSubmit={handleSubmit}
                        style={{ display: "flex", gap: 10, width: "100%", maxWidth: 460 }}
                    >
                        <input
                            type={showKey ? "text" : "password"}
                            value={keyInput}
                            onChange={(e) => setKeyInput(e.target.value)}
                            placeholder={isLocalBypass ? "Optional experimenter key..." : "Enter your experimenter key..."}
                            autoFocus
                            style={{
                                padding: "14px 18px",
                                borderRadius: 10,
                                border: "1px solid #333",
                                background: "#111",
                                color: "#fff",
                                fontSize: 15,
                                outline: "none",
                                flex: 1,
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
                            {loading ? "Loading..." : "Enter"}
                        </button>
                    </form>
                    <p style={{ marginTop: 24, color: "#555", fontSize: 13 }}>
                        {isLocalBypass
                            ? "Key entry is optional in local mode."
                            : <><span>Don&apos;t have a key? </span><a href="/admin" style={{ color: "#00ff88", textDecoration: "none" }}>Generate one</a><span> on the Experimenter page.</span></>}
                    </p>

                    {error && (
                        <div style={{ marginTop: 16, color: "#ff6666", fontSize: 13 }}>{error}</div>
                    )}
                </div>
            </div>
        </div>
    );
}
