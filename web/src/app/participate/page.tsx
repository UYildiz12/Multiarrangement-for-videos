"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { apiFetch } from "../lib/api";

interface StimulusResponse {
    id: string;
    ordinal: number;
    filename: string;
    media_type: "video" | "audio" | "image";
    media_url?: string | null;
    thumbnail_url?: string | null;
}

interface SessionStartResponse {
    session_id: string;
    study_id: string;
    stimuli: StimulusResponse[];
    config: Record<string, unknown>;
    paradigm: "setcover" | "adaptive" | "pairwise";
}

interface ChainSessionStartResponse {
    chain_session_id: string;
    chain_id: string;
    chain_name: string;
    total_studies: number;
    current_position: number;
    session_id: string;
    study_id: string;
    paradigm: "setcover" | "adaptive" | "pairwise";
    n_stimuli: number;
    stimuli: StimulusResponse[];
    config: Record<string, unknown>;
}

interface StudyResponse {
    id: string;
    instructions?: string[] | null;
    language?: "en" | "tr";
}

function LoadingFallback() {
    return (
        <div
            style={{
                minHeight: "100vh",
                background: "#000",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            Loading...
        </div>
    );
}

export default function ParticipatePage() {
    return (
        <Suspense fallback={<LoadingFallback />}>
            <ParticipateContent />
        </Suspense>
    );
}

function ParticipateContent() {
    const searchParams = useSearchParams();
    const router = useRouter();
    const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
    const [error, setError] = useState<string | null>(null);
    const inviteToken = searchParams.get("invite");
    const chainToken = searchParams.get("chain");
    const missingToken = !inviteToken && !chainToken;

    useEffect(() => {
        if (missingToken) return;

        let cancelled = false;

        const startSession = async () => {
            setStatus("loading");
            try {
                if (chainToken) {
                    // Handle chain invite
                    const chainSession = await apiFetch<ChainSessionStartResponse>(
                        `/api/v1/public/chain-invites/${chainToken}/start`,
                        { method: "POST" }
                    );

                    const stimuliForClient = chainSession.stimuli.map((s) => ({
                        id: s.id || `stim-${s.ordinal}`,
                        ordinal: s.ordinal,
                        label: s.filename,
                        mediaUrl: s.media_url || "",
                        mediaType: s.media_type,
                        thumbnail: s.thumbnail_url
                            || (s.media_type === "image"
                                ? (s.media_url || undefined)
                                : s.media_type === "audio"
                                    ? "/audio.png"
                                    : undefined),
                    }));

                    // Store chain info for experiment page (both sessionStorage and localStorage for persistence)
                    sessionStorage.setItem("chainToken", chainToken);
                    sessionStorage.setItem("chainSessionId", chainSession.chain_session_id);
                    sessionStorage.setItem("chainName", chainSession.chain_name);
                    sessionStorage.setItem("chainTotalStudies", String(chainSession.total_studies));
                    sessionStorage.setItem("chainCurrentPosition", String(chainSession.current_position));
                    // Also store in localStorage as backup for browser restart
                    localStorage.setItem("chainToken", chainToken);
                    localStorage.setItem("chainSessionId", chainSession.chain_session_id);
                    localStorage.setItem("chainName", chainSession.chain_name);
                    localStorage.setItem("chainTotalStudies", String(chainSession.total_studies));
                    localStorage.setItem("chainCurrentPosition", String(chainSession.current_position));
                    localStorage.setItem("chainCurrentStudySessionId", chainSession.session_id);

                    sessionStorage.setItem("experimentStimuli", JSON.stringify(stimuliForClient));
                    sessionStorage.setItem("experimentSessionId", chainSession.session_id);
                    sessionStorage.setItem("experimentStudyId", chainSession.study_id);
                    sessionStorage.setItem("experimentConfig", JSON.stringify({
                        ...(chainSession.config || {}),
                        paradigm: chainSession.paradigm,
                    }));
                    try {
                        const study = await apiFetch<StudyResponse>(`/api/v1/studies/${chainSession.study_id}`);
                        if (study.instructions && study.instructions.length > 0) {
                            sessionStorage.setItem("experimentInstructions", JSON.stringify(study.instructions));
                        } else {
                            sessionStorage.removeItem("experimentInstructions");
                        }
                        if (study.language === "en" || study.language === "tr") {
                            const storedConfig = sessionStorage.getItem("experimentConfig");
                            try {
                                const config = storedConfig ? JSON.parse(storedConfig) : {};
                                sessionStorage.setItem("experimentConfig", JSON.stringify({ ...config, language: study.language }));
                            } catch {
                                sessionStorage.setItem("experimentConfig", JSON.stringify({ language: study.language }));
                            }
                        }
                    } catch {
                        sessionStorage.removeItem("experimentInstructions");
                    }

                    if (!cancelled) {
                        router.push(`/experiment?session=${chainSession.session_id}`);
                    }
                } else if (inviteToken) {
                    // Handle regular invite
                    const session = await apiFetch<SessionStartResponse>(
                        `/api/v1/public/invites/${inviteToken}/start`,
                        { method: "POST" }
                    );

                    const stimuliForClient = session.stimuli.map((s) => ({
                        id: s.id || `stim-${s.ordinal}`,
                        ordinal: s.ordinal,
                        label: s.filename,
                        mediaUrl: s.media_url || "",
                        mediaType: s.media_type,
                        thumbnail: s.thumbnail_url
                            || (s.media_type === "image"
                                ? (s.media_url || undefined)
                                : s.media_type === "audio"
                                    ? "/audio.png"
                                    : undefined),
                    }));

                    // Clear any chain info
                    sessionStorage.removeItem("chainToken");
                    sessionStorage.removeItem("chainSessionId");
                    sessionStorage.removeItem("chainName");
                    sessionStorage.removeItem("chainTotalStudies");
                    sessionStorage.removeItem("chainCurrentPosition");
                    localStorage.removeItem("chainToken");
                    localStorage.removeItem("chainSessionId");
                    localStorage.removeItem("chainName");
                    localStorage.removeItem("chainTotalStudies");
                    localStorage.removeItem("chainCurrentPosition");
                    localStorage.removeItem("chainCurrentStudySessionId");

                    sessionStorage.setItem("experimentStimuli", JSON.stringify(stimuliForClient));
                    sessionStorage.setItem("experimentSessionId", session.session_id);
                    sessionStorage.setItem("experimentStudyId", session.study_id);
                    sessionStorage.setItem("experimentConfig", JSON.stringify({
                        ...(session.config || {}),
                        paradigm: session.paradigm,
                    }));
                    try {
                        const study = await apiFetch<StudyResponse>(`/api/v1/studies/${session.study_id}`);
                        if (study.instructions && study.instructions.length > 0) {
                            sessionStorage.setItem("experimentInstructions", JSON.stringify(study.instructions));
                        } else {
                            sessionStorage.removeItem("experimentInstructions");
                        }
                        if (study.language === "en" || study.language === "tr") {
                            const storedConfig = sessionStorage.getItem("experimentConfig");
                            try {
                                const config = storedConfig ? JSON.parse(storedConfig) : {};
                                sessionStorage.setItem("experimentConfig", JSON.stringify({ ...config, language: study.language }));
                            } catch {
                                sessionStorage.setItem("experimentConfig", JSON.stringify({ language: study.language }));
                            }
                        }
                    } catch {
                        sessionStorage.removeItem("experimentInstructions");
                    }

                    if (!cancelled) {
                        router.push(`/experiment?session=${session.session_id}`);
                    }
                }
            } catch (err) {
                if (cancelled) return;
                const msg = err instanceof Error ? err.message : "Failed to start session";
                setError(msg);
                setStatus("error");
            }
        };

        startSession();
        return () => {
            cancelled = true;
        };
    }, [inviteToken, chainToken, missingToken, router]);

    return (
        <div
            style={{
                minHeight: "100vh",
                background: "#000",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "'Inter', -apple-system, sans-serif",
                textAlign: "center",
                padding: 20,
            }}
        >
            {missingToken && <div style={{ color: "#ff6666" }}>Missing invite or chain token.</div>}
            {status === "loading" && <div>Starting your session...</div>}
            {status === "error" && <div style={{ color: "#ff6666" }}>{error}</div>}
        </div>
    );
}
