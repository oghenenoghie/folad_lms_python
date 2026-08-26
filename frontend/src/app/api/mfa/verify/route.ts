import { NextResponse } from "next/server";
import { authorizedDjangoFetch } from "@/lib/session";

export async function POST(request: Request) {
  const body = await request.json();
  const res = await authorizedDjangoFetch("/api/v1/auth/mfa/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
