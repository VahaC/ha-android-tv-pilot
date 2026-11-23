// Pure helpers with no DOM or Lit dependencies, so they can be unit-tested in Node.
import type { LayoutId, TvApp } from "./types";

export type Direction = "UP" | "DOWN" | "LEFT" | "RIGHT";

export interface WakeProgress {
  /** Seconds since the wake started (never negative). */
  elapsed: number;
  /** Seconds until the server-side timeout (never negative). */
  remaining: number;
  /** 0..1, clamped. */
  fraction: number;
  /** True once the timeout has passed but the server has not reported a result yet. */
  overdue: boolean;
}

/**
 * Progress of a BLE wake, derived from the integration's `wake_started_at` and `wake_timeout`.
 * A missing or unparsable start time yields zero progress instead of throwing.
 */
export function wakeProgress(
  startedAt: string | null | undefined,
  timeoutSeconds: number | null | undefined,
  nowMs: number,
): WakeProgress {
  const timeout = timeoutSeconds && timeoutSeconds > 0 ? timeoutSeconds : 30;
  const start = startedAt ? Date.parse(startedAt) : NaN;
  if (Number.isNaN(start)) {
    return { elapsed: 0, remaining: timeout, fraction: 0, overdue: false };
  }
  const elapsed = Math.max(0, (nowMs - start) / 1000);
  const fraction = Math.min(1, elapsed / timeout);
  return {
    elapsed,
    remaining: Math.max(0, timeout - elapsed),
    fraction,
    overdue: elapsed > timeout,
  };
}

/**
 * Turns a pointer movement into a D-pad direction. Returns null while the movement is shorter
 * than `threshold` px, or when it is too diagonal to call (the dominant axis must be at least
 * `ratio` times the other one).
 */
export function detectSwipe(dx: number, dy: number, threshold = 28, ratio = 1.2): Direction | null {
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  if (Math.max(ax, ay) < threshold) return null;
  if (ax >= ay * ratio) return dx > 0 ? "RIGHT" : "LEFT";
  if (ay >= ax * ratio) return dy > 0 ? "DOWN" : "UP";
  return null;
}

/**
 * Fills a deep-link template. `{query}` is URL-encoded (for search parameters); `{raw}` is
 * inserted as-is after trimming (for a pasted URL). Unknown placeholders are left untouched.
 */
export function fillTemplate(template: string, vars: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) => {
    if (!(name in vars)) return match;
    const value = vars[name].trim();
    return name === "raw" ? value : encodeURIComponent(value);
  });
}

/** Adds https:// to something that looks like a bare host ("youtube.com/watch?v=x"). */
export function normalizeUrl(input: string): string | null {
  const value = input.trim();
  if (!value) return null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(value)) return value;
  if (/^[\w-]+(\.[\w-]+)+(:\d+)?(\/|$|\?)/.test(value)) return `https://${value}`;
  return null;
}

const globCache = new Map<string, RegExp>();

function globToRegExp(pattern: string): RegExp {
  let re = globCache.get(pattern);
  if (!re) {
    const body = pattern.split("*").map((part) => part.replace(/[.+?^${}()|[\]\\]/g, "\\$&")).join(".*");
    re = new RegExp(`^${body}$`);
    globCache.set(pattern, re);
  }
  return re;
}

/**
 * Matches a package against a pattern: an exact name, or a glob where `*` matches any run of
 * characters anywhere ("org.mozilla.*", "com.xiaomi.*browser*"). Returns a specificity score
 * (the number of literal characters), or -1. Exact matches always win; among globs the one with
 * more literal characters wins.
 */
export function matchScore(pattern: string, pkg: string): number {
  if (pattern === pkg) return 10_000;
  if (!pattern.includes("*")) return -1;
  return globToRegExp(pattern).test(pkg) ? pattern.replace(/\*/g, "").length : -1;
}

export interface Matchable {
  id: string;
  match: string[];
}

/** Picks the most specific entry for `pkg`, or the fallback when nothing matches. */
export function pickBest<T extends Matchable>(entries: T[], pkg: string | null | undefined, fallback: T): T {
  if (!pkg) return fallback;
  let best: T | null = null;
  let bestScore = -1;
  for (const entry of entries) {
    for (const pattern of entry.match) {
      const score = matchScore(pattern, pkg);
      if (score > bestScore) {
        best = entry;
        bestScore = score;
      }
    }
  }
  return best ?? fallback;
}

/**
 * Applies pinned order and the hidden lists to the integration's app list. `system` is only
 * informational: the integration marks preinstalled YouTube / Netflix / Play Store as system apps,
 * so it must not hide anything. Hidden = the app's own `hidden` flag (overridden by pinning it) or
 * the card's `hidden_apps` (always wins).
 */
export function arrangeApps(apps: TvApp[], pinned: string[] = [], hidden: string[] = []): TvApp[] {
  const hiddenSet = new Set(hidden);
  const visible = apps.filter(
    (app) => !hiddenSet.has(app.package) && (!app.hidden || pinned.includes(app.package)),
  );
  const byPackage = new Map(visible.map((app) => [app.package, app]));
  const first = pinned.map((pkg) => byPackage.get(pkg)).filter((app): app is TvApp => !!app);
  const firstSet = new Set(first.map((app) => app.package));
  const rest = visible
    .filter((app) => !firstSet.has(app.package))
    .sort((a, b) => a.label.localeCompare(b.label));
  return [...first, ...rest];
}

/** Up to two initials for a tile without an icon ("Prime Video" -> "PV", "kodi" -> "KO"). */
export function initials(label: string): string {
  const words = label.trim().split(/[\s._-]+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

/** Parses #rgb / #rrggbb. Returns null for anything else. */
export function parseHex(color: string | null | undefined): [number, number, number] | null {
  if (!color) return null;
  const m = color.trim().match(/^#?([0-9a-f]{3}|[0-9a-f]{6})$/i);
  if (!m) return null;
  let hex = m[1];
  if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
  const n = parseInt(hex, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** WCAG relative luminance of an sRGB colour. */
export function luminance([r, g, b]: [number, number, number]): number {
  const lin = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** Black or white, whichever reads better on the given brand colour (app tiles). */
export function onColor(color: string | null | undefined): string {
  const rgb = parseHex(color);
  if (!rgb) return "#fff";
  return luminance(rgb) > 0.45 ? "#111" : "#fff";
}

type Rgb = [number, number, number];

/**
 * Parses #rgb, #rgba, #rrggbb, #rrggbbaa, rgb()/rgba() (comma or space syntax). Alpha is ignored.
 * Returns null for anything else (named colours etc. are resolved by the card via a canvas).
 */
export function parseCssColor(value: string | null | undefined): Rgb | null {
  if (!value) return null;
  const v = value.trim().toLowerCase();
  const hex = v.match(/^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/);
  if (hex) {
    let h = hex[1];
    if (h.length <= 4) h = h.split("").map((c) => c + c).join("");
    const n = parseInt(h.slice(0, 6), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  const fn = v.match(/^rgba?\(\s*([\d.]+%?)[\s,]+([\d.]+%?)[\s,]+([\d.]+%?)/);
  if (fn) {
    const ch = (s: string) => Math.round(Math.min(255, Math.max(0, s.endsWith("%") ? (parseFloat(s) * 255) / 100 : parseFloat(s))));
    return [ch(fn[1]), ch(fn[2]), ch(fn[3])];
  }
  return null;
}

/** WCAG contrast ratio between two colours (1..21). */
export function contrastRatio(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * Colour for icons and text drawn on the theme's primary colour: the theme's own
 * --text-primary-color when it reaches 3:1 (WCAG minimum for icons and large/bold text, which is all
 * the card draws on the accent; HA's own white-on-#009ac7 is 3.3:1), otherwise black or white,
 * whichever contrasts more.
 * Returns null when the primary cannot be parsed (CSS fallback applies).
 */
export function pickOnAccent(primary: Rgb | null, textPrimary: Rgb | null): string | null {
  if (!primary) return null;
  if (textPrimary && contrastRatio(primary, textPrimary) >= 3) {
    return `rgb(${textPrimary[0]}, ${textPrimary[1]}, ${textPrimary[2]})`;
  }
  return contrastRatio(primary, [255, 255, 255]) >= contrastRatio(primary, [17, 17, 17]) ? "#ffffff" : "#111111";
}

/** Formats a 0..1 volume level as a whole percentage, or null when unknown. */
export function volumePercent(level: number | null | undefined): number | null {
  if (typeof level !== "number" || Number.isNaN(level)) return null;
  return Math.round(Math.min(1, Math.max(0, level)) * 100);
}

export const LAYOUTS: readonly LayoutId[] = ["remote", "apps", "wide"];
const LAYOUT_ALIASES: Record<string, LayoutId> = { a: "remote", b: "apps", c: "wide" };

/** Maps a configured layout (including the old a/b/c aliases) to its id, or null if unknown. */
export function normalizeLayout(value: unknown): LayoutId | null {
  if (typeof value !== "string") return null;
  const v = value.trim().toLowerCase();
  if ((LAYOUTS as readonly string[]).includes(v)) return v as LayoutId;
  return LAYOUT_ALIASES[v] ?? null;
}

export interface StoredLayout {
  layout: LayoutId;
  /** The dashboard layout at the time of the choice. */
  base: LayoutId;
}

/** Parses the per-browser layout choice from storage; tolerates old a/b/c values and junk. */
export function parseStoredLayout(raw: string | null): StoredLayout | null {
  if (!raw) return null;
  try {
    const v = JSON.parse(raw) as { layout?: unknown; base?: unknown } | null;
    const layout = normalizeLayout(v?.layout);
    const base = normalizeLayout(v?.base);
    return layout && base ? { layout, base } : null;
  } catch {
    return null;
  }
}

/**
 * The per-browser choice only applies while the dashboard layout is the one it was made against;
 * once the dashboard (config) layout changes, the stored choice is dropped.
 */
export function effectiveOverride(stored: StoredLayout | null, configLayout: LayoutId): LayoutId | null {
  return stored && stored.base === configLayout ? stored.layout : null;
}

const EDITOR_DEFAULTS: Record<string, unknown> = { show_screenshot: false, haptics: true, layout_switch: false };

/**
 * Tidies a card config for the editor: maps layout aliases to names, renames the old
 * `prototype_switch` key to `layout_switch`, drops empty values and options left at their
 * default. `layout` is always kept so the YAML shows the chosen look.
 */
export function tidyConfig(input: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = { ...input };
  if ("prototype_switch" in out) {
    if (!("layout_switch" in out)) out.layout_switch = out.prototype_switch;
    delete out.prototype_switch;
  }
  out.layout = normalizeLayout(out.layout) ?? "remote";
  for (const [k, v] of Object.entries(out)) {
    const empty = v === "" || v === undefined || v === null || (Array.isArray(v) && v.length === 0);
    if (empty || (k in EDITOR_DEFAULTS && EDITOR_DEFAULTS[k] === v)) delete out[k];
  }
  return out;
}

/**
 * Compares two versions "MAJOR.MINOR.PATCH" (optional leading "v", optional "-pre" / "+build";
 * a pre-release sorts before its release). Returns -1, 0 or 1, or null if either is unparsable.
 */
export function compareVersions(a: unknown, b: unknown): -1 | 0 | 1 | null {
  const parse = (v: unknown) => {
    if (typeof v !== "string") return null;
    const m = v.trim().match(/^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/);
    return m ? { nums: [Number(m[1]), Number(m[2]), Number(m[3])], pre: m[4] ?? null } : null;
  };
  const pa = parse(a);
  const pb = parse(b);
  if (!pa || !pb) return null;
  for (let i = 0; i < 3; i++) {
    if (pa.nums[i] !== pb.nums[i]) return pa.nums[i] < pb.nums[i] ? -1 : 1;
  }
  if (pa.pre === pb.pre) return 0;
  if (pa.pre === null) return 1;
  if (pb.pre === null) return -1;
  return pa.pre < pb.pre ? -1 : 1;
}

export type VersionNotice = "reload" | "restart";

/**
 * What to tell the user when the loaded card and the running integration differ:
 * integration newer -> the browser still runs an old card ("reload");
 * card newer -> HA still runs the old integration ("restart"). Null when equal or unknown.
 */
export function versionNotice(cardVersion: string, integrationVersion: unknown): VersionNotice | null {
  const cmp = compareVersions(cardVersion, integrationVersion);
  if (cmp === null || cmp === 0) return null;
  return cmp < 0 ? "reload" : "restart";
}

/** sessionStorage key for a dismissed notice; tied to the version pair so a later update shows it again. */
export function versionNoticeKey(cardVersion: string, integrationVersion: string): string {
  return `android-tv-pilot:version-notice:${cardVersion}|${integrationVersion}`;
}

/** True when every character can be typed over ADB `input text` (printable ASCII). */
export function isAdbTypable(text: string): boolean {
  return /^[\x20-\x7e]*$/.test(text);
}
