import { NextResponse } from "next/server";
import { isAuthenticated } from "@/lib/auth";

export async function GET() {
  const ok = await isAuthenticated();
  const hasPassword = Boolean(process.env.APP_ACCESS_PASSWORD);
  const hasApiKey = Boolean(process.env.ANTHROPIC_API_KEY);
  return NextResponse.json({
    authenticated: ok,
    hasPassword,
    hasApiKey,
  });
}
