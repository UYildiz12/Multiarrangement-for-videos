"use client";

import Link from "next/link";
import ChainBuilder from "../components/ChainBuilder";

export default function ChainsPage() {
    return (
        <div
            style={{
                minHeight: "calc(100vh - 56px)",
                background: "#000",
                color: "#fff",
                padding: 40,
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            <div style={{ maxWidth: 1200, margin: "0 auto" }}>
                {/* Breadcrumb */}
                <div style={{ marginBottom: 8, fontSize: 13, color: "#555" }}>
                    <Link href="/" style={{ color: "#666", textDecoration: "none" }}>Dashboard</Link>
                    <span style={{ margin: "0 8px" }}>/</span>
                    <span style={{ color: "#fff" }}>Chains</span>
                </div>

                <div style={{ marginBottom: 32 }}>
                    <h1 style={{
                        fontSize: 28,
                        fontWeight: 700,
                        margin: 0,
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
                        <li>Create individual studies in the <Link href="/setup" style={{ color: "#00ff88" }}>Setup page</Link></li>
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
