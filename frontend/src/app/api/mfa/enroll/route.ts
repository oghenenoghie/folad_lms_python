import { NextResponse } from "next/server";
import { authorizedDjangoFetch } from "@/lib/session";

// Proxies to Django's /api/v1/auth/mfa/enroll — the same service call the
// Django server-rendered Security page uses (apps.accounts.services.
// mfa_service.start_enrollment), so enabling MFA here has identical effect.
export async function POST() {
  const res = await authorizedDjangoFetch("/api/v1/auth/mfa/enroll", { method: "POST" });
  const body = await res.json();
  return NextResponse.json(body, { status: res.status });
}
