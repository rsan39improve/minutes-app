import { NextResponse } from "next/server";
import {
  AUTH_COOKIE,
  SESSION_TTL_SEC,
  checkPassword,
  createSessionToken,
} from "@/lib/auth";

export async function POST(request: Request) {
  const expected = process.env.APP_ACCESS_PASSWORD;
  if (!expected) {
    return NextResponse.json(
      { error: "管理者設定（アクセスパスワード）が未完了のため、現在使用できません。" },
      { status: 503 },
    );
  }

  const body = (await request.json().catch(() => null)) as {
    password?: string;
  } | null;
  const password = body?.password ?? "";

  if (!checkPassword(password)) {
    return NextResponse.json(
      { error: "パスワードが正しくありません。" },
      { status: 401 },
    );
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set(AUTH_COOKIE, createSessionToken(), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_TTL_SEC,
  });
  return res;
}
