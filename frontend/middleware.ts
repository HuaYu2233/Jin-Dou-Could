import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PATHS = ["/dashboard", "/admin", "/profile"];
const AUTH_PATHS = ["/login", "/register", "/forgot-password"];
const TOKEN_COOKIE = "access_token";
const AUTH_EXPIRED_PARAM = "auth_expired";

export function middleware(request: NextRequest) {
  const { pathname, origin, searchParams } = request.nextUrl;
  const token = request.cookies.get(TOKEN_COOKIE)?.value;

  const isProtected = PROTECTED_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (isProtected && !token) {
    const loginUrl = new URL("/login", origin);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  const isAuthPath = AUTH_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (isAuthPath && token && !searchParams.get(AUTH_EXPIRED_PARAM)) {
    return NextResponse.redirect(new URL("/dashboard", origin));
  }

  if (pathname === "/" && token) {
    return NextResponse.redirect(new URL("/dashboard", origin));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};