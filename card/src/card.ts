import { LitElement, html, nothing, svg, type PropertyValues, type TemplateResult } from "lit";
import { property, state } from "lit/decorators.js";
import { TvApi, toWsError } from "./api";
import { profileFor, type AppProfile, type ProfileAction } from "./app-profiles";
import { cardStyles } from "./card-styles";
import "./dpad";
import type { KeyEventDetail } from "./dpad";
import { local, pickLanguage, translator, type Lang, type StringKey, type Translate } from "./i18n";
import {
  LAYOUTS,
  arrangeApps,
  effectiveOverride,
  fillTemplate,
  normalizeLayout,
  parseStoredLayout,
  initials,
  normalizeUrl,
  onColor,
  parseCssColor,
  pickOnAccent,
  volumePercent,
  wakeProgress,
} from "./logic";
import { HoldButton, REPEATABLE_KEYS, holdHandlers } from "./repeater";
import "./touchpad";
import type { CardConfig, Hass, HassEntity, KeyAction, LayoutId, TvApp, TvAttributes, TvKey } from "./types";

const NAV_MODE_KEY = "android-tv-pilot:nav-mode";
// Per-browser layout choice from the header layout button. Stored as {layout, base}: `base` is the
// dashboard (config) layout at the time of the choice, so changing `layout` in the editor drops the
// stored choice instead of being silently beaten by it.
const LAYOUT_KEY = "android-tv-pilot:layout";
const OPTIMISTIC_WAKE_MS = 10_000;
const VOLUME_REPEAT_MS = 250;
const SCREENSHOT_EVERY_MS = 10_000;
const SCREENSHOT_MIN_GAP_MS = 5_000;
const VOLUME_SET_FEATURE = 4;

type NavMode = "dpad" | "touchpad";
type SheetTab = "app" | "keyboard" | "screen";
type Power = "off" | "waking" | "on" | "asleep";

interface Toast {
  id: number;
  text: string;
  detail?: string;
  wake?: boolean;
}

function readStore(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

let colorCanvas: CanvasRenderingContext2D | null | undefined;

/** Parses a theme colour; names and other CSS syntaxes go through a 2D canvas to become hex/rgb. */
function resolveColor(value: string): [number, number, number] | null {
  const direct = parseCssColor(value);
  if (direct) return direct;
  if (colorCanvas === undefined) colorCanvas = document.createElement("canvas").getContext("2d");
  if (!colorCanvas) return null;
  colorCanvas.fillStyle = "#000001";
  colorCanvas.fillStyle = value;
  const normal = String(colorCanvas.fillStyle);
  return normal === "#000001" ? null : parseCssColor(normal);
}

function writeStore(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage blocked: the choice simply is not remembered */
  }
}

export class AndroidTvPilotCard extends LitElement {
  @property({ attribute: false }) hass?: Hass;
  @state() private config!: CardConfig;

  @state() private apps: TvApp[] | null = null;
  @state() private appsStatus: "idle" | "loading" | "ready" | "error" = "idle";
  @state() private appsError = "";
  @state() private navMode: NavMode = readStore(NAV_MODE_KEY) === "touchpad" ? "touchpad" : "dpad";
  /** Layout chosen with the header layout button in this browser; overrides the dashboard layout. */
  @state() private layoutOverride: LayoutId | null = null;
  /** Dashboard layout from the config, normalised (a/b/c aliases mapped). */
  @state() private configLayout: LayoutId = "remote";

  // Properties Home Assistant assigns to every card element (hui-card._loadElement, views). They
  // must stay plain writable fields: HA's `layout` is the VIEW layout ("masonry" | "grid" |
  // "panel"), unrelated to this card's remote/apps/wide layout (see cardLayout). A getter-only
  // `layout` here made hui-card throw, which blanked the editor preview and the whole section.
  /** View layout set by HA. Informational only. */
  public layout?: string;
  /** Set by HA when the card is shown in the card editor preview. */
  public preview = false;
  /** Set by HA while the dashboard is in edit mode. */
  public editMode = false;
  /** Set by HA's panel view. */
  public isPanel = false;
  @state() private layoutMenuOpen = false;
  /** Local "waking" shown from the tap on power until the entity next updates (max 10 s). */
  @state() private optimisticWakeAt: number | null = null;
  @state() private toasts: Toast[] = [];
  @state() private now = Date.now();
  @state() private sheetOpen = false;
  @state() private sheetTab: SheetTab = "app";
  @state() private activeAction: string | null = null;
  @state() private actionValue = "";
  @state() private actionError = "";
  @state() private kbText = "";
  @state() private kbEnter = false;
  @state() private kbError = "";
  @state() private kbSent = false;
  @state() private volDraft: number | null = null;
  @state() private shotUrl = "";
  @state() private shotLoading = false;
  @state() private shotError = false;
  @state() private shotAt = 0;
  @state() private visible = true;

  private api: TvApi | null = null;
  private entryId: string | null = null;
  private prevPower: Power | null = null;
  private wakeTicker: ReturnType<typeof setInterval> | null = null;
  private shotTimer: ReturnType<typeof setInterval> | null = null;
  private shotRequestedAt = 0;
  /** One hold at a time for every hold button on the card (volume, seek, delete, channel). */
  private keyHold = new HoldButton((key, action) => this.holdSend(key, action));
  /** Keys currently sent as `down`, from any source; all get an `up` when the card locks or leaves. */
  private heldKeys = new Set<TvKey>();
  private volumeLoop: { active: boolean } | null = null;
  private toastId = 0;
  private revealedApp = "";
  private themeKey = "";
  private observer: IntersectionObserver | null = null;
  private onVisibility = () => {
    if (document.visibilityState !== "visible") this.releaseAllKeys();
    this.updateVisibility();
  };

  // ---- Lovelace API ---------------------------------------------------------------------

  setConfig(config: CardConfig): void {
    if (!config || !config.entity) throw new Error("Set 'entity' to an Android TV Pilot media_player");
    const layout = config.layout === undefined ? "remote" : normalizeLayout(config.layout);
    if (!layout) throw new Error("'layout' must be remote, apps or wide");
    // The layout is chosen in the card editor; the header button is an opt-in extra.
    // `prototype_switch` is the old name of `layout_switch` and is still read.
    const layoutSwitch = config.layout_switch ?? config.prototype_switch ?? false;
    this.config = { haptics: true, show_screenshot: false, ...config, layout, layout_switch: layoutSwitch };
    this.configLayout = layout;
    // A stored per-browser choice only survives while the dashboard layout is unchanged.
    const stored = parseStoredLayout(readStore(LAYOUT_KEY));
    this.layoutOverride = effectiveOverride(stored, layout);
    if (readStore(LAYOUT_KEY) !== null && !this.layoutOverride) writeStore(LAYOUT_KEY, null);
  }

  getCardSize(): number {
    return { remote: 12, apps: 10, wide: 8 }[this.cardLayout];
  }

  getGridOptions() {
    return this.cardLayout === "wide"
      ? { columns: "full", rows: "auto", min_columns: 6 }
      : { columns: 6, rows: "auto", min_columns: 4 };
  }

  // ---- derived state --------------------------------------------------------------------

  private get uiLang(): Lang {
    return pickLanguage(this.hass?.locale?.language ?? this.hass?.language);
  }

  private get t(): Translate {
    return translator(this.uiLang);
  }

  /**
   * The per-browser choice wins over the dashboard layout only while the layout button is enabled;
   * with the button off (the default) the editor's layout always applies.
   */
  private get cardLayout(): LayoutId {
    if (this.config?.layout_switch === true && this.layoutOverride) return this.layoutOverride;
    return this.configLayout;
  }

  private get entity(): HassEntity | undefined {
    return this.config ? this.hass?.states[this.config.entity] : undefined;
  }

  private get attrs(): TvAttributes {
    return this.entity?.attributes ?? {};
  }

  private get power(): Power {
    const p = this.attrs.power_state;
    if (p) return p;
    return this.entity && this.entity.state !== "off" && this.entity.state !== "unavailable" ? "on" : "off";
  }

  private get waking(): boolean {
    if (this.power === "on") return false;
    if (this.power === "waking" || this.attrs.wake_state === "waking") return true;
    return this.optimisticWakeAt !== null && this.now - this.optimisticWakeAt < OPTIMISTIC_WAKE_MS;
  }

  private get failed(): boolean {
    // Only a TV that is still off counts as a failed BLE wake; an asleep TV was reached after all.
    return this.attrs.wake_state === "failed" && this.power === "off" && !this.waking;
  }

  private get locked(): boolean {
    return this.power !== "on";
  }

  private get volumeTarget(): string | null {
    return this.config.volume_entity || this.attrs.volume_entity || null;
  }

  private get runningApp(): TvApp | undefined {
    const id = this.attrs.app_id;
    return id ? this.apps?.find((a) => a.package === id) : undefined;
  }

  // ---- lifecycle ------------------------------------------------------------------------

  connectedCallback(): void {
    super.connectedCallback();
    document.addEventListener("visibilitychange", this.onVisibility);
    if ("IntersectionObserver" in window) {
      this.observer = new IntersectionObserver((entries) => {
        this.visible = entries.some((e) => e.isIntersecting);
        this.updateVisibility();
      });
      this.observer.observe(this);
    }
  }

  disconnectedCallback(): void {
    super.disconnectedCallback();
    document.removeEventListener("visibilitychange", this.onVisibility);
    this.observer?.disconnect();
    this.observer = null;
    this.stopWakeTicker();
    this.stopShotTimer();
    this.releaseAllKeys();
    document.removeEventListener("pointerdown", this.onOutsidePointer, true);
    this.layoutMenuOpen = false;
  }

  protected shouldUpdate(changed: PropertyValues): boolean {
    if (changed.size === 1 && changed.has("hass") && this.config) {
      const old = changed.get("hass") as Hass | undefined;
      if (!old || !this.hass) return true;
      const ids = [this.config.entity, this.volumeTarget].filter((x): x is string => !!x);
      return (
        ids.some((id) => old.states[id] !== this.hass!.states[id]) ||
        old.locale?.language !== this.hass.locale?.language ||
        old.themes !== this.hass.themes
      );
    }
    return true;
  }

  protected willUpdate(changed: PropertyValues): void {
    if (!changed.has("hass") || !this.hass || !this.config) return;
    const oldHass = changed.get("hass") as Hass | undefined;
    if (this.optimisticWakeAt !== null && oldHass && oldHass.states[this.config.entity] !== this.entity) {
      this.optimisticWakeAt = null;
    }
    const entryId = this.attrs.entry_id ?? null;
    if (entryId !== this.entryId) {
      this.entryId = entryId;
      this.api = entryId ? new TvApi(() => this.hass, entryId) : null;
      this.apps = null;
      this.appsStatus = "idle";
    }
    const power = this.power;
    if (this.api && power === "on" && (this.prevPower !== "on" || this.appsStatus === "idle")) {
      void this.loadApps();
    }
    if (power !== "on" && this.prevPower === "on") this.sheetOpen = false;
    if (this.locked) this.releaseAllKeys();
    if (this.waking && !this.wakeTicker) this.now = Date.now();
    this.prevPower = power;
  }

  /**
   * The accent is always the theme's --primary-color (pure CSS). Only the colour drawn on top of it
   * needs JS: --text-primary-color when it is readable on the primary, otherwise black or white.
   * Re-checked whenever the resolved theme colours change.
   */
  private syncAccentContrast(): void {
    const cs = getComputedStyle(this);
    const primary = cs.getPropertyValue("--primary-color").trim() || "#03a9f4";
    const text = cs.getPropertyValue("--text-primary-color").trim() || "#ffffff";
    const key = `${primary}|${text}`;
    if (key === this.themeKey) return;
    this.themeKey = key;
    const on = pickOnAccent(resolveColor(primary), resolveColor(text));
    if (on) this.style.setProperty("--atp-on-accent", on);
    else this.style.removeProperty("--atp-on-accent");
  }

  protected updated(): void {
    this.syncAccentContrast();
    if (this.waking) this.startWakeTicker();
    else this.stopWakeTicker();
    this.revealRunningApp();
    this.syncShotTimer();
  }

  /** Scrolls the app rail (remote layout) so the running app's tile is in view, once per app. */
  private revealRunningApp(): void {
    const rail = this.renderRoot.querySelector<HTMLElement>(".tiles.rail");
    const tile = rail?.querySelector<HTMLElement>(".tile.running")?.parentElement;
    const key = `${this.cardLayout}:${this.attrs.app_id ?? ""}`;
    if (!rail || !tile || key === this.revealedApp) return;
    this.revealedApp = key;
    const left = tile.offsetLeft - rail.offsetLeft;
    const right = left + tile.offsetWidth;
    // Leave room for the fade on the right edge of the rail.
    if (left < rail.scrollLeft || right > rail.scrollLeft + rail.clientWidth * 0.85) {
      rail.scrollLeft = Math.max(0, right - rail.clientWidth * 0.8);
    }
  }

  private startWakeTicker(): void {
    if (this.wakeTicker) return;
    this.wakeTicker = setInterval(() => (this.now = Date.now()), 250);
  }

  private stopWakeTicker(): void {
    if (this.wakeTicker) clearInterval(this.wakeTicker);
    this.wakeTicker = null;
  }

  // ---- commands -------------------------------------------------------------------------

  private haptic(type: "light" | "selection" | "success" | "failure" = "light"): void {
    if (this.config?.haptics === false) return;
    window.dispatchEvent(new CustomEvent("haptic", { detail: type, bubbles: true, composed: true }));
  }

  private fail(err: unknown): void {
    const e = toWsError(err);
    const key: StringKey =
      e.code === "tv_unreachable" ? "err_tv_unreachable"
      : e.code === "unsupported" ? "err_unsupported"
      : e.code === "not_found" ? "err_not_found"
      : "err_failed";
    this.toast(this.t(key), e.code === "failed" || e.code === "unsupported" ? e.message : undefined, e.code === "tv_unreachable");
    this.haptic("failure");
  }

  private toast(text: string, detail?: string, wake = false): void {
    const id = ++this.toastId;
    this.toasts = [...this.toasts.filter((t) => t.text !== text).slice(-2), { id, text, detail, wake }];
    setTimeout(() => this.dismissToast(id), wake ? 8000 : 4500);
  }

  private dismissToast(id: number): void {
    this.toasts = this.toasts.filter((t) => t.id !== id);
  }

  /**
   * HA's callService already shows its own error toast, so service failures only get haptic
   * feedback here; the card's toasts are for WebSocket command failures.
   */
  private serviceFailed(err: unknown): void {
    console.warn("[android-tv-pilot-card] service call failed", err);
    this.haptic("failure");
  }

  private sendKey(key: TvKey, action: KeyAction = "press", repeat = false): Promise<unknown> {
    if (!this.api) return Promise.resolve();
    // An `up` is always delivered, even after the card locked, so no key is left held on the TV.
    if (action === "up") {
      // Already released (e.g. by releaseAllKeys before the pad's own cancel): no duplicate up.
      if (!this.heldKeys.delete(key)) return Promise.resolve();
    } else {
      if (this.locked) return Promise.resolve();
      if (action === "down") this.heldKeys.add(key);
      this.haptic(repeat ? "selection" : "light");
    }
    const sent = this.api.key(key, action);
    sent.catch((e) => (action === "up" ? undefined : this.fail(e)));
    return sent.catch(() => undefined);
  }

  /** Target of the card's HoldButton: volume with a volume entity loops services, all else down/up. */
  private holdSend(key: TvKey, action: KeyAction): void {
    if ((key === "VOLUME_UP" || key === "VOLUME_DOWN") && this.volumeTarget) {
      if (action === "down") this.startVolumeLoop(key === "VOLUME_UP" ? "up" : "down");
      else if (action === "up") this.stopVolumeLoop();
      return;
    }
    void this.sendKey(key, action);
  }

  /** Sends `up` for every key still held and stops client-side loops (lock, hide, disconnect). */
  private releaseAllKeys(): void {
    this.keyHold.cancel();
    this.stopVolumeLoop();
    for (const key of [...this.heldKeys]) void this.sendKey(key, "up");
  }

  /** Volume entity hold: one service call at a time, the next only after the previous settled. */
  private startVolumeLoop(dir: "up" | "down"): void {
    this.stopVolumeLoop();
    const target = this.volumeTarget;
    if (!target || !this.hass || this.locked) return;
    const loop = { active: true };
    this.volumeLoop = loop;
    this.haptic("light");
    void (async () => {
      while (loop.active && this.hass && !this.locked) {
        try {
          await this.hass.callService("media_player", dir === "up" ? "volume_up" : "volume_down", { entity_id: target });
        } catch (e) {
          this.serviceFailed(e);
          break;
        }
        await new Promise((r) => setTimeout(r, VOLUME_REPEAT_MS));
      }
    })();
  }

  private stopVolumeLoop(): void {
    if (this.volumeLoop) this.volumeLoop.active = false;
    this.volumeLoop = null;
  }

  private onPadKey(e: CustomEvent<KeyEventDetail>): void {
    e.stopPropagation();
    const { key, action, repeat, ack } = e.detail;
    if (this.locked && action !== "up") return;
    const sent = this.sendKey(key, action, repeat);
    ack?.(sent);
  }

  private async power_(): Promise<void> {
    if (!this.hass || this.waking) return;
    if (this.power === "on") {
      this.haptic("light");
      try {
        await this.hass.callService("media_player", "turn_off", { entity_id: this.config.entity });
      } catch (e) {
        this.serviceFailed(e);
      }
      return;
    }
    await this.wake();
  }

  private async wake(): Promise<void> {
    if (!this.hass || this.waking) return;
    this.haptic("light");
    // Optimistic "waking" so the button cannot be double-tapped before the server reports back.
    this.now = Date.now();
    this.optimisticWakeAt = this.now;
    try {
      await this.hass.callService("media_player", "turn_on", { entity_id: this.config.entity });
    } catch (e) {
      this.optimisticWakeAt = null;
      this.serviceFailed(e);
    }
  }

  private async loadApps(): Promise<void> {
    if (!this.api) return;
    this.appsStatus = "loading";
    try {
      this.apps = await this.api.apps();
      this.appsStatus = "ready";
    } catch (e) {
      this.appsStatus = "error";
      this.appsError = toWsError(e).message;
    }
  }

  private launch(app: TvApp): void {
    if (!this.api || this.locked) return;
    this.haptic("light");
    this.api.launch(app.package).catch((e) => this.fail(e));
  }

  private toggleMute(): void {
    if (this.locked) return;
    const target = this.volumeTarget;
    if (target && this.hass) {
      this.haptic("selection");
      const muted = !this.hass.states[target]?.attributes.is_volume_muted;
      this.hass
        .callService("media_player", "volume_mute", { entity_id: target, is_volume_muted: muted })
        .catch((e) => this.serviceFailed(e));
      return;
    }
    void this.sendKey("MUTE");
  }

  private setVolume(level: number): void {
    const target = this.volumeTarget;
    if (!target || !this.hass) return;
    this.hass
      .callService("media_player", "volume_set", { entity_id: target, volume_level: Math.round(level) / 100 })
      .catch((e) => this.serviceFailed(e))
      .finally(() => (this.volDraft = null));
  }

  private async runKeys(keys: TvKey[], long = false): Promise<void> {
    if (!this.api) return;
    this.haptic("light");
    try {
      for (let i = 0; i < keys.length; i++) {
        if (i > 0) await new Promise((r) => setTimeout(r, 140));
        await this.api.key(keys[i], long ? "long" : "press");
      }
    } catch (e) {
      this.fail(e);
    }
  }

  private runAction(action: ProfileAction): void {
    if (this.locked || !this.api) return;
    if (action.type === "keys") {
      void this.runKeys(action.keys, action.long);
    } else if (action.type === "type") {
      this.haptic("light");
      this.api.text(action.text, !!action.enter).catch((e) => this.fail(e));
    } else {
      this.haptic("selection");
      const same = this.activeAction === action.id;
      this.activeAction = same ? null : action.id;
      this.actionValue = "";
      this.actionError = "";
    }
  }

  private async submitAction(action: ProfileAction, e: Event): Promise<void> {
    e.preventDefault();
    if (!this.api || this.locked) return;
    const value = this.actionValue;
    if (!value.trim()) return;
    this.actionError = "";
    try {
      if (action.type === "text") {
        if (action.before?.length) {
          await this.runKeys(action.before);
          await new Promise((r) => setTimeout(r, 600));
        }
        await this.api.text(value, !!action.enter);
      } else if (action.type === "link") {
        let url: string;
        if (action.input === "url") {
          const normal = normalizeUrl(value);
          if (!normal) {
            this.actionError = this.uiLang === "uk" ? "Це не схоже на адресу." : "That does not look like a URL.";
            return;
          }
          url = fillTemplate(action.template, { raw: normal });
        } else {
          url = fillTemplate(action.template, { query: value });
        }
        const pkg = action.package === "$current" ? this.attrs.app_id ?? undefined : action.package;
        await this.api.openUrl(url, pkg);
      }
      this.haptic("success");
      this.activeAction = null;
      this.actionValue = "";
    } catch (err) {
      const we = toWsError(err);
      if (we.code === "unsupported") this.actionError = this.t("keyboard_ascii");
      else this.fail(err);
    }
  }

  private async sendText(e?: Event): Promise<void> {
    e?.preventDefault();
    if (!this.api || this.locked) return;
    const text = this.kbText;
    this.kbError = "";
    if (!text) {
      if (this.kbEnter) this.sendKey("ENTER");
      return;
    }
    this.haptic("light");
    try {
      await this.api.text(text, this.kbEnter);
      this.kbText = "";
      this.kbSent = true;
      setTimeout(() => (this.kbSent = false), 1400);
    } catch (err) {
      const we = toWsError(err);
      if (we.code === "unsupported") {
        this.kbError = this.t("keyboard_ascii");
        this.haptic("failure");
      } else this.fail(err);
    }
  }

  // ---- screenshot -----------------------------------------------------------------------

  private updateVisibility(): void {
    this.syncShotTimer();
  }

  private get shotActive(): boolean {
    if (!this.config?.show_screenshot || this.power !== "on" || !this.visible) return false;
    if (document.visibilityState !== "visible") return false;
    // In layout A the screenshot lives in the bottom sheet: no signed URLs while it is not shown.
    if (this.cardLayout === "remote" && !(this.sheetOpen && this.sheetTab === "screen")) return false;
    return true;
  }

  private syncShotTimer(): void {
    if (this.shotActive) {
      if (!this.shotTimer) {
        this.shotTimer = setInterval(() => void this.refreshShot(), SCREENSHOT_EVERY_MS);
        // Deferred so the first request does not change state inside updated().
        if (Date.now() - this.shotRequestedAt > SCREENSHOT_EVERY_MS) setTimeout(() => void this.refreshShot(), 0);
      }
    } else this.stopShotTimer();
  }

  private stopShotTimer(): void {
    if (this.shotTimer) clearInterval(this.shotTimer);
    this.shotTimer = null;
  }

  private async refreshShot(manual = false): Promise<void> {
    if (!this.api || this.power !== "on") return;
    const since = Date.now() - this.shotRequestedAt;
    // Automatic refreshes never run faster than every 5 s; a tap may refresh sooner, but not spam.
    if (since < (manual ? 1000 : SCREENSHOT_MIN_GAP_MS)) return;
    this.shotRequestedAt = Date.now();
    if (manual) this.haptic("selection");
    this.shotLoading = true;
    try {
      this.shotUrl = await this.api.screenshotUrl();
      this.shotError = false;
    } catch {
      this.shotError = true;
      this.shotLoading = false;
    }
  }

  // ---- render helpers -------------------------------------------------------------------

  private keyContent(icon: string, label: string): TemplateResult {
    return icon ? html`<ha-icon icon=${icon}></ha-icon>` : html`<span class="txt" aria-hidden="true">${label}</span>`;
  }

  /** A button for a repeatable key: `down` while held, `up` on release (shared HoldButton). */
  private holdKey(key: TvKey, icon: string, label: string, cls = "", content?: TemplateResult): TemplateResult {
    const h = holdHandlers(this.keyHold, key, "repeat", () => this.locked);
    return html`<button
      class="key ${cls} ${this.keyHold.heldKey === key ? "pressed" : ""}"
      aria-label=${label}
      title=${label}
      ?disabled=${this.locked}
      @pointerdown=${h.pointerdown}
      @pointerup=${h.pointerup}
      @pointercancel=${h.pointercancel}
      @lostpointercapture=${h.lostpointercapture}
      @keydown=${h.keydown}
      @keyup=${h.keyup}
      @blur=${h.blur}
      @contextmenu=${h.contextmenu}
    >
      ${content ?? this.keyContent(icon, label)}
    </button>`;
  }

  /** A single-press key. */
  private keyButton(key: TvKey, icon: string, label: string, cls = ""): TemplateResult {
    return html`<button
      class="key ${cls}"
      aria-label=${label}
      title=${label}
      ?disabled=${this.locked}
      @click=${() => void this.sendKey(key)}
    >
      ${this.keyContent(icon, label)}
    </button>`;
  }

  private appArt(app: TvApp | undefined, fallbackLabel: string): TemplateResult {
    if (app?.icon_url) return html`<img src=${app.icon_url} alt="" loading="lazy" draggable="false" />`;
    if (app?.icon) return html`<ha-icon icon=${app.icon}></ha-icon>`;
    return html`<span class="initials">${initials(app?.label ?? fallbackLabel)}</span>`;
  }

  // ---- layout button (optional, `layout_switch: true`) ------------------------------------

  private static readonly LAYOUT_ICONS: Record<LayoutId, string> = {
    remote: "mdi:remote-tv",
    apps: "mdi:apps",
    wide: "mdi:view-column-outline",
  };

  private layoutName(id: LayoutId): string {
    return this.t(`layout_${id}` as StringKey);
  }

  /** Stores a per-browser layout; picking the dashboard's own layout (or null) clears the choice. */
  private pickLayout(layout: LayoutId | null): void {
    this.haptic("selection");
    const override = layout && layout !== this.configLayout ? layout : null;
    this.layoutOverride = override;
    writeStore(LAYOUT_KEY, override ? JSON.stringify({ layout: override, base: this.configLayout }) : null);
    this.closeLayoutMenu(true);
  }

  private onOutsidePointer = (e: Event): void => {
    const wrap = this.renderRoot.querySelector(".layout-wrap");
    if (wrap && !e.composedPath().includes(wrap)) this.closeLayoutMenu(false);
  };

  private openLayoutMenu(focus: "checked" | "first" | "last" = "checked"): void {
    this.layoutMenuOpen = true;
    document.addEventListener("pointerdown", this.onOutsidePointer, true);
    void this.updateComplete.then(() => {
      const items = this.menuItems();
      const target =
        focus === "last" ? items[items.length - 1]
        : focus === "first" ? items[0]
        : items.find((i) => i.getAttribute("aria-checked") === "true") ?? items[0];
      target?.focus();
    });
  }

  private closeLayoutMenu(returnFocus: boolean): void {
    if (!this.layoutMenuOpen) return;
    this.layoutMenuOpen = false;
    document.removeEventListener("pointerdown", this.onOutsidePointer, true);
    if (returnFocus) {
      void this.updateComplete.then(() => this.renderRoot.querySelector<HTMLElement>(".layout-btn")?.focus());
    }
  }

  private menuItems(): HTMLElement[] {
    return [...this.renderRoot.querySelectorAll<HTMLElement>(".layout-menu [role^='menuitem']")];
  }

  /** Menu keyboard: arrows / Home / End move, Escape closes and returns focus, Tab closes. */
  private onMenuKey(e: KeyboardEvent): void {
    const items = this.menuItems();
    const i = items.indexOf((this.renderRoot as ShadowRoot).activeElement as HTMLElement);
    const move = (n: number) => {
      e.preventDefault();
      items[(n + items.length) % items.length]?.focus();
    };
    if (e.key === "ArrowDown") move(i + 1);
    else if (e.key === "ArrowUp") move(i - 1);
    else if (e.key === "Home") move(0);
    else if (e.key === "End") move(items.length - 1);
    else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      this.closeLayoutMenu(true);
    } else if (e.key === "Tab") this.closeLayoutMenu(false);
  }

  private renderLayoutButton(): TemplateResult | typeof nothing {
    if (this.config.layout_switch !== true) return nothing;
    const t = this.t;
    const current = this.cardLayout;
    const open = this.layoutMenuOpen;
    return html`<div class="layout-wrap">
      <button
        class="key round layout-btn ${open ? "pressed" : ""} ${this.layoutOverride ? "overridden" : ""}"
        aria-label=${t("layout_button", { layout: this.layoutName(current) })}
        title=${t("layout_button", { layout: this.layoutName(current) })}
        aria-haspopup="menu"
        aria-expanded=${open ? "true" : "false"}
        aria-controls="atp-layout-menu"
        @click=${() => (open ? this.closeLayoutMenu(true) : this.openLayoutMenu())}
        @keydown=${(e: KeyboardEvent) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            this.openLayoutMenu(e.key === "ArrowDown" ? "first" : "last");
          }
        }}
      >
        <ha-icon icon="mdi:view-dashboard-outline"></ha-icon>
      </button>
      ${open
        ? html`<div class="layout-menu" role="menu" id="atp-layout-menu" aria-label=${t("layout_menu")} @keydown=${this.onMenuKey}>
            <div class="menu-title" aria-hidden="true">${t("layout_menu")}</div>
            ${LAYOUTS.map(
              (id) => html`<button
                class="menu-item ${current === id ? "on" : ""}"
                role="menuitemradio"
                aria-checked=${current === id ? "true" : "false"}
                tabindex="-1"
                @click=${() => this.pickLayout(id)}
              >
                <ha-icon class="mi-icon" icon=${AndroidTvPilotCard.LAYOUT_ICONS[id]}></ha-icon>
                <span class="mi-text">
                  <span class="mi-name">${this.layoutName(id)}</span>
                  <span class="mi-help">${t(`layout_${id}_help` as StringKey)}</span>
                </span>
                <ha-icon class="mi-check" icon="mdi:check" aria-hidden="true"></ha-icon>
              </button>`,
            )}
            ${this.layoutOverride
              ? html`<div class="menu-sep" role="separator"></div>
                  <button class="menu-item reset" role="menuitem" tabindex="-1" @click=${() => this.pickLayout(null)}>
                    <ha-icon class="mi-icon" icon="mdi:restore"></ha-icon>
                    <span class="mi-text">
                      <span class="mi-name">${t("layout_use_dashboard", { layout: this.layoutName(this.configLayout) })}</span>
                      <span class="mi-help">${t("layout_this_browser")}: ${this.layoutName(this.layoutOverride)}</span>
                    </span>
                  </button>`
              : nothing}
          </div>`
        : nothing}
    </div>`;
  }
  private renderHeader(): TemplateResult {
    const t = this.t;
    const a = this.attrs;
    const name = this.config.name || a.friendly_name || this.config.entity;
    const app = this.runningApp;
    const power = this.power;
    const prog = this.waking ? wakeProgress(a.wake_started_at, a.wake_timeout, this.now) : null;
    const powerLabel = this.failed
      ? t("power_retry")
      : power === "on"
        ? t("power_off")
        : power === "off" && a.has_wake_button === false
          ? t("power_try_on")
          : t("power_on");
    const stateKey: StringKey =
      power === "on" ? "state_on" : power === "asleep" ? "state_asleep" : power === "waking" ? "state_waking" : "state_off";
    const conn = (key: StringKey, ok: boolean | undefined) =>
      html`<span class="conn ${ok ? "ok" : "down"}" role="img" aria-label="${t(key)}: ${t(ok ? "conn_ok" : "conn_down")}" title="${t(key)}: ${t(ok ? "conn_ok" : "conn_down")}">
        <span class="dot"></span>${t(key)}
      </span>`;
    const appColor = app?.color ?? null;
    return html`<header class="head">
      <div class="title">
        <div class="name">${name}</div>
        <div class="sub">
          ${power === "on"
            ? html`<span class="chip" style=${appColor ? `--brand:${appColor};--on-brand:${onColor(appColor)}` : ""}>
                <span class="chip-art">${a.app_id ? this.appArt(app, a.app_name || a.app_id) : html`<ha-icon icon="mdi:home"></ha-icon>`}</span>
                <span class="chip-text">${a.app_name || app?.label || (a.app_id ? a.app_id : t("no_app"))}</span>
              </span>`
            : html`<span class="state-pill ${power} ${this.failed ? "failed" : ""}">${t(stateKey)}</span>`}
          ${conn("conn_adb", a.adb_connected)} ${conn("conn_remote", a.remote_connected)}
        </div>
      </div>
      ${this.renderLayoutButton()}
      <button
        class="power ${power} ${this.failed ? "failed" : ""} ${this.waking ? "waking" : ""}"
        aria-label=${powerLabel}
        title=${powerLabel}
        aria-busy=${this.waking ? "true" : "false"}
        ?disabled=${this.waking}
        @click=${() => this.power_()}
      >
        <svg class="power-ring" viewBox="0 0 100 100" aria-hidden="true">
          <circle class="track" cx="50" cy="50" r="46" pathLength="100"></circle>
          ${prog
            ? svg`<circle class="bar" cx="50" cy="50" r="46" pathLength="100" style="stroke-dashoffset:${100 - prog.fraction * 100}"></circle>`
            : nothing}
        </svg>
        <ha-icon icon=${this.failed ? "mdi:restart" : "mdi:power"}></ha-icon>
      </button>
    </header>`;
  }

  private renderStatus(): TemplateResult | typeof nothing {
    const t = this.t;
    const a = this.attrs;
    if (!this.entity) return nothing;
    if (this.waking) {
      const p = wakeProgress(a.wake_started_at, a.wake_timeout, this.now);
      const s = Math.floor(p.elapsed);
      return html`<div class="status waking" role="status" aria-live="polite">
        <div class="status-row">
          <span class="pulse" aria-hidden="true"></span>
          <strong>${p.overdue ? t("waking_overdue", { s }) : t("waking_seconds", { s })}</strong>
        </div>
        <div
          class="progress"
          role="progressbar"
          aria-label=${t("state_waking")}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow=${Math.round(p.fraction * 100)}
          aria-valuetext=${p.overdue ? t("waking_overdue", { s }) : t("waking_seconds", { s })}
        >
          <span style="width:${p.fraction * 100}%"></span>
        </div>
        <p>${t("waking_hint")}</p>
      </div>`;
    }
    if (this.failed) {
      return html`<div class="status failed" role="alert">
        <ha-icon icon="mdi:bluetooth-off"></ha-icon>
        <div>
          <strong>${t("wake_failed_title")}</strong>
          <p>${t("wake_failed_body")}</p>
        </div>
        <button class="key accent" @click=${() => this.wake()}>${t("power_retry")}</button>
      </div>`;
    }
    if (this.power === "off" && a.has_wake_button === false) {
      return html`<div class="status warn" role="status">
        <ha-icon icon="mdi:sleep"></ha-icon>
        <div>
          <strong>${t("off_no_wake_title")}</strong>
          <p>${t("off_no_wake_body")}</p>
        </div>
      </div>`;
    }
    if (this.power === "off" || this.power === "asleep") {
      const asleep = this.power === "asleep";
      return html`<div class="status idle" role="status">
        <ha-icon icon=${asleep ? "mdi:power-sleep" : "mdi:television-off"}></ha-icon>
        <div>
          <strong>${t(asleep ? "asleep_title" : "off_title")}</strong>
          <p>${t(asleep ? "asleep_body" : "off_body")}</p>
        </div>
        <button class="key accent" @click=${() => this.wake()}>${t("power_on")}</button>
      </div>`;
    }
    return nothing;
  }

  private renderNav(compact = false): TemplateResult {
    const t = this.t;
    const setMode = (m: NavMode) => {
      this.haptic("selection");
      this.releaseAllKeys();
      this.navMode = m;
      writeStore(NAV_MODE_KEY, m);
    };
    return html`<section class="nav ${compact ? "compact" : ""}" @atp-key=${this.onPadKey}>
      <div class="seg nav-toggle" role="group" aria-label=${t("nav_mode")}>
        <button class="seg-btn ${this.navMode === "dpad" ? "on" : ""}" aria-pressed=${this.navMode === "dpad" ? "true" : "false"} @click=${() => setMode("dpad")}>
          <ha-icon icon="mdi:gamepad-circle-outline"></ha-icon>${t("nav_dpad")}
        </button>
        <button class="seg-btn ${this.navMode === "touchpad" ? "on" : ""}" aria-pressed=${this.navMode === "touchpad" ? "true" : "false"} @click=${() => setMode("touchpad")}>
          <ha-icon icon="mdi:gesture-swipe"></ha-icon>${t("nav_touchpad")}
        </button>
      </div>
      ${this.navMode === "dpad"
        ? html`<atp-dpad
            ?disabled=${this.locked}
            ?compact=${compact}
            .labels=${{ up: t("key_up"), down: t("key_down"), left: t("key_left"), right: t("key_right"), center: t("key_center") }}
          ></atp-dpad>`
        : html`<atp-touchpad
            ?disabled=${this.locked}
            ?compact=${compact}
            .label=${t("touchpad_label")}
            .hint=${t("touchpad_hint")}
            .backLabel=${t("key_back")}
          ></atp-touchpad>`}
    </section>`;
  }

  private renderNavKeys(cls = ""): TemplateResult {
    const t = this.t;
    return html`<div class="navkeys ${cls}">
      ${this.keyButton("BACK", "mdi:arrow-u-left-top", t("key_back"))}
      ${this.keyButton("HOME", "mdi:home-outline", t("key_home"))}
      ${this.keyButton("MENU", "mdi:menu", t("key_menu"))}
      ${this.keyButton("SETTINGS", "mdi:cog-outline", t("key_settings"))}
      ${this.keyButton("SEARCH", "mdi:magnify", t("key_search"))}
      ${this.keyButton("ASSIST", "mdi:microphone-outline", t("key_assist"))}
    </div>`;
  }

  private renderVolume(): TemplateResult {
    const t = this.t;
    const target = this.volumeTarget;
    const src = target ? this.hass?.states[target] : this.entity;
    const level = volumePercent(src?.attributes.volume_level);
    const muted = !!src?.attributes.is_volume_muted;
    const canSet = !!target && !!src && ((src.attributes.supported_features ?? 0) & VOLUME_SET_FEATURE) !== 0;
    const shown = this.volDraft ?? level;
    return html`<div class="volume">
      <button
        class="key ${muted ? "muted" : ""}"
        aria-label=${muted ? t("unmute") : t("mute")}
        title=${muted ? t("unmute") : t("mute")}
        aria-pressed=${muted ? "true" : "false"}
        ?disabled=${this.locked}
        @click=${() => this.toggleMute()}
      >
        <ha-icon icon=${muted ? "mdi:volume-off" : "mdi:volume-high"}></ha-icon>
      </button>
      ${this.holdKey("VOLUME_DOWN", "mdi:minus", t("volume_down"))}
      <div class="level">
        ${canSet
          ? html`<input
              class="slider focusable"
              type="range"
              min="0"
              max="100"
              step="1"
              aria-label=${t("volume")}
              .value=${String(shown ?? 0)}
              ?disabled=${this.locked}
              style="--fill:${shown ?? 0}%"
              @input=${(e: Event) => (this.volDraft = Number((e.target as HTMLInputElement).value))}
              @change=${(e: Event) => this.setVolume(Number((e.target as HTMLInputElement).value))}
            />`
          : html`<div class="meter" role="meter" aria-label=${t("volume")} aria-valuemin="0" aria-valuemax="100" aria-valuenow=${level ?? nothing}>
              <span style="width:${level ?? 0}%"></span>
            </div>`}
        <span class="level-num" aria-hidden="true">${muted ? "—" : shown !== null ? `${shown}` : t("volume")}</span>
      </div>
      ${this.holdKey("VOLUME_UP", "mdi:plus", t("volume_up"))}
    </div>`;
  }

  private renderTransport(): TemplateResult {
    const t = this.t;
    const a = this.attrs;
    const title = a.media_title;
    return html`<div class="transport-wrap">
      ${title && this.power === "on"
        ? html`<div class="now" title=${title}>
            <ha-icon icon="mdi:music-note-eighth"></ha-icon>
            <span class="sr-only">${t("now_playing")}:</span>
            <span class="now-text">${title}${a.media_artist ? html` <span class="muted">· ${a.media_artist}</span>` : nothing}</span>
          </div>`
        : nothing}
      <div class="transport">
        ${this.keyButton("PREVIOUS", "mdi:skip-previous", t("previous"), "ghost")}
        ${this.holdKey("REWIND", "mdi:rewind", t("rewind"), "ghost")}
        ${this.keyButton("PLAY_PAUSE", this.entity?.state === "playing" ? "mdi:pause" : this.entity?.state === "paused" ? "mdi:play" : "mdi:play-pause", t("play_pause"), "accent round play")}
        ${this.holdKey("FAST_FORWARD", "mdi:fast-forward", t("fast_forward"), "ghost")}
        ${this.keyButton("NEXT", "mdi:skip-next", t("next"), "ghost")}
      </div>
    </div>`;
  }

  private renderApps(mode: "rail" | "grid"): TemplateResult {
    const t = this.t;
    let body: TemplateResult;
    if (this.appsStatus === "loading" && !this.apps) {
      body = html`<div class="tiles ${mode}" aria-busy="true" aria-label=${t("apps_loading")}>
        ${Array.from({ length: 6 }, () => html`<div class="tile skeleton" aria-hidden="true"><span class="art"></span><span class="lbl"></span></div>`)}
      </div>`;
    } else if (this.appsStatus === "error") {
      body = html`<div class="empty error" role="alert">
        <ha-icon icon="mdi:alert-circle-outline"></ha-icon>
        <span>${t("apps_error")} ${this.appsError ? html`<small>${this.appsError}</small>` : nothing}</span>
        <button class="key" @click=${() => this.loadApps()}>${t("retry")}</button>
      </div>`;
    } else if (!this.apps) {
      body = html`<div class="empty"><ha-icon icon="mdi:apps"></ha-icon><span>${t("apps_off")}</span></div>`;
    } else {
      const list = arrangeApps(this.apps, this.config.pinned_apps, this.config.hidden_apps);
      if (list.length === 0) {
        body = html`<div class="empty"><ha-icon icon="mdi:apps"></ha-icon><span>${t("apps_empty")}</span></div>`;
      } else {
        const running = this.attrs.app_id;
        body = html`<div class="tiles ${mode}" role="list">
          ${list.map((app) => {
            const on = app.package === running;
            const color = app.color || "#5f6368";
            return html`<div role="listitem" class="tile-li">
              <button
                class="tile ${on ? "running" : ""}"
                style="--brand:${color};--on-brand:${onColor(color)}"
                aria-label=${t("launch", { app: app.label }) + (on ? ` (${t("running")})` : "")}
                aria-current=${on ? "true" : "false"}
                ?disabled=${this.locked}
                @click=${() => this.launch(app)}
              >
                <span class="art">${this.appArt(app, app.label)}</span>
                <span class="lbl">${app.label}</span>
                ${on ? html`<span class="live" aria-hidden="true"></span>` : nothing}
              </button>
            </div>`;
          })}
        </div>`;
      }
    }
    return html`<section class="apps ${mode}" aria-label=${t("apps")}>
      <div class="sechead">
        <h3>${t("apps")}</h3>
        ${this.appsStatus === "loading" && this.apps ? html`<span class="spinner" aria-hidden="true"></span>` : nothing}
      </div>
      ${body}
    </section>`;
  }

  private profileName(profile: AppProfile): string {
    if (profile.id === "generic") return this.attrs.app_name || this.runningApp?.label || this.t("inapp_generic");
    return local(profile.name, this.uiLang);
  }

  private renderActionInput(action: ProfileAction): TemplateResult | typeof nothing {
    if (this.activeAction !== action.id) return nothing;
    const t = this.t;
    if (action.type === "numpad") {
      const digits: TvKey[] = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];
      return html`<div class="numpad" role="group" aria-label=${local(action.label, this.uiLang)}>
        ${digits.map((d) => this.keyButton(d, "", d, "digit"))}
        ${this.keyButton("BACK", "mdi:arrow-u-left-top", t("key_back"), "digit")}
        ${this.keyButton("0", "", "0", "digit")}
        ${this.keyButton("ENTER", "mdi:keyboard-return", t("keyboard_enter"), "digit")}
      </div>`;
    }
    if (action.type !== "text" && action.type !== "link") return nothing;
    const isUrl = action.type === "link" && action.input === "url";
    return html`<form class="action-form" @submit=${(e: Event) => this.submitAction(action, e)}>
      <input
        class="field focusable"
        type=${isUrl ? "url" : "search"}
        inputmode=${isUrl ? "url" : "search"}
        autocomplete="off"
        autocapitalize="off"
        spellcheck="false"
        enterkeyhint="go"
        aria-label=${local(action.label, this.uiLang)}
        placeholder=${local(action.placeholder, this.uiLang)}
        .value=${this.actionValue}
        @input=${(e: Event) => (this.actionValue = (e.target as HTMLInputElement).value)}
        @keydown=${(e: KeyboardEvent) => e.key === "Escape" && (this.activeAction = null)}
      />
      <button class="key accent" type="submit" ?disabled=${!this.actionValue.trim()}>${t("go")}</button>
      ${this.actionError ? html`<p class="field-error" role="alert">${this.actionError}</p>` : nothing}
    </form>`;
  }

  private renderInApp(): TemplateResult {
    const t = this.t;
    const a = this.attrs;
    const profile = profileFor(a.app_id);
    const app = this.runningApp;
    const name = this.profileName(profile);
    return html`<section class="inapp" aria-label=${t("inapp", { app: name })}>
      <div class="sechead">
        <span class="mini-art" style="--brand:${app?.color ?? "var(--atp-accent-base)"};--on-brand:${onColor(app?.color)}">
          ${a.app_id ? this.appArt(app, name) : html`<ha-icon icon="mdi:remote-tv"></ha-icon>`}
        </span>
        <h3>${profile.id === "generic" && !a.app_id ? t("inapp_generic") : t("inapp", { app: name })}</h3>
      </div>
      <div class="actions">
        ${profile.actions.map((action) => {
          const opens = action.type === "text" || action.type === "link" || action.type === "numpad";
          const label = local(action.label, this.uiLang);
          // A single repeatable key (seek, channel ±) holds with down/up like the D-pad.
          if (action.type === "keys" && !action.long && action.keys.length === 1 && REPEATABLE_KEYS.has(action.keys[0])) {
            return this.holdKey(action.keys[0], action.icon, label, "act", html`<ha-icon icon=${action.icon}></ha-icon><span>${label}</span>`);
          }
          return html`<button
            class="key act ${this.activeAction === action.id ? "pressed" : ""}"
            ?disabled=${this.locked}
            aria-expanded=${opens ? (this.activeAction === action.id ? "true" : "false") : nothing}
            @click=${() => this.runAction(action)}
          >
            <ha-icon icon=${action.icon}></ha-icon><span>${label}</span>
          </button>`;
        })}
      </div>
      ${profile.actions.map((action) => this.renderActionInput(action))}
    </section>`;
  }

  private renderKeyboard(): TemplateResult {
    const t = this.t;
    return html`<section class="kbd" aria-label=${t("keyboard")}>
      <div class="sechead"><h3>${t("keyboard")}</h3>${this.kbSent ? html`<span class="sent" role="status">${t("keyboard_sent")}</span>` : nothing}</div>
      <form class="kbd-form" @submit=${(e: Event) => this.sendText(e)}>
        <input
          class="field focusable"
          type="text"
          autocomplete="off"
          autocapitalize="off"
          spellcheck="false"
          enterkeyhint="send"
          aria-label=${t("keyboard_placeholder")}
          placeholder=${t("keyboard_placeholder")}
          ?disabled=${this.locked}
          .value=${this.kbText}
          @input=${(e: Event) => {
            this.kbText = (e.target as HTMLInputElement).value;
            this.kbError = "";
          }}
        />
        <button class="key accent" type="submit" aria-label=${this.kbEnter ? t("keyboard_send_enter") : t("keyboard_send")} ?disabled=${this.locked}>
          <ha-icon icon="mdi:send"></ha-icon>
        </button>
      </form>
      <div class="kbd-row">
        <label class="switch">
          <input type="checkbox" .checked=${this.kbEnter} @change=${(e: Event) => (this.kbEnter = (e.target as HTMLInputElement).checked)} />
          <span class="track" aria-hidden="true"><span class="thumb"></span></span>
          ${t("keyboard_send_enter")}
        </label>
        <span class="spacer"></span>
        ${this.holdKey("DELETE", "mdi:backspace-outline", t("keyboard_delete"))}
        ${this.keyButton("ENTER", "mdi:keyboard-return", t("keyboard_enter"))}
      </div>
      ${this.kbError ? html`<p class="field-error" role="alert">${this.kbError}</p>` : nothing}
    </section>`;
  }

  private renderScreenshot(): TemplateResult | typeof nothing {
    if (!this.config.show_screenshot) return nothing;
    const t = this.t;
    const paused = !this.visible || document.visibilityState !== "visible";
    return html`<section class="shot" aria-label=${t("screenshot")}>
      <button class="shot-btn focusable" aria-label="${t("screenshot")}. ${t("screenshot_refresh")}" ?disabled=${this.locked} @click=${() => this.refreshShot(true)}>
        ${this.shotUrl
          ? html`<img
              src=${this.shotUrl}
              alt=${t("screenshot")}
              @load=${() => {
                this.shotLoading = false;
                this.shotAt = Date.now();
              }}
              @error=${() => {
                this.shotLoading = false;
                this.shotError = true;
              }}
            />`
          : html`<span class="shot-empty"><ha-icon icon="mdi:monitor-screenshot"></ha-icon></span>`}
        <span class="shot-cap">
          ${this.shotLoading
            ? t("screenshot_loading")
            : this.shotError
              ? t("screenshot_error")
              : paused && this.shotUrl
                ? t("screenshot_paused")
                : t("screenshot_refresh")}
          ${this.shotAt && !this.shotLoading ? html` · ${new Date(this.shotAt).toLocaleTimeString(this.uiLang)}` : nothing}
        </span>
        ${this.shotLoading ? html`<span class="spinner on-shot" aria-hidden="true"></span>` : nothing}
      </button>
    </section>`;
  }

  private renderToasts(): TemplateResult {
    const t = this.t;
    return html`<div class="toasts" role="status" aria-live="polite">
      ${this.toasts.map(
        (toast) => html`<div class="toast">
          <ha-icon icon=${toast.wake ? "mdi:lan-disconnect" : "mdi:alert-circle-outline"}></ha-icon>
          <span class="toast-text">${toast.text}${toast.detail ? html` <small>${toast.detail}</small>` : nothing}</span>
          ${toast.wake
            ? html`<button class="toast-btn" @click=${() => {
                this.dismissToast(toast.id);
                void this.wake();
              }}>${t("wake_tv")}</button>`
            : nothing}
          <button class="toast-x" aria-label=${t("dismiss")} @click=${() => this.dismissToast(toast.id)}>
            <ha-icon icon="mdi:close"></ha-icon>
          </button>
        </div>`,
      )}
    </div>`;
  }

  private selectTab(id: SheetTab): void {
    this.haptic("selection");
    this.sheetTab = id;
  }

  /** WAI-ARIA tabs: Left/Right move and select, Home/End jump to the ends. */
  private onTabKey(e: KeyboardEvent, ids: SheetTab[]): void {
    const current = Math.max(0, ids.indexOf(this.sheetTab));
    const next =
      e.key === "ArrowRight" ? (current + 1) % ids.length
      : e.key === "ArrowLeft" ? (current - 1 + ids.length) % ids.length
      : e.key === "Home" ? 0
      : e.key === "End" ? ids.length - 1
      : -1;
    if (next < 0) return;
    e.preventDefault();
    this.selectTab(ids[next]);
    void this.updateComplete.then(() =>
      (this.renderRoot as ShadowRoot).querySelector<HTMLElement>(`#atp-tab-${ids[next]}`)?.focus(),
    );
  }

  private renderSheet(): TemplateResult {
    const t = this.t;
    const profile = profileFor(this.attrs.app_id);
    const name = this.profileName(profile);
    const tabs: [SheetTab, string, string][] = [
      ["app", this.attrs.app_id ? name : t("inapp_generic"), "mdi:gesture-tap-button"],
      ["keyboard", t("keyboard"), "mdi:keyboard-outline"],
    ];
    if (this.config.show_screenshot) tabs.push(["screen", t("screen"), "mdi:monitor-screenshot"]);
    const active: SheetTab = tabs.some(([id]) => id === this.sheetTab) ? this.sheetTab : "app";
    const toggle = () => {
      this.haptic("selection");
      this.sheetOpen = !this.sheetOpen;
    };
    return html`
      ${this.sheetOpen ? html`<div class="scrim" @click=${toggle} aria-hidden="true"></div>` : nothing}
      <div class="sheet ${this.sheetOpen ? "open" : ""}" @keydown=${(e: KeyboardEvent) => e.key === "Escape" && (this.sheetOpen = false)}>
        <button
          class="handle"
          aria-expanded=${this.sheetOpen ? "true" : "false"}
          aria-label=${this.sheetOpen ? t("inapp_close") : t("inapp_open", { app: name })}
          @click=${toggle}
        >
          <span class="grabber" aria-hidden="true"></span>
          <span class="handle-row">
            <span class="mini-art" style="--brand:${this.runningApp?.color ?? "var(--atp-accent-base)"};--on-brand:${onColor(this.runningApp?.color)}">
              ${this.attrs.app_id ? this.appArt(this.runningApp, name) : html`<ha-icon icon="mdi:remote-tv"></ha-icon>`}
            </span>
            <span class="handle-text">${this.attrs.app_id ? t("inapp", { app: name }) : t("inapp_generic")}</span>
            <ha-icon class="chev" icon="mdi:chevron-up"></ha-icon>
          </span>
        </button>
        <div class="sheet-body" ?inert=${!this.sheetOpen}>
          <div class="tabs" role="tablist" @keydown=${(e: KeyboardEvent) => this.onTabKey(e, tabs.map(([id]) => id))}>
            ${tabs.map(
              ([id, label, icon]) => html`<button
                role="tab"
                id="atp-tab-${id}"
                class="tab ${active === id ? "on" : ""}"
                aria-selected=${active === id ? "true" : "false"}
                aria-controls="atp-tabpanel"
                tabindex=${active === id ? 0 : -1}
                @click=${() => this.selectTab(id)}
              >
                <ha-icon icon=${icon}></ha-icon><span>${label}</span>
              </button>`,
            )}
          </div>
          <div class="tabpanel" role="tabpanel" id="atp-tabpanel" aria-labelledby="atp-tab-${active}">
            ${active === "app" ? this.renderInApp() : active === "keyboard" ? this.renderKeyboard() : this.renderScreenshot()}
          </div>
        </div>
      </div>
    `;
  }

  // ---- layouts --------------------------------------------------------------------------
  // Three layouts built from the same render helpers: remote first, apps first, wide.

  private remoteLayout(): TemplateResult {
    return html`<div class="body ${this.locked ? "locked" : ""}">
        ${this.renderNav()} ${this.renderNavKeys()} ${this.renderVolume()} ${this.renderTransport()} ${this.renderApps("rail")}
      </div>
      ${this.renderSheet()}`;
  }

  private appsLayout(): TemplateResult {
    return html`<div class="body ${this.locked ? "locked" : ""}">
      ${this.renderApps("grid")} ${this.renderInApp()}
      <div class="split">${this.renderNav(true)} ${this.renderNavKeys("stack")}</div>
      ${this.renderVolume()} ${this.renderTransport()}
      <details class="fold">
        <summary class="focusable"><ha-icon icon="mdi:keyboard-outline"></ha-icon>${this.t("keyboard")}</summary>
        ${this.renderKeyboard()}
      </details>
      ${this.renderScreenshot()}
    </div>`;
  }

  private wideLayout(): TemplateResult {
    return html`<div class="body cols ${this.locked ? "locked" : ""}">
      <div class="col col-apps">${this.renderApps("grid")} ${this.renderScreenshot()}</div>
      <div class="col col-pad">${this.renderNav()} ${this.renderNavKeys()} ${this.renderVolume()} ${this.renderTransport()}</div>
      <div class="col col-app">${this.renderInApp()} ${this.renderKeyboard()}</div>
    </div>`;
  }

  /**
   * Never render blank: if building the card throws, show a small error inside ha-card and log the
   * error, instead of an empty element (or, worse, an empty section).
   */
  render() {
    try {
      return this.renderCard();
    } catch (err) {
      console.error("[android-tv-pilot-card] render failed", err);
      const message = err instanceof Error ? err.message : String(err);
      return html`<ha-card>
        <div class="wrap">
          <div class="status failed render-error" role="alert">
            <ha-icon icon="mdi:alert-octagon-outline"></ha-icon>
            <div>
              <strong>${this.safeT("render_error")}</strong>
              <p>${message}</p>
            </div>
          </div>
        </div>
      </ha-card>`;
    }
  }

  private safeT(key: StringKey): string {
    try {
      return this.t(key);
    } catch {
      return translator("en")(key);
    }
  }

  private renderCard() {
    if (!this.config || !this.hass) return nothing;
    const t = this.t;
    const entity = this.entity;
    if (!entity) {
      return html`<ha-card><div class="wrap"><div class="status warn" role="alert">
        <ha-icon icon="mdi:alert"></ha-icon><div><p>${t("entity_missing", { entity: this.config.entity })}</p></div>
      </div></div></ha-card>`;
    }
    if (!entity.attributes.entry_id) {
      return html`<ha-card><div class="wrap"><div class="status warn" role="alert">
        <ha-icon icon="mdi:alert"></ha-icon><div><p>${t("entity_not_pilot", { entity: this.config.entity })}</p></div>
      </div></div></ha-card>`;
    }
    const layout = this.cardLayout;
    return html`<ha-card>
      <div class="wrap layout-${layout} ${this.sheetOpen ? "sheet-open" : ""}" lang=${this.uiLang}>
        ${this.renderHeader()} ${this.renderStatus()}
        ${layout === "apps" ? this.appsLayout() : layout === "wide" ? this.wideLayout() : this.remoteLayout()}
        ${this.renderToasts()}
      </div>
    </ha-card>`;
  }

  static styles = cardStyles;
}
