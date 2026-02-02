"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Redirect to setup page
    router.replace("/setup");
  }, [router]);

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
      <p>Redirecting to setup...</p>
    </div>
  );
}
