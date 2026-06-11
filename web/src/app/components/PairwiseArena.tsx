"use client";
/* eslint-disable @next/next/no-img-element */

import { useState, useCallback } from "react";

interface Stimulus {
    id: string;
    ordinal: number;
    label: string;
    mediaUrl: string;
    thumbnail?: string;
    mediaType: "video" | "audio" | "image";
}

interface PairwiseArenaProps {
    stimulusA: Stimulus;
    stimulusB: Stimulus;
    onSubmit: (rating: number) => void;
    onMediaPlay: (itemId: string, mediaUrl: string, mediaType: Stimulus["mediaType"]) => void;
    trialIndex: number;
    totalTrials: number;
    language?: "en" | "tr";
    submitting?: boolean;
}

export default function PairwiseArena({
    stimulusA,
    stimulusB,
    onSubmit,
    onMediaPlay,
    trialIndex,
    totalTrials,
    language = "en",
    submitting = false,
}: PairwiseArenaProps) {
    const [rating, setRating] = useState<number | null>(null);
    const [watchedA, setWatchedA] = useState(stimulusA.mediaType === "image");
    const [watchedB, setWatchedB] = useState(stimulusB.mediaType === "image");

    // Re-derive per trial: the component stays mounted across trials, and
    // image stimuli never need playing before submission. State is adjusted
    // during render (the React-documented pattern) rather than in an effect.
    const trialKey = `${trialIndex}:${stimulusA.id}:${stimulusB.id}`;
    const [prevTrialKey, setPrevTrialKey] = useState(trialKey);
    if (prevTrialKey !== trialKey) {
        setPrevTrialKey(trialKey);
        setRating(null);
        setWatchedA(stimulusA.mediaType === "image");
        setWatchedB(stimulusB.mediaType === "image");
    }

    const canSubmit = rating !== null && watchedA && watchedB && !submitting;

    const handlePlayA = useCallback(() => {
        onMediaPlay(stimulusA.id, stimulusA.mediaUrl, stimulusA.mediaType);
        setWatchedA(true);
    }, [stimulusA, onMediaPlay]);

    const handlePlayB = useCallback(() => {
        onMediaPlay(stimulusB.id, stimulusB.mediaUrl, stimulusB.mediaType);
        setWatchedB(true);
    }, [stimulusB, onMediaPlay]);

    const handleSubmit = useCallback(() => {
        if (rating !== null && !submitting) {
            onSubmit(rating);
            // Per-trial state resets via the trialKey check above when the next pair arrives.
        }
    }, [rating, submitting, onSubmit]);

    // Rating labels: 1 = very different to 7 = very similar (similarity scale)
    const ratingLabels = language === "tr"
        ? [
            "Çok farklı",
            "Farklı",
            "Biraz farklı",
            "Nötr",
            "Biraz benzer",
            "Benzer",
            "Çok benzer",
        ]
        : [
            "Very Different",
            "Different",
            "Somewhat Different",
            "Neutral",
            "Somewhat Similar",
            "Similar",
            "Very Similar",
        ];

    return (
        <div
            style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 32,
                padding: 32,
                color: "#fff",
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            {/* Progress */}
            <div style={{ color: "#666", fontSize: 14 }}>
                {language === "tr"
                    ? `Aşama ${trialIndex + 1} / ${totalTrials}`
                    : `Trial ${trialIndex + 1} of ${totalTrials}`}
            </div>

            {/* Instruction */}
            <h2 style={{ fontSize: 20, fontWeight: 600, textAlign: "center", margin: 0 }}>
                {language === "tr"
                    ? "Bu iki öğe ne kadar benzer?"
                    : "How similar are these two items?"}
            </h2>

            {/* Two stimuli side by side */}
            <div style={{ display: "flex", gap: 48, justifyContent: "center" }}>
                {/* Stimulus A */}
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 12,
                    }}
                >
                    <div
                        style={{
                            width: 180,
                            height: 180,
                            borderRadius: 12,
                            overflow: "hidden",
                            border: watchedA ? "3px solid #00ff00" : "3px solid #444",
                            cursor: "pointer",
                            transition: "border-color 0.2s",
                        }}
                        onClick={handlePlayA}
                    >
                        {stimulusA.thumbnail ? (
                            <img
                                src={stimulusA.thumbnail}
                                alt={stimulusA.label}
                                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                            />
                        ) : (
                            <div
                                style={{
                                    width: "100%",
                                    height: "100%",
                                    background: "#222",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontSize: 14,
                                    color: "#666",
                                }}
                            >
                                {stimulusA.mediaType.toUpperCase()}
                            </div>
                        )}
                    </div>
                    <button
                        onClick={handlePlayA}
                        style={{
                            padding: "10px 24px",
                            borderRadius: 8,
                            border: "none",
                            background: watchedA ? "#00ff00" : "#333",
                            color: watchedA ? "#000" : "#fff",
                            fontSize: 14,
                            fontWeight: 600,
                            cursor: "pointer",
                            transition: "all 0.2s",
                        }}
                    >
                        {watchedA
                            ? (language === "tr" ? "✓ A görüldü" : "✓ Viewed A")
                            : (stimulusA.mediaType === "image"
                                ? (language === "tr" ? "🔍 A büyüt" : "🔍 View A")
                                : (language === "tr" ? "▶ A oynat" : "▶ Play A"))}
                    </button>
                </div>

                {/* VS divider */}
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        fontSize: 24,
                        fontWeight: 700,
                        color: "#444",
                    }}
                >
                    vs
                </div>

                {/* Stimulus B */}
                <div
                    style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "center",
                        gap: 12,
                    }}
                >
                    <div
                        style={{
                            width: 180,
                            height: 180,
                            borderRadius: 12,
                            overflow: "hidden",
                            border: watchedB ? "3px solid #00ff00" : "3px solid #444",
                            cursor: "pointer",
                            transition: "border-color 0.2s",
                        }}
                        onClick={handlePlayB}
                    >
                        {stimulusB.thumbnail ? (
                            <img
                                src={stimulusB.thumbnail}
                                alt={stimulusB.label}
                                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                            />
                        ) : (
                            <div
                                style={{
                                    width: "100%",
                                    height: "100%",
                                    background: "#222",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontSize: 14,
                                    color: "#666",
                                }}
                            >
                                {stimulusB.mediaType.toUpperCase()}
                            </div>
                        )}
                    </div>
                    <button
                        onClick={handlePlayB}
                        style={{
                            padding: "10px 24px",
                            borderRadius: 8,
                            border: "none",
                            background: watchedB ? "#00ff00" : "#333",
                            color: watchedB ? "#000" : "#fff",
                            fontSize: 14,
                            fontWeight: 600,
                            cursor: "pointer",
                            transition: "all 0.2s",
                        }}
                    >
                        {watchedB
                            ? (language === "tr" ? "✓ B görüldü" : "✓ Viewed B")
                            : (stimulusB.mediaType === "image"
                                ? (language === "tr" ? "🔍 B büyüt" : "🔍 View B")
                                : (language === "tr" ? "▶ B oynat" : "▶ Play B"))}
                    </button>
                </div>
            </div>

            {/* Rating scale */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
                <div style={{ display: "flex", gap: 8 }}>
                    {[1, 2, 3, 4, 5, 6, 7].map((value) => (
                        <button
                            key={value}
                            onClick={() => setRating(value)}
                            style={{
                                width: 48,
                                height: 48,
                                borderRadius: 8,
                                border: rating === value ? "3px solid #00ff00" : "2px solid #444",
                                background: rating === value ? "#0a2a0a" : "#1a1a1a",
                                color: rating === value ? "#00ff00" : "#fff",
                                fontSize: 18,
                                fontWeight: 600,
                                cursor: "pointer",
                                transition: "all 0.15s",
                            }}
                        >
                            {value}
                        </button>
                    ))}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", width: "100%", maxWidth: 400 }}>
                    <span style={{ color: "#888", fontSize: 12 }}>
                        {language === "tr" ? "1 = Çok farklı" : "1 = Very Different"}
                    </span>
                    <span style={{ color: "#888", fontSize: 12 }}>
                        {language === "tr" ? "7 = Çok benzer" : "7 = Very Similar"}
                    </span>
                </div>
                {rating !== null && (
                    <div style={{ color: "#00ff00", fontSize: 14 }}>
                        {ratingLabels[rating - 1]}
                    </div>
                )}
            </div>

            {/* Submit button */}
            <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                style={{
                    padding: "14px 48px",
                    borderRadius: 12,
                    border: "none",
                    background: canSubmit ? "#00ff00" : "#333",
                    color: canSubmit ? "#000" : "#666",
                    fontSize: 16,
                    fontWeight: 700,
                    cursor: canSubmit ? "pointer" : "not-allowed",
                    transition: "all 0.2s",
                    marginTop: 16,
                }}
            >
                {canSubmit
                    ? (language === "tr" ? "Puanı gönder" : "Submit Rating")
                    : (language === "tr" ? "Devam etmek için ikisini izleyip puanlayın" : "Watch both & rate to continue")}
            </button>
        </div>
    );
}
