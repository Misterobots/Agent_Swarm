/**
 * Palace Viewer API client — fetches MemPalace layout, room memories,
 * and provides CRUD + audit operations for the 3D Palace Viewer.
 */

const API_BASE = "/api/backend";

// ── Types ─────────────────────────────────────────────────────────────────

export interface RoomInfo {
  name: string;
  drawer_count: number;
}

export interface HallInfo {
  name: string;
  rooms: RoomInfo[];
}

export interface WingInfo {
  name: string;
  halls: HallInfo[];
}

export interface PalaceLayout {
  wings: WingInfo[];
  total_memories: number;
}

export interface MemoryItem {
  id: string;
  content: string;
  memory_type: string;
  domain: string | null;
  agent_id: string | null;
  team_id: string | null;
  owner_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  access_count: number;
  score: number | null;
  wing: string | null;
  hall: string | null;
  room: string | null;
}

export interface AuditEntry {
  id: string;
  memory_id: string;
  action: "created" | "edited" | "deleted";
  actor_id: string;
  actor_role: string;
  previous_content: string | null;
  new_content: string | null;
  changed_fields: Record<string, unknown>;
  created_at: string;
}

// ── Fetchers ──────────────────────────────────────────────────────────────

export async function fetchPalaceLayout(
  ownerId?: string,
  agentId?: string,
): Promise<PalaceLayout> {
  const params = new URLSearchParams();
  if (ownerId) params.set("owner_id", ownerId);
  if (agentId) params.set("agent_id", agentId);
  const qs = params.toString();
  const url = `${API_BASE}/v1/palace/layout${qs ? `?${qs}` : ""}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Palace layout fetch failed: ${resp.status}`);
  return resp.json();
}

export async function fetchRoomMemories(
  wing: string,
  hall: string,
  room: string,
  ownerId?: string,
  limit = 100,
  offset = 0,
): Promise<MemoryItem[]> {
  const params = new URLSearchParams({ wing, hall, room });
  if (ownerId) params.set("owner_id", ownerId);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  const resp = await fetch(`${API_BASE}/v1/palace/room?${params}`);
  if (!resp.ok) throw new Error(`Room memories fetch failed: ${resp.status}`);
  return resp.json();
}

export async function searchMemories(
  query: string,
  ownerId?: string,
  limit = 20,
): Promise<MemoryItem[]> {
  const resp = await fetch(`${API_BASE}/v1/memories/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, owner_id: ownerId, limit }),
  });
  if (!resp.ok) throw new Error(`Memory search failed: ${resp.status}`);
  return resp.json();
}

// ── Mutations ─────────────────────────────────────────────────────────────

export async function editMemory(
  memoryId: string,
  updates: { content?: string; memory_type?: string; domain?: string; metadata?: Record<string, unknown> },
  actorId: string,
  actorRole: "user" | "admin",
): Promise<MemoryItem> {
  const params = new URLSearchParams({ actor_id: actorId, actor_role: actorRole });
  const resp = await fetch(`${API_BASE}/v1/memories/${memoryId}?${params}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
  if (!resp.ok) throw new Error(`Memory edit failed: ${resp.status}`);
  return resp.json();
}

export async function deleteMemory(memoryId: string): Promise<void> {
  const resp = await fetch(`${API_BASE}/v1/memories/${memoryId}`, {
    method: "DELETE",
  });
  if (!resp.ok) throw new Error(`Memory delete failed: ${resp.status}`);
}

export async function createMemory(data: {
  content: string;
  memory_type: string;
  domain: string;
  owner_id?: string;
  agent_id?: string;
  metadata?: Record<string, unknown>;
}): Promise<MemoryItem> {
  const resp = await fetch(`${API_BASE}/v1/memories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error(`Memory create failed: ${resp.status}`);
  return resp.json();
}

export async function fetchAuditLog(memoryId: string): Promise<AuditEntry[]> {
  const resp = await fetch(`${API_BASE}/v1/memories/${memoryId}/audit`);
  if (!resp.ok) throw new Error(`Audit log fetch failed: ${resp.status}`);
  return resp.json();
}
