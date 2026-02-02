"use client";

import ChainBuilder from "../components/ChainBuilder";

export default function ChainsPage() {
    return (
        <div
            style={{
                minHeight: "100vh",
                background: "#000",
                color: "#fff",
                padding: 40,
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            <div style={{ maxWidth: 1200, margin: "0 auto" }}>
                <div style={{ marginBottom: 32 }}>
                    <h1 style={{
                        fontSize: 32,
                        fontWeight: 700,
                        margin: 0,
                        background: "linear-gradient(135deg, #fff 0%, #888 100%)",
                        WebkitBackgroundClip: "text",
                        WebkitTextFillColor: "transparent",
                    }}>
                        Experiment Chains
                    </h1>
                    <p style={{ color: "#666", fontSize: 14, margin: "8px 0 0" }}>
                        Chain multiple experiments together for sequential participation
                    </p>
                </div>

                <ChainBuilder />

                <div style={{
                    marginTop: 40,
                    padding: 20,
                    background: "#0a0a0a",
                    borderRadius: 12,
                    border: "1px solid #1a1a1a",
                }}>
                    <h3 style={{ margin: "0 0 12px", fontSize: 14, color: "#666" }}>
                        How Chains Work
                    </h3>
                    <ol style={{ margin: 0, paddingLeft: 20, color: "#888", fontSize: 13, lineHeight: 1.8 }}>
                        <li>Create individual studies in the <a href="/setup" style={{ color: "#00ff88" }}>Setup page</a></li>
                        <li>Create a chain and add studies by their IDs</li>
                        <li>Generate an invite link for the chain</li>
                        <li>When participants open the link, they complete studies in sequence</li>
                        <li>After finishing one study, they automatically continue to the next</li>
                    </ol>
                </div>
            </div>
        </div>
    );
}
