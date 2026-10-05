import type { NextConfig } from "next";
import { publicEnv } from "./src/lib/env";

// Validate configuration at startup and build time, before future API calls run.
void publicEnv;

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
};

export default nextConfig;
