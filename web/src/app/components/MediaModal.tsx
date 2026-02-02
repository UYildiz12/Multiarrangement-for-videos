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
            }}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                style={{
                    position: "relative",
                    maxWidth: "80vw",
                    maxHeight: "80vh",
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
                    <audio
                        ref={audioRef}
                        src={mediaUrl}
                        controls
                        autoPlay
                        onEnded={() => {
                            onEnded?.();
                            onClose();
                        }}
                        style={{
                            width: "60vw",
                            maxWidth: 640,
                            display: "block",
                            padding: 24,
                            background: "#111",
                        }}
                    />
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
                    style={{
                        position: "absolute",
                        top: 10,
                        right: 10,
                        width: 32,
                        height: 32,
                        borderRadius: "50%",
                        border: "none",
                        background: "rgba(255, 255, 255, 0.2)",
                        color: "#fff",
                        fontSize: 18,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                    }}
                >
                    ×
                </button>
            </div>
        </div>
    );
}
