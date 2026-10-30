import type { NextConfig } from "next";

const minioHost = process.env.MINIO_PUBLIC_ENDPOINT || "localhost:9000";
const minioProtocol = process.env.MINIO_SECURE === "true" ? "https" : "http";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  allowedDevOrigins: ["localhost", "*.localhost"],

  images: {
    remotePatterns: [
      {
        protocol: minioProtocol as "http" | "https",
        hostname: minioHost.split(":")[0],
        port: minioHost.split(":")[1] || "9000",
        pathname: "/cloud-drive/**",
      },
    ],
    minimumCacheTTL: 7200,
    deviceSizes: [640, 828, 1080, 1200, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 256],
  },

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