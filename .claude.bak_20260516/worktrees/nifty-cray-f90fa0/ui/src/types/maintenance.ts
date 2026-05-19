export type MaintenanceRoute =
  | "agent"
  | "human"
  | "suppressed_cooldown"
  | "unmatched";

export type MaintenanceQueueStatus =
  | "pending"
  | "acked"
  | "escalated"
  | "resolved";

export interface MaintenanceQueueItem {
  id: number;
  created_at: string;
  alert_name: string;
  alert_labels: Record<string, string>;
  severity?: string | null;
  summary?: string | null;
  description?: string | null;
  blast_radius?: string | null;
  runbook?: string | null;
  status: MaintenanceQueueStatus;
  acked_at?: string | null;
  acked_by?: string | null;
  note?: string | null;
}

export interface MaintenanceAuditRow {
  id: number;
  ts: string;
  alert_name: string;
  route: MaintenanceRoute;
  action?: string | null;
  rule_index?: number | null;
  queue_item_id?: number | null;
}

export interface AckRequest {
  by: string;
  status: Exclude<MaintenanceQueueStatus, "pending">;
  note?: string;
}
