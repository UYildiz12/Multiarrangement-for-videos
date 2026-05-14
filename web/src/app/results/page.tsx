"use client";

import { useEffect, useState, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import * as XLSX from "xlsx";
import RdmHeatmap from "../components/RdmHeatmap";
import { apiFetch } from "../lib/api";

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

type Paradigm = "setcover" | "adaptive" | "pairwise";

interface SessionResponse {
    paradigm: Paradigm;
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

export default function ResultsPage() {
    return (
        <Suspense fallback={<LoadingFallback />}>
            <ResultsContent />
        </Suspense>
    );
}

function ResultsContent() {
    const searchParams = useSearchParams();
    const sessionId = searchParams.get("session");

    const [results, setResults] = useState<ResultsResponse | null>(null);
    const [loading, setLoading] = useState(Boolean(sessionId));
    const [error, setError] = useState<string | null>(null);
    const [paradigm, setParadigm] = useState<Paradigm | null>(null);
    const [language] = useState<"en" | "tr">(getStoredLanguage());

    const timeInfo = useCallback(() => {
        if (!sessionId) return { seconds: null, startIso: null, endIso: null };
        const key = `experimentTime_${sessionId}`;
        const stored = sessionStorage.getItem(key);
        if (!stored) return { seconds: null, startIso: null, endIso: null };
        try {
            const parsed = JSON.parse(stored) as { start?: number; end?: number };
            if (typeof parsed.start !== "number" || typeof parsed.end !== "number") {
                return { seconds: null, startIso: null, endIso: null };
            }
            const seconds = Math.max(0, (parsed.end - parsed.start) / 1000);
            return {
                seconds,
                startIso: new Date(parsed.start).toISOString(),
                endIso: new Date(parsed.end).toISOString(),
            };
        } catch {
            return { seconds: null, startIso: null, endIso: null };
        }
    }, [sessionId]);

    const copy = useCallback(() => {
        const tr = language === "tr";
        return {
            loading: tr ? "Yükleniyor..." : "Loading...",
            noSessionId: tr ? "Oturum kimliği verilmedi" : "No session ID provided",
            loadResultsError: tr ? "Sonuçlar yüklenemedi" : "Failed to load results",
            errorLabel: tr ? "Hata" : "Error",
            experimentComplete: tr ? "Deney tamamlandı" : "Experiment complete",
            sessionTrials: (id: string | null, nTrials: number | undefined) => (
                tr ? `Oturum ${id?.slice(0, 8)}… • ${nTrials ?? 0} aşama`
                    : `Session ${id?.slice(0, 8)}… • ${nTrials ?? 0} trials`
            ),
            backToAdmin: tr ? "← Yöneticiye dön" : "← Back to Admin",
        };
    }, [language]);

    useEffect(() => {
        if (!sessionId) return;
        apiFetch<ResultsResponse>(`/api/v1/sessions/${sessionId}/results`)
            .then((data) => setResults(data))
            .catch((err) => setError(err instanceof Error ? err.message : copy().loadResultsError))
            .finally(() => setLoading(false));
    }, [sessionId, copy]);

    useEffect(() => {
        if (!sessionId) return;
        apiFetch<SessionResponse>(`/api/v1/sessions/${sessionId}`)
            .then((data) => setParadigm(data.paradigm))
            .catch(() => {
                setParadigm(null);
            });
    }, [sessionId]);

    const handleDownloadJSON = useCallback(() => {
        if (!results) return;
        const t = timeInfo();
        const payload = {
            ...results,
            time_spent_seconds: t.seconds,
            time_spent_minutes: t.seconds === null ? null : t.seconds / 60,
            time_started_at: t.startIso,
            time_ended_at: t.endIso,
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
        const t = timeInfo();
        const metaLines = [
            `# rdm_scale_method,${results.rdm_scale?.method ?? ""}`,
            `# rdm_scale_divisor,${results.rdm_scale?.divisor ?? ""}`,
            `# rdm_raw_units,${results.rdm_scale?.raw_units ?? ""}`,
            `# time_spent_seconds,${t.seconds ?? ""}`,
            `# time_spent_minutes,${t.seconds === null ? "" : (t.seconds / 60).toFixed(2)}`,
            `# time_started_at,${t.startIso ?? ""}`,
            `# time_ended_at,${t.endIso ?? ""}`,
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
        const t = timeInfo();
        const metaData = [
            ["rdm_scale_method", results.rdm_scale?.method ?? ""],
            ["rdm_scale_divisor", results.rdm_scale?.divisor ?? ""],
            ["rdm_raw_units", results.rdm_scale?.raw_units ?? ""],
            ["time_spent_seconds", t.seconds ?? ""],
            ["time_spent_minutes", t.seconds === null ? "" : (t.seconds / 60).toFixed(2)],
            ["time_started_at", t.startIso ?? ""],
            ["time_ended_at", t.endIso ?? ""],
        ];
        const metaWs = XLSX.utils.aoa_to_sheet(metaData);
        XLSX.utils.book_append_sheet(wb, metaWs, "Meta");
        XLSX.utils.book_append_sheet(wb, ws, "RDM");
        XLSX.writeFile(wb, `session_${sessionId}_rdm.xlsx`);
    }, [results, sessionId, timeInfo]);

    if (loading) {
        return <LoadingFallback />;
    }

    const displayError = error ?? (!sessionId ? copy().noSessionId : null);

    if (displayError) {
        return (
            <div
                style={{
                    minHeight: "100vh",
                    background: "#000",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#ff6666",
                    fontFamily: "'Inter', -apple-system, sans-serif",
                }}
            >
                {copy().errorLabel}: {displayError}
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
                padding: 40,
                gap: 32,
                color: "#fff",
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            <div style={{ textAlign: "center" }}>
                <h2 style={{ marginBottom: 12 }}>{copy().experimentComplete}</h2>
                <p style={{ color: "#888", fontSize: 13, margin: 0 }}>
                    {copy().sessionTrials(sessionId, results?.n_trials)}
                </p>
            </div>

            {results && (
                <>
                    <RdmHeatmap
                        rdm={results.rdm}
                        labels={results.labels}
                        paradigm={paradigm ?? undefined}
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
                            onClick={handleDownloadJSON}
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

                    <a
                        href="/admin"
                        style={{
                            color: "#00ff88",
                            fontSize: 13,
                            marginTop: 16,
                            textDecoration: "none",
                        }}
                    >
                        {copy().backToAdmin}
                    </a>
                    <div style={{ display: "flex", gap: 12, marginTop: 8, justifyContent: "center" }}>
                        <Link href="/" style={{ color: "#666", fontSize: 12, textDecoration: "none" }}>Dashboard</Link>
                        <Link href="/setup" style={{ color: "#666", fontSize: 12, textDecoration: "none" }}>New Experiment</Link>
                    </div>
                </>
            )}
        </div>
    );
}
