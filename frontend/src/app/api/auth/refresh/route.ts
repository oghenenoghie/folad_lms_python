import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { DJANGO_API_URL } from "@/lib/env";
import { REFRESH_COOKIE, setSessionCookies, clearSessionCookies } from "@/lib/auth-cookies";
import type { Envelope } from "@/lib/api-types";

type TokenPairData = { access: string; refresh: string; access_expires_in: number; refresh_expires_in: number };

// Manual refresh, for a client-side fetch wrapper to call after a 401 from
// one of this app's own API routes. proxy.ts performs the same refresh
// optimistically on page navigation, so this mostly covers the gap between
// navigations (a long-lived tab with an expired access token).
export async function POST() {
  const store = await cookies();
  const refresh = store.get(REFRESH_COOKIE)?.value;

  if (!refresh) {
    return NextResponse.json({ success: false, message: "no session" }, { status: 401 });
  }

  const djangoRes = await fetch(`${DJANGO_API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
    cache: "no-store",
  });

  const envelope: Envelope<TokenPairData> = await djangoRes.json();

  if (!djangoRes.ok || !envelope.success || !envelope.data) {
    clearSessionCookies(store);
    return NextResponse.json({ success: false, message: envelope.message }, { status: djangoRes.status });
  }

  setSessionCookies(store, envelope.data);
  return NextResponse.json({ success: true });
}
