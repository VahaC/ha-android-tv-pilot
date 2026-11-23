// Home Assistant host simulation (demo/ha.html).
//
// Mounts the card the way the HA frontend does, in the containers HA uses, with the exact entity
// attributes from a real Xiaomi TV on HA 2026.11.2 (release 0.1.0 showed a blank editor preview and
// a blank section there). Per hui-card._loadElement + tryCreateCardElement:
//   el = document.createElement(tag); el.setConfig(config);      // create-element-base
//   el.hass = hass; el.layout = <view layout>; el.preview = ...; el.editMode = ...;
//   hostCard.appendChild(el)                                       // _setElementVisibility
// If any of those steps throws, HA leaves the hui-card empty (and in a sections view the whole
// section fails); this page does the same so the bug is visible, and logs the exception.
//
// By default it loads the built bundle (what HA loads); add ?src to use the TypeScript sources.

import "./ha-stubs";
import type { Hass } from "../src/types";

const params = new URLSearchParams(location.search);
if (params.has("src")) {
  await import("../src/android-tv-pilot-card");
} else {
  // @ts-ignore the build output has no type declarations
  await import("../../custom_components/android_tv_pilot/frontend/android-tv-pilot-card.js");
}

const ENTITY = "media_player.living_room_xiaomi_mitv_mooq0";
const TAG = "android-tv-pilot-card";
const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const logEl = $("log");
$("src").textContent = params.has("src") ? "(TypeScript sources)" : "(built bundle)";

function log(text: string, error = false): void {
  const line = document.createElement("div");
  line.textContent = `${new Date().toLocaleTimeString()}  ${text}`;
  if (error) line.style.color = "#ff6b6b";
  logEl.prepend(line);
}

const hass: Hass = {
  states: {
    [ENTITY]: {
      entity_id: ENTITY,
      state: "idle",
      attributes: {
        adb_connected: true,
        remote_connected: true,
        power_state: "on",
        wake_state: "idle",
        wake_started_at: null,
        wake_timeout: 20,
        has_wake_button: true,
        app_id: "com.google.android.tvlauncher",
        app_name: "Home",
        app_activity: "com.google.android.tvlauncher.MainActivity",
        entry_id: "01M83V11QKPW2ABWFHRQQTCEVX",
        volume_entity: null,
        volume_level: 0.03,
        is_volume_muted: false,
        supported_features: 24509,
        source: "Home",
        source_list: ["Home", "YouTube", "Netflix", "Kodi", "Spotify", "Prime Video", "Plex", "VLC", "Jellyfin", "Twitch", "Settings", "Play Store", "Live Channels", "Disney+", "SmartTube"],
        device_class: "tv",
        friendly_name: "Xiaomi MiTV-MOOQ0",
      },
    },
  },
  locale: { language: "en" },
  language: "en",
  themes: { darkMode: true },
  connection: {
    sendMessagePromise: (async (msg: Record<string, unknown>) => {
      log(`ws ${String(msg.type)}`);
      if (msg.type === "android_tv_pilot/apps") {
        const app = (pkg: string, label: string, color: string | null, icon: string | null, extra = {}) => ({
          package: pkg, label, color, icon, icon_url: null, hidden: false, system: false, ...extra,
        });
        return {
          apps: [
            app("com.google.android.tvlauncher", "Home", null, null, { hidden: true, system: true }),
            app("com.google.android.youtube.tv", "YouTube", "#ff0033", "mdi:youtube", { system: true }),
            app("com.netflix.ninja", "Netflix", "#e50914", "mdi:netflix", { system: true }),
            app("org.xbmc.kodi", "Kodi", "#17b2e7", "mdi:kodi"),
            app("com.spotify.tv.android", "Spotify", "#1db954", "mdi:spotify"),
            app("com.android.vending", "Play Store", "#01875f", "mdi:google-play", { system: true }),
          ],
        };
      }
      return {};
    }) as Hass["connection"]["sendMessagePromise"],
  },
  callService: (async (domain: string, service: string) => log(`service ${domain}.${service}`)) as Hass["callService"],
};

type Card = HTMLElement & Record<string, unknown> & { setConfig(c: unknown): void; getGridOptions?: () => { columns: number | "full"; rows: number | "auto" } };

/** hui-card._loadElement + _setElementVisibility, in HA's order. Returns the hui-card wrapper. */
function huiCard(viewLayout: string, preview: boolean, cardLayout: string): { host: HTMLElement; el: Card | null } {
  const host = document.createElement("hui-card");
  let el: Card | null = null;
  try {
    el = document.createElement(TAG) as Card;
    if ($<HTMLInputElement>("bug").checked) {
      // What release 0.1.0 had: an accessor named `layout` with only a getter.
      Object.defineProperty(el, "layout", { get: () => cardLayout, configurable: true });
    }
    el.setConfig({ type: `custom:${TAG}`, entity: ENTITY, layout: cardLayout });
    el.hass = hass;
    el.layout = viewLayout;
    el.preview = preview;
    el.editMode = preview;
    if (viewLayout === "panel") el.isPanel = true;
    host.appendChild(el);
  } catch (err) {
    log(`hui-card (${viewLayout}${preview ? ", preview" : ""}) threw: ${String(err)} -> nothing appended`, true);
    console.error(err);
    el = null;
  }
  return { host, el };
}

function otherCard(text: string): HTMLElement {
  const c = document.createElement("ha-card");
  c.className = "other";
  c.textContent = text;
  return c;
}

function mountAll(): void {
  const layout = $<HTMLSelectElement>("layout").value;
  for (const id of ["editor-preview", "masonry-col", "section", "panel"]) $(id).replaceChildren();

  $("editor-preview").append(huiCard("masonry", true, layout).host);

  const masonry = huiCard("masonry", false, layout);
  $("masonry-col").append(otherCard("Card above in the same column"), masonry.host, otherCard("Card below in the same column"));

  // hui-grid-section: every card in a wrapper sized from getGridOptions().
  const section = $("section");
  const cell = (child: HTMLElement, columns: number | "full", rows: number | "auto") => {
    const wrap = document.createElement("div");
    wrap.className = "card";
    wrap.style.gridColumn = `span ${columns === "full" ? 12 : Math.min(12, columns)}`;
    if (rows !== "auto") wrap.style.gridRow = `span ${rows}`;
    wrap.append(child);
    return wrap;
  };
  section.append(cell(otherCard("Heading card in the same section"), 12, 1));
  const grid = huiCard("grid", false, layout);
  let opts: { columns: number | "full"; rows: number | "auto" } = { columns: 12, rows: "auto" };
  try {
    if (grid.el?.getGridOptions) opts = grid.el.getGridOptions();
  } catch (err) {
    log(`getGridOptions threw: ${String(err)}`, true);
  }
  section.append(cell(grid.host, opts.columns, opts.rows), cell(otherCard("Tile card after it"), 6, 1));

  $("panel").append(huiCard("panel", false, layout).host);

  // After everything settles, report the rendered size of each card element.
  setTimeout(() => {
    for (const el of document.querySelectorAll<HTMLElement>(TAG)) {
      const r = el.getBoundingClientRect();
      const where = el.closest("#editor-preview, #masonry-col, #section, #panel")?.id;
      const wrap = el.shadowRoot?.querySelector(".wrap");
      log(`${where}: ${Math.round(r.width)}x${Math.round(r.height)} px, ${wrap ? wrap.className.trim() : "NO CONTENT"}`, !wrap || r.height < 50);
    }
  }, 800);
}

$("layout").addEventListener("change", mountAll);
$("bug").addEventListener("change", mountAll);
$("remount").addEventListener("click", mountAll);
if (params.get("layout")) $<HTMLSelectElement>("layout").value = params.get("layout")!;
if (params.has("bug")) $<HTMLInputElement>("bug").checked = true;
mountAll();
