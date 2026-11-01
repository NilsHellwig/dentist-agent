import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Der Dev-Server wird nur über localhost geöffnet; weitere Hosts bewusst nicht freigegeben
  allowedDevOrigins: ["localhost", "127.0.0.1"],
};

export default nextConfig;
