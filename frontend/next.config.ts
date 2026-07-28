import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    // Without this, Next infers the workspace root by walking up for any
    // lockfile-like file and lands on the user's own ~/pnpm-workspace.yaml
    // (unrelated to this project) instead of this directory -- pin it
    // explicitly rather than let that inference guess wrong.
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
