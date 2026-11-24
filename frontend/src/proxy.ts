import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { DJANGO_API_URL } from "@/lib/env";
import { ACCESS_COOKIE, REFRESH_COOKIE, setSessionCookies } from "@/lib/auth-cookies";

// Optimistic route gate for everything under /(app) — the real
// authorization check is Django rejecting an expired/invalid access token
// on the actual API call (see lib/session.ts). This only avoids rendering
// a protected page for a client with no session at all, and transparently
// refreshes an access token that expired between page loads so a session
// doesn't die just because the tab sat idle past the 15-minute access TTL.
const PUBLIC_PATHS = ["/login"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    return NextResponse.next();
  }

  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  if (access) {
    return NextResponse.next();
  }

  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  if (refresh) {
    const refreshRes = await fetch(`${DJANGO_API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh }),
      cache: "no-store",
    });

    if (refreshRes.ok) {
      const envelope = await refreshRes.json();
      if (envelope.success && envelope.data) {
        const response = NextResponse.next();
        setSessionCookies(response.cookies, envelope.data);
        return response;
      }
    }
  }

  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
