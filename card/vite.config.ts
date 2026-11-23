import { resolve } from "node:path";
import { transform } from "esbuild";
import { defineConfig, type Plugin } from "vite";

const here = import.meta.dirname;

/** Collapses whitespace and comments inside Lit css`...` templates (they contain no ${}). */
function minifyLitCss(): Plugin {
  return {
    name: "minify-lit-css",
    apply: "build",
    transform(code, id) {
      if (!id.includes("/src/") || !id.endsWith(".ts")) return null;
      const out = code.replace(/css`([^`]*)`/g, (_m, body: string) => {
        const min = body
          .replace(/\/\*[\s\S]*?\*\//g, "")
          .replace(/\s+/g, " ")
          .replace(/\s*([{};,>])\s*/g, "$1")
          .replace(/:\s+/g, ":")
          .trim();
        return "css`" + min + "`";
      });
      return { code: out, map: null };
    },
  };
}

/**
 * Vite (5 to 8) does not minify whitespace in ES library builds, and with Vite 8's Oxc minifier
 * the bundle stays about 3.5 kB larger with ~3000 lines. Run one full esbuild minify on the final
 * chunk instead; Vite's own minifier is switched off so the output comes from a single, pinned
 * minifier (esbuild is a direct devDependency for this).
 */
function minifyChunk(): Plugin {
  return {
    name: "minify-es-chunk",
    apply: "build",
    enforce: "post",
    async generateBundle(_options, bundle) {
      for (const file of Object.values(bundle)) {
        if (file.type !== "chunk") continue;
        const result = await transform(file.code, { minify: true, format: "esm", target: "es2021", legalComments: "none" });
        file.code = result.code;
      }
    },
  };
}

// Library build: one minified ES module that Home Assistant loads as a Lovelace resource.
export default defineConfig({
  plugins: [minifyLitCss(), minifyChunk()],
  build: {
    target: "es2021",
    outDir: resolve(here, "../custom_components/android_tv_pilot/frontend"),
    // The frontend folder is shared with the integration; only overwrite our own file.
    emptyOutDir: false,
    copyPublicDir: false,
    minify: false,
    sourcemap: false,
    lib: {
      entry: resolve(here, "src/android-tv-pilot-card.ts"),
      formats: ["es"],
      fileName: () => "android-tv-pilot-card.js",
    },
    rolldownOptions: {
      // One self-contained file (the card has no dynamic imports, but never split it).
      output: { codeSplitting: false },
    },
  },
});
