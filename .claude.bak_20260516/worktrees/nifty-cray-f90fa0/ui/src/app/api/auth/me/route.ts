import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const username = req.headers.get("x-authentik-username") ?? null;
  const uid = req.headers.get("x-authentik-uid") ?? null;
  const name = req.headers.get("x-authentik-name") ?? null;
  const email = req.headers.get("x-authentik-email") ?? null;
  const groups = req.headers.get("x-authentik-groups") ?? null;

  return NextResponse.json({ username, uid, name, email, groups });
}
