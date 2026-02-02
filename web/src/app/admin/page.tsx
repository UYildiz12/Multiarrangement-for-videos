"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import ChainBuilder from "../components/ChainBuilder";

interface StudySummary {
    id: string;
    name: string;
    description?: string | null;
    paradigm: string;
    language: string;
    created_at: string;
    n_stimuli: number;
}

interface SessionSummary {
    id: string;
    participant_id: string;
    status: string;
    current_trial_index: number;
    started_at: string;
    completed_at?: string | null;
    n_trials: number;
}

interface ChainSession {
    chain_session_id: string;
    participant_id: string;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    current_position: number;
    sessions: {
        session_id: string;
        study_id: string;
        study_name: string;
        paradigm: string;
        status: string;
        n_trials: number;
        started_at: string | null;
    }[];
}

interface ChainSessionsData {
    chain_id: string;
    chain_name: string;
    total_studies: number;
    participants: ChainSession[];
}

type Tab = "studies" | "chains" | "settings";

export default function AdminPage() {
    const [adminSecret, setAdminSecret] = useState("");
    const [activeTab, setActiveTab] = useState<Tab>("studies");
    const [studies, setStudies] = useState<StudySummary[]>([]);
    const [sessions, setSessions] = useState<SessionSummary[]>([]);
    const [selectedStudyId, setSelectedStudyId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loadingStudies, setLoadingStudies] = useState(false);
    const [loadingSessions, setLoadingSessions] = useState(false);

    // Chain sessions state
    const [selectedChainId, setSelectedChainId] = useState<string | null>(null);
    const [chainSessions, setChainSessions] = useState<ChainSessionsData | null>(null);
    const [loadingChainSessions, setLoadingChainSessions] = useState(false);

    useEffect(() => {
        const saved = sessionStorage.getItem("adminSecret");
        if (saved) setAdminSecret(saved);
    }, []);

    const loadStudies = async () => {
        if (!adminSecret.trim()) {
            setError("Admin secret required.");
            return;
        }
        setError(null);
        setLoadingStudies(true);
        try {
            sessionStorage.setItem("adminSecret", adminSecret);
            const data = await apiFetch<StudySummary[]>("/api/v1/admin/studies", {
                headers: { "x-admin-secret": adminSecret },
            });
            setStudies(data);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to load studies";
            setError(msg);
        } finally {
            setLoadingStudies(false);
        }
    };

    const loadSessions = async (studyId: string) => {
        if (!adminSecret.trim()) {
            setError("Admin secret required.");
            return;
        }
        setError(null);
        setLoadingSessions(true);
        setSelectedStudyId(studyId);
        try {
            const data = await apiFetch<SessionSummary[]>(
                `/api/v1/admin/studies/${studyId}/sessions`,
                { headers: { "x-admin-secret": adminSecret } }
            );
            setSessions(data);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to load sessions";
            setError(msg);
        } finally {
            setLoadingSessions(false);
        }
    };

    const downloadResults = async (sessionId: string) => {
        try {
            const data = await apiFetch(`/api/v1/sessions/${sessionId}/results`);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `session_${sessionId}_results.json`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to download results";
            setError(msg);
        }
    };

    const deleteSession = async (sessionId: string) => {
        if (!confirm(`Delete session ${sessionId}? This cannot be undone.`)) return;
        try {
            await apiFetch(`/api/v1/admin/sessions/${sessionId}`, {
                method: "DELETE",
                headers: { "x-admin-secret": adminSecret },
            });
            setSessions(sessions.filter((s) => s.id !== sessionId));
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to delete session";
            setError(msg);
        }
    };

    const deleteStudy = async (studyId: string) => {
        if (!confirm(`Delete study ${studyId} and ALL its sessions? This cannot be undone.`)) return;
        try {
            await apiFetch(`/api/v1/admin/studies/${studyId}`, {
                method: "DELETE",
                headers: { "x-admin-secret": adminSecret },
            });
            setStudies(studies.filter((s) => s.id !== studyId));
            if (selectedStudyId === studyId) {
                setSelectedStudyId(null);
                setSessions([]);
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to delete study";
            setError(msg);
        }
    };

    const loadChainSessions = async (chainId: string) => {
        setLoadingChainSessions(true);
        setSelectedChainId(chainId);
        setError(null);
        try {
            const data = await apiFetch<ChainSessionsData>(`/api/v1/chains/${chainId}/sessions`);
            setChainSessions(data);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to load chain sessions";
            setError(msg);
        } finally {
            setLoadingChainSessions(false);
        }
    };

    const deleteChainSession = async (chainId: string, chainSessionId: string, participantId: string) => {
        if (!confirm(`Delete participant "${participantId}" and all their session data? This cannot be undone.`)) return;
        try {
            await apiFetch(`/api/v1/chains/${chainId}/sessions/${chainSessionId}`, {
                method: "DELETE",
            });
            // Reload chain sessions
            if (selectedChainId) {
                loadChainSessions(selectedChainId);
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to delete chain session";
            setError(msg);
        }
    };

    const tabStyle = (isActive: boolean) => ({
        padding: "12px 24px",
        background: isActive ? "#1a1a1a" : "transparent",
        border: "none",
        borderBottom: isActive ? "2px solid #00ff88" : "2px solid transparent",
        color: isActive ? "#fff" : "#666",
        fontWeight: isActive ? 600 : 400,
        fontSize: 14,
        cursor: "pointer",
        transition: "all 0.2s ease",
    });

    return (
        <div
            style={{
                minHeight: "100vh",
                background: "#000",
                color: "#fff",
                padding: 40,
                fontFamily: "'Inter', -apple-system, sans-serif",
                overflowY: "auto",
            }}
        >
            <div style={{ maxWidth: 1100, margin: "0 auto" }}>
                <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Admin Dashboard</h1>
                <p style={{ color: "#666", fontSize: 14, marginBottom: 24 }}>
                    Manage studies, chains, and view participant results.
                </p>

                {/* Admin Secret Input */}
                <div style={{ background: "#111", padding: 20, borderRadius: 8, marginBottom: 24 }}>
                    <label style={{ color: "#aaa", fontSize: 12, marginBottom: 6, display: "block" }}>
                        Admin Secret
                    </label>
                    <div style={{ display: "flex", gap: 8 }}>
                        <input
                            type="password"
                            value={adminSecret}
                            onChange={(e) => setAdminSecret(e.target.value)}
                            style={{
                                flex: 1,
                                padding: "8px 12px",
                                borderRadius: 4,
                                border: "1px solid #444",
                                background: "#1a1a1a",
                                color: "#fff",
                                fontSize: 14,
                            }}
                        />
                        <button
                            onClick={loadStudies}
                            disabled={loadingStudies}
                            style={{
                                padding: "8px 16px",
                                borderRadius: 6,
                                border: "1px solid #444",
                                background: "#1a1a1a",
                                color: "#fff",
                                cursor: loadingStudies ? "not-allowed" : "pointer",
                            }}
                        >
                            {loadingStudies ? "Loading..." : "Load Data"}
                        </button>
                    </div>
                    {error && (
                        <div style={{ marginTop: 8, color: "#ff6666", fontSize: 13 }}>
                            {error}
                        </div>
                    )}
                </div>

                {/* Tabs */}
                <div style={{ borderBottom: "1px solid #333", marginBottom: 24 }}>
                    <button
                        onClick={() => setActiveTab("studies")}
                        style={tabStyle(activeTab === "studies")}
                    >
                        Studies
                    </button>
                    <button
                        onClick={() => setActiveTab("chains")}
                        style={tabStyle(activeTab === "chains")}
                    >
                        Chains
                    </button>
                    <button
                        onClick={() => setActiveTab("settings")}
                        style={tabStyle(activeTab === "settings")}
                    >
                        Settings
                    </button>
                </div>

                {/* Tab Content */}
                {activeTab === "studies" && (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                        <div style={{ background: "#111", padding: 20, borderRadius: 8 }}>
                            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Studies</h2>
                            {studies.length === 0 ? (
                                <div style={{ color: "#666", fontSize: 13 }}>No studies loaded.</div>
                            ) : (
                                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                    {studies.map((study) => (
                                        <div
                                            key={study.id}
                                            style={{
                                                padding: 12,
                                                borderRadius: 6,
                                                border: `1px solid ${study.id === selectedStudyId ? "#00ff00" : "#333"}`,
                                                background: "#0a0a0a",
                                            }}
                                        >
                                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                                <button
                                                    onClick={() => loadSessions(study.id)}
                                                    style={{
                                                        textAlign: "left",
                                                        background: "transparent",
                                                        border: "none",
                                                        color: "#fff",
                                                        cursor: "pointer",
                                                        padding: 0,
                                                        flex: 1,
                                                    }}
                                                >
                                                    <div style={{ fontWeight: 600 }}>{study.name}</div>
                                                    <div style={{ fontSize: 12, color: "#666" }}>
                                                        {study.paradigm} • {study.n_stimuli} stimuli
                                                    </div>
                                                </button>
                                                <button
                                                    onClick={() => deleteStudy(study.id)}
                                                    style={{
                                                        padding: "0 12px",
                                                        height: 28,
                                                        borderRadius: 4,
                                                        border: "1px solid #ff4444",
                                                        background: "rgba(255, 68, 68, 0.1)",
                                                        color: "#ff4444",
                                                        cursor: "pointer",
                                                        fontSize: 12,
                                                        fontWeight: 500,
                                                    }}
                                                >
                                                    Delete
                                                </button>
                                            </div>
                                            <div style={{ fontSize: 10, color: "#444", marginTop: 4, fontFamily: "monospace" }}>
                                                ID: {study.id.slice(0, 8)}...
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        <div style={{ background: "#111", padding: 20, borderRadius: 8 }}>
                            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Sessions</h2>
                            {loadingSessions ? (
                                <div style={{ color: "#666", fontSize: 13 }}>Loading sessions...</div>
                            ) : sessions.length === 0 ? (
                                <div style={{ color: "#666", fontSize: 13 }}>Select a study to view sessions.</div>
                            ) : (
                                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                    {sessions.map((session) => (
                                        <div
                                            key={session.id}
                                            style={{
                                                padding: 12,
                                                borderRadius: 6,
                                                border: "1px solid #333",
                                                background: "#0a0a0a",
                                            }}
                                        >
                                            <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                                                <div>
                                                    <div style={{ fontWeight: 600 }}>{session.participant_id}</div>
                                                    <div style={{ fontSize: 12, color: "#666" }}>
                                                        {session.status} • {session.n_trials} trials
                                                    </div>
                                                </div>
                                                <div style={{ display: "flex", gap: 8 }}>
                                                    <a
                                                        href={`/results?session=${session.id}`}
                                                        style={{
                                                            padding: "0 12px",
                                                            height: 28,
                                                            borderRadius: 4,
                                                            border: "1px solid #00ff00",
                                                            background: "#0a2a0a",
                                                            color: "#00ff00",
                                                            textDecoration: "none",
                                                            fontSize: 12,
                                                            fontWeight: 500,
                                                            display: "flex",
                                                            alignItems: "center",
                                                        }}
                                                    >
                                                        View Results
                                                    </a>

                                                    <button
                                                        onClick={() => deleteSession(session.id)}
                                                        style={{
                                                            padding: "0 12px",
                                                            height: 28,
                                                            borderRadius: 4,
                                                            border: "1px solid #ff4444",
                                                            background: "rgba(255, 68, 68, 0.1)",
                                                            color: "#ff4444",
                                                            cursor: "pointer",
                                                            fontSize: 12,
                                                            fontWeight: 500,
                                                        }}
                                                    >
                                                        Delete
                                                    </button>
                                                </div>
                                            </div>
                                            <div style={{ fontSize: 11, color: "#555", marginTop: 6 }}>
                                                Started: {new Date(session.started_at).toLocaleString()}
                                            </div>
                                            <div style={{ fontSize: 10, color: "#444", marginTop: 2, fontFamily: "monospace" }}>
                                                ID: {session.id.slice(0, 8)}...
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {activeTab === "chains" && (
                    <div>
                        <ChainBuilder
                            onChainSelected={loadChainSessions}
                            adminSecret={adminSecret}
                        />

                        {/* Chain Sessions Viewer */}
                        {selectedChainId && (
                            <div style={{
                                marginTop: 24,
                                background: "#111",
                                padding: 20,
                                borderRadius: 12,
                                border: "1px solid #222"
                            }}>
                                <h3 style={{
                                    margin: "0 0 16px",
                                    fontSize: 16,
                                    fontWeight: 600,
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 8
                                }}>
                                    <span style={{ color: "#00ff88" }}>⛓</span>
                                    Chain Participants
                                    {chainSessions && (
                                        <span style={{
                                            fontSize: 12,
                                            color: "#666",
                                            fontWeight: 400
                                        }}>
                                            ({chainSessions.participants.length} participants)
                                        </span>
                                    )}
                                </h3>

                                {loadingChainSessions ? (
                                    <div style={{ color: "#666", fontSize: 13, padding: 20, textAlign: "center" }}>
                                        Loading chain sessions...
                                    </div>
                                ) : chainSessions && chainSessions.participants.length === 0 ? (
                                    <div style={{
                                        color: "#555",
                                        fontSize: 13,
                                        padding: 32,
                                        textAlign: "center",
                                        border: "1px dashed #333",
                                        borderRadius: 8
                                    }}>
                                        No participants have started this chain yet.
                                    </div>
                                ) : chainSessions && (
                                    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                                        {chainSessions.participants.map((participant) => (
                                            <div
                                                key={participant.chain_session_id}
                                                style={{
                                                    padding: 16,
                                                    borderRadius: 8,
                                                    border: "1px solid #333",
                                                    background: "#0a0a0a",
                                                }}
                                            >
                                                <div style={{
                                                    display: "flex",
                                                    justifyContent: "space-between",
                                                    alignItems: "center",
                                                    marginBottom: 12
                                                }}>
                                                    <div>
                                                        <div style={{ fontWeight: 600, fontSize: 14 }}>
                                                            {participant.participant_id}
                                                        </div>
                                                        <div style={{ fontSize: 12, color: "#666", marginTop: 2 }}>
                                                            Started: {participant.started_at ? new Date(participant.started_at).toLocaleString() : "N/A"}
                                                        </div>
                                                    </div>
                                                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                                                        {/* Progress indicator */}
                                                        <div style={{
                                                            padding: "4px 12px",
                                                            borderRadius: 12,
                                                            background: participant.status === "completed"
                                                                ? "rgba(0, 255, 136, 0.15)"
                                                                : "rgba(255, 200, 0, 0.15)",
                                                            color: participant.status === "completed" ? "#00ff88" : "#ffcc00",
                                                            fontSize: 12,
                                                            fontWeight: 500,
                                                        }}>
                                                            {participant.current_position}/{chainSessions.total_studies} studies
                                                            {participant.status === "completed" && " ✓"}
                                                        </div>
                                                        <span style={{
                                                            padding: "4px 10px",
                                                            borderRadius: 4,
                                                            background: participant.status === "completed"
                                                                ? "#0a2a0a"
                                                                : participant.status === "in_progress"
                                                                    ? "#2a2a0a"
                                                                    : "#2a0a0a",
                                                            color: participant.status === "completed"
                                                                ? "#00ff88"
                                                                : participant.status === "in_progress"
                                                                    ? "#ffcc00"
                                                                    : "#ff6666",
                                                            fontSize: 11,
                                                            textTransform: "uppercase",
                                                        }}>
                                                            {participant.status}
                                                        </span>
                                                        <button
                                                            onClick={() => deleteChainSession(
                                                                chainSessions.chain_id,
                                                                participant.chain_session_id,
                                                                participant.participant_id
                                                            )}
                                                            style={{
                                                                padding: "4px 10px",
                                                                borderRadius: 4,
                                                                border: "1px solid #ff4444",
                                                                background: "rgba(255, 68, 68, 0.1)",
                                                                color: "#ff4444",
                                                                cursor: "pointer",
                                                                fontSize: 11,
                                                                fontWeight: 500,
                                                            }}
                                                        >
                                                            Delete
                                                        </button>
                                                    </div>
                                                </div>

                                                {/* Individual sessions */}
                                                {participant.sessions.length > 0 && (
                                                    <div style={{
                                                        display: "flex",
                                                        flexWrap: "wrap",
                                                        gap: 8,
                                                        paddingTop: 12,
                                                        borderTop: "1px solid #222"
                                                    }}>
                                                        {participant.sessions.map((sess) => (
                                                            <a
                                                                key={sess.session_id}
                                                                href={`/results?session=${sess.session_id}`}
                                                                style={{
                                                                    padding: "6px 12px",
                                                                    borderRadius: 6,
                                                                    border: "1px solid #333",
                                                                    background: "#111",
                                                                    color: "#ccc",
                                                                    textDecoration: "none",
                                                                    fontSize: 12,
                                                                    display: "flex",
                                                                    alignItems: "center",
                                                                    gap: 6,
                                                                }}
                                                            >
                                                                <span style={{
                                                                    width: 8,
                                                                    height: 8,
                                                                    borderRadius: "50%",
                                                                    background: sess.status === "completed" ? "#00ff88" : "#ffcc00"
                                                                }} />
                                                                {sess.study_name}
                                                                <span style={{ color: "#555" }}>•</span>
                                                                <span style={{ color: "#666" }}>{sess.n_trials} trials</span>
                                                            </a>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {activeTab === "settings" && (
                    <div style={{ background: "#111", padding: 32, borderRadius: 12, textAlign: "center" }}>
                        <div style={{ fontSize: 48, marginBottom: 16 }}>⚙️</div>
                        <h3 style={{ margin: 0, color: "#888" }}>Settings</h3>
                        <p style={{ color: "#555", fontSize: 13, maxWidth: 400, margin: "12px auto 0" }}>
                            Admin configuration options will be available here in future updates.
                        </p>
                    </div>
                )}
            </div>
        </div >
    );
}

