import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Mounted at /app/docs in Docker, or relative to project root in dev
function getDocsRoot(): string {
  const mounted = "/app/docs";
  if (fs.existsSync(mounted)) return mounted;
  // Local dev: ui/ is cwd, docs/ is one level up
  return path.join(process.cwd(), "..", "docs");
}

const ALLOWED_DOCS: Record<string, string> = {
  "user/overview": "user/overview.md",
  "user/framework": "user/framework.md",
  "user/faq": "user/faq.md",
  "admin/design_framework": "admin/design_framework.md",
  "admin/security": "admin/security.md",
  "admin/technical_reference": "admin/technical_reference.md",
  "admin/troubleshooting": "admin/troubleshooting.md",
  "architecture/multi-user-propagation": "architecture/multi_user_propagation_trace.md",
  "architecture/cross-user-isolation-tests": "architecture/cross_user_isolation_test_plan.md",
  "governance/standard": "governance/documentation_governance_standard.md",
  "governance/gap-register": "governance/documentation_gap_register.md",
  "security/identity-trust": "security/identity_token_trust_standard.md",
  "security/api-auth-contract": "security/api_authentication_contract.md",
  "security/api-auth-examples": "security/api_contract_validation_examples.md",
  "security/key-lifecycle": "security/key_lifecycle_rotation_runbook.md",
  "security/key-compromise-runbook": "security/key_compromise_incident_runbook.md",
  "security/key-compromise-checklist": "security/key_compromise_incident_checklist.md",
  "security/multi-user-scoping": "security/multi_user_identity_scoping_standard.md",
  "security/hook-policy": "security/hook_security_execution_policy.md",
  "catalog/system": "catalog/system_component_service_catalog.md",
  "compliance/feature-traceability": "compliance/feature_control_traceability_matrix.md",
  "compliance/voice-feature-mapping": "compliance/voice_feature_control_mapping.md",
  "compliance/iot-feature-mapping": "compliance/iot_feature_control_mapping.md",
};

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const doc = searchParams.get("doc");

  if (!doc || !ALLOWED_DOCS[doc]) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const filePath = path.join(getDocsRoot(), ALLOWED_DOCS[doc]);

  try {
    const content = fs.readFileSync(filePath, "utf-8");
    return new NextResponse(content, {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  } catch {
    return NextResponse.json({ error: "File not found" }, { status: 404 });
  }
}
