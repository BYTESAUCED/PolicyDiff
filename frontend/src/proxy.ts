import { auth0 } from "./lib/auth0";
import { NextResponse } from "next/server";

export async function proxy(request: Request) {
  // Surface missing env vars clearly instead of generic 500
  const required = ["AUTH0_SECRET", "AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET", "APP_BASE_URL"];
  const missing = required.filter((k) => !process.env[k]);
  if (missing.length > 0) {
    console.error("[proxy] Missing env vars:", missing.join(", "));
    return NextResponse.json(
      { error: "Server misconfiguration", missing },
      { status: 500 }
    );
  }

  try {
    return await auth0.middleware(request);
  } catch (e) {
    console.error("[proxy] auth0.middleware error:", e);
    return NextResponse.json(
      { error: "Auth middleware failed", detail: String(e) },
      { status: 500 }
    );
  }
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
