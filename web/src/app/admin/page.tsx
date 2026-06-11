"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "../lib/api";
import { useKey } from "../lib/KeyContext";
import { refreshOwnerData, setAdminStudies, useAdminStudies } from "../lib/ownerData";
import ChainBuilder from "../components/ChainBuilder";
import Link from "next/link";
import { EyeIcon, EyeOffIcon } from "../components/EyeIcon";
import TrialReconstruction, { TrialDetail } from "../components/TrialReconstruction";

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

interface StudyStimulus {
    id: string;
    ordinal: number;
    filename: string;
    media_type: "video" | "audio" | "image";
    media_url?: string | null;
    thumbnail_url?: string | null;
    media_storage_path?: string | null;
    thumbnail_storage_path?: string | null;
    duration_seconds?: number | null;
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

type Tab = "studies" | "chains";

export default function AdminPage() {
    return (
        <Suspense fallback={<div style={{ minHeight: "100vh", background: "#000", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center" }}>Loading...</div>}>
            <AdminContent />
        </Suspense>
    );
}

function AdminContent() {
    const searchParams = useSearchParams();
    const { adminKey, setAdminKey, isAuthenticated, isLocalBypass, authReady, generateKey, generating } = useKey();
    const [keyInput, setKeyInput] = useState("");
    const [showKey, setShowKey] = useState(false);
    const [copied, setCopied] = useState(false);
    const [justGenerated, setJustGenerated] = useState(false);
    const [activeTab, setActiveTab] = useState<Tab>("studies");
    const [studies, setStudies] = useState<StudySummary[]>([]);
    const [sessions, setSessions] = useState<SessionSummary[]>([]);
    const [selectedStudyId, setSelectedStudyId] = useState<string | null>(null);
    const [selectedStudyStimuli, setSelectedStudyStimuli] = useState<StudyStimulus[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [loadingStudies, setLoadingStudies] = useState(false);
    const [loadingSessions, setLoadingSessions] = useState(false);
    const [loadingStimuli, setLoadingStimuli] = useState(false);
    const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null);
    const [sessionTrials, setSessionTrials] = useState<Record<string, TrialDetail[]>>({});
    const [loadingTrialSessionId, setLoadingTrialSessionId] = useState<string | null>(null);

    // Chain sessions state
    const [selectedChainId, setSelectedChainId] = useState<string | null>(null);
    const [chainSessions, setChainSessions] = useState<ChainSessionsData | null>(null);
    const [loadingChainSessions, setLoadingChainSessions] = useState(false);
    const canFetchOwnerData = authReady && isAuthenticated;
    const {
        data: cachedStudies,
        error: cachedStudiesError,
        isLoading: cachedStudiesLoading,
    } = useAdminStudies(adminKey, canFetchOwnerData);
    const studiesBusy = loadingStudies || (canFetchOwnerData && cachedStudiesLoading && studies.length === 0);

    useEffect(() => {
        if (adminKey) setKeyInput(adminKey);
    }, [adminKey]);

    useEffect(() => {
        if (canFetchOwnerData && cachedStudies) {
            setStudies(cachedStudies);
        }
    }, [cachedStudies, canFetchOwnerData]);

    useEffect(() => {
        if (cachedStudiesError) {
            setError(describeAuthError(cachedStudiesError, "Failed to load studies"));
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [cachedStudiesError]);

    // Auto-select study from URL
    useEffect(() => {
        const studyFromUrl = searchParams.get("study");
        if (studyFromUrl && studies.length > 0) {
            loadSessions(studyFromUrl);
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [studies]);

    const handleKeySubmit = (e: React.FormEvent) => {
        e.preventDefault();
        setAdminKey(keyInput);
        loadStudies(keyInput);
    };

    const handleGenerate = async () => {
        try {
            const key = await generateKey();
            setKeyInput(key);
            setJustGenerated(true);
            setShowKey(true);
            setCopied(false);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to generate key");
        }
    };

    const handleCopyKey = () => {
        navigator.clipboard.writeText(keyInput || adminKey);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const buildKeyHeaders = (keyOverride?: string): Record<string, string> => {
        const key = (keyOverride ?? adminKey).trim();
        return key ? { "x-experimenter-key": key } : {};
    };

    const describeAuthError = (err: unknown, fallback: string, keyOverride?: string) => {
        const msg = err instanceof Error ? err.message : fallback;
        if (!msg.includes("API error 401")) {
            return msg;
        }
        const activeKey = (keyOverride ?? adminKey).trim();
        if (activeKey) {
            return msg;
        }
        return "Experimenter key required to log your experiments and share them online. We strongly recommend always immediately backing up your data.";
    };

    const loadStudies = async (key?: string) => {
        setError(null);
        setLoadingStudies(true);
        try {
            const data = await apiFetch<StudySummary[]>("/api/v1/admin/studies", {
                headers: buildKeyHeaders(key),
            });
            setStudies(data);
            setAdminStudies(key ?? adminKey, () => data);
        } catch (err) {
            setError(describeAuthError(err, "Failed to load studies", key));
        } finally {
            setLoadingStudies(false);
        }
    };

    const loadSessions = async (studyId: string) => {
        setError(null);
        setLoadingSessions(true);
        setLoadingStimuli(true);
        setSelectedStudyId(studyId);
        try {
            const [sessionData, stimulusData] = await Promise.all([
                apiFetch<SessionSummary[]>(
                    `/api/v1/admin/studies/${studyId}/sessions`,
                    { headers: buildKeyHeaders() }
                ),
                apiFetch<StudyStimulus[]>(
                    `/api/v1/studies/${studyId}/stimuli`,
                    { headers: buildKeyHeaders() }
                ),
            ]);
            setSessions(sessionData);
            setSelectedStudyStimuli(stimulusData);
        } catch (err) {
            setError(describeAuthError(err, "Failed to load sessions"));
        } finally {
            setLoadingSessions(false);
            setLoadingStimuli(false);
        }
    };

    const deleteSession = async (sessionId: string) => {
        if (!confirm(`Delete session ${sessionId}? This cannot be undone.`)) return;
        try {
            await apiFetch(`/api/v1/admin/sessions/${sessionId}`, {
                method: "DELETE",
                headers: buildKeyHeaders(),
            });
            setSessions(sessions.filter((s) => s.id !== sessionId));
        } catch (err) {
            setError(describeAuthError(err, "Failed to delete session"));
        }
    };

    const toggleSessionTrials = async (sessionId: string) => {
        if (expandedSessionId === sessionId) {
            setExpandedSessionId(null);
            return;
        }
        setExpandedSessionId(sessionId);
        if (sessionTrials[sessionId]) return;
        setLoadingTrialSessionId(sessionId);
        setError(null);
        try {
            const data = await apiFetch<TrialDetail[]>(`/api/v1/admin/sessions/${sessionId}/trials`, {
                headers: buildKeyHeaders(),
            });
            setSessionTrials((current) => ({ ...current, [sessionId]: data }));
        } catch (err) {
            setError(describeAuthError(err, "Failed to load trial reconstructions"));
        } finally {
            setLoadingTrialSessionId(null);
        }
    };

    const deleteStudy = async (studyId: string) => {
        if (!confirm(`Delete study ${studyId} and ALL its sessions? This cannot be undone.`)) return;
        try {
            await apiFetch(`/api/v1/admin/studies/${studyId}`, {
                method: "DELETE",
                headers: buildKeyHeaders(),
            });
            const nextStudies = studies.filter((s) => s.id !== studyId);
            setStudies(nextStudies);
            setAdminStudies(adminKey, () => nextStudies);
            refreshOwnerData(adminKey, isAuthenticated);
            if (selectedStudyId === studyId) {
                setSelectedStudyId(null);
                setSessions([]);
                setSelectedStudyStimuli([]);
            }
        } catch (err) {
            setError(describeAuthError(err, "Failed to delete study"));
        }
    };

    const loadChainSessions = async (chainId: string) => {
        setLoadingChainSessions(true);
        setSelectedChainId(chainId);
        setError(null);
        try {
            const data = await apiFetch<ChainSessionsData>(`/api/v1/chains/${chainId}/sessions`, {
                headers: buildKeyHeaders(),
            });
            setChainSessions(data);
        } catch (err) {
            setError(describeAuthError(err, "Failed to load chain sessions"));
        } finally {
            setLoadingChainSessions(false);
        }
    };

    const deleteChainSession = async (chainId: string, chainSessionId: string, participantId: string) => {
        if (!confirm(`Delete participant "${participantId}" and all their session data? This cannot be undone.`)) return;
        try {
            await apiFetch(`/api/v1/chains/${chainId}/sessions/${chainSessionId}`, {
                method: "DELETE",
                headers: buildKeyHeaders(),
            });
            // Reload chain sessions
            if (selectedChainId) {
                loadChainSessions(selectedChainId);
            }
        } catch (err) {
            setError(describeAuthError(err, "Failed to delete chain session"));
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

    const selectedStudy = studies.find((study) => study.id === selectedStudyId) ?? null;

    return (
        <div
            style={{
                minHeight: "calc(100vh - 56px)",
                background: "#000",
                color: "#fff",
                padding: 40,
                fontFamily: "'Inter', -apple-system, sans-serif",
                overflowY: "auto",
            }}
        >
            <div style={{ maxWidth: 1100, margin: "0 auto" }}>
                {/* Breadcrumb */}
                <div style={{ marginBottom: 8, fontSize: 13, color: "#555" }}>
                    <Link href="/" style={{ color: "#666", textDecoration: "none" }}>Dashboard</Link>
                    <span style={{ margin: "0 8px" }}>/</span>
                    <span style={{ color: "#fff" }}>Experimenter</span>
                </div>

                <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>Experimenter Panel</h1>
                <p style={{ color: "#666", fontSize: 14, marginBottom: 24 }}>
                    Manage studies, chains, and view participant results.
                </p>

                {!authReady ? (
                    <div style={{ background: "#111", padding: 24, borderRadius: 10, marginBottom: 24, color: "#888", fontSize: 13 }}>
                        Checking auth mode...
                    </div>
                ) : (
                    <>
                {/* Experimenter Key Input */}
                {!isAuthenticated ? (
                    <div style={{ background: "#111", padding: 24, borderRadius: 10, marginBottom: 24 }}>
                        <label style={{ color: "#aaa", fontSize: 12, marginBottom: 8, display: "block" }}>
                            Experimenter Key
                        </label>
                        <form onSubmit={handleKeySubmit} style={{ display: "flex", gap: 8 }}>
                            <input
                                type={showKey ? "text" : "password"}
                                value={keyInput}
                                onChange={(e) => { setKeyInput(e.target.value); setJustGenerated(false); }}
                                placeholder="Enter your experimenter key..."
                                style={{
                                    flex: 1,
                                    padding: "10px 14px",
                                    borderRadius: 8,
                                    border: "1px solid #444",
                                    background: "#1a1a1a",
                                    color: "#fff",
                                    fontSize: 14,
                                    fontFamily: justGenerated ? "monospace" : "inherit",
                                }}
                            />
                            <button
                                type="button"
                                onClick={() => setShowKey(!showKey)}
                                style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid #444", background: "#1a1a1a", color: "#888", cursor: "pointer", display: "flex", alignItems: "center" }}
                                title={showKey ? "Hide key" : "Show key"}
                            >
                                {showKey ? <EyeOffIcon size={18} color="#888" /> : <EyeIcon size={18} color="#888" />}
                            </button>
                            <button
                                type="submit"
                                disabled={studiesBusy}
                                style={{
                                    padding: "10px 20px",
                                    borderRadius: 8,
                                    border: "none",
                                    background: "linear-gradient(135deg, #00ff88 0%, #00cc66 100%)",
                                    color: "#000",
                                    fontWeight: 600,
                                    cursor: studiesBusy ? "not-allowed" : "pointer",
                                }}
                            >
                                {studiesBusy ? "Loading..." : "Enter"}
                            </button>
                        </form>

                        <div style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 12 }}>
                            <div style={{ flex: 1, height: 1, background: "#333" }} />
                            <span style={{ color: "#555", fontSize: 12 }}>or</span>
                            <div style={{ flex: 1, height: 1, background: "#333" }} />
                        </div>

                        <button
                            onClick={handleGenerate}
                            disabled={generating}
                            style={{
                                width: "100%",
                                marginTop: 16,
                                padding: "12px 24px",
                                borderRadius: 8,
                                border: "1px dashed #444",
                                background: "transparent",
                                color: "#aaa",
                                fontSize: 14,
                                cursor: generating ? "not-allowed" : "pointer",
                                transition: "all 0.2s ease",
                            }}
                        >
                            {generating ? "Generating..." : "Generate New Experimenter Key"}
                        </button>

                        {justGenerated && (
                            <div style={{
                                marginTop: 16,
                                background: "#1a1200",
                                border: "1px solid #554400",
                                borderRadius: 10,
                                padding: 16,
                            }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                                    <span style={{ fontSize: 16 }}>⚠️</span>
                                    <strong style={{ color: "#ffcc00", fontSize: 14 }}>Save Your Key!</strong>
                                </div>
                                <p style={{ color: "#cca700", fontSize: 13, margin: "0 0 12px", lineHeight: 1.5 }}>
                                    This key is your only way to access your experiments later.
                                    The server does not store it. Copy it somewhere safe now.
                                </p>
                                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                                    <code style={{
                                        flex: 1,
                                        padding: "10px 14px",
                                        background: "#0a0a0a",
                                        border: "1px solid #333",
                                        borderRadius: 8,
                                        color: "#00ff88",
                                        fontSize: 13,
                                        fontFamily: "monospace",
                                        wordBreak: "break-all",
                                    }}>
                                        {keyInput}
                                    </code>
                                    <button
                                        onClick={handleCopyKey}
                                        style={{
                                            padding: "10px 16px",
                                            borderRadius: 8,
                                            border: "1px solid #333",
                                            background: copied ? "#00ff88" : "#222",
                                            color: copied ? "#000" : "#fff",
                                            fontSize: 13,
                                            fontWeight: 600,
                                            cursor: "pointer",
                                            whiteSpace: "nowrap",
                                            transition: "all 0.2s",
                                        }}
                                    >
                                        {copied ? "✓ Copied" : "Copy"}
                                    </button>
                                </div>
                                <p style={{ color: "#887700", fontSize: 11, margin: "10px 0 0", fontStyle: "italic" }}>
                                    After copying, click &quot;Enter&quot; above to access your experiments.
                                </p>
                            </div>
                        )}

                        {error && (
                            <div style={{ marginTop: 12, color: "#ff6666", fontSize: 13 }}>
                                {error}
                            </div>
                        )}
                    </div>
                ) : (
                    <>
                    {isLocalBypass && !adminKey.trim() && (
                        <div style={{ marginBottom: 16, padding: 12, background: "rgba(0, 255, 136, 0.08)", border: "1px solid #1e5f45", borderRadius: 8, color: "#8ddfbf", fontSize: 13 }}>
                            Running in local keyless mode. Experimenter key entry is optional.
                        </div>
                    )}
                    {error && (
                        <div style={{ marginBottom: 16, padding: 12, background: "rgba(255,0,0,0.1)", border: "1px solid #f66", borderRadius: 8, color: "#f66", fontSize: 13 }}>
                            {error}
                        </div>
                    )
                    }
                    </>
                )}
                </>
                )}

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
                            <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Study Detail</h2>
                            {!selectedStudyId || !selectedStudy ? (
                                <div style={{ color: "#666", fontSize: 13 }}>Select a study to inspect its media and sessions.</div>
                            ) : (
                                <div style={{ display: "flex", flexDirection: "column", gap: 18, marginBottom: 18 }}>
                                    <div style={{ padding: 14, borderRadius: 8, background: "#0a0a0a", border: "1px solid #222" }}>
                                        <div style={{ fontWeight: 600, marginBottom: 4 }}>{selectedStudy.name}</div>
                                        <div style={{ fontSize: 12, color: "#666" }}>
                                            {selectedStudy.paradigm}{" \u2022 "}{selectedStudy.n_stimuli} stimuli
                                        </div>
                                        <div style={{ fontSize: 11, color: "#444", marginTop: 6, fontFamily: "monospace", wordBreak: "break-all" }}>
                                            {selectedStudy.id}
                                        </div>
                                    </div>

                                    <div>
                                        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Registered media</div>
                                        {loadingStimuli ? (
                                            <div style={{ color: "#666", fontSize: 13 }}>Loading media...</div>
                                        ) : selectedStudyStimuli.length === 0 ? (
                                            <div style={{ color: "#666", fontSize: 13 }}>No stimuli registered for this study.</div>
                                        ) : (
                                            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: 10 }}>
                                                {selectedStudyStimuli.map((stimulus) => {
                                                    const previewUrl = stimulus.thumbnail_url || stimulus.media_url || "";
                                                    const canPreview = Boolean(previewUrl) && (stimulus.media_type === "image" || stimulus.media_type === "video");
                                                    const storageLabel = stimulus.media_storage_path ? "Hosted" : "Bundled";
                                                    return (
                                                        <a
                                                            key={stimulus.id}
                                                            href={stimulus.media_url || "#"}
                                                            target={stimulus.media_url ? "_blank" : undefined}
                                                            rel={stimulus.media_url ? "noreferrer" : undefined}
                                                            style={{
                                                                display: "block",
                                                                padding: 10,
                                                                borderRadius: 8,
                                                                border: "1px solid #222",
                                                                background: "#0a0a0a",
                                                                textDecoration: "none",
                                                                color: "#fff",
                                                            }}
                                                        >
                                                            <div style={{
                                                                height: 84,
                                                                borderRadius: 6,
                                                                overflow: "hidden",
                                                                background: "#151515",
                                                                display: "flex",
                                                                alignItems: "center",
                                                                justifyContent: "center",
                                                                marginBottom: 8,
                                                            }}>
                                                                {canPreview ? (
                                                                    <div
                                                                        aria-label={stimulus.filename}
                                                                        role="img"
                                                                        style={{
                                                                            width: "100%",
                                                                            height: "100%",
                                                                            backgroundImage: `url("${previewUrl}")`,
                                                                            backgroundSize: "cover",
                                                                            backgroundPosition: "center",
                                                                            backgroundRepeat: "no-repeat",
                                                                        }}
                                                                    />
                                                                ) : (
                                                                    <div style={{ color: "#666", fontSize: 12, textTransform: "uppercase" }}>
                                                                        {stimulus.media_type}
                                                                    </div>
                                                                )}
                                                            </div>
                                                            <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                                                                {stimulus.filename}
                                                            </div>
                                                            <div style={{ fontSize: 11, color: "#666", marginBottom: 4 }}>
                                                                #{stimulus.ordinal}{" \u2022 "}{storageLabel}
                                                            </div>
                                                            <div style={{ fontSize: 10, color: "#444", fontFamily: "monospace", wordBreak: "break-all" }}>
                                                                {stimulus.media_storage_path || stimulus.media_url || "No media URL"}
                                                            </div>
                                                        </a>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>

                                    <div style={{ fontSize: 13, fontWeight: 600 }}>Sessions</div>
                                </div>
                            )}
                            {selectedStudyId && loadingSessions ? (
                                <div style={{ color: "#666", fontSize: 13 }}>Loading sessions...</div>
                            ) : sessions.length === 0 ? (
                                <div style={{ color: "#666", fontSize: 13 }}>
                                    {selectedStudyId ? "No participant sessions yet." : "Select a study to view sessions."}
                                </div>
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
                                                    <button
                                                        onClick={() => toggleSessionTrials(session.id)}
                                                        style={{
                                                            padding: "0 12px",
                                                            height: 28,
                                                            borderRadius: 4,
                                                            border: "1px solid #444",
                                                            background: expandedSessionId === session.id ? "#1a1a1a" : "#0a0a0a",
                                                            color: "#ddd",
                                                            cursor: "pointer",
                                                            fontSize: 12,
                                                            fontWeight: 500,
                                                        }}
                                                    >
                                                        {expandedSessionId === session.id ? "Hide Trials" : "Trials"}
                                                    </button>
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
                                            {expandedSessionId === session.id && (
                                                <div style={{ marginTop: 12 }}>
                                                    {loadingTrialSessionId === session.id ? (
                                                        <div style={{ color: "#666", fontSize: 12 }}>Loading exact trial reconstructions...</div>
                                                    ) : (
                                                        <TrialReconstruction
                                                            trials={sessionTrials[session.id] || []}
                                                            stimuli={selectedStudyStimuli}
                                                        />
                                                    )}
                                                </div>
                                            )}
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
                            adminSecret={adminKey}
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


            </div>
        </div >
    );
}
