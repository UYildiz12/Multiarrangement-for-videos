"use client";

import { useState, useCallback, useEffect } from "react";
import { apiFetch } from "../lib/api";

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

    // Load chains and studies
    useEffect(() => {
        let cancelled = false;
        const loadData = async () => {
            setLoading(true);
            try {
                const [chainsData] = await Promise.all([
                    apiFetch<Chain[]>("/api/v1/chains"),
                ]);
                if (!cancelled) {
                    setChains(chainsData);
                }
            } catch (err) {
                if (!cancelled) {
                    const msg = err instanceof Error ? err.message : "Failed to load data";
                    setError(msg);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        loadData();
        return () => { cancelled = true; };
    }, []);

    const handleCreateChain = useCallback(async () => {
        if (!newChainName.trim()) return;
        setCreating(true);
        setError(null);
        try {
            const chain = await apiFetch<Chain>("/api/v1/chains", {
                method: "POST",
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
            const msg = err instanceof Error ? err.message : "Failed to create chain";
            setError(msg);
        } finally {
            setCreating(false);
        }
    }, [newChainName, newChainDescription, onChainCreated]);

    const handleAddStudy = useCallback(async () => {
        if (!selectedChain || !selectedStudyId) return;
        try {
            const chainStudy = await apiFetch<ChainStudy>(
                `/api/v1/chains/${selectedChain.id}/studies`,
                {
                    method: "POST",
                    body: JSON.stringify({ study_id: selectedStudyId }),
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
            const msg = err instanceof Error ? err.message : "Failed to add study";
            setError(msg);
        }
    }, [selectedChain, selectedStudyId]);

    const handleRemoveStudy = useCallback(async (studyId: string) => {
        if (!selectedChain) return;
        try {
            await apiFetch(
                `/api/v1/chains/${selectedChain.id}/studies/${studyId}`,
                { method: "DELETE" }
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
            const msg = err instanceof Error ? err.message : "Failed to remove study";
            setError(msg);
        }
    }, [selectedChain]);

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
            const msg = err instanceof Error ? err.message : "Failed to generate invite";
            setError(msg);
        } finally {
            setGeneratingInvite(false);
        }
    }, [selectedChain, inviteParticipantId]);

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
                            <div style={{ display: "flex", gap: 8 }}>
                                <input
                                    type="text"
                                    placeholder="Enter Study ID (UUID)"
                                    value={selectedStudyId}
                                    onChange={(e) => setSelectedStudyId(e.target.value)}
                                    style={{ ...inputStyle, flex: 1 }}
                                />
                                <button
                                    onClick={handleAddStudy}
                                    disabled={!selectedStudyId}
                                    style={{
                                        ...buttonStyle,
                                        opacity: !selectedStudyId ? 0.5 : 1,
                                    }}
                                >
                                    Add
                                </button>
                            </div>
                            <p style={{ margin: "8px 0 0", fontSize: 12, color: "#555" }}>
                                Create studies in the Setup page first, then add them here by ID.
                            </p>
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
