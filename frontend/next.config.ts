import type { NextConfig } from "next";

import { buildSecurityHeaders } from "./src/lib/securityHeaders";

const DEFAULT_API_URL = "http://127.0.0.1:8000"; // keep equal to the default in src/lib/api.ts

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: buildSecurityHeaders({
          isProduction: process.env.NODE_ENV === "production",
          apiUrl: process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL,
        }),
      },
    ];
  },
};

export default nextConfig;
