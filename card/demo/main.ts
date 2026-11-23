// Review harness: a mock `hass` with a TV state machine and mocked WebSocket commands.
import "./ha-stubs";
import type { CardConfig, Hass, HassEntity, TvApp, TvAttributes } from "../src/types";

// ?bundle loads the minified build output instead of the TypeScript sources.
const USE_BUNDLE = new URLSearchParams(location.search).has("bundle");
if (USE_BUNDLE) {
  // @ts-ignore the build output has no type declarations
  await import("../../custom_components/android_tv_pilot/frontend/android-tv-pilot-card.js");
} else {
  await import("../src/android-tv-pilot-card");
}

const TV = "media_player.living_room_tv";
const SOUNDBAR = "media_player.soundbar";
const ENTRY = "01JDEMO0ANDROIDTVPILOT";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const card = $("card") as HTMLElement & { hass?: Hass; setConfig(c: CardConfig): void };
const logEl = $("log");

function log(kind: "ws" | "svc" | "err" | "hap" | "info", text: string): void {
  const line = document.createElement("div");
  line.className = kind;
  line.textContent = `${new Date().toLocaleTimeString()}  ${text}`;
  logEl.prepend(line);
  while (logEl.childElementCount > 200) logEl.lastElementChild?.remove();
}

// ---- mock data --------------------------------------------------------------------------

const app = (pkg: string, label: string, color: string | null, icon: string | null, extra: Partial<TvApp> = {}): TvApp => ({
  package: pkg, label, color, icon, icon_url: null, hidden: false, system: false, ...extra,
});

const APPS: TvApp[] = [
  app("com.google.android.youtube.tv", "YouTube", "#ff0033", "mdi:youtube", { system: true }),
  app("com.teamsmart.videomanager.tv", "SmartTube", "#e0312b", null),
  app("com.netflix.ninja", "Netflix", "#e50914", "mdi:netflix", { system: true }),
  app("org.jellyfin.androidtv", "Jellyfin", "#aa5cc3", null),
  app("com.plexapp.android", "Plex", "#e5a00d", "mdi:plex"),
  app("org.xbmc.kodi", "Kodi", "#17b2e7", "mdi:kodi"),
  app("org.videolan.vlc", "VLC", "#ff8800", "mdi:vlc"),
  app("com.spotify.tv.android", "Spotify", "#1db954", "mdi:spotify"),
  app("com.amazon.amazonvideo.livingroom", "Prime Video", "#00a8e1", null),
  app("com.google.android.youtube.tvmusic", "YouTube Music", "#ff0000", "mdi:music-circle"),
  app("org.mozilla.tv.firefox", "Firefox", "#ff7139", "mdi:firefox"),
  app("com.google.android.tv", "Live Channels", "#4285f4", "mdi:television-classic"),
  app("tv.twitch.android.app", "Twitch", "#9146ff", "mdi:twitch"),
  app("com.disney.disneyplus", "Disney+", "#113ccf", null),
  app("com.android.tv.settings", "Settings", "#607d8b", "mdi:cog", { system: true }),
  app("com.android.vending", "Play Store", "#01875f", "mdi:google-play", { system: true }),
  app("com.google.android.tvlauncher", "Launcher", null, null, { system: true, hidden: true }),
];

const MEDIA: Record<string, string> = {
  "com.google.android.youtube.tv": "Lofi Girl — beats to relax/study to",
  "com.spotify.tv.android": "Океан Ельзи — Обійми",
  "org.jellyfin.androidtv": "Тіні забутих предків (1965)",
};

// ---- state machine ----------------------------------------------------------------------

let dark = false;
let lang = "en";
let wakeTimer: ReturnType<typeof setTimeout> | null = null;

const tv: TvAttributes & { state: string } = {
  state: "off",
  friendly_name: "Living room TV",
  supported_features: 0,
  volume_level: 0.24,
  is_volume_muted: false,
  media_title: undefined,
  entry_id: ENTRY,
  power_state: "off",
  wake_state: "idle",
  wake_started_at: null,
  wake_timeout: 30,
  app_id: null,
  app_name: null,
  app_activity: null,
  adb_connected: false,
  remote_connected: false,
  volume_entity: null,
  has_wake_button: true,
};

const soundbar = { state: "on", volume_level: 0.35, is_volume_muted: false, supported_features: 4 | 8 | 1024 };

function entity(id: string, state: string, attributes: TvAttributes): HassEntity {
  return { entity_id: id, state, attributes: { ...attributes }, last_changed: new Date().toISOString() };
}

function setApp(pkg: string | null): void {
  const a = APPS.find((x) => x.package === pkg);
  tv.app_id = pkg;
  tv.app_name = a?.label ?? null;
  tv.app_activity = pkg ? `${pkg}/.MainActivity` : null;
  tv.media_title = (pkg && MEDIA[pkg]) || undefined;
  tv.state = tv.media_title ? "playing" : "on";
}

function powerOn(): void {
  tv.power_state = "on";
  tv.wake_state = "idle";
  tv.wake_started_at = null;
  tv.adb_connected = $<HTMLInputElement>("adb").checked;
  tv.remote_connected = $<HTMLInputElement>("remote").checked;
  setApp("com.google.android.tvlauncher");
  tv.app_name = null;
}

function powerOff(state: "off" | "asleep" = "off"): void {
  if (wakeTimer) clearTimeout(wakeTimer);
  tv.power_state = state;
  tv.wake_state = "idle";
  tv.wake_started_at = null;
  tv.state = "off";
  tv.adb_connected = state === "asleep";
  tv.remote_connected = false;
  setApp(null);
  tv.state = "off";
}

function startWake(): void {
  if (wakeTimer) clearTimeout(wakeTimer);
  const fail = $<HTMLInputElement>("failnext").checked;
  tv.power_state = "waking";
  tv.wake_state = "waking";
  tv.wake_started_at = new Date().toISOString();
  tv.wake_timeout = fail ? 10 : 30;
  tv.state = "off";
  const delay = fail ? 10_000 : 6_000 + Math.random() * 6_000;
  wakeTimer = setTimeout(() => {
    if (fail) {
      tv.power_state = "off";
      tv.wake_state = "failed";
      tv.wake_started_at = null;
      $<HTMLInputElement>("failnext").checked = false;
      log("err", "wake timed out -> wake_state=failed");
    } else {
      powerOn();
      log("info", "TV is on");
    }
    publish();
  }, delay);
  log("info", `waking over BLE (${fail ? "will fail" : `~${Math.round(delay / 1000)} s`})`);
}

// ---- mock hass --------------------------------------------------------------------------

function wsError(code: string, message: string) {
  return { code, message };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function screenshotPng(): string {
  const c = document.createElement("canvas");
  c.width = 640;
  c.height = 360;
  const g = c.getContext("2d")!;
  const a = APPS.find((x) => x.package === tv.app_id);
  const grad = g.createLinearGradient(0, 0, 640, 360);
  grad.addColorStop(0, a?.color ?? "#263238");
  grad.addColorStop(1, "#000");
  g.fillStyle = grad;
  g.fillRect(0, 0, 640, 360);
  g.fillStyle = "#fff";
  g.font = "bold 44px sans-serif";
  g.fillText(a?.label ?? "Home", 40, 170);
  g.font = "22px sans-serif";
  g.fillText(tv.media_title ?? "", 40, 215);
  g.fillText(new Date().toLocaleTimeString(), 40, 320);
  return c.toDataURL("image/png");
}

async function keyLatency(): Promise<void> {
  if ($<HTMLInputElement>("slowadb").checked) await sleep(800);
}

function applyKey(key: string): void {
  if (key === "HOME") {
    setApp("com.google.android.tvlauncher");
    tv.app_name = null;
  }
  if (key === "VOLUME_UP") tv.volume_level = Math.min(1, (tv.volume_level ?? 0) + 0.02);
  if (key === "VOLUME_DOWN") tv.volume_level = Math.max(0, (tv.volume_level ?? 0) - 0.02);
  if (key === "MUTE") tv.is_volume_muted = !tv.is_volume_muted;
  if (key === "PLAY_PAUSE" && tv.media_title) tv.state = tv.state === "playing" ? "paused" : "playing";
  publish();
}

const repeats = new Map<string, { active: boolean }>();

function startServerRepeat(key: string): void {
  stopServerRepeat(key, true);
  const token = { active: true };
  repeats.set(key, token);
  const started = Date.now();
  void (async () => {
    let n = 0;
    while (token.active && Date.now() - started < 15_000) {
      await keyLatency();
      if (!token.active) break;
      applyKey(key);
      n++;
      await sleep(n === 1 ? 400 : 120);
    }
    if (token.active) log("err", `server repeat of ${key} stopped by the 15 s limit`);
    log("info", `server repeat ${key}: ${n} press(es)`);
    if (repeats.get(key) === token) repeats.delete(key);
  })();
}

function stopServerRepeat(key: string, quiet = false): void {
  const token = repeats.get(key);
  if (token) token.active = false;
  else if (!quiet) log("info", `stray up for ${key} (no-op)`);
  repeats.delete(key);
}
async function handleWs(msg: Record<string, unknown>): Promise<unknown> {
  const { type, entry_id, ...rest } = msg;
  log("ws", `${type} ${JSON.stringify(rest)}`);
  if (entry_id !== ENTRY) throw wsError("not_found", "Unknown entry");
  await sleep(80 + Math.random() * 120);
  const cmd = String(type).replace("android_tv_pilot/", "");
  if (cmd === "apps") {
    const mode = $<HTMLSelectElement>("appsmode").value;
    if (mode === "slow") await sleep(3000);
    if (mode === "error") throw wsError("failed", "ADB returned no package list");
    return { apps: mode === "empty" ? [] : APPS };
  }
  // An `up` always stops a server-side repeat, even when the TV became unreachable meanwhile.
  if (cmd === "send_key" && rest.action === "up") {
    stopServerRepeat(rest.key as string);
    return {};
  }
  if (tv.power_state !== "on" || $<HTMLInputElement>("unreachable").checked) {
    for (const key of [...repeats.keys()]) stopServerRepeat(key, true);
    throw wsError("tv_unreachable", "ADB connection to 192.168.1.50:5555 refused");
  }
  switch (cmd) {
    case "send_key": {
      const key = rest.key as string;
      const action = (rest.action as string) ?? "press";
      // Mirrors the integration: down starts a server-side repeat (each press awaited, restart on a
      // second down, stop after 15 s), up stops it, a stray up is a no-op.
      if (action === "down") {
        startServerRepeat(key);
        return {};
      }
      if (action === "up") {
        stopServerRepeat(key);
        return {};
      }
      await keyLatency();
      applyKey(key);
      return {};
    }
    case "send_text": {
      if (!/^[\x20-\x7e]*$/.test(String(rest.text))) throw wsError("unsupported", "ADB input text supports ASCII only");
      return {};
    }
    case "launch_app": {
      setApp(rest.package as string);
      publish();
      return {};
    }
    case "open_url":
      return {};
    case "screenshot_url":
      await sleep(400);
      return { url: screenshotPng() };
  }
  throw wsError("unsupported", `Unknown command ${cmd}`);
}

async function callService(domain: string, service: string, data: Record<string, unknown> = {}): Promise<void> {
  log("svc", `${domain}.${service} ${JSON.stringify(data)}`);
  if (data.entity_id === SOUNDBAR) {
    if (service === "volume_up") soundbar.volume_level = Math.min(1, soundbar.volume_level + 0.05);
    if (service === "volume_down") soundbar.volume_level = Math.max(0, soundbar.volume_level - 0.05);
    if (service === "volume_set") soundbar.volume_level = Number(data.volume_level);
    if (service === "volume_mute") soundbar.is_volume_muted = !!data.is_volume_muted;
    publish();
    return;
  }
  if (service === "turn_on") {
    if (tv.power_state === "on") return;
    startWake();
  } else if (service === "turn_off") {
    powerOff();
  }
  publish();
}

function publish(): void {
  tv.volume_entity = $<HTMLInputElement>("volent").checked ? SOUNDBAR : null;
  tv.has_wake_button = $<HTMLInputElement>("wakebtn").checked;
  const { state, ...attrs } = tv;
  const hass: Hass = {
    states: {
      [TV]: entity(TV, state, attrs),
      [SOUNDBAR]: entity(SOUNDBAR, soundbar.state, { friendly_name: "Soundbar", ...soundbar }),
      "media_player.kitchen_speaker": entity("media_player.kitchen_speaker", "idle", { friendly_name: "Kitchen" }),
    },
    locale: { language: lang },
    language: lang,
    themes: { darkMode: dark },
    connection: { sendMessagePromise: handleWs as Hass["connection"]["sendMessagePromise"] },
    callService: callService as Hass["callService"],
  };
  card.hass = hass;
}

// ---- config + controls ------------------------------------------------------------------

function applyConfig(): void {
  const config: CardConfig = {
    type: "custom:android-tv-pilot-card",
    entity: TV,
    layout: $<HTMLSelectElement>("layout").value as CardConfig["layout"],
    show_screenshot: $<HTMLInputElement>("shot").checked,
    prototype_switch: $<HTMLInputElement>("proto").checked,
  };
  if ($<HTMLInputElement>("pinned").checked) config.pinned_apps = ["org.jellyfin.androidtv", "com.google.android.youtube.tv"];
  card.setConfig(config);
  log("info", `config ${JSON.stringify(config)}`);
}

const STATES: Record<string, () => void> = {
  off: () => powerOff(),
  waking: () => startWake(),
  on: () => powerOn(),
  asleep: () => powerOff("asleep"),
  failed: () => {
    powerOff();
    tv.wake_state = "failed";
  },
};
for (const [name, fn] of Object.entries(STATES)) {
  const b = document.createElement("button");
  b.textContent = name;
  b.addEventListener("click", () => {
    fn();
    publish();
    log("info", `forced state ${name}`);
  });
  $("states").append(b);
}

const VIEWPORTS: [string, number][] = [["320", 320], ["phone 390", 390], ["tablet 768", 768], ["desktop 1180", 1180]];
function setViewport(w: number): void {
  $("frame").style.setProperty("--frame-w", `${w}px`);
  $("frame-label").textContent = `Card width ${w}px`;
  for (const b of $("viewports").querySelectorAll("button")) b.classList.toggle("on", Number(b.dataset.w) === w);
}
for (const [label, w] of VIEWPORTS) {
  const b = document.createElement("button");
  b.textContent = label;
  b.dataset.w = String(w);
  b.addEventListener("click", () => setViewport(w));
  $("viewports").append(b);
}

$("theme").addEventListener("click", () => {
  dark = !dark;
  document.body.classList.toggle("dark", dark);
  $("theme").textContent = dark ? "Light theme" : "Dark theme";
  publish();
});
$("lang").addEventListener("click", () => {
  lang = lang === "en" ? "uk" : "en";
  $("lang").textContent = lang === "en" ? "Українська" : "English";
  publish();
});
for (const id of ["unreachable", "wakebtn", "adb", "remote", "volent", "appsmode"]) {
  $(id).addEventListener("change", () => {
    if (id === "adb" || id === "remote") {
      if (tv.power_state === "on") {
        tv.adb_connected = $<HTMLInputElement>("adb").checked;
        tv.remote_connected = $<HTMLInputElement>("remote").checked;
      }
    }
    publish();
  });
}
for (const id of ["layout", "shot", "proto", "pinned"]) $(id).addEventListener("change", applyConfig);

window.addEventListener("haptic", (e) => log("hap", `haptic: ${(e as CustomEvent).detail}`));
window.addEventListener("error", (e) => log("err", `page error: ${e.message}`));

applyConfig();
publish();
setViewport(390);
log("info", `Demo ready (${USE_BUNDLE ? "built bundle" : "sources"}). Tap the power button to start a simulated BLE wake.`);
