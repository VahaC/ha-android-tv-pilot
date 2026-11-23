import { describe, expect, it } from "vitest";
import { GENERIC_PROFILE, PROFILES, profileFor } from "../src/app-profiles";
import { pickLanguage, translator } from "../src/i18n";
import {
  LAYOUTS,
  arrangeApps,
  detectSwipe,
  effectiveOverride,
  normalizeLayout,
  parseStoredLayout,
  tidyConfig,
  fillTemplate,
  initials,
  matchScore,
  normalizeUrl,
  onColor,
  usableAccent,
  wakeProgress,
} from "../src/logic";
import type { TvApp } from "../src/types";

describe("profile matching", () => {
  it("picks exact packages", () => {
    expect(profileFor("com.google.android.youtube.tv").id).toBe("youtube");
    expect(profileFor("org.xbmc.kodi").id).toBe("kodi");
    expect(profileFor("org.jellyfin.androidtv").id).toBe("jellyfin");
    expect(profileFor("com.netflix.ninja").id).toBe("netflix");
  });

  it("matches wildcard prefixes", () => {
    expect(profileFor("org.mozilla.firefox").id).toBe("browser");
    expect(profileFor("com.liskovsoft.smarttubetv.beta").id).toBe("smarttube");
  });

  it("prefers exact over prefix and longer prefixes over shorter", () => {
    expect(matchScore("org.xbmc.kodi", "org.xbmc.kodi")).toBeGreaterThan(matchScore("org.xbmc.*", "org.xbmc.kodi"));
    expect(matchScore("com.a.b.*", "com.a.b.c")).toBeGreaterThan(matchScore("com.a.*", "com.a.b.c"));
    expect(matchScore("com.a.*", "com.b.c")).toBe(-1);
  });

  it("supports * anywhere in a pattern", () => {
    expect(matchScore("com.xiaomi.*browser*", "com.xiaomi.mitv.browser")).toBeGreaterThan(0);
    expect(matchScore("com.xiaomi.*browser*", "com.xiaomi.browser.tv")).toBeGreaterThan(0);
    expect(matchScore("com.xiaomi.*browser*", "com.xiaomi.mitv.settings")).toBe(-1);
    expect(matchScore("*.kodi", "org.xbmc.kodi")).toBeGreaterThan(0);
    // dots are literal, not regex wildcards
    expect(matchScore("org.xbmc.*", "orgXxbmc.kodi")).toBe(-1);
    expect(profileFor("com.xiaomi.mitv.browser").id).toBe("browser");
  });

  it("keeps exact matches above any glob", () => {
    expect(matchScore("org.xbmc.kodi", "org.xbmc.kodi")).toBeGreaterThan(matchScore("org.xbmc.k*", "org.xbmc.kodi"));
  });

  it("sends Kodi shortcuts as key codes, not text", () => {
    const kodi = profileFor("org.xbmc.kodi");
    const info = kodi.actions.find((a) => a.id === "info");
    expect(info).toMatchObject({ type: "keys", keys: ["KEYCODE_I"] });
    for (const p of [...PROFILES, GENERIC_PROFILE]) {
      expect(p.actions.some((a) => a.type === "type"), p.id).toBe(false);
    }
  });

  it("falls back to the generic profile", () => {
    expect(profileFor("com.example.unknown")).toBe(GENERIC_PROFILE);
    expect(profileFor(null)).toBe(GENERIC_PROFILE);
    expect(profileFor("")).toBe(GENERIC_PROFILE);
  });

  it("has unique action ids inside every profile", () => {
    for (const p of [...PROFILES, GENERIC_PROFILE]) {
      const ids = p.actions.map((a) => a.id);
      expect(new Set(ids).size, p.id).toBe(ids.length);
    }
  });
});

describe("deep-link templating", () => {
  it("URL-encodes {query}", () => {
    expect(fillTemplate("https://www.youtube.com/results?search_query={query}", { query: "lo-fi & chill/beats?" })).toBe(
      "https://www.youtube.com/results?search_query=lo-fi%20%26%20chill%2Fbeats%3F",
    );
  });

  it("encodes non-ASCII text", () => {
    expect(fillTemplate("x?q={query}", { query: "Тіні забутих предків" })).toBe(
      "x?q=%D0%A2%D1%96%D0%BD%D1%96%20%D0%B7%D0%B0%D0%B1%D1%83%D1%82%D0%B8%D1%85%20%D0%BF%D1%80%D0%B5%D0%B4%D0%BA%D1%96%D0%B2",
    );
  });

  it("inserts {raw} untouched but trimmed, and leaves unknown placeholders", () => {
    expect(fillTemplate("{raw}", { raw: "  https://youtu.be/abc?t=10  " })).toBe("https://youtu.be/abc?t=10");
    expect(fillTemplate("a/{other}", { query: "x" })).toBe("a/{other}");
  });

  it("normalises bare hosts into URLs", () => {
    expect(normalizeUrl("youtube.com/watch?v=1")).toBe("https://youtube.com/watch?v=1");
    expect(normalizeUrl("http://192.168.1.5:8096")).toBe("http://192.168.1.5:8096");
    expect(normalizeUrl("spotify:track:1")).toBe("spotify:track:1");
    expect(normalizeUrl("just words")).toBeNull();
    expect(normalizeUrl("   ")).toBeNull();
  });
});

describe("wake progress", () => {
  const start = "2026-11-23T10:00:00.000Z";
  const t0 = Date.parse(start);

  it("computes elapsed, remaining and fraction", () => {
    const p = wakeProgress(start, 30, t0 + 12_000);
    expect(p.elapsed).toBe(12);
    expect(p.remaining).toBe(18);
    expect(p.fraction).toBeCloseTo(0.4);
    expect(p.overdue).toBe(false);
  });

  it("clamps after the timeout and flags overdue", () => {
    const p = wakeProgress(start, 30, t0 + 45_000);
    expect(p.fraction).toBe(1);
    expect(p.remaining).toBe(0);
    expect(p.overdue).toBe(true);
  });

  it("never goes negative with clock skew", () => {
    expect(wakeProgress(start, 30, t0 - 2_000).elapsed).toBe(0);
  });

  it("handles a missing start or timeout", () => {
    expect(wakeProgress(null, 30, t0)).toEqual({ elapsed: 0, remaining: 30, fraction: 0, overdue: false });
    expect(wakeProgress("garbage", 0, t0).remaining).toBe(30);
  });
});

describe("swipe detection", () => {
  it("ignores short moves", () => {
    expect(detectSwipe(10, 5, 28)).toBeNull();
  });

  it("detects the four directions", () => {
    expect(detectSwipe(40, 3)).toBe("RIGHT");
    expect(detectSwipe(-40, 3)).toBe("LEFT");
    expect(detectSwipe(2, 40)).toBe("DOWN");
    expect(detectSwipe(2, -40)).toBe("UP");
  });

  it("refuses ambiguous diagonals", () => {
    expect(detectSwipe(35, 33)).toBeNull();
    expect(detectSwipe(50, 30)).toBe("RIGHT");
  });
});

describe("apps and colours", () => {
  const app = (pkg: string, label: string, extra: Partial<TvApp> = {}): TvApp => ({
    package: pkg, label, color: null, icon: null, icon_url: null, hidden: false, system: false, ...extra,
  });
  const apps = [app("b", "Bravo"), app("a", "Alpha"), app("s", "System", { system: true }), app("h", "Hidden", { hidden: true }), app("c", "Charlie")];

  it("keeps system apps (system is informational), hides hidden ones, sorts the rest", () => {
    expect(arrangeApps(apps).map((a) => a.package)).toEqual(["a", "b", "c", "s"]);
  });

  it("puts pinned first in order and applies the card's hidden_apps", () => {
    expect(arrangeApps(apps, ["c", "b"], ["a", "s"]).map((a) => a.package)).toEqual(["c", "b"]);
    expect(arrangeApps(apps, ["s"]).map((a) => a.package)).toEqual(["s", "a", "b", "c"]);
  });

  it("shows an integration-hidden app only when pinned; hidden_apps always wins", () => {
    expect(arrangeApps(apps, ["h"]).map((a) => a.package)).toEqual(["h", "a", "b", "c", "s"]);
    expect(arrangeApps(apps, ["h"], ["h"]).map((a) => a.package)).toEqual(["a", "b", "c", "s"]);
  });

  it("does not empty the launcher when every app is a system app", () => {
    const mi = [app("com.google.android.youtube.tv", "YouTube", { system: true }), app("com.netflix.ninja", "Netflix", { system: true })];
    expect(arrangeApps(mi)).toHaveLength(2);
  });

  it("builds initials", () => {
    expect(initials("Prime Video")).toBe("PV");
    expect(initials("kodi")).toBe("KO");
    expect(initials("")).toBe("?");
  });

  it("chooses readable text and drops unusable accents", () => {
    expect(onColor("#ffffff")).toBe("#111");
    expect(onColor("#e50914")).toBe("#fff");
    expect(usableAccent("#000000", "fb")).toBe("fb");
    expect(usableAccent("#1db954", "fb")).toBe("#1db954");
    expect(usableAccent(null, "fb")).toBe("fb");
  });
});

describe("layouts", () => {
  it("accepts names and the old a/b/c aliases", () => {
    expect(normalizeLayout("remote")).toBe("remote");
    expect(normalizeLayout("Apps")).toBe("apps");
    expect(normalizeLayout("a")).toBe("remote");
    expect(normalizeLayout("b")).toBe("apps");
    expect(normalizeLayout("c")).toBe("wide");
    expect(normalizeLayout("d")).toBeNull();
    expect(normalizeLayout(undefined)).toBeNull();
  });

  it("parses the stored per-browser choice, including old values", () => {
    expect(parseStoredLayout('{"layout":"wide","base":"remote"}')).toEqual({ layout: "wide", base: "remote" });
    expect(parseStoredLayout('{"layout":"b","base":"a"}')).toEqual({ layout: "apps", base: "remote" });
    expect(parseStoredLayout("b")).toBeNull();
    expect(parseStoredLayout("{oops")).toBeNull();
    expect(parseStoredLayout(null)).toBeNull();
  });

  it("drops the stored choice once the dashboard layout changes", () => {
    const stored = { layout: "wide" as const, base: "remote" as const };
    expect(effectiveOverride(stored, "remote")).toBe("wide");
    expect(effectiveOverride(stored, "apps")).toBeNull();
    expect(effectiveOverride(null, "remote")).toBeNull();
  });

  it("tidies editor output: names, renamed switch key, defaults removed, layout kept", () => {
    expect(tidyConfig({ entity: "media_player.tv", layout: "c", prototype_switch: true, haptics: true, name: "" })).toEqual({
      entity: "media_player.tv",
      layout: "wide",
      layout_switch: true,
    });
    expect(tidyConfig({ entity: "x", layout_switch: false, show_screenshot: false })).toEqual({ entity: "x", layout: "remote" });
    expect(tidyConfig({ entity: "x", layout_switch: false, prototype_switch: true })).toEqual({ entity: "x", layout: "remote" });
  });
});

describe("i18n", () => {
  it("has a name and a helper for every layout in both languages", () => {
    for (const lang of ["en", "uk"] as const) {
      const t = translator(lang);
      for (const id of LAYOUTS) {
        expect(t(`layout_${id}` as never)).not.toMatch(/^layout_/);
        expect(t(`layout_${id}_help` as never)).not.toMatch(/^layout_/);
      }
    }
  });

  it("picks Ukrainian only for uk", () => {
    expect(pickLanguage("uk")).toBe("uk");
    expect(pickLanguage("uk-UA")).toBe("uk");
    expect(pickLanguage("en-GB")).toBe("en");
    expect(pickLanguage(undefined)).toBe("en");
  });

  it("fills placeholders", () => {
    expect(translator("uk")("waking_seconds", { s: 12 })).toBe("Прокидається… 12 с");
    expect(translator("en")("waking_seconds", { s: 12 })).toBe("Waking up… 12 s");
  });
});
