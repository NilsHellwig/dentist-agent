import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // The dev server is only opened via localhost; other hosts are deliberately not allowed
  allowedDevOrigins: ["localhost", "127.0.0.1"],
  // Proxy the admin API so the session cookie is same-origin with the dashboard
  async rewrites() {
    return [{ source: "/admin/api/:path*", destination: `${backendUrl}/admin/api/:path*` }];
  },
};

export default nextConfig;
