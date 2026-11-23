// @vitest-environment happy-dom
//
// Regression test for the blank editor preview / blank section in Home Assistant 2026.11:
// hui-card assigns properties to the card element that the demo never set. In particular
// `element.layout = "grid" | "masonry" | "panel"` threw a TypeError because the card had a
// getter-only `layout` accessor, so hui-card never appended the element and the whole section
// failed to render. This file drives the element the way hui-card / hui-grid-section do.

import { beforeAll, describe, expect, it } from "vitest";
import type { Hass } from "../src/types";

type CardElement = HTMLElement & {
  setConfig(config: Record<string, unknown>): void;
  getCardSize(): number;
  getGridOptions(): { columns: number | "full"; rows: number | "auto"; min_columns?: number };
  hass?: Hass;
  layout?: unknown;
  preview?: unknown;
  editMode?: unknown;
  isPanel?: unknown;
  updateComplete: Promise<boolean>;
};

const ENTITY = "media_player.living_room_xiaomi_mitv_mooq0";

/** The exact attribute set from the user's instance when the preview was blank. */
function userHass(): Hass {
  return {
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
          source_list: ["Home", "YouTube", "Netflix"],
          device_class: "tv",
          friendly_name: "Xiaomi MiTV-MOOQ0",
        },
      },
    },
    locale: { language: "en" },
    themes: { darkMode: true },
    connection: {
      sendMessagePromise: (async (msg: Record<string, unknown>) => {
        if (msg.type === "android_tv_pilot/apps") {
          return {
            apps: [
              { package: "com.google.android.tvlauncher", label: "Home", color: null, icon: null, icon_url: null, hidden: true, system: true },
              { package: "com.google.android.youtube.tv", label: "YouTube", color: "#ff0033", icon: "mdi:youtube", icon_url: null, hidden: false, system: true },
            ],
          };
        }
        return {};
      }) as Hass["connection"]["sendMessagePromise"],
    },
    callService: async () => undefined,
  };
}

beforeAll(async () => {
  await import("../src/android-tv-pilot-card");
});

function create(): CardElement {
  return document.createElement("android-tv-pilot-card") as CardElement;
}

describe("card element driven like Home Assistant's hui-card", () => {
  it("accepts HA's host properties before setConfig (layout, preview, editMode, isPanel)", () => {
    const el = create();
    expect(() => {
      el.layout = "grid";
      el.preview = true;
      el.editMode = true;
      el.isPanel = false;
    }).not.toThrow();
    expect(el.layout).toBe("grid");
  });

  it("returns valid sizes before and after setConfig", () => {
    const el = create();
    const check = () => {
      const size = el.getCardSize();
      expect(Number.isFinite(size) && size > 0).toBe(true);
      const g = el.getGridOptions();
      expect(g.columns === "full" || (Number.isInteger(g.columns) && g.columns >= 1 && g.columns <= 12)).toBe(true);
      expect(g.rows === "auto" || (Number.isInteger(g.rows) && g.rows >= 1)).toBe(true);
      if (typeof g.columns === "number" && g.min_columns !== undefined) expect(g.min_columns).toBeLessThanOrEqual(g.columns);
    };
    check();
    el.setConfig({ type: "custom:android-tv-pilot-card", entity: ENTITY, layout: "remote" });
    check();
    el.setConfig({ type: "custom:android-tv-pilot-card", entity: ENTITY, layout: "wide" });
    check();
    expect(el.getGridOptions().columns).toBe("full");
  });

  it("keeps HA's view layout separate from the card's own layout", () => {
    const el = create();
    el.setConfig({ type: "custom:android-tv-pilot-card", entity: ENTITY, layout: "apps" });
    el.layout = "grid";
    el.layout = "masonry";
    el.layout = "panel";
    expect(el.getCardSize()).toBe(10); // still the "apps" card layout
  });

  it("shows a visible error instead of a blank card when rendering throws", async () => {
    const el = create();
    el.setConfig({ type: "custom:android-tv-pilot-card", entity: ENTITY });
    const hass = userHass();
    Object.defineProperty(hass, "locale", {
      get() {
        throw new Error("boom");
      },
    });
    el.hass = hass;
    const errors: unknown[] = [];
    const orig = console.error;
    console.error = (...args: unknown[]) => errors.push(args);
    try {
      document.body.appendChild(el);
      await el.updateComplete;
    } finally {
      console.error = orig;
    }
    const box = el.shadowRoot!.querySelector("ha-card .render-error");
    expect(box?.textContent).toContain("boom");
    expect(box?.textContent).toContain("browser console");
    expect(errors.length).toBeGreaterThan(0);
    el.remove();
  });

  for (const layout of ["remote", "apps", "wide"]) {
    it(`renders the user's TV in the ${layout} layout after the hui-card sequence`, async () => {
      // tryCreateCardElement: createElement + setConfig, then hass, layout, preview, editMode,
      // then appendChild (hui-card._loadElement / _setElementVisibility).
      const el = create();
      el.setConfig({ type: "custom:android-tv-pilot-card", entity: ENTITY, layout });
      el.hass = userHass();
      el.layout = "grid";
      el.preview = true;
      el.editMode = true;
      document.body.appendChild(el);
      await el.updateComplete;
      await new Promise((r) => setTimeout(r, 0)); // apps request resolves
      await el.updateComplete;
      const root = el.shadowRoot!;
      expect(root.querySelector(`ha-card .wrap.layout-${layout}`)).not.toBeNull();
      expect(root.querySelector(".render-error")).toBeNull();
      expect(root.querySelector(".name")?.textContent).toBe("Xiaomi MiTV-MOOQ0");
      el.remove();
    });
  }
});
