// Regenerates the card screenshots in docs/images from the demo harness (npm run screenshots).
//
// Playwright is deliberately not a dependency (CI runs `npm ci` and must not pull a browser).
// Install it ad hoc first:
//   npm i --no-save playwright && npx playwright install chromium
//
// It starts its own demo server on a free port (from 5181 up), loads the built bundle
// (?bundle, so run `npm run build` first), and takes element screenshots of the card at device
// scale factor 2 with reduced motion, so no frame is caught mid-animation.
//
// Optional: with `npm i --no-save sharp` the PNGs are re-encoded as palette PNGs (much smaller,
// visually the same); without it they are written as Chromium produced them.

import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const here = dirname(fileURLToPath(import.meta.url));
const cardDir = resolve(here, "..");
const outDir = resolve(cardDir, "../docs/images");

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  console.error(
    [
      "Playwright is not installed (it is intentionally not in package.json).",
      "Install it without touching package.json / package-lock.json, then run again:",
      "",
      "  npm i --no-save playwright",
      "  npx playwright install chromium",
      "  npm run screenshots",
    ].join("\n"),
  );
  process.exit(1);
}

// Default card config (layout button off), English UI, TV on with YouTube running.
let sharp = null;
try {
  sharp = (await import("sharp")).default;
} catch {
  console.warn("sharp not installed: PNGs are not optimised (npm i --no-save sharp to shrink them).");
}

const SHOTS = [
  { file: "card-light.png", layout: "remote", theme: "light", width: 390 },
  { file: "card-dark.png", layout: "remote", theme: "dark", width: 390 },
  { file: "card-apps-light.png", layout: "apps", theme: "light", width: 390 },
  { file: "card-apps-dark.png", layout: "apps", theme: "dark", width: 390 },
  { file: "card-wide-light.png", layout: "wide", theme: "light", width: 1180 },
  { file: "card-wide-dark.png", layout: "wide", theme: "dark", width: 1180 },
];

const server = await createServer({
  configFile: resolve(cardDir, "vite.demo.config.ts"),
  server: { port: 5181, strictPort: false },
  logLevel: "warn",
});
await server.listen();
const base = server.resolvedUrls.local[0];
console.log(`demo server: ${base}`);

const browser = await chromium.launch();
try {
  await mkdir(outDir, { recursive: true });
  for (const shot of SHOTS) {
    const context = await browser.newContext({
      viewport: { width: shot.width + 80, height: 1800 },
      deviceScaleFactor: 2,
      reducedMotion: "reduce",
      colorScheme: shot.theme,
      locale: "en-US",
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

    const query = new URLSearchParams({
      bundle: "1",
      chrome: "0",
      shot: "0",
      lang: "en",
      state: "on",
      app: "com.google.android.youtube.tv",
      layout: shot.layout,
      theme: shot.theme,
      width: String(shot.width),
    });
    await page.goto(`${base}?${query}`);
    // Ready = apps loaded, accent applied (YouTube), fonts in, and no transitions left running.
    await page.waitForFunction(
      (layout) => {
        const root = document.getElementById("card")?.shadowRoot;
        return (
          !!root?.querySelector(`.wrap.layout-${layout}`) &&
          root.querySelectorAll(".tile").length > 0 &&
          !!root.querySelector(".tile.running") &&
          !root.querySelector(".tile.skeleton")
        );
      },
      shot.layout,
      { timeout: 15_000 },
    );
    await page.evaluate(() => document.fonts.ready);
    await page.mouse.move(0, 0);
    await page.waitForTimeout(800);

    const path = resolve(outDir, shot.file);
    await page.locator("#frame").screenshot({ path, animations: "disabled" });
    if (sharp) {
      const optimised = await sharp(await readFile(path))
        .png({ palette: true, quality: 95, effort: 10, compressionLevel: 9 })
        .toBuffer();
      await writeFile(path, optimised);
    }
    const { size } = await stat(path);
    console.log(`${shot.file}: ${(size / 1024).toFixed(0)} KB`);
    if (errors.length) console.warn(`  page errors: ${errors.join(" | ")}`);
    await context.close();
  }
} finally {
  await browser.close();
  await server.close();
}
