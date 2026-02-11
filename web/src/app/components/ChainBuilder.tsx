"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import { apiFetch } from "../lib/api";
import { useKey } from "../lib/KeyContext";

interface Study {
    id: string;
    name: string;
    paradigm: "setcover" | "adaptive" | "pairwise";
    n_stimuli: number;
}

interface ChainStudy {
    id: string;
    chain_id: string;
    study_id: string;
    study_name: string;
    paradigm: string;
    position: number;
}

interface Chain {
    id: string;
    name: string;
    description: string | null;
    studies: ChainStudy[];
}

interface ChainBuilderProps {
    onChainCreated?: (chain: Chain) => void;
    onChainSelected?: (chainId: string) => void;
    adminSecret?: string;
}

export default function ChainBuilder({ onChainCreated, onChainSelected, adminSecret }: ChainBuilderProps) {
    const { adminKey } = useKey();
    const expKey = adminSecret || adminKey;
    const keyHeaders = useMemo<Record<string, string>>(() => {
        const headers: Record<string, string> = {};
        const key = expKey.trim();
        if (key) {
            headers["x-experimenter-key"] = key;
        }
        return headers;
    }, [expKey]);

    const [chains, setChains] = useState<Chain[]>([]);
    const [studies, setStudies] = useState<Study[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // New chain form
    const [newChainName, setNewChainName] = useState("");
    const [newChainDescription, setNewChainDescription] = useState("");
    const [creating, setCreating] = useState(false);

    // Selected chain for editing
    const [selectedChain, setSelectedChain] = useState<Chain | null>(null);
    const [selectedStudyId, setSelectedStudyId] = useState<string>("");

    // Invite generation
    const [generatingInvite, setGeneratingInvite] = useState(false);
    const [inviteLink, setInviteLink] = useState<string | null>(null);
    const [inviteParticipantId, setInviteParticipantId] = useState("");

    const describeAuthError = useCallback((err: unknown, fallback: string) => {
        const msg = err instanceof Error ? err.message : fallback;
        if (!msg.includes("API error 401")) {
            return msg;
        }
        if (expKey.trim()) {
            return msg;
        }
        return "Experimenter key required to log your experiments and share them online. We strongly recommend always immediately backing up your data.";
    }, [expKey]);

    // Load chains and studies (skip when no key — server returns empty anyway)
    useEffect(() => {
        if (!expKey.trim()) {
            setChains([]);
            setStudies([]);
            setLoading(false);
            return;
        }
        let cancelled = false;
        const loadData = async () => {
            setLoading(true);
            setError(null);
            try {
                const [chainsData, studiesData] = await Promise.all([
                    apiFetch<Chain[]>("/api/v1/chains", { headers: keyHeaders }),
                    apiFetch<Study[]>("/api/v1/studies", { headers: keyHeaders }),
                ]);
                if (!cancelled) {
                    setChains(chainsData);
                    setStudies(studiesData);
                }
            } catch (err) {
                if (!cancelled) {
                    setError(describeAuthError(err, "Failed to load data"));
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        loadData();
        return () => { cancelled = true; };
    }, [keyHeaders, describeAuthError]);

    const handleCreateChain = useCallback(async () => {
        if (!newChainName.trim()) return;
        setCreating(true);
        setError(null);
        try {
            const chain = await apiFetch<Chain>("/api/v1/chains", {
                method: "POST",
                headers: keyHeaders,
                body: JSON.stringify({
                    name: newChainName,
                    description: newChainDescription || null,
                }),
            });
            setChains((prev) => [...prev, chain]);
            setNewChainName("");
            setNewChainDescription("");
            setSelectedChain(chain);
            onChainCreated?.(chain);
        } catch (err) {
            setError(describeAuthError(err, "Failed to create chain"));
        } finally {
            setCreating(false);
        }
    }, [newChainName, newChainDescription, onChainCreated, keyHeaders]);

    const addStudyById = useCallback(async (studyId: string) => {
        if (!selectedChain) return;
        try {
            const chainStudy = await apiFetch<ChainStudy>(
                `/api/v1/chains/${selectedChain.id}/studies`,
                {
                    method: "POST",
                    headers: keyHeaders,
                    body: JSON.stringify({ study_id: studyId }),
                }
            );
            setSelectedChain((prev) => prev && ({
                ...prev,
                studies: [...prev.studies, chainStudy],
            }));
            setChains((prev) => prev.map((c) =>
                c.id === selectedChain.id
                    ? { ...c, studies: [...c.studies, chainStudy] }
                    : c
            ));
            setSelectedStudyId("");
        } catch (err) {
            setError(describeAuthError(err, "Failed to add study"));
        }
    }, [selectedChain, keyHeaders, describeAuthError]);

    const handleAddStudy = useCallback(async () => {
        if (!selectedStudyId) return;
        await addStudyById(selectedStudyId);
    }, [selectedStudyId, addStudyById]);

    const handleRemoveStudy = useCallback(async (studyId: string) => {
        if (!selectedChain) return;
        try {
            await apiFetch(
                `/api/v1/chains/${selectedChain.id}/studies/${studyId}`,
                { method: "DELETE", headers: keyHeaders }
            );
            setSelectedChain((prev) => prev && ({
                ...prev,
                studies: prev.studies.filter((s) => s.study_id !== studyId),
            }));
            setChains((prev) => prev.map((c) =>
                c.id === selectedChain.id
                    ? { ...c, studies: c.studies.filter((s) => s.study_id !== studyId) }
                    : c
            ));
        } catch (err) {
            setError(describeAuthError(err, "Failed to remove study"));
        }
    }, [selectedChain, keyHeaders, describeAuthError]);

    const handleGenerateInvite = useCallback(async () => {
        if (!selectedChain) return;
        setGeneratingInvite(true);
        setInviteLink(null);
        setError(null);
        try {
            const invites = await apiFetch<{ token: string }[]>(
                `/api/v1/chains/${selectedChain.id}/invites`,
                {
                    method: "POST",
                    headers: keyHeaders,
                    body: JSON.stringify({
                        participant_id: inviteParticipantId || null,
                        count: 1,
                    }),
                }
            );
            const token = invites[0]?.token;
            if (token) {
                const origin = typeof window !== "undefined" ? window.location.origin : "";
                setInviteLink(`${origin}/participate?chain=${token}`);
            }
        } catch (err) {
            setError(describeAuthError(err, "Failed to generate invite"));
        } finally {
            setGeneratingInvite(false);
        }
    }, [selectedChain, inviteParticipantId, keyHeaders, describeAuthError]);

    const inputStyle = {
        padding: "10px 14px",
        borderRadius: 8,
        border: "1px solid #333",
        background: "#111",
        color: "#fff",
        fontSize: 14,
        width: "100%",
    };

    const buttonStyle = {
        padding: "10px 20px",
        borderRadius: 8,
        border: "none",
        background: "linear-gradient(135deg, #00ff88 0%, #00cc66 100%)",
        color: "#000",
        fontSize: 14,
        fontWeight: 600 as const,
        cursor: "pointer",
        transition: "all 0.2s ease",
    };

    const secondaryButtonStyle = {
        ...buttonStyle,
        background: "#1a1a1a",
        border: "1px solid #333",
        color: "#fff",
    };

    const cardStyle = {
        background: "linear-gradient(145deg, #111 0%, #0a0a0a 100%)",
        borderRadius: 12,
        padding: 20,
        border: "1px solid #222",
    };

    if (loading) {
        return (
            <div style={{ padding: 40, textAlign: "center", color: "#666" }}>
                Loading...
            </div>
        );
    }

    return (
        <div style={{ display: "flex", gap: 24 }}>
            {/* Left Panel: Chain List */}
            <div style={{ flex: "0 0 280px" }}>
                <div style={cardStyle}>
                    <h3 style={{ margin: "0 0 16px", fontSize: 14, color: "#888", textTransform: "uppercase", letterSpacing: 1 }}>
                        Experiment Chains
                    </h3>

                    {chains.length === 0 ? (
                        <p style={{ color: "#555", fontSize: 13 }}>No chains yet. Create one below.</p>
                    ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                            {chains.map((chain) => (
                                <button
                                    key={chain.id}
                                    onClick={() => {
                                        setSelectedChain(chain);
                                        setInviteLink(null);
                                        onChainSelected?.(chain.id);
                                    }}
                                    style={{
                                        padding: "12px 16px",
                                        borderRadius: 8,
                                        border: selectedChain?.id === chain.id
                                            ? "2px solid #00ff88"
                                            : "1px solid #333",
                                        background: selectedChain?.id === chain.id
                                            ? "rgba(0, 255, 136, 0.1)"
                                            : "#1a1a1a",
                                        color: "#fff",
                                        textAlign: "left",
                                        cursor: "pointer",
                                    }}
                                >
                                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{chain.name}</div>
                                    <div style={{ fontSize: 12, color: "#666" }}>
                                        {chain.studies.length} studies
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}

                    <div style={{ marginTop: 20, borderTop: "1px solid #222", paddingTop: 20 }}>
                        <input
                            type="text"
                            placeholder="Chain name"
                            value={newChainName}
                            onChange={(e) => setNewChainName(e.target.value)}
                            style={{ ...inputStyle, marginBottom: 8 }}
                        />
                        <input
                            type="text"
                            placeholder="Description (optional)"
                            value={newChainDescription}
                            onChange={(e) => setNewChainDescription(e.target.value)}
                            style={{ ...inputStyle, marginBottom: 12 }}
                        />
                        <button
                            onClick={handleCreateChain}
                            disabled={creating || !newChainName.trim()}
                            style={{
                                ...buttonStyle,
                                width: "100%",
                                opacity: creating || !newChainName.trim() ? 0.5 : 1,
                            }}
                        >
                            {creating ? "Creating..." : "+ Create Chain"}
                        </button>
                    </div>
                </div>
            </div>

            {/* Right Panel: Chain Editor */}
            <div style={{ flex: 1 }}>
                {error && (
                    <div style={{
                        padding: 12,
                        background: "rgba(255, 0, 0, 0.1)",
                        border: "1px solid #f66",
                        borderRadius: 8,
                        color: "#f66",
                        marginBottom: 16,
                        fontSize: 13,
                    }}>
                        {error}
                    </div>
                )}

                {selectedChain ? (
                    <div style={cardStyle}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
                            <div>
                                <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
                                    {selectedChain.name}
                                </h2>
                                {selectedChain.description && (
                                    <p style={{ margin: "4px 0 0", color: "#666", fontSize: 13 }}>
                                        {selectedChain.description}
                                    </p>
                                )}
                            </div>
                        </div>

                        {/* Study Sequence */}
                        <div style={{ marginBottom: 24 }}>
                            <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#888", textTransform: "uppercase", letterSpacing: 1 }}>
                                Study Sequence
                            </h3>

                            {selectedChain.studies.length === 0 ? (
                                <div style={{
                                    padding: 32,
                                    border: "2px dashed #333",
                                    borderRadius: 12,
                                    textAlign: "center",
                                    color: "#555",
                                }}>
                                    <p style={{ margin: 0 }}>No studies in this chain yet.</p>
                                    <p style={{ margin: "8px 0 0", fontSize: 13 }}>
                                        Add studies below to build the sequence.
                                    </p>
                                </div>
                            ) : (
                                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                    {selectedChain.studies
                                        .sort((a, b) => a.position - b.position)
                                        .map((study, i) => (
                                            <div
                                                key={study.id}
                                                style={{
                                                    display: "flex",
                                                    alignItems: "center",
                                                    gap: 12,
                                                    padding: 12,
                                                    background: "#1a1a1a",
                                                    borderRadius: 8,
                                                    border: "1px solid #333",
                                                }}
                                            >
                                                <div style={{
                                                    width: 28,
                                                    height: 28,
                                                    borderRadius: "50%",
                                                    background: "linear-gradient(135deg, #00ff88 0%, #00cc66 100%)",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    justifyContent: "center",
                                                    fontWeight: 700,
                                                    fontSize: 13,
                                                    color: "#000",
                                                    flexShrink: 0,
                                                }}>
                                                    {i + 1}
                                                </div>
                                                <div style={{ flex: 1 }}>
                                                    <div style={{ fontWeight: 500 }}>{study.study_name}</div>
                                                    <div style={{ fontSize: 12, color: "#666" }}>
                                                        {study.paradigm}
                                                    </div>
                                                </div>
                                                <button
                                                    onClick={() => handleRemoveStudy(study.study_id)}
                                                    style={{
                                                        width: 28,
                                                        height: 28,
                                                        borderRadius: 6,
                                                        border: "1px solid #444",
                                                        background: "transparent",
                                                        color: "#888",
                                                        cursor: "pointer",
                                                        display: "flex",
                                                        alignItems: "center",
                                                        justifyContent: "center",
                                                        fontSize: 16,
                                                    }}
                                                >
                                                    ×
                                                </button>
                                                {i < selectedChain.studies.length - 1 && (
                                                    <div style={{
                                                        position: "absolute",
                                                        left: 48,
                                                        bottom: -12,
                                                        color: "#333",
                                                        fontSize: 16,
                                                    }}>
                                                        ↓
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                </div>
                            )}
                        </div>

                        {/* Add Study */}
                        <div style={{ marginBottom: 24, paddingTop: 16, borderTop: "1px solid #222" }}>
                            <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#888", textTransform: "uppercase", letterSpacing: 1 }}>
                                Add Study
                            </h3>
                            {(() => {
                                const alreadyAdded = new Set(selectedChain.studies.map(s => s.study_id));
                                const available = studies.filter(s => !alreadyAdded.has(s.id));
                                if (studies.length === 0) {
                                    return (
                                        <p style={{ margin: 0, fontSize: 13, color: "#555" }}>
                                            No studies found. <a href="/setup" style={{ color: "#00ff88", textDecoration: "underline" }}>Create one</a> first.
                                        </p>
                                    );
                                }
                                if (available.length === 0) {
                                    return (
                                        <p style={{ margin: 0, fontSize: 13, color: "#555" }}>
                                            All your studies have been added. <a href="/setup" style={{ color: "#00ff88", textDecoration: "underline" }}>Create another</a> to add more.
                                        </p>
                                    );
                                }
                                return (
                                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                                        {available.map((study) => (
                                            <div
                                                key={study.id}
                                                style={{
                                                    display: "flex",
                                                    alignItems: "center",
                                                    justifyContent: "space-between",
                                                    padding: "8px 12px",
                                                    background: selectedStudyId === study.id ? "rgba(0,255,136,0.08)" : "#1a1a1a",
                                                    border: selectedStudyId === study.id ? "1px solid #00ff88" : "1px solid #333",
                                                    borderRadius: 6,
                                                    cursor: "pointer",
                                                    transition: "all 0.15s",
                                                }}
                                                onClick={() => {
                                                    setSelectedStudyId(study.id);
                                                }}
                                            >
                                                <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
                                                    <span style={{ fontSize: 13, color: "#fff", fontWeight: 500 }}>
                                                        {study.name}
                                                    </span>
                                                    <span style={{ fontSize: 11, color: "#666" }}>
                                                        {study.paradigm} · {study.n_stimuli} stimuli
                                                    </span>
                                                </div>
                                                <button
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setSelectedStudyId(study.id);
                                                        void addStudyById(study.id);
                                                    }}
                                                    style={{
                                                        padding: "4px 12px",
                                                        borderRadius: 4,
                                                        border: "1px solid #00ff88",
                                                        background: "transparent",
                                                        color: "#00ff88",
                                                        cursor: "pointer",
                                                        fontSize: 12,
                                                        fontWeight: 600,
                                                        flexShrink: 0,
                                                        marginLeft: 8,
                                                    }}
                                                >
                                                    + Add
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                );
                            })()}
                        </div>

                        {/* Generate Invite */}
                        {selectedChain.studies.length > 0 && (
                            <div style={{ paddingTop: 16, borderTop: "1px solid #222" }}>
                                <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#888", textTransform: "uppercase", letterSpacing: 1 }}>
                                    Generate Invite Link
                                </h3>
                                <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
                                    <input
                                        type="text"
                                        placeholder="Participant ID (optional)"
                                        value={inviteParticipantId}
                                        onChange={(e) => setInviteParticipantId(e.target.value)}
                                        style={{ ...inputStyle, flex: 1 }}
                                    />
                                    <button
                                        onClick={handleGenerateInvite}
                                        disabled={generatingInvite}
                                        style={{
                                            ...secondaryButtonStyle,
                                            opacity: generatingInvite ? 0.5 : 1,
                                        }}
                                    >
                                        {generatingInvite ? "..." : "Generate"}
                                    </button>
                                </div>

                                {inviteLink && (
                                    <div style={{
                                        padding: 12,
                                        background: "rgba(0, 255, 136, 0.1)",
                                        border: "1px solid #00ff88",
                                        borderRadius: 8,
                                    }}>
                                        <div style={{ fontSize: 12, color: "#00ff88", marginBottom: 4 }}>
                                            Invite Link:
                                        </div>
                                        <input
                                            type="text"
                                            value={inviteLink}
                                            readOnly
                                            onClick={(e) => (e.target as HTMLInputElement).select()}
                                            style={{
                                                ...inputStyle,
                                                background: "transparent",
                                                border: "none",
                                                fontSize: 12,
                                            }}
                                        />
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                ) : (
                    <div style={{
                        ...cardStyle,
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        justifyContent: "center",
                        minHeight: 300,
                        textAlign: "center",
                    }}>
                        <div style={{ fontSize: 48, marginBottom: 16 }}>⛓️</div>
                        <h3 style={{ margin: 0, color: "#888" }}>Select or Create a Chain</h3>
                        <p style={{ color: "#555", fontSize: 13, maxWidth: 300 }}>
                            Chains let you link multiple experiments together so participants complete them in sequence.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
