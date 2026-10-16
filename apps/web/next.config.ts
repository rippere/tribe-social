import type { NextConfig } from "next";

// STATIC_EXPORT=1 builds the Cloudflare Pages site (npm run cf:deploy): plain files in
// out/, with POST /api/clip-chat served by functions/api/clip-chat.ts instead of the
// Next route. That route is named route.node.ts so only non-export builds pick it up.
const staticExport = process.env.STATIC_EXPORT === "1";

const nextConfig: NextConfig = {
  // Dev server is reached over the tailnet (http://benderman:PORT); Next 16
  // blocks cross-origin dev resources from hosts not listed here.
  allowedDevOrigins: ["benderman", "100.80.167.1"],
  pageExtensions: staticExport ? ["tsx", "ts", "jsx", "js"] : ["tsx", "ts", "jsx", "js", "node.ts"],
  ...(staticExport ? { output: "export" as const, images: { unoptimized: true } } : {}),
};

export default nextConfig;
