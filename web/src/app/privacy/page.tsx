import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
    title: "Privacy | Multiarrangement",
    description: "What the hosted Multiarrangement service stores and who controls it.",
};

const paragraphStyle = { color: "#aaa", fontSize: 15, lineHeight: 1.7, margin: "0 0 16px" } as const;

export default function PrivacyPage() {
    return (
        <div
            style={{
                minHeight: "calc(100vh - 56px)",
                background: "#000",
                color: "#fff",
                padding: "40px 24px",
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            <div style={{ maxWidth: 720, margin: "0 auto" }}>
                <div style={{ marginBottom: 8, fontSize: 13, color: "#555" }}>
                    <Link href="/" style={{ color: "#666", textDecoration: "none" }}>Home</Link>
                    <span style={{ margin: "0 8px" }}>/</span>
                    <span style={{ color: "#fff" }}>Privacy</span>
                </div>

                <h1 style={{ fontSize: 28, fontWeight: 700, marginBottom: 24 }}>Privacy</h1>

                <p style={paragraphStyle}>
                    Multiarrangement stores studies, sessions and trial records (the stimuli shown in each
                    trial, final positions, ratings, durations and movement traces) in a PostgreSQL database
                    hosted by Supabase, and uploaded stimuli in a storage bucket scoped by study.
                </p>
                <p style={paragraphStyle}>
                    Its database stores no names, e-mail addresses or network addresses; the web server&apos;s
                    access log may record client addresses. Participants are identified only by the identifier
                    the experimenter assigns to an invite, or by the invite token.
                </p>
                <p style={paragraphStyle}>
                    Each study belongs to the experimenter key that created it; exporting a study&apos;s data
                    requires that key. Experimenters can delete single sessions or whole studies, and deleting a
                    study removes its sessions, trials and uploaded media.
                </p>
                <p style={paragraphStyle}>
                    Nothing is deleted automatically: retention, consent and compliance with local
                    data-protection rules rest with the experimenter. Studies that need institutional control
                    of their data can run the same open-source code on their own servers.
                </p>

                <p style={{ ...paragraphStyle, marginTop: 32, color: "#888" }}>
                    Questions:{" "}
                    <a href="mailto:umur.yildiz@bilkent.edu.tr" style={{ color: "#00ff88", textDecoration: "none" }}>
                        umur.yildiz@bilkent.edu.tr
                    </a>
                </p>
            </div>
        </div>
    );
}
