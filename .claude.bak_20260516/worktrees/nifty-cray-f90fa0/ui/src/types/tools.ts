import type { LucideIcon } from "lucide-react";

export interface ToolDefinition {
  id: string;
  label: string;
  icon: LucideIcon;
  path: string;
  description: string;
}
