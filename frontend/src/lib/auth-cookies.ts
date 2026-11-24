// Structural type covering both next/headers' cookies() store (in Route
// Handlers) and NextResponse.cookies — the two cookie-writer shapes this
// module is ever handed.
type CookieWriter = {
  set(name: string, value: string, options?: Record<string, unknown>): unknown;
};

// Cookie names for the BFF session. Both are httpOnly — the browser never
// sees the raw JWTs, only this Next.js origin does (see docs/BFF pattern).
// This mirrors Django's own token TTLs (JWT_ACCESS_TOKEN_TTL /
// JWT_REFRESH_TOKEN_TTL in config/settings/base.py) so a cookie never
// outlives the token it holds.
export const ACCESS_COOKIE = "flms_access";
export const REFRESH_COOKIE = "flms_refresh";

const isProd = process.env.NODE_ENV === "production";

const baseCookieOptions = {
  httpOnly: true,
  secure: isProd,
  sameSite: "lax" as const,
  path: "/",
};

export function setSessionCookies(
  cookies: CookieWriter,
  tokens: { access: string; refresh: string; access_expires_in: number; refresh_expires_in: number }
) {
  cookies.set(ACCESS_COOKIE, tokens.access, {
    ...baseCookieOptions,
    maxAge: tokens.access_expires_in,
  });
  cookies.set(REFRESH_COOKIE, tokens.refresh, {
    ...baseCookieOptions,
    maxAge: tokens.refresh_expires_in,
  });
}

export function clearSessionCookies(cookies: CookieWriter) {
  cookies.set(ACCESS_COOKIE, "", { ...baseCookieOptions, maxAge: 0 });
  cookies.set(REFRESH_COOKIE, "", { ...baseCookieOptions, maxAge: 0 });
}
