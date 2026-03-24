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
