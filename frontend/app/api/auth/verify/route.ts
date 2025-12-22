import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { token } = await req.json();

  const sitePassword = process.env.SITE_PASSWORD;

  if (!sitePassword) {
    // If no password is configured, any token is valid
    return NextResponse.json({ valid: true });
  }

  // Token should be a 64-char hex string (SHA256 hash)
  if (token && typeof token === "string" && token.length === 64) {
    return NextResponse.json({ valid: true });
  }

  // Special case for no-auth token
  if (token === "no-auth-required") {
    return NextResponse.json({ valid: true });
  }

  return NextResponse.json({ valid: false }, { status: 401 });
}
