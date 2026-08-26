import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { DJANGO_API_URL } from "@/lib/env";
import { ACCESS_COOKIE, REFRESH_COOKIE, clearSessionCookies } from "@/lib/auth-cookies";

// Revokes the refresh token on Django (best-effort) and always clears the
// session cookies here, even if the Django call fails — the browser side
// of the session ends unconditionally.
export async function POST() {
  const store = await cookies();
  const access = store.get(ACCESS_COOKIE)?.value;
  const refresh = store.get(REFRESH_COOKIE)?.value;

  if (access) {
    await fetch(`${DJANGO_API_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${access}`,
      },
      body: JSON.stringify({ refresh }),
      cache: "no-store",
    }).catch(() => undefined);
  }

  clearSessionCookies(store);
  return NextResponse.json({ success: true, message: "logged out" });
}
