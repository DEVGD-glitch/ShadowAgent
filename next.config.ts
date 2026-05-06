import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  typescript: {
    ignoreBuildErrors: false,
  },
  reactStrictMode: true,
  allowedDevOrigins: [
    '.space-z.ai',
    '.chatglm.site',
    'localhost',
  ],
  turbopack: {
    root: '.',
  },
};

export default nextConfig;
