import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { DJANGO_API_URL } from "@/lib/env";
import { setSessionCookies } from "@/lib/auth-cookies";
import type { Envelope } from "@/lib/api-types";

type TokenPairData = { access: string; refresh: string; access_expires_in: number; refresh_expires_in: number };

// Proxies to Django's /api/v1/auth/login and, on success, converts the
// returned JWT pair into httpOnly cookies on this origin — the browser
// never sees the raw tokens (BFF pattern; see docs/app/guides/backend-for-frontend).
export async function POST(request: Request) {
  const body = await request.json();

  const djangoRes = await fetch(`${DJANGO_API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });

  const envelope: Envelope<TokenPairData> = await djangoRes.json();

  if (!djangoRes.ok || !envelope.success || !envelope.data) {
    return NextResponse.json(
      { success: false, message: envelope.message, errors: envelope.errors },
      { status: djangoRes.status }
    );
  }

  const store = await cookies();
  setSessionCookies(store, envelope.data);

  return NextResponse.json({ success: true, message: envelope.message });
}
