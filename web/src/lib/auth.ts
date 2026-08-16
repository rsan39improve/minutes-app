import { createHmac, timingSafeEqual } from "crypto";
import { cookies } from "next/headers";

export const AUTH_COOKIE = "minutes_auth";
export const SESSION_TTL_SEC = 24 * 60 * 60;

function signingSecret(): string {
  return (
    process.env.AUTH_SECRET ||
    process.env.APP_ACCESS_PASSWORD ||
    "dev-insecure-secret"
  );
}

function sign(payload: string): string {
  return createHmac("sha256", signingSecret()).update(payload).digest("hex");
}

export function createSessionToken(nowSec = Math.floor(Date.now() / 1000)): string {
  const payload = `ok.${nowSec}`;
  return `${payload}.${sign(payload)}`;
}

export function verifySessionToken(token: string | undefined | null): boolean {
  if (!token) return false;
  const parts = token.split(".");
  if (parts.length !== 3) return false;
  const [flag, tsStr, sig] = parts;
  if (flag !== "ok") return false;
  const ts = Number(tsStr);
  if (!Number.isFinite(ts)) return false;
  if (Math.floor(Date.now() / 1000) - ts > SESSION_TTL_SEC) return false;

  const payload = `${flag}.${tsStr}`;
  const expected = sign(payload);
  try {
    const a = Buffer.from(sig);
    const b = Buffer.from(expected);
    if (a.length !== b.length) return false;
    return timingSafeEqual(a, b);
  } catch {
    return false;
  }
}

export function checkPassword(password: string): boolean {
  const expected = process.env.APP_ACCESS_PASSWORD || "";
  if (!expected) return false;
  const a = Buffer.from(password);
  const b = Buffer.from(expected);
  if (a.length !== b.length) return false;
  try {
    return timingSafeEqual(a, b);
  } catch {
    return false;
  }
}

export async function isAuthenticated(): Promise<boolean> {
  const jar = await cookies();
  return verifySessionToken(jar.get(AUTH_COOKIE)?.value);
}
