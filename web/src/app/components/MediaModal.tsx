"use client";

import { useEffect, useRef } from "react";

interface MediaModalProps {
    mediaUrl: string;
    mediaType: "video" | "audio" | "image";
    isOpen: boolean;
    onClose: () => void;
    onEnded?: () => void;
}

export default function MediaModal({
    mediaUrl,
    mediaType,
    isOpen,
    onClose,
    onEnded,
}: MediaModalProps) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const audioRef = useRef<HTMLAudioElement>(null);

    useEffect(() => {
        if (!isOpen) return;
        if (mediaType === "video" && videoRef.current) {
            videoRef.current.play();
        }
        if (mediaType === "audio" && audioRef.current) {
            audioRef.current.play();
        }
    }, [isOpen, mediaType]);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && isOpen) {
                onClose();
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, onClose]);

    if (!isOpen) return null;

    return (
        <div
            onClick={onClose}
            style={{
                position: "fixed",
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: "rgba(0, 0, 0, 0.9)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 2000,
                padding: 16,
            }}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                style={{
                    position: "relative",
                    borderRadius: 8,
                    overflow: "hidden",
                    boxShadow: "0 20px 60px rgba(0, 0, 0, 0.5)",
                    background: "#000",
                }}
            >
                {mediaType === "video" ? (
                    <video
                        ref={videoRef}
                        src={mediaUrl}
                        controls
                        autoPlay
                        onEnded={() => {
                            onEnded?.();
                            onClose();
                        }}
                        style={{
                            maxWidth: "80vw",
                            maxHeight: "80vh",
                            display: "block",
                        }}
                    />
                ) : mediaType === "audio" ? (
                    <div
                        style={{
                            width: "min(720px, 82vw)",
                            minHeight: 180,
                            padding: "28px 32px 24px",
                            display: "flex",
                            flexDirection: "column",
                            justifyContent: "center",
                            gap: 18,
                            background: "linear-gradient(180deg, #161616 0%, #0d0d0d 100%)",
                            color: "#fff",
                        }}
                    >
                        <div style={{ paddingRight: 36 }}>
                            <div
                                style={{
                                    fontSize: 12,
                                    fontWeight: 700,
                                    letterSpacing: "0.16em",
                                    textTransform: "uppercase",
                                    color: "rgba(255,255,255,0.55)",
                                    marginBottom: 8,
                                }}
                            >
                                Audio Stimulus
                            </div>
                            <div
                                style={{
                                    fontSize: 20,
                                    fontWeight: 600,
                                    lineHeight: 1.3,
                                }}
                            >
                                Playback
                            </div>
                        </div>
                        <audio
                            ref={audioRef}
                            src={mediaUrl}
                            controls
                            autoPlay
                            preload="metadata"
                            onEnded={() => {
                                onEnded?.();
                                onClose();
                            }}
                            style={{
                                width: "100%",
                                minHeight: 54,
                                display: "block",
                                borderRadius: 12,
                            }}
                        />
                    </div>
                ) : (
                    <img
                        src={mediaUrl}
                        alt="Stimulus"
                        style={{
                            maxWidth: "80vw",
                            maxHeight: "80vh",
                            display: "block",
                        }}
                    />
                )}
                <button
                    onClick={onClose}
                    aria-label="Close media"
                    style={{
                        position: "absolute",
                        top: 12,
                        right: 12,
                        width: 32,
                        height: 32,
                        borderRadius: "50%",
                        border: "none",
                        background: "rgba(255, 255, 255, 0.18)",
                        color: "#fff",
                        fontSize: 18,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                    }}
                >
                    x
                </button>
            </div>
        </div>
    );
}
