import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// 需要保护的路径前缀
const PROTECTED_PATHS = ["/dashboard"];
// 已登录用户无需再访问的路径（可选：已登录访问 /login 自动回 /dashboard）
const AUTH_PATHS = ["/login", "/register"];
// 存放 token 的 Cookie 名
const TOKEN_COOKIE = "access_token";

export function proxy(request: NextRequest) {
  const { pathname, origin } = request.nextUrl;
  const token = request.cookies.get(TOKEN_COOKIE)?.value;

  // ① 未登录访问 /dashboard/* → 重定向到 /login
  const isProtected = PROTECTED_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (isProtected && !token) {
    const loginUrl = new URL("/login", origin);
    // 登录成功后可以回跳原地址
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // ② 已登录访问 /login 或 /register → 重定向到 /dashboard（可选）
  const isAuthPath = AUTH_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
  if (isAuthPath && token) {
    return NextResponse.redirect(new URL("/dashboard", origin));
  }

  return NextResponse.next();
}

// ③ 匹配路径，排除静态资源 /api / Next.js 内部路径
export const config = {
  matcher: [
    "/((?!api|_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)",
  ],
};