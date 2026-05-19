"use client";

import { ToolLauncher } from "@/components/tools/tool-launcher";
import { ToolsHub } from "@/components/tools/tools-hub";
import { useIsMobile } from "@/lib/hooks/use-mobile";

export default function ToolsPage() {
  const { isMobile } = useIsMobile();
  return isMobile ? <ToolsHub /> : <ToolLauncher />;
}
