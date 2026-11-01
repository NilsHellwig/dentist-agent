import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The dev server is only opened via localhost; other hosts are deliberately not allowed
  allowedDevOrigins: ["localhost", "127.0.0.1"],
};

export default nextConfig;
