import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Docker 内开发需要允许所有 host
  allowedDevOrigins: ["localhost", "*.localhost"],

  // 开发环境 API 代理（可选，你也可以在前端直接写完整 URL）
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_URL || "http://backend:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;