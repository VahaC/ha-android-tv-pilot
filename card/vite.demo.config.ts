import { resolve } from "node:path";
import { defineConfig } from "vite";

// Dev server for the review harness in card/demo (npm run demo).
export default defineConfig({
  root: resolve(__dirname, "demo"),
  server: {
    port: 5179,
    strictPort: true,
    open: false,
    fs: { allow: [resolve(__dirname), resolve(__dirname, "../custom_components/android_tv_pilot/frontend")] },
  },
});
