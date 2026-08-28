/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Docker 内开发需要允许所有 host
  allowedDevOrigins: ['localhost', '*.localhost'],
  // 如果需要静态导出（不常用），取消下面注释
  // output: 'standalone',
  
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.API_URL || 'http://backend:8000'}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;