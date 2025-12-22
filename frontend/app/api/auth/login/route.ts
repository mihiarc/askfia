import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

export async function POST(req: NextRequest) {
  const { password } = await req.json();

  const sitePassword = process.env.SITE_PASSWORD;

  if (!sitePassword) {
    // If no password is configured, allow access
    return NextResponse.json({ token: "no-auth-required" });
  }

  if (password === sitePassword) {
    // Generate a simple token (hash of password + timestamp)
    const token = crypto
      .createHash("sha256")
      .update(sitePassword + Date.now().toString())
      .digest("hex");

    return NextResponse.json({ token });
  }

  return NextResponse.json({ error: "Invalid password" }, { status: 401 });
}
