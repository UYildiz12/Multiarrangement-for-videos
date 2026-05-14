"use client";

import { useState, useCallback, useEffect, useMemo, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import * as XLSX from "xlsx";
import DragArena from "../components/DragArena";
import PairwiseArena from "../components/PairwiseArena";
import RdmHeatmap from "../components/RdmHeatmap";
import MediaModal from "../components/MediaModal";
import { apiFetch } from "../lib/api";
import { deriveTrialAdvanceState } from "../lib/experimentHelpers";
import { getExperimentArenaSize } from "../lib/experimentDisplay";
import { getCachedMedia } from "../lib/mediaCache";

interface ResultsResponse {
    rdm: number[][];
    rdm_raw?: number[][] | null;
    rdm_scale?: {
        method: string;
        divisor: number;
        raw_units: string;
        description: string;
    };
    labels: string[];
    n_trials: number;
}

interface Position {
    x: number;
    y: number;
}

interface Stimulus {
    id: string;
    ordinal: number;
    label: string;
    mediaUrl: string;
    thumbnail?: string;
    mediaType: "video" | "audio" | "image";
}

interface NextTrialResponse {
    trial_index: number;
    subset_indices: number[];
    is_final: boolean;
}

interface TrialSubmitResponse {
    id: string;
    trial_index: number;
    subset_indices: number[];
    duration_seconds?: number | null;
    started_at: string;
    completed_at?: string | null;
    next_trial?: NextTrialResponse | null;
}

type Paradigm = "setcover" | "adaptive" | "pairwise";

interface SessionResponse {
    study_id: string;
    paradigm: Paradigm;
}

interface ServerStimulus {
    id: string;
    ordinal: number;
    filename: string;
    media_type: "video" | "audio" | "image";
    media_url?: string | null;
    thumbnail_url?: string | null;
}

interface StudyResponse {
    instructions?: string[] | null;
    language?: "en" | "tr";
}

function getStoredLanguage(): "en" | "tr" {
    if (typeof window === "undefined") return "en";
    try {
        const storedConfig = sessionStorage.getItem("experimentConfig");
        if (!storedConfig) return "en";
        const parsed = JSON.parse(storedConfig);
        return parsed?.language === "tr" ? "tr" : "en";
    } catch {
        return "en";
    }
}

async function captureVideoThumbnail(url: string): Promise<string | null> {
    return new Promise((resolve) => {
        const video = document.createElement("video");
        let settled = false;
        const finish = (value: string | null) => {
            if (settled) return;
            settled = true;
            window.clearTimeout(timeoutId);
            video.src = "";
            video.load();
            video.remove();
            resolve(value);
        };
        const timeoutId = window.setTimeout(() => finish(null), 2500);
        video.preload = "metadata";
        video.muted = true;
        video.crossOrigin = "anonymous";
        video.onloadedmetadata = () => {
            try {
                const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 1;
                const target = Math.min(0.1, Math.max(0, duration * 0.1));
                video.currentTime = target;
            } catch {
                finish(null);
            }
        };
        video.onseeked = () => {
            try {
                const canvas = document.createElement("canvas");
                const w = video.videoWidth || 160;
                const h = video.videoHeight || 90;
                canvas.width = 100;
                canvas.height = Math.max(60, Math.round((canvas.width * h) / w));
                const ctx = canvas.getContext("2d");
                if (!ctx) {
                    finish(null);
                    return;
                }
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataUrl = canvas.toDataURL("image/jpeg", 0.7);
                finish(dataUrl);
            } catch {
                finish(null);
            }
        };
        video.onerror = () => finish(null);
        video.src = url;
    });
}

function LoadingFallback() {
    const lang = getStoredLanguage();
    return (
        <div
            style={{
                minHeight: "100vh",
                background: "#000",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            {lang === "tr" ? "Yükleniyor..." : "Loading..."}
        </div>
    );
}

export default function ExperimentPage() {
    return (
        <Suspense fallback={<LoadingFallback />}>
            <ExperimentContent />
        </Suspense>
    );
}

function ExperimentContent() {
    const searchParams = useSearchParams();
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [studyId, setStudyId] = useState<string | null>(null);
    const [stimuli, setStimuli] = useState<Stimulus[]>([]);
    const [subsetIndices, setSubsetIndices] = useState<number[]>([]);
    const [trialIndex, setTrialIndex] = useState(0);
    const [totalTrials, setTotalTrials] = useState(0);
    const [isFinal, setIsFinal] = useState(false);
    const [loadingTrial, setLoadingTrial] = useState(false);
    const [loadingSession, setLoadingSession] = useState(false);
    const [submittingTrial, setSubmittingTrial] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [paradigm, setParadigm] = useState<Paradigm>("setcover");
    const [instructions, setInstructions] = useState<string[]>([]);
    const [showInstructions, setShowInstructions] = useState(true);
    const [language, setLanguage] = useState<"en" | "tr">("en");

    const [allInside, setAllInside] = useState(false);
    const [positions, setPositions] = useState<Record<string, Position>>({});
    const [playedItems, setPlayedItems] = useState<Set<string>>(new Set());
    const [trialStartedAt, setTrialStartedAt] = useState<number | null>(null);

    const [mediaModalOpen, setMediaModalOpen] = useState(false);
    const [currentMedia, setCurrentMedia] = useState<{ url: string; type: Stimulus["mediaType"] } | null>(null);
    const [results, setResults] = useState<ResultsResponse | null>(null);
    const [loadingResults, setLoadingResults] = useState(false);
    const [arenaSize, setArenaSize] = useState(600);

    // Chain state
    const hydrationDoneRef = useRef(false);
    const hydrationKeyRef = useRef<string | null>(null);
    const submittingTrialRef = useRef(false);
    const [chainToken, setChainToken] = useState<string | null>(null);
    const [chainName, setChainName] = useState<string | null>(null);
    const [chainTotalStudies, setChainTotalStudies] = useState<number>(0);
    const [chainCurrentPosition, setChainCurrentPosition] = useState<number>(0);
    const [loadingNextStudy, setLoadingNextStudy] = useState(false);
    const [sessionStartAt, setSessionStartAt] = useState<number | null>(null);
    const [sessionEndAt, setSessionEndAt] = useState<number | null>(null);

    const copy = useMemo(() => {
        const tr = language === "tr";
        return {
            noSession: tr ? "Oturum yüklenmedi." : "No session loaded.",
            goToSetup: tr ? "Kurulum'a git" : "Go to Setup",
            loadingNextTrial: tr ? "Sonraki aşama yükleniyor..." : "Loading next trial...",
            preparingTrial: tr ? "Aşama hazırlanıyor..." : "Preparing trial...",
            experimentComplete: tr ? "Deney tamamlandı" : "Experiment complete",
            thanks: tr ? "Katıldığınız için teşekkürler." : "Thank you for participating.",
            partOf: (name: string | null) => (tr ? `Seri: ${name ?? ""}` : `Part of: ${name ?? ""}`),
            studyComplete: (pos: number, total: number) => (
                tr ? `Çalışma ${pos} / ${total} tamamlandı` : `Study ${pos} of ${total} complete`
            ),
            loading: tr ? "Yükleniyor..." : "Loading...",
            loadingResults: tr ? "Sonuçlar yükleniyor..." : "Loading results...",
            continueToStudy: (n: number) => (
                tr ? `Çalışma ${n} için devam →` : `Continue to Study ${n} →`
            ),
            instructionsTitle: tr ? "Talimatlar" : "Instructions",
            hide: tr ? "Gizle" : "Hide",
            showInstructions: tr ? "Talimatları göster" : "Show instructions",
            trial: tr ? "Aşama" : "Trial",
            batch: tr ? "Grup" : "Batch",
            allInside: tr ? "✓ Hepsi içeride" : "✓ All inside",
            moveItems: tr ? "⚠ Öğeleri dairenin içine taşıyın" : "⚠ Move items into circle",
            loadStimuliError: tr ? "Uyaranlar yüklenemedi" : "Failed to load stimuli",
            loadTrialError: tr ? "Aşama yüklenemedi" : "Failed to load trial",
            submitTrialError: tr ? "Aşama gönderilemedi" : "Failed to submit trial",
            loadNextStudyError: tr ? "Sonraki çalışma yüklenemedi" : "Failed to load next study",
        };
    }, [language]);

    useEffect(() => {
        const fromQuery = searchParams.get("session");
        const stored = sessionStorage.getItem("experimentSessionId");
        const resolvedSessionId = fromQuery || stored;
        if (fromQuery && stored && fromQuery !== stored) {
            // New session in query params: clear stale per-session cache.
            sessionStorage.removeItem("experimentStimuli");
            sessionStorage.removeItem("experimentStudyId");
            sessionStorage.removeItem("experimentInstructions");
            sessionStorage.setItem("experimentSessionId", fromQuery);
            hydrationDoneRef.current = false;
            hydrationKeyRef.current = null;
        }
        setSessionId(resolvedSessionId);
        const storedStudyId = sessionStorage.getItem("experimentStudyId");
        if (storedStudyId && resolvedSessionId === sessionStorage.getItem("experimentSessionId")) {
            setStudyId(storedStudyId);
        }

        // Load chain info if present (check sessionStorage first, then localStorage as backup)
        let storedChainToken = sessionStorage.getItem("chainToken");
        let storedChainName = sessionStorage.getItem("chainName");
        let storedChainTotal = sessionStorage.getItem("chainTotalStudies");
        let storedChainPosition = sessionStorage.getItem("chainCurrentPosition");

        // Only use localStorage backup when it belongs to this exact study session.
        const localChainSessionId = localStorage.getItem("chainCurrentStudySessionId");
        if (!storedChainToken && resolvedSessionId && localChainSessionId === resolvedSessionId) {
            storedChainToken = localStorage.getItem("chainToken");
            storedChainName = localStorage.getItem("chainName");
            storedChainTotal = localStorage.getItem("chainTotalStudies");
            storedChainPosition = localStorage.getItem("chainCurrentPosition");
        }

        if (storedChainToken) {
            setChainToken(storedChainToken);
            setChainName(storedChainName);
            setChainTotalStudies(parseInt(storedChainTotal || "0", 10));
            setChainCurrentPosition(parseInt(storedChainPosition || "0", 10));
        } else {
            setChainToken(null);
            setChainName(null);
            setChainTotalStudies(0);
            setChainCurrentPosition(0);
        }
    }, [searchParams]);

    useEffect(() => {
        if (!sessionId) return;
        const key = `experimentTime_${sessionId}`;
        const stored = sessionStorage.getItem(key);
        if (!stored) {
            setSessionStartAt(null);
            setSessionEndAt(null);
            return;
        }
        try {
            const parsed = JSON.parse(stored) as { start?: number; end?: number };
            setSessionStartAt(typeof parsed.start === "number" ? parsed.start : null);
            setSessionEndAt(typeof parsed.end === "number" ? parsed.end : null);
        } catch {
            setSessionStartAt(null);
            setSessionEndAt(null);
        }
    }, [sessionId]);

    useEffect(() => {
        if (!sessionId) return;
        const storedSessionId = sessionStorage.getItem("experimentSessionId");
        const canUseCache = storedSessionId === sessionId;
        if (!canUseCache) {
            setStimuli([]);
            setInstructions([]);
            setShowInstructions(false);
            return;
        }

        const storedStimuli = sessionStorage.getItem("experimentStimuli");
        if (storedStimuli) {
            try {
                const parsed = JSON.parse(storedStimuli) as Stimulus[];
                setStimuli(parsed);
            } catch {
                setStimuli([]);
            }
        } else {
            setStimuli([]);
        }
        const storedInstructions = sessionStorage.getItem("experimentInstructions");
        if (storedInstructions) {
            try {
                const parsed = JSON.parse(storedInstructions) as string[];
                if (Array.isArray(parsed)) {
                    setInstructions(parsed);
                    setShowInstructions(parsed.length > 0);
                }
            } catch {
                setInstructions([]);
                setShowInstructions(false);
            }
        } else {
            setInstructions([]);
            setShowInstructions(false);
        }
        const storedConfig = sessionStorage.getItem("experimentConfig");
        if (storedConfig) {
            try {
                const config = JSON.parse(storedConfig);
                if (config.paradigm) setParadigm(config.paradigm);
                if (config.language === "en" || config.language === "tr") {
                    setLanguage(config.language);
                }
            } catch {
                // ignore
            }
        }
    }, [sessionId]);

    useEffect(() => {
        if (paradigm !== "pairwise" || stimuli.length === 0) return;
        const n = stimuli.length;
        setTotalTrials((n * (n - 1)) / 2);
    }, [paradigm, stimuli.length]);

    useEffect(() => {
        if (!studyId || instructions.length > 0) return;
        let cancelled = false;
        const loadStudy = async () => {
            try {
                const study = await apiFetch<StudyResponse>(`/api/v1/studies/${studyId}`);
                const list = Array.isArray(study.instructions) ? study.instructions : [];
                if (cancelled) return;
                if (study.language === "en" || study.language === "tr") {
                    setLanguage(study.language);
                    const storedConfig = sessionStorage.getItem("experimentConfig");
                    try {
                        const config = storedConfig ? JSON.parse(storedConfig) : {};
                        sessionStorage.setItem("experimentConfig", JSON.stringify({ ...config, language: study.language }));
                    } catch {
                        sessionStorage.setItem("experimentConfig", JSON.stringify({ language: study.language }));
                    }
                }
                if (list.length > 0) {
                    setInstructions(list);
                    setShowInstructions(true);
                    sessionStorage.setItem("experimentInstructions", JSON.stringify(list));
                } else {
                    setInstructions([]);
                    setShowInstructions(false);
                    sessionStorage.removeItem("experimentInstructions");
                }
            } catch {
                if (!cancelled) {
                    setShowInstructions(false);
                }
            }
        };
        loadStudy();
        return () => {
            cancelled = true;
        };
    }, [studyId, instructions.length]);


    useEffect(() => {
        if (!sessionId) return;
        let cancelled = false;
        const loadFromServer = async () => {
            setLoadingSession(true);
            setError(null);
            setStimuli([]);
            setSubsetIndices([]);
            setTrialIndex(0);
            setIsFinal(false);
            setResults(null);
            try {
                const session = await apiFetch<SessionResponse>(`/api/v1/sessions/${sessionId}`);
                setStudyId(session.study_id);
                sessionStorage.setItem("experimentSessionId", sessionId);
                sessionStorage.setItem("experimentStudyId", session.study_id);
                const serverStimuli = await apiFetch<ServerStimulus[]>(`/api/v1/studies/${session.study_id}/stimuli`);

                // Merge with cached stimuli — demo sessions return empty media_url from server.
                // Prefer cached mediaUrl/thumbnail so the frontend-provided video URLs survive.
                const cachedRaw = sessionStorage.getItem("experimentStimuli");
                const cachedByOrdinal: Record<number, Stimulus> = {};
                if (cachedRaw) {
                    try {
                        (JSON.parse(cachedRaw) as Stimulus[]).forEach((c) => { cachedByOrdinal[c.ordinal] = c; });
                    } catch { /* ignore */ }
                }

                const mapped = serverStimuli.map((s) => {
                    const cached = cachedByOrdinal[s.ordinal];
                    const mediaUrl = s.media_url || cached?.mediaUrl || "";
                    const thumbnail = s.thumbnail_url
                        || (s.media_type === "image" ? (s.media_url || undefined) : (s.media_type === "audio" ? "/audio.png" : undefined))
                        || cached?.thumbnail;
                    const label = (s.filename && !s.filename.startsWith("Stimulus "))
                        ? s.filename
                        : (cached?.label || s.filename);
                    return { id: s.id || `stim-${s.ordinal}`, ordinal: s.ordinal, label, mediaUrl, mediaType: s.media_type, thumbnail };
                });

                if (!cancelled) {
                    setStimuli(mapped);
                    setParadigm(session.paradigm);
                    sessionStorage.setItem("experimentStimuli", JSON.stringify(mapped));
                }
            } catch (err) {
                const msg = err instanceof Error ? err.message : "Failed to load stimuli";
                if (!cancelled) setError(msg);
            } finally {
                if (!cancelled) setLoadingSession(false);
            }
        };
        loadFromServer();
        return () => {
            cancelled = true;
        };
    }, [sessionId]);

    useEffect(() => {
        if (!sessionId || stimuli.length === 0) return;
        if (!stimuli.some((s) => !s.mediaUrl)) return;
        let cancelled = false;
        const refresh = async () => {
            try {
                const session = await apiFetch<SessionResponse>(`/api/v1/sessions/${sessionId}`);
                setStudyId(session.study_id);
                const serverStimuli = await apiFetch<ServerStimulus[]>(`/api/v1/studies/${session.study_id}/stimuli`);

                // Same merge logic: prefer cached media URLs over empty server values.
                const cachedRaw = sessionStorage.getItem("experimentStimuli");
                const cachedByOrdinal: Record<number, Stimulus> = {};
                if (cachedRaw) {
                    try {
                        (JSON.parse(cachedRaw) as Stimulus[]).forEach((c) => { cachedByOrdinal[c.ordinal] = c; });
                    } catch { /* ignore */ }
                }

                const mapped = serverStimuli.map((s) => {
                    const cached = cachedByOrdinal[s.ordinal];
                    const mediaUrl = s.media_url || cached?.mediaUrl || "";
                    const thumbnail = s.thumbnail_url
                        || (s.media_type === "image" ? (s.media_url || undefined) : (s.media_type === "audio" ? "/audio.png" : undefined))
                        || cached?.thumbnail;
                    const label = (s.filename && !s.filename.startsWith("Stimulus "))
                        ? s.filename
                        : (cached?.label || s.filename);
                    return { id: s.id || `stim-${s.ordinal}`, ordinal: s.ordinal, label, mediaUrl, mediaType: s.media_type, thumbnail };
                });

                if (!cancelled) {
                    setStimuli(mapped);
                    setParadigm(session.paradigm);
                    sessionStorage.setItem("experimentStimuli", JSON.stringify(mapped));
                }
            } catch {
                // ignore refresh errors
            }
        };
        refresh();
        return () => {
            cancelled = true;
        };
    }, [sessionId, stimuli]);

    useEffect(() => {
        const updateArenaSize = () => {
            setArenaSize(getExperimentArenaSize(window.innerWidth, window.innerHeight, subsetIndices.length || stimuli.length));
        };
        updateArenaSize();
        window.addEventListener("resize", updateArenaSize);
        return () => window.removeEventListener("resize", updateArenaSize);
    }, [stimuli.length, subsetIndices.length]);

    useEffect(() => {
        if (stimuli.length === 0 || hydrationDoneRef.current) return;
        const hydrationKey = stimuli.map((s) => s.id).join(",");
        if (hydrationKeyRef.current === hydrationKey) return;
        hydrationKeyRef.current = hydrationKey;
        let cancelled = false;
        const hydrate = async () => {
            for (const s of stimuli) {
                if (cancelled) return;
                let changed = false;
                let mediaUrl = s.mediaUrl;
                let thumbnail = s.thumbnail;

                if (!mediaUrl || mediaUrl.startsWith("blob:")) {
                    const cached = await getCachedMedia(s.label);
                    if (cached) {
                        mediaUrl = URL.createObjectURL(cached.blob);
                        if (!thumbnail && cached.thumbnail) {
                            thumbnail = cached.thumbnail;
                        }
                        changed = true;
                    }
                }

                if (!thumbnail && s.mediaType === "video" && mediaUrl) {
                    const captured = await captureVideoThumbnail(mediaUrl);
                    if (captured) {
                        thumbnail = captured;
                        changed = true;
                    }
                }

                if (changed && !cancelled) {
                    setStimuli((current) => current.map((item) => (
                        item.id === s.id ? { ...item, mediaUrl, thumbnail } : item
                    )));
                }
            }
            if (!cancelled) hydrationDoneRef.current = true;
        };
        hydrate();
        return () => {
            cancelled = true;
        };
    }, [stimuli]);

    const applyNextTrial = useCallback((next: NextTrialResponse) => {
        const now = Date.now();
        const nextState = deriveTrialAdvanceState(next, now, sessionStartAt);
        setTrialIndex(nextState.trialIndex);
        setIsFinal(nextState.isFinal);
        setSubsetIndices(nextState.subsetIndices);
        setTrialStartedAt(nextState.trialStartedAt);
        if (nextState.sessionStartAt !== sessionStartAt) {
            setSessionStartAt(nextState.sessionStartAt);
        }
        setPlayedItems(new Set());
        setPositions({});
        setAllInside(false);
    }, [sessionStartAt]);

    const loadNextTrial = useCallback(async () => {
        if (!sessionId) return;
        setLoadingTrial(true);
        setError(null);
        try {
            const next = await apiFetch<NextTrialResponse>(`/api/v1/sessions/${sessionId}/next`);
            applyNextTrial(next);
        } catch (err) {
            const msg = err instanceof Error ? err.message : copy.loadTrialError;
            setError(msg);
        } finally {
            setLoadingTrial(false);
        }
    }, [sessionId, copy, applyNextTrial]);

    useEffect(() => {
        if (sessionId && stimuli.length > 0) {
            loadNextTrial();
        }
    }, [sessionId, stimuli.length, loadNextTrial]);

    useEffect(() => {
        if (!sessionId || !isFinal) return;
        if (sessionStartAt !== null && sessionEndAt === null) {
            const end = Date.now();
            setSessionEndAt(end);
            const key = `experimentTime_${sessionId}`;
            sessionStorage.setItem(key, JSON.stringify({ start: sessionStartAt, end }));
        }
        apiFetch(`/api/v1/sessions/${sessionId}/complete`, { method: "POST" }).catch(() => {
            // ignore completion errors for now
        });
    }, [sessionId, isFinal, sessionStartAt, sessionEndAt]);

    const currentStimuli = useMemo(
        () => subsetIndices.map((i) => stimuli[i]).filter(Boolean),
        [subsetIndices, stimuli]
    );

    const hasInstructions = instructions.length > 0;

    const handleMediaPlay = useCallback((itemId: string, mediaUrl: string, mediaType: Stimulus["mediaType"]) => {
        setCurrentMedia({ url: mediaUrl, type: mediaType });
        setMediaModalOpen(true);
        setPlayedItems((prev) => new Set(prev).add(itemId));
    }, []);

    const handleMediaClose = useCallback(() => {
        setMediaModalOpen(false);
        setCurrentMedia(null);
    }, []);

    const handleSubmit = useCallback(async () => {
        if (!sessionId || subsetIndices.length === 0) return;
        if (submittingTrialRef.current) return;
        submittingTrialRef.current = true;
        setSubmittingTrial(true);
        setError(null);
        const durationSeconds = trialStartedAt ? (Date.now() - trialStartedAt) / 1000 : 0;

        try {
            const response = await apiFetch<TrialSubmitResponse>(`/api/v1/sessions/${sessionId}/trials`, {
                method: "POST",
                body: JSON.stringify({
                    trial_index: trialIndex,
                    subset_indices: subsetIndices,
                    positions,
                    duration_seconds: durationSeconds,
                }),
            });
            if (response.next_trial) {
                applyNextTrial(response.next_trial);
            } else {
                await loadNextTrial();
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : copy.submitTrialError;
            setError(msg);
        } finally {
            submittingTrialRef.current = false;
            setSubmittingTrial(false);
        }
    }, [sessionId, subsetIndices, positions, trialStartedAt, trialIndex, loadNextTrial, applyNextTrial, copy]);

    const handlePairwiseSubmit = useCallback(async (rating: number) => {
        if (!sessionId || subsetIndices.length !== 2) return;
        if (submittingTrialRef.current) return;
        submittingTrialRef.current = true;
        setSubmittingTrial(true);
        setError(null);
        const durationSeconds = trialStartedAt ? (Date.now() - trialStartedAt) / 1000 : 0;

        try {
            const response = await apiFetch<TrialSubmitResponse>(`/api/v1/sessions/${sessionId}/trials`, {
                method: "POST",
                body: JSON.stringify({
                    trial_index: trialIndex,
                    subset_indices: subsetIndices,
                    rating,
                    duration_seconds: durationSeconds,
                }),
            });
            if (response.next_trial) {
                applyNextTrial(response.next_trial);
            } else {
                await loadNextTrial();
            }
        } catch (err) {
            const msg = err instanceof Error ? err.message : copy.submitTrialError;
            setError(msg);
        } finally {
            submittingTrialRef.current = false;
            setSubmittingTrial(false);
        }
    }, [sessionId, subsetIndices, trialStartedAt, trialIndex, loadNextTrial, applyNextTrial, copy]);

    // Fetch results when experiment is complete
    useEffect(() => {
        if (isFinal && sessionId && !results && !loadingResults) {
            setLoadingResults(true);
            apiFetch<ResultsResponse>(`/api/v1/sessions/${sessionId}/results`)
                .then((data) => setResults(data))
                .catch(() => setResults(null))
                .finally(() => setLoadingResults(false));
        }
    }, [isFinal, sessionId, results, loadingResults]);

    const timeInfo = useMemo(() => {
        if (sessionStartAt === null) return { seconds: null, startIso: null, endIso: null };
        const end = sessionEndAt ?? Date.now();
        const seconds = Math.max(0, (end - sessionStartAt) / 1000);
        return {
            seconds,
            startIso: new Date(sessionStartAt).toISOString(),
            endIso: new Date(end).toISOString(),
        };
    }, [sessionStartAt, sessionEndAt]);

    const handleDownloadResults = useCallback(() => {
        if (!results) return;
        const payload = {
            ...results,
            time_spent_seconds: timeInfo.seconds,
            time_spent_minutes: timeInfo.seconds === null ? null : timeInfo.seconds / 60,
            time_started_at: timeInfo.startIso,
            time_ended_at: timeInfo.endIso,
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `session_${sessionId}_results.json`;
        a.click();
        URL.revokeObjectURL(url);
    }, [results, sessionId, timeInfo]);

    const handleDownloadCSV = useCallback(() => {
        if (!results) return;
        const { rdm, labels } = results;
        const header = ["", ...labels].join(",");
        const rows = rdm.map((row, i) => [labels[i], ...row.map(v => v.toFixed(4))].join(","));
        const metaLines = [
            `# rdm_scale_method,${results.rdm_scale?.method ?? ""}`,
            `# rdm_scale_divisor,${results.rdm_scale?.divisor ?? ""}`,
            `# rdm_raw_units,${results.rdm_scale?.raw_units ?? ""}`,
            `# time_spent_seconds,${timeInfo.seconds ?? ""}`,
            `# time_spent_minutes,${timeInfo.seconds === null ? "" : (timeInfo.seconds / 60).toFixed(2)}`,
            `# time_started_at,${timeInfo.startIso ?? ""}`,
            `# time_ended_at,${timeInfo.endIso ?? ""}`,
            "",
        ];
        const csv = [...metaLines, header, ...rows].join("\n");
        const blob = new Blob([csv], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `session_${sessionId}_rdm.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }, [results, sessionId, timeInfo]);

    const handleDownloadXLSX = useCallback(() => {
        if (!results) return;
        const { rdm, labels } = results;
        const wsData = [["Video", ...labels], ...rdm.map((row, i) => [labels[i], ...row])];
        const ws = XLSX.utils.aoa_to_sheet(wsData);
        const wb = XLSX.utils.book_new();
        const metaData = [
            ["rdm_scale_method", results.rdm_scale?.method ?? ""],
            ["rdm_scale_divisor", results.rdm_scale?.divisor ?? ""],
            ["rdm_raw_units", results.rdm_scale?.raw_units ?? ""],
            ["time_spent_seconds", timeInfo.seconds ?? ""],
            ["time_spent_minutes", timeInfo.seconds === null ? "" : (timeInfo.seconds / 60).toFixed(2)],
            ["time_started_at", timeInfo.startIso ?? ""],
            ["time_ended_at", timeInfo.endIso ?? ""],
        ];
        const metaWs = XLSX.utils.aoa_to_sheet(metaData);
        XLSX.utils.book_append_sheet(wb, metaWs, "Meta");
        XLSX.utils.book_append_sheet(wb, ws, "RDM");
        XLSX.writeFile(wb, `session_${sessionId}_rdm.xlsx`);
    }, [results, sessionId, timeInfo]);

    if (!sessionId) {
        return (
            <div
                style={{
                    minHeight: "100vh",
                    background: "#000",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontFamily: "'Inter', -apple-system, sans-serif",
                }}
            >
                <div style={{ textAlign: "center" }}>
                    <p style={{ marginBottom: 16 }}>{copy.noSession}</p>
                    <a href="/setup" style={{ color: "#00ff00" }}>
                        {copy.goToSetup}
                    </a>
                </div>
            </div>
        );
    }

    if (loadingSession) {
        return (
            <div
                style={{
                    minHeight: "100vh",
                    background: "#000",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontFamily: "'Inter', -apple-system, sans-serif",
                }}
            >
                {copy.loading}
            </div>
        );
    }

    if (stimuli.length === 0) {
        return (
            <div
                style={{
                    minHeight: "100vh",
                    background: "#000",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontFamily: "'Inter', -apple-system, sans-serif",
                }}
            >
                <div style={{ textAlign: "center" }}>
                    <p style={{ marginBottom: 16 }}>{error || copy.loadStimuliError}</p>
                    <a href="/setup" style={{ color: "#00ff00" }}>
                        {copy.goToSetup}
                    </a>
                </div>
            </div>
        );
    }

    if (loadingTrial) {
        return (
            <div
                style={{
                    minHeight: "100vh",
                    background: "#000",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontFamily: "'Inter', -apple-system, sans-serif",
                }}
            >
                {copy.loadingNextTrial}
            </div>
        );
    }

    if (!isFinal && subsetIndices.length === 0) {
        return (
            <div
                style={{
                    minHeight: "100vh",
                    background: "#000",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontFamily: "'Inter', -apple-system, sans-serif",
                }}
            >
                {error ? error : copy.preparingTrial}
            </div>
        );
    }

    if (isFinal) {
        return (
            <div
                style={{
                    minHeight: "100vh",
                    background: "#000",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    justifyContent: "center",
                    padding: 40,
                    gap: 32,
                    color: "#fff",
                    fontFamily: "'Inter', -apple-system, sans-serif",
                }}
            >
                <div style={{ textAlign: "center" }}>
                    <h2 style={{ marginBottom: 12 }}>
                        {chainToken && chainCurrentPosition < chainTotalStudies - 1
                            ? copy.studyComplete(chainCurrentPosition + 1, chainTotalStudies)
                            : copy.experimentComplete}
                    </h2>
                    <p style={{ color: "#888" }}>
                        {chainToken && chainCurrentPosition < chainTotalStudies - 1
                            ? copy.partOf(chainName)
                            : copy.thanks}
                    </p>
                </div>

                {/* Chain continuation button */}
                {chainToken && chainCurrentPosition < chainTotalStudies - 1 && (
                    <button
                        onClick={async () => {
                            setLoadingNextStudy(true);
                            try {
                                interface NextStudyResponse {
                                    chain_session_id: string;
                                    session_id: string;
                                    study_id: string;
                                    paradigm: "setcover" | "adaptive" | "pairwise";
                                    n_stimuli: number;
                                    stimuli: { id: string; ordinal: number; filename: string; media_type: "video" | "audio" | "image"; media_url?: string | null; thumbnail_url?: string | null }[];
                                    config: Record<string, unknown>;
                                    current_position: number;
                                }
                                const next = await apiFetch<NextStudyResponse>(
                                    `/api/v1/public/chain-invites/${chainToken}/next`,
                                    { method: "POST" }
                                );
                                const stimuliForClient = next.stimuli.map((s) => ({
                                    id: s.id || `stim-${s.ordinal}`,
                                    ordinal: s.ordinal,
                                    label: s.filename,
                                    mediaUrl: s.media_url || "",
                                    mediaType: s.media_type,
                                    thumbnail: s.thumbnail_url
                                        || (s.media_type === "image" ? (s.media_url || undefined) : s.media_type === "audio" ? "/audio.png" : undefined),
                                }));
                                sessionStorage.setItem("experimentStimuli", JSON.stringify(stimuliForClient));
                                sessionStorage.setItem("experimentSessionId", next.session_id);
                                sessionStorage.setItem("experimentStudyId", next.study_id);
                                sessionStorage.setItem("chainCurrentPosition", String(next.current_position));
                                localStorage.setItem("chainCurrentPosition", String(next.current_position));
                                localStorage.setItem("chainCurrentStudySessionId", next.session_id);
                                sessionStorage.setItem("experimentConfig", JSON.stringify({
                                    ...(next.config || {}),
                                    paradigm: next.paradigm,
                                }));
                                sessionStorage.removeItem("experimentInstructions");
                                window.location.href = `/experiment?session=${next.session_id}`;
                            } catch (err) {
                                const msg = err instanceof Error ? err.message : copy.loadNextStudyError;
                                setError(msg);
                                setLoadingNextStudy(false);
                            }
                        }}
                        disabled={loadingNextStudy}
                        style={{
                            padding: "16px 32px",
                            borderRadius: 12,
                            border: "none",
                            background: "linear-gradient(135deg, #00ff88 0%, #00cc66 100%)",
                            color: "#000",
                            fontSize: 16,
                            fontWeight: 700,
                            cursor: loadingNextStudy ? "wait" : "pointer",
                            opacity: loadingNextStudy ? 0.7 : 1,
                        }}
                    >
                        {loadingNextStudy ? copy.loading : copy.continueToStudy(chainCurrentPosition + 2)}
                    </button>
                )}

                {loadingResults && <p style={{ color: "#666" }}>{copy.loadingResults}</p>}

                {results && (
                    <>
                        <RdmHeatmap
                            rdm={results.rdm}
                            labels={results.labels}
                            size={Math.min(400, stimuli.length * 25)}
                            paradigm={paradigm}
                            scaleMode="auto"
                            language={language}
                        />
                        {results.rdm_scale && (
                            <p style={{ maxWidth: 620, margin: "-16px 0 0", color: "#777", fontSize: 12, textAlign: "center", lineHeight: 1.5 }}>
                                RDM scale: {results.rdm_scale.description} Raw divisor: {results.rdm_scale.divisor.toFixed(4)}.
                            </p>
                        )}
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
                            <button
                                onClick={handleDownloadResults}
                                style={{
                                    padding: "10px 16px",
                                    borderRadius: 8,
                                    border: "1px solid #444",
                                    background: "#1a1a1a",
                                    color: "#fff",
                                    fontSize: 13,
                                    cursor: "pointer",
                                }}
                            >
                                JSON
                            </button>
                            <button
                                onClick={handleDownloadCSV}
                                style={{
                                    padding: "10px 16px",
                                    borderRadius: 8,
                                    border: "1px solid #444",
                                    background: "#1a1a1a",
                                    color: "#fff",
                                    fontSize: 13,
                                    cursor: "pointer",
                                }}
                            >
                                CSV
                            </button>
                            <button
                                onClick={handleDownloadXLSX}
                                style={{
                                    padding: "10px 16px",
                                    borderRadius: 8,
                                    border: "1px solid #444",
                                    background: "#1a1a1a",
                                    color: "#fff",
                                    fontSize: 13,
                                    cursor: "pointer",
                                }}
                            >
                                Excel
                            </button>
                        </div>
                    </>

                )}
            </div>
        );
    }

    return (
        <div
            style={{
                minHeight: "100vh",
                background: "#000",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                padding: 20,
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            {error && (
                <div style={{ color: "#ff6666", marginBottom: 12, fontSize: 13 }}>
                    {error}
                </div>
            )}
            {hasInstructions && showInstructions && (
                <div
                    style={{
                        position: "fixed",
                        top: 20,
                        left: 20,
                        maxWidth: 360,
                        background: "rgba(0, 0, 0, 0.8)",
                        border: "1px solid #333",
                        borderRadius: 10,
                        padding: "12px 14px",
                        color: "#ddd",
                        fontSize: 12,
                        zIndex: 20,
                    }}
                >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{copy.instructionsTitle}</div>
                        <button
                            onClick={() => setShowInstructions(false)}
                            style={{
                                border: "1px solid #333",
                                background: "#111",
                                color: "#aaa",
                                borderRadius: 6,
                                padding: "2px 8px",
                                fontSize: 11,
                                cursor: "pointer",
                            }}
                        >
                            {copy.hide}
                        </button>
                    </div>
                    <ul style={{ margin: 0, paddingLeft: 18, lineHeight: 1.5 }}>
                        {instructions.map((line, idx) => (
                            <li key={`${idx}-${line}`}>{line}</li>
                        ))}
                    </ul>
                </div>
            )}
            {hasInstructions && !showInstructions && (
                <button
                    onClick={() => setShowInstructions(true)}
                    style={{
                        position: "fixed",
                        top: 20,
                        left: 20,
                        border: "1px solid #333",
                        background: "#111",
                        color: "#aaa",
                        borderRadius: 8,
                        padding: "6px 10px",
                        fontSize: 12,
                        cursor: "pointer",
                        zIndex: 20,
                    }}
                >
                    {copy.showInstructions}
                </button>
            )}
            {paradigm === "pairwise" ? (
                <PairwiseArena
                    key={`${trialIndex}-${currentStimuli[0]?.id ?? "a"}-${currentStimuli[1]?.id ?? "b"}`}
                    stimulusA={currentStimuli[0]}
                    stimulusB={currentStimuli[1]}
                    onSubmit={handlePairwiseSubmit}
                    onMediaPlay={handleMediaPlay}
                    trialIndex={trialIndex}
                    totalTrials={totalTrials || 0} // You might want to get total from session
                    language={language}
                    submitting={submittingTrial}
                />
            ) : (
                <DragArena
                    stimuli={currentStimuli}
                    onPositionsChange={setPositions}
                    onAllInside={setAllInside}
                    onSubmit={handleSubmit}
                    onMediaPlay={handleMediaPlay}
                    playedItems={playedItems}
                    size={arenaSize}
                    trialIndex={trialIndex}
                    language={language}
                    submitting={submittingTrial}
                />
            )}

            {/* Info bar */}
            {paradigm !== "pairwise" && (
                <div
                    style={{
                        position: "fixed",
                        bottom: 20,
                        right: 20,
                        color: "rgba(255, 255, 255, 0.4)",
                        fontSize: 12,
                        textAlign: "right",
                    }}
                >
                    <div>{copy.trial}: {trialIndex + 1}</div>
                    <div>
                        {copy.batch}: {subsetIndices.length > 16
                            ? `${subsetIndices.length} items`
                            : subsetIndices.map((i) => i + 1).join(", ")}
                    </div>
                    <div>{allInside ? copy.allInside : copy.moveItems}</div>
                </div>
            )}

            <MediaModal

                mediaUrl={currentMedia?.url || ""}
                mediaType={currentMedia?.type || "video"}
                isOpen={mediaModalOpen}
                onClose={handleMediaClose}
            />
        </div>
    );
}
