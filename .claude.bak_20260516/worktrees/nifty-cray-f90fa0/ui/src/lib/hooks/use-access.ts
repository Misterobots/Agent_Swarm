"use client";

import { useEffect, useState } from "react";

const API_BASE = "/api/backend";

interface CallerIdentity {
  security_level?: string;
  username?: string;
  email?: string;
  name?: string;
  uid?: string;
  groups?: string[];
  auth_source?: string;
  [key: string]: unknown;
}

interface IdentityResponse {
  caller_identity?: CallerIdentity | string;
}

function parseIdentity(payload: IdentityResponse) {
  const caller = payload?.caller_identity;
  if (!caller || typeof caller === "string") {
    return { securityLevel: "", username: "", displayName: "", email: "", authenticated: false };
  }
  const level = typeof caller.security_level === "string" ? caller.security_level.toUpperCase() : "";
  return {
    securityLevel: level,
    username: caller.username || "",
    uid: caller.uid || "",
    displayName: caller.name || caller.username || "",
    email: caller.email || "",
    authenticated: !!caller.auth_source,
  };
}

export function useAccess() {
  const [loading, setLoading] = useState(true);
  const [securityLevel, setSecurityLevel] = useState("");
  const [username, setUsername] = useState("");
  const [uid, setUid] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    let mounted = true;

    fetch(`${API_BASE}/api/v1/identity`)
      .then(async (resp) => {
        if (!resp.ok) return null;
        return (await resp.json()) as IdentityResponse;
      })
      .then((data) => {
        if (!mounted || !data) return;
        const id = parseIdentity(data);
        setSecurityLevel(id.securityLevel);
        setUsername(id.username);
        setUid(id.uid);
        setDisplayName(id.displayName);
        setEmail(id.email);
        setAuthenticated(id.authenticated);
      })
      .catch(() => {
        if (!mounted) return;
        setSecurityLevel("");
        setAuthenticated(false);
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
    username,
    uid,
    displayName,
    email,
    authenticated,
  };
}
