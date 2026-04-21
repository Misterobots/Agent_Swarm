"use client";

import { useEffect, useState } from "react";

export interface GroundingStatus {
  web_grounding: boolean;
  docs_grounding: boolean;
  file_grounding: boolean;
}

async function fetchGroundingStatus(): Promise<GroundingStatus> {
  const res = await fetch("/api/backend/api/v1/grounding/status");
  if (!res.ok) return { web_grounding: false, docs_grounding: false, file_grounding: false };
  return res.json();
}

async function submitGroundingRequest(
  permission: "web_grounding" | "docs_grounding" | "file_grounding",
  reason: string
): Promise<{ status: string; request_id: string }> {
  const res = await fetch("/api/backend/api/v1/grounding/request", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ permission, reason }),
  });
  if (!res.ok) throw new Error(`Request failed: ${res.statusText}`);
  return res.json();
}

export function useGroundingPermissions() {
  const [status, setStatus] = useState<GroundingStatus>({ web_grounding: false, docs_grounding: false, file_grounding: false });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchGroundingStatus()
      .then(setStatus)
      .catch(() => {/* permissions endpoint unavailable – stay false */})
      .finally(() => setLoading(false));
  }, []);

  const request = async (permission: "web_grounding" | "docs_grounding" | "file_grounding", reason: string) => {
    return submitGroundingRequest(permission, reason);
  };

  return { status, loading, request };
}
