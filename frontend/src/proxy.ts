import { auth0 } from "./lib/auth0";

export async function proxy(request: Request) {
  try {
    return await auth0.middleware(request);
  } catch (e) {
    console.error("[auth0 proxy error]", e);
    throw e;
  }
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};
