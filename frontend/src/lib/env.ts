// Server-only: the Django origin this BFF proxies to. Never exposed to the
// browser — the client only ever talks to this Next.js origin.
export const DJANGO_API_URL = (process.env.DJANGO_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
