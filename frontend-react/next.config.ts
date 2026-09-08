import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ];
  },
  images: {
    remotePatterns: [
      { protocol: 'http', hostname: 'localhost', port: '8000' },
    ],
  },
};

export default nextConfig;
