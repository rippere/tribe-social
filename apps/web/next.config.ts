import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Dev server is reached over the tailnet (http://benderman:PORT); Next 16
  // blocks cross-origin dev resources from hosts not listed here.
  allowedDevOrigins: ["benderman", "100.80.167.1"],
};

export default nextConfig;
