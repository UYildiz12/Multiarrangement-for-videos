"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "../lib/api";
import { cacheMedia } from "../lib/mediaCache";
import { getSupabaseClient, SUPABASE_BUCKET } from "../lib/supabaseClient";

type Paradigm = "setcover" | "adaptive" | "pairwise";
type WeightMode = "max" | "rms" | "k2012";
type RobustMethod = "none" | "winsor" | "huber";

interface AvailableVideo {
    filename: string;
    label: string;
    url: string;
    mediaType: "video" | "audio" | "image";
    thumbnail?: string;
    durationSeconds?: number;
}

interface VideoFile {
    name: string;
    url: string;
    thumbnail?: string;
    selected: boolean;
    mediaType: "video" | "audio" | "image";
    durationSeconds?: number;
}

interface ExperimentConfig {
    paradigm: Paradigm;
    language: "en" | "tr";
    instructionsMode: "off" | "en" | "tr" | "custom";
    customInstructions: string;
    videos: VideoFile[];
    batchSize: number;
    flex: boolean;
    setcoverWeightMode: WeightMode;
    setcoverWeightAlpha: number;
    useInverseMds: boolean;
    inverseMdsMaxIter: number;
    inverseMdsStepC: number;
    inverseMdsTol: number;
    robustMethod: RobustMethod;
    robustWinsorHigh: number;
    robustHuberC: number;
    evidenceThreshold: number;
    stopOnUtility: boolean;
    minSubsetSize: number;
    maxSubsetSize: number;
    evidenceWeightMode: WeightMode;
    evidenceAlpha: number;
    utilityExponent: number;
    timeCostExponent: number;
    arenaMax: number;
    maxJaccard: number | null;
    overlapPenalty: number;
    recencyPenalty: number;
    unseenBoost: number;
    stressWeight: number;
    recencyDecay: number;
    durationCostWeight: number;
    targetTimeSeconds: number | null;
    targetTimeTolerance: number;
    durationCostCapPerItem: number | null;
    longClipThresholdSeconds: number | null;
    minLongClipInclusionRate: number;
    longClipBoost: number;
    coldStartRequireUnseenTrials: number;
    avoidAnchorReuse: boolean;
    timeLimitMinutes: number | null;
    randomizePairs: boolean;
}

const defaultConfig: ExperimentConfig = {
    paradigm: "setcover",
    language: "en",
    instructionsMode: "en",
    customInstructions: "",
    videos: [],
    batchSize: 6,
    flex: false,
    setcoverWeightMode: "max",
    setcoverWeightAlpha: 2.0,
    useInverseMds: false,
    inverseMdsMaxIter: 15,
    inverseMdsStepC: 0.3,
    inverseMdsTol: 1e-4,
    robustMethod: "none",
    robustWinsorHigh: 0.98,
    robustHuberC: 0.9,
    evidenceThreshold: 0.35,
    stopOnUtility: false,
    minSubsetSize: 4,
    maxSubsetSize: 6,
    evidenceWeightMode: "k2012",
    evidenceAlpha: 2.0,
    utilityExponent: 10.0,
    timeCostExponent: 1.5,
    arenaMax: 1.0,
    maxJaccard: null,
    overlapPenalty: 0.0,
    recencyPenalty: 0.0,
    unseenBoost: 0.0,
    stressWeight: 0.0,
    recencyDecay: 0.85,
    durationCostWeight: 0.0,
    targetTimeSeconds: null,
    targetTimeTolerance: 0.05,
    durationCostCapPerItem: null,
    longClipThresholdSeconds: null,
    minLongClipInclusionRate: 0.0,
    longClipBoost: 0.0,
    coldStartRequireUnseenTrials: 0,
    avoidAnchorReuse: false,
    timeLimitMinutes: null,
    randomizePairs: true,
};

export default function SetupPage() {
    const router = useRouter();
    const [config, setConfig] = useState<ExperimentConfig>(defaultConfig);
    const [videoSource, setVideoSource] = useState<"preset" | "upload">("preset");
    const [classicVideos, setClassicVideos] = useState<VideoFile[]>([]);
    const [loadingPresets, setLoadingPresets] = useState(false);
    const [loadingError, setLoadingError] = useState<string | null>(null);
    const [processingUploads, setProcessingUploads] = useState(false);
    const [starting, setStarting] = useState(false);
    const [startError, setStartError] = useState<string | null>(null);
    const [adminSecret, setAdminSecret] = useState("");
    const [publishing, setPublishing] = useState(false);
    const [publishError, setPublishError] = useState<string | null>(null);
    const [publishedStudyId, setPublishedStudyId] = useState<string | null>(null);
    const [inviteParticipantId, setInviteParticipantId] = useState("");
    const [creatingInvite, setCreatingInvite] = useState(false);
    const [inviteLink, setInviteLink] = useState<string | null>(null);
    const [inviteError, setInviteError] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [uploadMode, setUploadMode] = useState<"local" | "supabase">("local");
    const supabaseAvailable = Boolean(getSupabaseClient());

    useEffect(() => {
        let cancelled = false;
        const loadPresets = async () => {
            setLoadingPresets(true);
            setLoadingError(null);
            try {
                const res = await fetch("/api/videos");
                if (!res.ok) {
                    throw new Error(`Failed to load media (${res.status})`);
                }
                const data = await res.json();
                const items = (data.videos || []) as AvailableVideo[];
                const mapped = items.map((v) => ({
                    name: v.label || v.filename,
                    url: v.url,
                    thumbnail: v.thumbnail,
                    selected: false,
                    mediaType: v.mediaType,
                    durationSeconds: typeof v.durationSeconds === "number" ? v.durationSeconds : undefined,
                }));
                if (!cancelled) {
                    setClassicVideos(mapped);
                }
            } catch (err) {
                if (!cancelled) {
                    const msg = err instanceof Error ? err.message : "Failed to load media";
                    setLoadingError(msg);
                }
            } finally {
                if (!cancelled) {
                    setLoadingPresets(false);
                }
            }
        };
        loadPresets();
        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        const saved = sessionStorage.getItem("adminSecret");
        if (saved) setAdminSecret(saved);
    }, []);

    // Preset selection handlers
    const selectPreset = (count: 16 | 36 | 58) => {
        const targetCount = Math.min(count, classicVideos.length);
        const newVideos = classicVideos.map((v, i) => ({
            ...v,
            selected: i < targetCount,
        }));
        setClassicVideos(newVideos);
    };

    const toggleVideo = (index: number) => {
        const newVideos = [...classicVideos];
        newVideos[index] = { ...newVideos[index], selected: !newVideos[index].selected };
        setClassicVideos(newVideos);
    };

    const selectAll = () => {
        setClassicVideos(classicVideos.map((v) => ({ ...v, selected: true })));
    };

    const clearSelection = () => {
        setClassicVideos(classicVideos.map((v) => ({ ...v, selected: false })));
    };

    // File upload handler
    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        setProcessingUploads(true);
        const newVideos: VideoFile[] = [];

        const supabase = uploadMode === "supabase" ? getSupabaseClient() : null;

        for (const file of Array.from(files)) {
            const label = file.name.replace(/\.[^/.]+$/, "");
            if (file.type.startsWith("video/")) {
                const durationSeconds = await getDurationFromFile(file, "video");
                const mediaUrl = uploadMode === "supabase" && supabase
                    ? await uploadToSupabase(file, label, supabase)
                    : URL.createObjectURL(file);
                try {
                    const thumbnail = await extractThumbnail(file);
                    const thumbUrl = uploadMode === "supabase" && supabase
                        ? await uploadThumbnailToSupabase(thumbnail, label, supabase)
                        : thumbnail;
                    newVideos.push({
                        name: label,
                        url: mediaUrl,
                        thumbnail: thumbUrl,
                        selected: true,
                        mediaType: "video",
                        durationSeconds: coalesceDuration(durationSeconds, "video"),
                    });
                    if (uploadMode === "local") {
                        await cacheMedia(label, {
                            blob: file,
                            mediaType: "video",
                            thumbnail: thumbUrl,
                            durationSeconds: coalesceDuration(durationSeconds, "video"),
                        });
                    }
                } catch {
                    newVideos.push({
                        name: label,
                        url: mediaUrl,
                        selected: true,
                        mediaType: "video",
                        durationSeconds: coalesceDuration(durationSeconds, "video"),
                    });
                    if (uploadMode === "local") {
                        await cacheMedia(label, {
                            blob: file,
                            mediaType: "video",
                            durationSeconds: coalesceDuration(durationSeconds, "video"),
                        });
                    }
                }
            } else if (file.type.startsWith("audio/")) {
                const durationSeconds = await getDurationFromFile(file, "audio");
                const mediaUrl = uploadMode === "supabase" && supabase
                    ? await uploadToSupabase(file, label, supabase)
                    : URL.createObjectURL(file);
                newVideos.push({
                    name: label,
                    url: mediaUrl,
                    thumbnail: "/audio.png",
                    selected: true,
                    mediaType: "audio",
                    durationSeconds: coalesceDuration(durationSeconds, "audio"),
                });
                if (uploadMode === "local") {
                    await cacheMedia(label, {
                        blob: file,
                        mediaType: "audio",
                        thumbnail: "/audio.png",
                        durationSeconds: coalesceDuration(durationSeconds, "audio"),
                    });
                }
            } else if (file.type.startsWith("image/")) {
                const mediaUrl = uploadMode === "supabase" && supabase
                    ? await uploadToSupabase(file, label, supabase)
                    : URL.createObjectURL(file);
                newVideos.push({
                    name: label,
                    url: mediaUrl,
                    thumbnail: mediaUrl,
                    selected: true,
                    mediaType: "image",
                    durationSeconds: coalesceDuration(null, "image"),
                });
                if (uploadMode === "local") {
                    await cacheMedia(label, {
                        blob: file,
                        mediaType: "image",
                        thumbnail: mediaUrl,
                        durationSeconds: coalesceDuration(null, "image"),
                    });
                }
            }
        }

        setConfig((prev) => ({
            ...prev,
            videos: [...prev.videos, ...newVideos],
        }));
        setProcessingUploads(false);
    };

    const selectedCount = videoSource === "preset"
        ? classicVideos.filter((v) => v.selected).length
        : config.videos.length;
    const minItemsRequired = config.paradigm === "pairwise" ? 2 : 3;

    const addIfNumber = (target: Record<string, unknown>, key: string, value: number | null | undefined) => {
        if (value === null || value === undefined || Number.isNaN(value)) return;
        target[key] = value;
    };

    const handleStart = async () => {
        if (selectedCount < minItemsRequired) {
            alert(`Please select at least ${minItemsRequired} items for the experiment.`);
            return;
        }

        const videosToUse = videoSource === "preset"
            ? classicVideos.filter((v) => v.selected)
            : config.videos;
        if (starting) return;
        setStarting(true);
        setStartError(null);

        try {
            const videosWithDuration = await ensureDurations(videosToUse);
            const instructions = buildInstructions(config);
            const participantId = (() => {
                const existing = sessionStorage.getItem("participantId");
                if (existing) return existing;
                if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
                    return crypto.randomUUID();
                }
                return `p_${Math.random().toString(36).slice(2, 10)}_${Date.now()}`;
            })();
            sessionStorage.setItem("participantId", participantId);

            const studyConfig: Record<string, unknown> = {};
            addIfNumber(studyConfig, "time_limit_minutes", config.timeLimitMinutes);
            if (config.paradigm !== "pairwise" && config.robustMethod !== "none") {
                studyConfig.robust_method = config.robustMethod;
                addIfNumber(studyConfig, "robust_winsor_high", config.robustWinsorHigh);
                addIfNumber(studyConfig, "robust_huber_c", config.robustHuberC);
            }
            if (config.paradigm === "setcover") {
                studyConfig.batch_size = config.batchSize;
                studyConfig.flex = config.flex;
                studyConfig.setcover_weight_mode = config.setcoverWeightMode;
                studyConfig.setcover_weight_alpha = config.setcoverWeightAlpha;
                studyConfig.use_inverse_mds = config.useInverseMds;
                studyConfig.inverse_mds_max_iter = config.inverseMdsMaxIter;
                studyConfig.inverse_mds_step_c = config.inverseMdsStepC;
                studyConfig.inverse_mds_tol = config.inverseMdsTol;
            } else if (config.paradigm === "pairwise") {
                studyConfig.randomize_pairs = config.randomizePairs;
            } else {
                studyConfig.evidence_threshold = config.evidenceThreshold;
                studyConfig.stop_on_utility = config.stopOnUtility;
                studyConfig.min_subset_size = config.minSubsetSize;
                studyConfig.max_subset_size = config.maxSubsetSize;
                studyConfig.evidence_weight_mode = config.evidenceWeightMode;
                studyConfig.evidence_alpha = config.evidenceAlpha;
                studyConfig.utility_exponent = config.utilityExponent;
                studyConfig.use_inverse_mds = config.useInverseMds;
                studyConfig.inverse_mds_max_iter = config.inverseMdsMaxIter;
                studyConfig.inverse_mds_step_c = config.inverseMdsStepC;
                studyConfig.inverse_mds_tol = config.inverseMdsTol;
                studyConfig.time_cost_exponent = config.timeCostExponent;
                studyConfig.arena_max = config.arenaMax;
                addIfNumber(studyConfig, "max_jaccard", config.maxJaccard);
                studyConfig.overlap_penalty = config.overlapPenalty;
                studyConfig.recency_penalty = config.recencyPenalty;
                studyConfig.unseen_boost = config.unseenBoost;
                studyConfig.stress_weight = config.stressWeight;
                studyConfig.recency_decay = config.recencyDecay;
                studyConfig.duration_cost_weight = config.durationCostWeight;
                addIfNumber(studyConfig, "target_time_seconds", config.targetTimeSeconds);
                studyConfig.target_time_tolerance = config.targetTimeTolerance;
                addIfNumber(studyConfig, "duration_cost_cap_per_item", config.durationCostCapPerItem);
                addIfNumber(studyConfig, "long_clip_threshold_seconds", config.longClipThresholdSeconds);
                studyConfig.min_long_clip_inclusion_rate = config.minLongClipInclusionRate;
                studyConfig.long_clip_boost = config.longClipBoost;
                studyConfig.cold_start_require_unseen_trials = config.coldStartRequireUnseenTrials;
                studyConfig.avoid_anchor_reuse = config.avoidAnchorReuse;
            }

            const study = await apiFetch<{ id: string }>("/api/v1/studies", {
                method: "POST",
                body: JSON.stringify({
                    name: "Multiarrangement Web Study",
                    description: "Web session",
                    paradigm: config.paradigm,
                    language: config.language,
                    config: studyConfig,
                    instructions: instructions ?? null,
                }),
            });

            const stimuliPayload = {
                stimuli: videosWithDuration.map((v, i) => ({
                    ordinal: i,
                    filename: v.name,
                    media_type: v.mediaType,
                    media_url: v.url,
                    thumbnail_url: v.thumbnail ?? null,
                    duration_seconds: v.durationSeconds ?? null,
                })),
            };
            await apiFetch(`/api/v1/studies/${study.id}/stimuli`, {
                method: "POST",
                body: JSON.stringify(stimuliPayload),
            });

            const session = await apiFetch<{ session_id: string }>(
                `/api/v1/studies/${study.id}/sessions`,
                {
                    method: "POST",
                    body: JSON.stringify({ participant_id: participantId }),
                }
            );

            const stimuliForClient = videosWithDuration.map((v, i) => ({
                id: `stim-${i}`,
                ordinal: i,
                label: v.name,
                mediaUrl: v.url,
                thumbnail: v.thumbnail,
                mediaType: v.mediaType,
            }));

            sessionStorage.setItem("experimentConfig", JSON.stringify({
                ...config,
                videos: videosWithDuration,
            }));
            if (instructions && instructions.length > 0) {
                sessionStorage.setItem("experimentInstructions", JSON.stringify(instructions));
            } else {
                sessionStorage.removeItem("experimentInstructions");
            }
            sessionStorage.setItem("experimentStimuli", JSON.stringify(stimuliForClient));
            sessionStorage.setItem("experimentSessionId", session.session_id);
            sessionStorage.setItem("experimentStudyId", study.id);

            router.push(`/experiment?session=${session.session_id}`);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to start experiment";
            setStartError(msg);
        } finally {
            setStarting(false);
        }
    };

    const handlePublish = async () => {
        if (selectedCount < minItemsRequired) {
            setPublishError(`Please select at least ${minItemsRequired} items.`);
            return;
        }
        if (videoSource === "upload" && uploadMode !== "supabase") {
            setPublishError("Custom uploads are local to your browser. Use preset media or upload to hosted storage first.");
            return;
        }

        const videosToUse = videoSource === "preset"
            ? classicVideos.filter((v) => v.selected)
            : config.videos;
        setPublishing(true);
        setPublishError(null);
        setInviteLink(null);
        setInviteError(null);
        try {
            const videosWithDuration = await ensureDurations(videosToUse);
            const instructions = buildInstructions(config);
            const studyConfig: Record<string, unknown> = {};
            addIfNumber(studyConfig, "time_limit_minutes", config.timeLimitMinutes);
            if (config.paradigm !== "pairwise" && config.robustMethod !== "none") {
                studyConfig.robust_method = config.robustMethod;
                addIfNumber(studyConfig, "robust_winsor_high", config.robustWinsorHigh);
                addIfNumber(studyConfig, "robust_huber_c", config.robustHuberC);
            }
            if (config.paradigm === "setcover") {
                studyConfig.batch_size = config.batchSize;
                studyConfig.flex = config.flex;
                studyConfig.setcover_weight_mode = config.setcoverWeightMode;
                studyConfig.setcover_weight_alpha = config.setcoverWeightAlpha;
                studyConfig.use_inverse_mds = config.useInverseMds;
                studyConfig.inverse_mds_max_iter = config.inverseMdsMaxIter;
                studyConfig.inverse_mds_step_c = config.inverseMdsStepC;
                studyConfig.inverse_mds_tol = config.inverseMdsTol;
            } else if (config.paradigm === "pairwise") {
                studyConfig.randomize_pairs = config.randomizePairs;
            } else {

                studyConfig.evidence_threshold = config.evidenceThreshold;
                studyConfig.stop_on_utility = config.stopOnUtility;
                studyConfig.min_subset_size = config.minSubsetSize;
                studyConfig.max_subset_size = config.maxSubsetSize;
                studyConfig.evidence_weight_mode = config.evidenceWeightMode;
                studyConfig.evidence_alpha = config.evidenceAlpha;
                studyConfig.utility_exponent = config.utilityExponent;
                studyConfig.use_inverse_mds = config.useInverseMds;
                studyConfig.inverse_mds_max_iter = config.inverseMdsMaxIter;
                studyConfig.inverse_mds_step_c = config.inverseMdsStepC;
                studyConfig.inverse_mds_tol = config.inverseMdsTol;
                studyConfig.time_cost_exponent = config.timeCostExponent;
                studyConfig.arena_max = config.arenaMax;
                addIfNumber(studyConfig, "max_jaccard", config.maxJaccard);
                studyConfig.overlap_penalty = config.overlapPenalty;
                studyConfig.recency_penalty = config.recencyPenalty;
                studyConfig.unseen_boost = config.unseenBoost;
                studyConfig.stress_weight = config.stressWeight;
                studyConfig.recency_decay = config.recencyDecay;
                studyConfig.duration_cost_weight = config.durationCostWeight;
                addIfNumber(studyConfig, "target_time_seconds", config.targetTimeSeconds);
                studyConfig.target_time_tolerance = config.targetTimeTolerance;
                addIfNumber(studyConfig, "duration_cost_cap_per_item", config.durationCostCapPerItem);
                addIfNumber(studyConfig, "long_clip_threshold_seconds", config.longClipThresholdSeconds);
                studyConfig.min_long_clip_inclusion_rate = config.minLongClipInclusionRate;
                studyConfig.long_clip_boost = config.longClipBoost;
                studyConfig.cold_start_require_unseen_trials = config.coldStartRequireUnseenTrials;
                studyConfig.avoid_anchor_reuse = config.avoidAnchorReuse;
            }

            const study = await apiFetch<{ id: string }>("/api/v1/studies", {
                method: "POST",
                body: JSON.stringify({
                    name: "Multiarrangement Web Study",
                    description: "Published study",
                    paradigm: config.paradigm,
                    language: config.language,
                    config: studyConfig,
                    instructions: instructions ?? null,
                }),
            });

            const stimuliPayload = {
                stimuli: videosWithDuration.map((v, i) => ({
                    ordinal: i,
                    filename: v.name,
                    media_type: v.mediaType,
                    media_url: v.url,
                    thumbnail_url: v.thumbnail ?? null,
                    duration_seconds: v.durationSeconds ?? null,
                })),
            };
            await apiFetch(`/api/v1/studies/${study.id}/stimuli`, {
                method: "POST",
                body: JSON.stringify(stimuliPayload),
            });

            setPublishedStudyId(study.id);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to publish study";
            setPublishError(msg);
        } finally {
            setPublishing(false);
        }
    };

    const handleGenerateInvite = async () => {
        if (!publishedStudyId) {
            setInviteError("Publish the study first.");
            return;
        }
        if (!adminSecret.trim()) {
            setInviteError("Admin secret is required.");
            return;
        }
        if (!inviteParticipantId.trim()) {
            setInviteError("Participant ID is required for a unique link.");
            return;
        }
        setInviteError(null);
        setCreatingInvite(true);
        try {
            sessionStorage.setItem("adminSecret", adminSecret);
            const invites = await apiFetch<{ token: string }[]>(
                `/api/v1/admin/studies/${publishedStudyId}/invites`,
                {
                    method: "POST",
                    headers: { "x-admin-secret": adminSecret },
                    body: JSON.stringify({ participant_id: inviteParticipantId, count: 1 }),
                }
            );
            const token = invites[0]?.token;
            if (!token) throw new Error("No invite token returned");
            const origin = typeof window !== "undefined" ? window.location.origin : "";
            const link = `${origin}/participate?invite=${token}`;
            setInviteLink(link);
        } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to create invite";
            setInviteError(msg);
        } finally {
            setCreatingInvite(false);
        }
    };

    const inputStyle = {
        padding: "8px 12px",
        borderRadius: 4,
        border: "1px solid #444",
        background: "#1a1a1a",
        color: "#fff",
        fontSize: 14,
        width: "100%",
    };

    const optionalNumber = (value: string) => {
        if (value.trim() === "") return null;
        const parsed = parseFloat(value);
        if (Number.isNaN(parsed)) return null;
        if (parsed <= 0) return null;
        return parsed;
    };


    const labelStyle = {
        color: "#aaa",
        fontSize: 12,
        marginBottom: 4,
        display: "block" as const,
    };

    const sectionStyle = {
        background: "#111",
        padding: 20,
        borderRadius: 8,
        marginBottom: 16,
    };

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
            <div style={{ maxWidth: 800, margin: "0 auto" }}>
                <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 8 }}>
                    Multiarrangement
                </h1>
                <p style={{ color: "#666", fontSize: 14, marginBottom: 32 }}>
                    Configure your experiment settings
                </p>

                {/* Video Source Selection */}
                <div style={sectionStyle}>
                    <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>
                        Select Media
                    </h2>

                    {/* Source toggle */}
                    <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                        <button
                            onClick={() => setVideoSource("preset")}
                            style={{
                                padding: "8px 16px",
                                borderRadius: 4,
                                border: videoSource === "preset" ? "2px solid #00ff00" : "1px solid #444",
                                background: videoSource === "preset" ? "#0a2a0a" : "#1a1a1a",
                                color: "#fff",
                                cursor: "pointer",
                                fontSize: 13,
                            }}
                        >
                            Preset Library
                        </button>
                        <button
                            onClick={() => setVideoSource("upload")}
                            style={{
                                padding: "8px 16px",
                                borderRadius: 4,
                                border: videoSource === "upload" ? "2px solid #00ff00" : "1px solid #444",
                                background: videoSource === "upload" ? "#0a2a0a" : "#1a1a1a",
                                color: "#fff",
                                cursor: "pointer",
                                fontSize: 13,
                            }}
                        >
                            Upload Custom
                        </button>
                    </div>

                    {videoSource === "preset" ? (
                        <>
                            {/* Preset buttons */}
                            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                                <button onClick={() => selectPreset(16)} style={presetBtnStyle(classicVideos.filter(v => v.selected).length === 16)}>16 Items</button>
                                <button onClick={() => selectPreset(36)} style={presetBtnStyle(classicVideos.filter(v => v.selected).length === 36)}>36 Items</button>
                                <button onClick={() => selectPreset(58)} style={presetBtnStyle(classicVideos.filter(v => v.selected).length === 58)}>58 Items</button>
                                <button onClick={clearSelection} style={{ ...presetBtnStyle(false), borderColor: "#666" }}>Clear</button>
                            </div>

                            {/* Video grid */}
                            {loadingPresets ? (
                                <div style={{ color: "#666", fontSize: 13 }}>Loading media...</div>
                            ) : loadingError ? (
                                <div style={{ color: "#ff6666", fontSize: 13 }}>{loadingError}</div>
                            ) : classicVideos.length === 0 ? (
                                <div style={{ color: "#666", fontSize: 13 }}>No media found in /public/videos.</div>
                            ) : (
                                <div style={{
                                    display: "grid",
                                    gridTemplateColumns: "repeat(auto-fill, minmax(70px, 1fr))",
                                    gap: 8,
                                    maxHeight: 300,
                                    overflowY: "auto",
                                    padding: 8,
                                    background: "#0a0a0a",
                                    borderRadius: 4,
                                }}>
                                    {classicVideos.map((video, i) => (
                                        <div
                                            key={`${video.name}-${i}`}
                                            onClick={() => toggleVideo(i)}
                                            style={{
                                                width: 70,
                                                height: 70,
                                                borderRadius: 6,
                                                overflow: "hidden",
                                                border: video.selected ? "3px solid #00ff00" : "2px solid #333",
                                                cursor: "pointer",
                                                opacity: video.selected ? 1 : 0.5,
                                                transition: "all 0.15s ease",
                                            }}
                                        >
                                            {video.thumbnail ? (
                                                <img src={video.thumbnail} alt={video.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                                            ) : (
                                                <div style={{ width: "100%", height: "100%", background: "#222", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "#666", textTransform: "uppercase" }}>
                                                    {video.mediaType}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </>
                    ) : (
                        <>
                            <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                    <input
                                        id="upload-local"
                                        type="radio"
                                        name="upload-mode"
                                        checked={uploadMode === "local"}
                                        onChange={() => setUploadMode("local")}
                                    />
                                    <label htmlFor="upload-local" style={{ color: "#aaa", fontSize: 12 }}>
                                        Local (not shareable)
                                    </label>
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                    <input
                                        id="upload-supabase"
                                        type="radio"
                                        name="upload-mode"
                                        checked={uploadMode === "supabase"}
                                        onChange={() => setUploadMode("supabase")}
                                        disabled={!supabaseAvailable}
                                    />
                                    <label htmlFor="upload-supabase" style={{ color: supabaseAvailable ? "#aaa" : "#555", fontSize: 12 }}>
                                        Hosted (Supabase)
                                    </label>
                                </div>
                                {!supabaseAvailable && (
                                    <span style={{ color: "#555", fontSize: 12 }}>
                                        Set NEXT_PUBLIC_SUPABASE_URL/ANON_KEY to enable.
                                    </span>
                                )}
                            </div>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="video/*,audio/*,image/*"
                                multiple
                                onChange={handleFileSelect}
                                style={{ display: "none" }}
                            />
                            <button
                                onClick={() => fileInputRef.current?.click()}
                                disabled={processingUploads}
                                style={{
                                    padding: "12px 24px",
                                    borderRadius: 6,
                                    border: "2px dashed #444",
                                    background: "transparent",
                                    color: "#888",
                                    fontSize: 14,
                                    cursor: "pointer",
                                    width: "100%",
                                }}
                            >
                                {processingUploads ? "Processing..." : "+ Click to add media"}
                            </button>

                            {config.videos.length > 0 && (
                                <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 16 }}>
                                    {config.videos.map((video, i) => (
                                        <div key={i} style={{ width: 70, height: 70, borderRadius: 6, overflow: "hidden", border: "2px solid #00ff00" }}>
                                            {video.thumbnail ? (
                                                <img src={video.thumbnail} alt={video.name} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                                            ) : (
                                                <div style={{ width: "100%", height: "100%", background: "#222", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "#666", textTransform: "uppercase" }}>
                                                    {video.mediaType}
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </>
                    )}

                    <p style={{ color: "#888", fontSize: 13, marginTop: 12 }}>
                        <strong style={{ color: "#00ff00" }}>{selectedCount}</strong> items selected
                    </p>
                </div>

                {/* Paradigm Selection */}
                <div style={sectionStyle}>
                    <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Paradigm</h2>
                    <div style={{ display: "flex", gap: 12 }}>
                        <button onClick={() => setConfig({ ...config, paradigm: "setcover" })} style={paradigmBtnStyle(config.paradigm === "setcover")}>
                            <div style={{ fontWeight: 600 }}>Set-Cover</div>
                            <div style={{ fontSize: 12, color: "#888" }}>Fixed batches</div>
                        </button>
                        <button onClick={() => setConfig({ ...config, paradigm: "adaptive" })} style={paradigmBtnStyle(config.paradigm === "adaptive")}>
                            <div style={{ fontWeight: 600 }}>Adaptive LTW</div>
                            <div style={{ fontSize: 12, color: "#888" }}>Lift-the-Weakest</div>
                        </button>
                        <button onClick={() => setConfig({ ...config, paradigm: "pairwise" })} style={paradigmBtnStyle(config.paradigm === "pairwise")}>
                            <div style={{ fontWeight: 600 }}>Pairwise</div>
                            <div style={{ fontSize: 12, color: "#888" }}>1-7 Similarity</div>
                        </button>
                    </div>
                </div>


                {/* General Settings */}
                <div style={sectionStyle}>
                    <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>General Settings</h2>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                        <div>
                            <label style={labelStyle}>Language</label>
                            <select value={config.language} onChange={(e) => setConfig({ ...config, language: e.target.value as "en" | "tr" })} style={inputStyle}>
                                <option value="en">English</option>
                                <option value="tr">Turkish</option>
                            </select>
                        </div>
                        <div>
                            <label style={labelStyle}>Instructions</label>
                            <select
                                value={config.instructionsMode}
                                onChange={(e) => setConfig({ ...config, instructionsMode: e.target.value as ExperimentConfig["instructionsMode"] })}
                                style={inputStyle}
                            >
                                <option value="off">Off</option>
                                <option value="en">English</option>
                                <option value="tr">Turkish</option>
                                <option value="custom">Custom</option>
                            </select>
                        </div>
                        {config.instructionsMode === "custom" && (
                            <div style={{ gridColumn: "1 / -1" }}>
                                <label style={labelStyle}>Custom Instructions</label>
                                <textarea
                                    value={config.customInstructions}
                                    onChange={(e) => setConfig({ ...config, customInstructions: e.target.value })}
                                    rows={4}
                                    style={{ ...inputStyle, height: "auto", resize: "vertical" }}
                                    placeholder="One instruction per line"
                                />
                            </div>
                        )}
                            <div>
                                <label style={labelStyle}>Time Limit (minutes)</label>
                                <input
                                    type="number"
                                    min={0}
                                    value={config.timeLimitMinutes ?? ""}
                                    onChange={(e) => setConfig({ ...config, timeLimitMinutes: optionalNumber(e.target.value) })}
                                    style={inputStyle}
                                    placeholder="No limit"
                                />
                            </div>
                        {config.paradigm !== "pairwise" && (
                            <>
                                <div>
                                    <label style={labelStyle}>Robust Method</label>
                                    <select value={config.robustMethod} onChange={(e) => setConfig({ ...config, robustMethod: e.target.value as RobustMethod })} style={inputStyle}>
                                        <option value="none">None</option>
                                        <option value="winsor">Winsorization</option>
                                        <option value="huber">Huber</option>
                                    </select>
                                </div>
                                {config.robustMethod !== "none" && (
                                    <div>
                                        <label style={labelStyle}>Robust Params</label>
                                        <div style={{ display: "flex", gap: 8 }}>
                                            <input
                                                type="number"
                                                step={0.01}
                                                value={config.robustWinsorHigh}
                                                onChange={(e) => setConfig({ ...config, robustWinsorHigh: parseFloat(e.target.value) || 0.98 })}
                                                style={{ ...inputStyle, width: "50%" }}
                                                placeholder="Winsor high"
                                            />
                                            <input
                                                type="number"
                                                step={0.01}
                                                value={config.robustHuberC}
                                                onChange={(e) => setConfig({ ...config, robustHuberC: parseFloat(e.target.value) || 0.9 })}
                                                style={{ ...inputStyle, width: "50%" }}
                                                placeholder="Huber C"
                                            />
                                        </div>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                </div>

                {/* Paradigm-specific options */}
                {config.paradigm === "setcover" ? (
                    <div style={sectionStyle}>
                        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Set-Cover Options</h2>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                            <div>
                                <label style={labelStyle}>Batch Size (k)</label>
                                <input type="number" min={3} max={12} value={config.batchSize} onChange={(e) => setConfig({ ...config, batchSize: parseInt(e.target.value) || 6 })} style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>Weight Mode</label>
                                <select value={config.setcoverWeightMode} onChange={(e) => setConfig({ ...config, setcoverWeightMode: e.target.value as WeightMode })} style={inputStyle}>
                                    <option value="max">max (d/max)</option>
                                    <option value="rms">rms (RMS-matched)</option>
                                    <option value="k2012">k2012 (hybrid)</option>
                                </select>
                            </div>
                            <div>
                                <label style={labelStyle}>Weight Alpha</label>
                                <input type="number" step={0.1} value={config.setcoverWeightAlpha} onChange={(e) => setConfig({ ...config, setcoverWeightAlpha: parseFloat(e.target.value) || 2.0 })} style={inputStyle} />
                            </div>
                        </div>
                        <details style={{ marginTop: 16 }}>
                            <summary style={{ cursor: "pointer", color: "#aaa", fontSize: 13 }}>
                                Advanced Set-Cover
                            </summary>
                            <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                    <input
                                        id="inverse-mds-setcover"
                                        type="checkbox"
                                        checked={config.useInverseMds}
                                        onChange={(e) => setConfig({ ...config, useInverseMds: e.target.checked })}
                                    />
                                    <label htmlFor="inverse-mds-setcover" style={{ color: "#aaa", fontSize: 12 }}>
                                        Use inverse MDS refinement
                                    </label>
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                    <input
                                        id="flex-setcover"
                                        type="checkbox"
                                        checked={config.flex}
                                        onChange={(e) => setConfig({ ...config, flex: e.target.checked })}
                                    />
                                    <label htmlFor="flex-setcover" style={{ color: "#aaa", fontSize: 12 }}>
                                        Use flexible batch sizes
                                    </label>
                                </div>
                                <div>
                                    <label style={labelStyle}>Inverse MDS Max Iter</label>
                                    <input type="number" min={1} value={config.inverseMdsMaxIter} onChange={(e) => setConfig({ ...config, inverseMdsMaxIter: parseInt(e.target.value) || 15 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Inverse MDS Step C</label>
                                    <input type="number" step={0.01} value={config.inverseMdsStepC} onChange={(e) => setConfig({ ...config, inverseMdsStepC: parseFloat(e.target.value) || 0.3 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Inverse MDS Tolerance</label>
                                    <input type="number" step={1e-5} value={config.inverseMdsTol} onChange={(e) => setConfig({ ...config, inverseMdsTol: parseFloat(e.target.value) || 1e-4 })} style={inputStyle} />
                                </div>
                            </div>
                        </details>
                    </div>
                ) : config.paradigm === "pairwise" ? (
                    <div style={sectionStyle}>
                        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Pairwise Options</h2>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <input
                                    id="randomize-pairs"
                                    type="checkbox"
                                    checked={config.randomizePairs}
                                    onChange={(e) => setConfig({ ...config, randomizePairs: e.target.checked })}
                                />
                                <label htmlFor="randomize-pairs" style={{ color: "#aaa", fontSize: 12 }}>
                                    Randomize Order
                                </label>
                            </div>
                            <div style={{ color: "#666", fontSize: 12, display: "flex", alignItems: "center" }}>
                                {config.randomizePairs ? "Pairs shown in random order." : "Pairs shown in fixed order."}
                            </div>
                        </div>
                    </div>
                ) : (
                    <div style={sectionStyle}>
                        <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Adaptive LTW Options</h2>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                            <div>
                                <label style={labelStyle}>Evidence Threshold</label>
                                <input type="number" step={0.05} min={0.1} max={1.0} value={config.evidenceThreshold} onChange={(e) => setConfig({ ...config, evidenceThreshold: parseFloat(e.target.value) || 0.35 })} style={inputStyle} />
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <input
                                    id="stop-on-utility"
                                    type="checkbox"
                                    checked={config.stopOnUtility}
                                    onChange={(e) => setConfig({ ...config, stopOnUtility: e.target.checked })}
                                />
                                <label htmlFor="stop-on-utility" style={{ color: "#aaa", fontSize: 12 }}>
                                    Stop on utility threshold
                                </label>
                            </div>
                            <div>
                                <label style={labelStyle}>Min/Max Subset Size</label>
                                <div style={{ display: "flex", gap: 8 }}>
                                    <input type="number" min={2} max={10} value={config.minSubsetSize} onChange={(e) => setConfig({ ...config, minSubsetSize: parseInt(e.target.value) || 4 })} style={{ ...inputStyle, width: "50%" }} />
                                    <input type="number" min={3} max={15} value={config.maxSubsetSize} onChange={(e) => setConfig({ ...config, maxSubsetSize: parseInt(e.target.value) || 6 })} style={{ ...inputStyle, width: "50%" }} />
                                </div>
                            </div>
                            <div>
                                <label style={labelStyle}>Evidence Weight Mode</label>
                                <select value={config.evidenceWeightMode} onChange={(e) => setConfig({ ...config, evidenceWeightMode: e.target.value as WeightMode })} style={inputStyle}>
                                    <option value="max">max (d/max)</option>
                                    <option value="rms">rms (RMS-matched)</option>
                                    <option value="k2012">k2012 (hybrid)</option>
                                </select>
                            </div>
                            <div>
                                <label style={labelStyle}>Evidence Alpha</label>
                                <input type="number" step={0.1} value={config.evidenceAlpha} onChange={(e) => setConfig({ ...config, evidenceAlpha: parseFloat(e.target.value) || 2.0 })} style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>Utility Exponent</label>
                                <input type="number" step={0.1} value={config.utilityExponent} onChange={(e) => setConfig({ ...config, utilityExponent: parseFloat(e.target.value) || 10.0 })} style={inputStyle} />
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                <input
                                    id="inverse-mds-adaptive"
                                    type="checkbox"
                                    checked={config.useInverseMds}
                                    onChange={(e) => setConfig({ ...config, useInverseMds: e.target.checked })}
                                />
                                <label htmlFor="inverse-mds-adaptive" style={{ color: "#aaa", fontSize: 12 }}>
                                    Use inverse MDS refinement
                                </label>
                            </div>
                            <div>
                                <label style={labelStyle}>Inverse MDS Max Iter</label>
                                <input type="number" min={1} value={config.inverseMdsMaxIter} onChange={(e) => setConfig({ ...config, inverseMdsMaxIter: parseInt(e.target.value) || 15 })} style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>Inverse MDS Step C</label>
                                <input type="number" step={0.01} value={config.inverseMdsStepC} onChange={(e) => setConfig({ ...config, inverseMdsStepC: parseFloat(e.target.value) || 0.3 })} style={inputStyle} />
                            </div>
                            <div>
                                <label style={labelStyle}>Inverse MDS Tolerance</label>
                                <input type="number" step={1e-5} value={config.inverseMdsTol} onChange={(e) => setConfig({ ...config, inverseMdsTol: parseFloat(e.target.value) || 1e-4 })} style={inputStyle} />
                            </div>
                        </div>
                        <details style={{ marginTop: 16 }}>
                            <summary style={{ cursor: "pointer", color: "#aaa", fontSize: 13 }}>
                                Adaptive Policy Details
                            </summary>
                            <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                                <div>
                                    <label style={labelStyle}>Recency Decay</label>
                                    <input type="number" step={0.01} value={config.recencyDecay} onChange={(e) => setConfig({ ...config, recencyDecay: parseFloat(e.target.value) || 0.85 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Cold Start Require Unseen Trials</label>
                                    <input type="number" min={0} value={config.coldStartRequireUnseenTrials} onChange={(e) => setConfig({ ...config, coldStartRequireUnseenTrials: parseInt(e.target.value) || 0 })} style={inputStyle} />
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                    <input
                                        id="avoid-anchor-reuse"
                                        type="checkbox"
                                        checked={config.avoidAnchorReuse}
                                        onChange={(e) => setConfig({ ...config, avoidAnchorReuse: e.target.checked })}
                                    />
                                    <label htmlFor="avoid-anchor-reuse" style={{ color: "#aaa", fontSize: 12 }}>
                                        Avoid anchor pair reuse
                                    </label>
                                </div>
                                <div />
                                <div>
                                    <label style={labelStyle}>Max Jaccard (optional)</label>
                                    <input type="number" step={0.05} value={config.maxJaccard ?? ""} onChange={(e) => setConfig({ ...config, maxJaccard: optionalNumber(e.target.value) })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Overlap Penalty</label>
                                    <input type="number" step={0.1} value={config.overlapPenalty} onChange={(e) => setConfig({ ...config, overlapPenalty: parseFloat(e.target.value) || 0.0 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Recency Penalty</label>
                                    <input type="number" step={0.1} value={config.recencyPenalty} onChange={(e) => setConfig({ ...config, recencyPenalty: parseFloat(e.target.value) || 0.0 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Unseen Boost</label>
                                    <input type="number" step={0.1} value={config.unseenBoost} onChange={(e) => setConfig({ ...config, unseenBoost: parseFloat(e.target.value) || 0.0 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Stress Weight</label>
                                    <input type="number" step={0.1} value={config.stressWeight} onChange={(e) => setConfig({ ...config, stressWeight: parseFloat(e.target.value) || 0.0 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Time Cost Exponent</label>
                                    <input type="number" step={0.1} value={config.timeCostExponent} onChange={(e) => setConfig({ ...config, timeCostExponent: parseFloat(e.target.value) || 1.5 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Arena Max</label>
                                    <input type="number" step={0.1} value={config.arenaMax} onChange={(e) => setConfig({ ...config, arenaMax: parseFloat(e.target.value) || 1.0 })} style={inputStyle} />
                                </div>
                            </div>
                        </details>
                        <details style={{ marginTop: 16 }}>
                            <summary style={{ cursor: "pointer", color: "#aaa", fontSize: 13 }}>
                                Timing & Duration Controls
                            </summary>
                            <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                                <div>
                                    <label style={labelStyle}>Duration Cost Weight</label>
                                    <input type="number" step={0.1} value={config.durationCostWeight} onChange={(e) => setConfig({ ...config, durationCostWeight: parseFloat(e.target.value) || 0.0 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Target Time Seconds (optional)</label>
                                    <input type="number" min={0} value={config.targetTimeSeconds ?? ""} onChange={(e) => setConfig({ ...config, targetTimeSeconds: optionalNumber(e.target.value) })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Target Time Tolerance</label>
                                    <input type="number" step={0.01} value={config.targetTimeTolerance} onChange={(e) => setConfig({ ...config, targetTimeTolerance: parseFloat(e.target.value) || 0.05 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Duration Cost Cap / Item (optional)</label>
                                    <input type="number" step={0.1} value={config.durationCostCapPerItem ?? ""} onChange={(e) => setConfig({ ...config, durationCostCapPerItem: optionalNumber(e.target.value) })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Long Clip Threshold Seconds (optional)</label>
                                    <input type="number" min={0} value={config.longClipThresholdSeconds ?? ""} onChange={(e) => setConfig({ ...config, longClipThresholdSeconds: optionalNumber(e.target.value) })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Min Long Clip Inclusion Rate</label>
                                    <input type="number" step={0.01} value={config.minLongClipInclusionRate} onChange={(e) => setConfig({ ...config, minLongClipInclusionRate: parseFloat(e.target.value) || 0.0 })} style={inputStyle} />
                                </div>
                                <div>
                                    <label style={labelStyle}>Long Clip Boost</label>
                                    <input type="number" step={0.1} value={config.longClipBoost} onChange={(e) => setConfig({ ...config, longClipBoost: parseFloat(e.target.value) || 0.0 })} style={inputStyle} />
                                </div>
                            </div>
                        </details>
                    </div>
                )}

                {/* Start Button */}
                <button
                    onClick={handleStart}
                    disabled={selectedCount < minItemsRequired || starting}
                    style={{
                        width: "100%",
                        padding: "16px 32px",
                        borderRadius: 8,
                        border: "none",
                        background: selectedCount >= minItemsRequired ? "#00ff00" : "#333",
                        color: selectedCount >= minItemsRequired ? "#000" : "#666",
                        fontSize: 18,
                        fontWeight: 700,
                        cursor: selectedCount >= minItemsRequired && !starting ? "pointer" : "not-allowed",
                        marginTop: 16,
                    }}
                >
                    {starting ? "Starting..." : `Start Experiment (${selectedCount} items)`}
                </button>
                {startError && (
                    <div style={{ marginTop: 8, color: "#ff6666", fontSize: 13 }}>
                        {startError}
                    </div>
                )}

                {/* Admin publish + invite */}
                <div style={{ ...sectionStyle, marginTop: 24 }}>
                    <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Share With Participants</h2>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 12 }}>
                        <div>
                            <label style={labelStyle}>Admin Secret</label>
                            <input
                                type="password"
                                value={adminSecret}
                                onChange={(e) => setAdminSecret(e.target.value)}
                                style={inputStyle}
                                placeholder="Set in server ADMIN_SECRET"
                            />
                        </div>
                        <div>
                            <label style={labelStyle}>Participant ID</label>
                            <input
                                type="text"
                                value={inviteParticipantId}
                                onChange={(e) => setInviteParticipantId(e.target.value)}
                                style={inputStyle}
                                placeholder="e.g. P001"
                            />
                        </div>
                    </div>
                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button
                            onClick={handlePublish}
                            disabled={publishing}
                            style={{
                                padding: "10px 20px",
                                borderRadius: 6,
                                border: "1px solid #444",
                                background: "#1a1a1a",
                                color: "#fff",
                                cursor: publishing ? "not-allowed" : "pointer",
                                fontSize: 13,
                            }}
                        >
                            {publishing ? "Publishing..." : "Publish Study"}
                        </button>
                        <button
                            onClick={handleGenerateInvite}
                            disabled={creatingInvite || !publishedStudyId}
                            style={{
                                padding: "10px 20px",
                                borderRadius: 6,
                                border: "1px solid #444",
                                background: publishedStudyId ? "#0a2a0a" : "#1a1a1a",
                                color: "#fff",
                                cursor: creatingInvite || !publishedStudyId ? "not-allowed" : "pointer",
                                fontSize: 13,
                            }}
                        >
                            {creatingInvite ? "Generating..." : "Generate Invite Link"}
                        </button>
                    </div>
                    {publishedStudyId && (
                        <div style={{ marginTop: 8, color: "#666", fontSize: 12 }}>
                            Study ID: {publishedStudyId}
                        </div>
                    )}
                    {publishError && (
                        <div style={{ marginTop: 8, color: "#ff6666", fontSize: 13 }}>
                            {publishError}
                        </div>
                    )}
                    {inviteError && (
                        <div style={{ marginTop: 8, color: "#ff6666", fontSize: 13 }}>
                            {inviteError}
                        </div>
                    )}
                    {inviteLink && (
                        <div style={{ marginTop: 12 }}>
                            <label style={labelStyle}>Invite Link</label>
                            <input
                                type="text"
                                readOnly
                                value={inviteLink}
                                style={inputStyle}
                                onFocus={(e) => e.currentTarget.select()}
                            />
                            <button
                                onClick={() => navigator.clipboard?.writeText(inviteLink)}
                                style={{
                                    marginTop: 8,
                                    padding: "8px 12px",
                                    borderRadius: 6,
                                    border: "1px solid #444",
                                    background: "#1a1a1a",
                                    color: "#fff",
                                    cursor: "pointer",
                                    fontSize: 12,
                                }}
                            >
                                Copy link
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

// Helper styles
const presetBtnStyle = (active: boolean) => ({
    padding: "8px 16px",
    borderRadius: 4,
    border: active ? "2px solid #00ff00" : "1px solid #444",
    background: active ? "#0a2a0a" : "#1a1a1a",
    color: "#fff",
    cursor: "pointer" as const,
    fontSize: 13,
});

const paradigmBtnStyle = (active: boolean) => ({
    flex: 1,
    padding: "16px",
    borderRadius: 8,
    border: active ? "2px solid #00ff00" : "2px solid #333",
    background: active ? "#0a2a0a" : "#1a1a1a",
    color: "#fff",
    cursor: "pointer" as const,
});

const IMAGE_DURATION_FALLBACK = 0.5;
const AUDIO_DURATION_FALLBACK = 3.0;
const VIDEO_DURATION_FALLBACK = 5.0;

const DEFAULT_INSTRUCTIONS = {
    en: {
        arrangement: [
            "Drag all items inside the circle.",
            "Place similar items close together and dissimilar items farther apart.",
            "Double-click an item to play it (audio/video).",
            "When all items are inside, click Done to continue.",
        ],
        pairwise: [
            "Play both items, then rate how similar they are.",
            "Use the full 1–7 scale when possible.",
            "1 = very different, 7 = very similar.",
        ],
    },
    tr: {
        arrangement: [
            "Tüm öğeleri dairenin içine sürükleyin.",
            "Benzerleri yakın, farklıları daha uzak yerleştirin.",
            "Öğeyi oynatmak için çift tıklayın (ses/video).",
            "Hepsi içerideyken Bitir'e basın.",
        ],
        pairwise: [
            "Her iki öğeyi oynatın, sonra benzerlik puanı verin.",
            "Mümkün olduğunca 1–7 ölçeğinin tamamını kullanın.",
            "1 = çok farklı, 7 = çok benzer.",
        ],
    },
};

function parseCustomInstructions(text: string): string[] {
    return text
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
}

function buildInstructions(config: ExperimentConfig): string[] | null {
    if (config.instructionsMode === "off") return null;
    if (config.instructionsMode === "custom") {
        const custom = parseCustomInstructions(config.customInstructions || "");
        return custom.length ? custom : null;
    }
    const lang = config.instructionsMode === "tr" ? "tr" : "en";
    const key = config.paradigm === "pairwise" ? "pairwise" : "arrangement";
    return DEFAULT_INSTRUCTIONS[lang][key];
}

function coalesceDuration(value: number | null | undefined, mediaType: "video" | "audio" | "image"): number {
    if (typeof value === "number" && Number.isFinite(value) && value > 0) return value;
    if (mediaType === "image") return IMAGE_DURATION_FALLBACK;
    if (mediaType === "audio") return AUDIO_DURATION_FALLBACK;
    return VIDEO_DURATION_FALLBACK;
}

function getDurationFromUrl(url: string, mediaType: "video" | "audio"): Promise<number | null> {
    return new Promise((resolve) => {
        const el = document.createElement(mediaType === "audio" ? "audio" : "video");
        let settled = false;
        const cleanup = () => {
            if (settled) return;
            settled = true;
            el.src = "";
            el.load();
            el.remove();
        };
        el.preload = "metadata";
        el.crossOrigin = "anonymous";
        el.onloadedmetadata = () => {
            const dur = Number.isFinite(el.duration) ? el.duration : null;
            cleanup();
            resolve(dur);
        };
        el.onerror = () => {
            cleanup();
            resolve(null);
        };
        el.src = url;
    });
}

async function getDurationFromFile(file: File, mediaType: "video" | "audio" | "image"): Promise<number | null> {
    if (mediaType === "image") return IMAGE_DURATION_FALLBACK;
    const objUrl = URL.createObjectURL(file);
    try {
        const duration = await getDurationFromUrl(objUrl, mediaType === "audio" ? "audio" : "video");
        return duration;
    } finally {
        URL.revokeObjectURL(objUrl);
    }
}

async function ensureDurations(videos: VideoFile[]): Promise<VideoFile[]> {
    return Promise.all(
        videos.map(async (v) => {
            if (typeof v.durationSeconds === "number" && Number.isFinite(v.durationSeconds) && v.durationSeconds > 0) {
                return v;
            }
            if (v.mediaType === "image") {
                return { ...v, durationSeconds: IMAGE_DURATION_FALLBACK };
            }
            if (!v.url) {
                return { ...v, durationSeconds: coalesceDuration(null, v.mediaType) };
            }
            const duration = await getDurationFromUrl(v.url, v.mediaType === "audio" ? "audio" : "video");
            return { ...v, durationSeconds: coalesceDuration(duration, v.mediaType) };
        })
    );
}

// Thumbnail extractor
function extractThumbnail(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
        const video = document.createElement("video");
        video.preload = "metadata";
        video.muted = true;
        video.onloadeddata = () => { video.currentTime = 0.1; };
        video.onseeked = () => {
            const canvas = document.createElement("canvas");
            canvas.width = 100; canvas.height = 75;
            const ctx = canvas.getContext("2d");
            if (ctx) {
                ctx.drawImage(video, 0, 0, 100, 75);
                resolve(canvas.toDataURL("image/jpeg", 0.7));
            } else reject(new Error("No context"));
            URL.revokeObjectURL(video.src);
        };
        video.onerror = () => { reject(new Error("Load error")); URL.revokeObjectURL(video.src); };
        video.src = URL.createObjectURL(file);
    });
}

function dataUrlToBlob(dataUrl: string): Blob {
    const [meta, data] = dataUrl.split(",");
    const match = /data:(.*);base64/.exec(meta);
    const mime = match ? match[1] : "image/jpeg";
    const binary = atob(data);
    const len = binary.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i += 1) {
        bytes[i] = binary.charCodeAt(i);
    }
    return new Blob([bytes], { type: mime });
}

function safeName(name: string): string {
    return name.replace(/[^a-zA-Z0-9_-]+/g, "_");
}

async function uploadToSupabase(file: File, label: string, supabase: ReturnType<typeof getSupabaseClient>) {
    if (!supabase) throw new Error("Supabase client not configured");
    const ext = file.name.split(".").pop() || "dat";
    const filename = `${Date.now()}_${safeName(label)}.${ext}`;
    const { error } = await supabase.storage.from(SUPABASE_BUCKET).upload(filename, file, {
        cacheControl: "3600",
        upsert: false,
    });
    if (error) throw new Error(`Upload failed: ${error.message}`);
    const { data } = supabase.storage.from(SUPABASE_BUCKET).getPublicUrl(filename);
    return data.publicUrl;
}

async function uploadThumbnailToSupabase(dataUrl: string, label: string, supabase: ReturnType<typeof getSupabaseClient>) {
    if (!supabase) throw new Error("Supabase client not configured");
    const blob = dataUrlToBlob(dataUrl);
    const filename = `${Date.now()}_${safeName(label)}_thumb.jpg`;
    const { error } = await supabase.storage.from(SUPABASE_BUCKET).upload(filename, blob, {
        cacheControl: "3600",
        upsert: false,
        contentType: "image/jpeg",
    });
    if (error) throw new Error(`Thumbnail upload failed: ${error.message}`);
    const { data } = supabase.storage.from(SUPABASE_BUCKET).getPublicUrl(filename);
    return data.publicUrl;
}
