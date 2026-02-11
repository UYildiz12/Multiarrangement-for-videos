"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { useKey } from "../lib/KeyContext";
import Logo from "./Logo";
import { EyeIcon, EyeOffIcon } from "./EyeIcon";

const NAV_ITEMS = [
    { href: "/", label: "Dashboard", icon: "◉" },
    { href: "/setup", label: "Setup", icon: "⚙" },
    { href: "/chains", label: "Chains", icon: "⛓" },
    { href: "/admin", label: "Experimenter", icon: "☸" },
];

// Pages where nav should be hidden (participant-facing)
const HIDDEN_PATHS = ["/experiment", "/participate"];

export default function NavBar() {
    const pathname = usePathname();
    const { adminKey, isAuthenticated, isLocalBypass, clearKey } = useKey();
    const [showKey, setShowKey] = useState(false);
    const [copied, setCopied] = useState(false);
    const copyTimeoutRef = useRef<number | null>(null);
    const hasKey = adminKey.trim().length > 0;

    const handleCopy = () => {
        navigator.clipboard.writeText(adminKey);
        setCopied(true);
        if (copyTimeoutRef.current !== null) {
            window.clearTimeout(copyTimeoutRef.current);
        }
        copyTimeoutRef.current = window.setTimeout(() => {
            setCopied(false);
            copyTimeoutRef.current = null;
        }, 2000);
    };

    useEffect(() => {
        return () => {
            if (copyTimeoutRef.current !== null) {
                window.clearTimeout(copyTimeoutRef.current);
            }
        };
    }, []);

    // Hide nav on participant-facing pages
    if (HIDDEN_PATHS.some((p) => pathname.startsWith(p))) {
        return null;
    }

    return (
        <nav
            style={{
                position: "sticky",
                top: 0,
                zIndex: 100,
                background: "rgba(0, 0, 0, 0.85)",
                backdropFilter: "blur(12px)",
                borderBottom: "1px solid #1a1a1a",
                padding: "0 24px",
                fontFamily: "'Inter', -apple-system, sans-serif",
            }}
        >
            <div
                style={{
                    maxWidth: 1200,
                    margin: "0 auto",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    height: 56,
                }}
            >
                {/* Logo / Brand */}
                <Link
                    href="/"
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        textDecoration: "none",
                        color: "#fff",
                    }}
                >
                    <Logo size={32} variant="mono" animated={false} />
                    <span
                        style={{
                            fontWeight: 600,
                            fontSize: 15,
                            letterSpacing: "-0.3px",
                        }}
                    >
                        Multiarrangement
                    </span>
                </Link>

                {/* Nav Links */}
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    {NAV_ITEMS.map((item) => {
                        const isActive = item.href === "/"
                            ? pathname === "/"
                            : pathname.startsWith(item.href);
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 6,
                                    padding: "8px 14px",
                                    borderRadius: 8,
                                    textDecoration: "none",
                                    fontSize: 13,
                                    fontWeight: isActive ? 600 : 400,
                                    color: isActive ? "#fff" : "#888",
                                    background: isActive ? "rgba(255,255,255,0.08)" : "transparent",
                                    transition: "all 0.15s ease",
                                }}
                            >
                                <span style={{ fontSize: 14 }}>{item.icon}</span>
                                {item.label}
                            </Link>
                        );
                    })}
                </div>

                {/* Auth Badge */}
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    {isAuthenticated ? (
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <span
                                style={{
                                    width: 8,
                                    height: 8,
                                    borderRadius: "50%",
                                    background: "#00ff88",
                                    display: "inline-block",
                                }}
                            />
                            {isLocalBypass && !hasKey ? (
                                <span
                                    style={{
                                        fontSize: 12,
                                        color: "#7fcaab",
                                        letterSpacing: "0.1px",
                                    }}
                                >
                                    Local Keyless Mode
                                </span>
                            ) : (
                                <>
                                    <span style={{ fontSize: 12, color: "#888", fontFamily: showKey ? "monospace" : "inherit" }}>
                                        {showKey ? adminKey.slice(0, 12) + "..." : `Key: ${adminKey.slice(0, 4)}***`}
                                    </span>
                                    <button
                                        onClick={() => setShowKey(!showKey)}
                                        style={{
                                            background: "none",
                                            border: "none",
                                            color: "#888",
                                            cursor: "pointer",
                                            padding: "2px",
                                            display: "flex",
                                            alignItems: "center",
                                        }}
                                        title={showKey ? "Hide key" : "Show key"}
                                    >
                                        {showKey ? <EyeOffIcon size={14} color="#888" /> : <EyeIcon size={14} color="#888" />}
                                    </button>
                                    {showKey && (
                                        <button
                                            onClick={handleCopy}
                                            style={{
                                                padding: "3px 8px",
                                                borderRadius: 4,
                                                border: "1px solid #333",
                                                background: copied ? "#00ff88" : "transparent",
                                                color: copied ? "#000" : "#888",
                                                fontSize: 10,
                                                cursor: "pointer",
                                                fontWeight: copied ? 700 : 400,
                                            }}
                                        >
                                            {copied ? "✓" : "Copy"}
                                        </button>
                                    )}
                                    <button
                                        onClick={clearKey}
                                        style={{
                                            padding: "4px 10px",
                                            borderRadius: 6,
                                            border: "1px solid #333",
                                            background: "transparent",
                                            color: "#666",
                                            fontSize: 11,
                                            cursor: "pointer",
                                        }}
                                    >
                                        Sign out
                                    </button>
                                </>
                            )}
                        </div>
                    ) : (
                        <Link
                            href="/"
                            style={{
                                padding: "6px 14px",
                                borderRadius: 6,
                                border: "1px solid #333",
                                background: "rgba(0, 255, 136, 0.1)",
                                color: "#00ff88",
                                fontSize: 12,
                                fontWeight: 500,
                                textDecoration: "none",
                            }}
                        >
                            Enter Experimenter Key
                        </Link>
                    )}
                </div>
            </div>
        </nav>
    );
}
