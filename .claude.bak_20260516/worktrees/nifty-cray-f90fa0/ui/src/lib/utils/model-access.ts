const ADMIN_ONLY_PREFIXES = ["claude", "anthropic/"];

export function isAdminOnlyModel(modelId: string): boolean {
  const normalized = (modelId || "").trim().toLowerCase();
  return ADMIN_ONLY_PREFIXES.some((prefix) => normalized.startsWith(prefix));
}

export function canSelectModel(modelId: string, isAdmin: boolean): boolean {
  if (!isAdminOnlyModel(modelId)) return true;
  return isAdmin;
}
