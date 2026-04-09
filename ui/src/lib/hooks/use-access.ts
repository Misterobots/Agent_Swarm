"use client";

import { useEffect, useState } from "react";

const API_BASE = "/api/backend";

interface IdentityResponse {
  caller_identity?: {
    security_level?: string;
    [key: string]: unknown;
  } | string;
}

function parseSecurityLevel(payload: IdentityResponse): string {
  const caller = payload?.caller_identity;
  if (!caller || typeof caller === "string") return "";
  const level = caller.security_level;
  return typeof level === "string" ? level.toUpperCase() : "";
}

export function useAccess() {
  const [loading, setLoading] = useState(true);
  const [securityLevel, setSecurityLevel] = useState<string>("");

  useEffect(() => {
    let mounted = true;

    fetch(`${API_BASE}/api/v1/identity`)
      .then(async (resp) => {
        if (!resp.ok) return null;
        const data = (await resp.json()) as IdentityResponse;
        return parseSecurityLevel(data);
      })
      .then((level) => {
        if (!mounted) return;
        setSecurityLevel(level || "");
      })
      .catch(() => {
        if (!mounted) return;
        setSecurityLevel("");
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  return {
    loading,
    securityLevel,
    isAdmin: securityLevel === "L3_ADMIN" || securityLevel === "L4_SYSTEM",
  };
}
