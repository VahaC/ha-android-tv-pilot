import { resolve } from "node:path";
import { defineConfig } from "vite";

const here = import.meta.dirname;

// Dev server for the review harness in card/demo (npm run demo).
export default defineConfig({
  root: resolve(here, "demo"),
  server: {
    port: 5179,
    strictPort: true,
    open: false,
    fs: { allow: [resolve(here), resolve(here, "../custom_components/android_tv_pilot/frontend")] },
  },
});
