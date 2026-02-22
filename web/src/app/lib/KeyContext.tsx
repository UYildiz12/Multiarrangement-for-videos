"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { apiFetch } from "./api";

interface KeyContextType {
    adminKey: string;
    setAdminKey: (key: string) => void;
    isAuthenticated: boolean;
    isLocalBypass: boolean;
    authReady: boolean;
    clearKey: () => void;
    generateKey: () => Promise<string>;
    generating: boolean;
}

const KeyContext = createContext<KeyContextType>({
    adminKey: "",
    setAdminKey: () => {},
    isAuthenticated: false,
    isLocalBypass: false,
    authReady: false,
    clearKey: () => {},
    generateKey: async () => "",
    generating: false,
});

const STORAGE_KEY = "experimenterKey";
const TRUTHY_ENV_VALUES = new Set(["1", "true", "yes", "on"]);
// Only allow auth bypass in development builds — never in production
const LOCAL_DEV_BYPASS_AUTH =
    process.env.NODE_ENV !== "production" &&
    TRUTHY_ENV_VALUES.has(
        (process.env.NEXT_PUBLIC_LOCAL_DEV_BYPASS_AUTH || "").trim().toLowerCase()
    );

export function KeyProvider({ children }: { children: ReactNode }) {
    const [adminKey, setAdminKeyState] = useState("");
    const [generating, setGenerating] = useState(false);
    const [isLocalBypass, setIsLocalBypass] = useState(LOCAL_DEV_BYPASS_AUTH);
    const [authReady, setAuthReady] = useState(false);

    useEffect(() => {
        let cancelled = false;
        const bootstrapAuth = async () => {
            if (LOCAL_DEV_BYPASS_AUTH) {
                if (cancelled) return;
                setIsLocalBypass(true);
                setAdminKeyState("");
                localStorage.removeItem(STORAGE_KEY);
                sessionStorage.removeItem("adminSecret");
                setAuthReady(true);
                return;
            }

            // Try localStorage first (persistent), fall back to sessionStorage (legacy)
            const saved = localStorage.getItem(STORAGE_KEY)
                || sessionStorage.getItem("adminSecret");
            if (saved) {
                if (cancelled) return;
                setAdminKeyState(saved);
                localStorage.setItem(STORAGE_KEY, saved);
                sessionStorage.removeItem("adminSecret");
                setAuthReady(true);
                return;
            }

            // Auto-detect local keyless mode from backend behavior.
            try {
                await apiFetch<unknown[]>("/api/v1/admin/studies");
                if (!cancelled) {
                    setIsLocalBypass(true);
                }
            } catch {
                if (!cancelled) {
                    setIsLocalBypass(false);
                }
            } finally {
                if (!cancelled) {
                    setAuthReady(true);
                }
            }
        };

        bootstrapAuth();
        return () => {
            cancelled = true;
        };
    }, []);

    const setAdminKey = useCallback((key: string) => {
        const normalized = key.trim();
        setAdminKeyState(normalized);
        if (normalized) {
            localStorage.setItem(STORAGE_KEY, normalized);
        } else {
            localStorage.removeItem(STORAGE_KEY);
        }
    }, []);

    const clearKey = useCallback(() => {
        setAdminKeyState("");
        localStorage.removeItem(STORAGE_KEY);
        sessionStorage.removeItem("adminSecret");
    }, []);

    const generateKey = useCallback(async () => {
        setGenerating(true);
        try {
            const data = await apiFetch<{ key: string }>("/api/v1/experimenter/generate-key", {
                method: "POST",
            });
            return data.key;
        } finally {
            setGenerating(false);
        }
    }, []);

    return (
        <KeyContext.Provider
            value={{
                adminKey,
                setAdminKey,
                isAuthenticated: isLocalBypass || adminKey.trim().length > 0,
                isLocalBypass,
                authReady,
                clearKey,
                generateKey,
                generating,
            }}
        >
            {children}
        </KeyContext.Provider>
    );
}

export function useKey() {
    return useContext(KeyContext);
}
