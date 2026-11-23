import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import { property, state } from "lit/decorators.js";
import { TvApi } from "./api";
import { pickLanguage, translator, type StringKey } from "./i18n";
import type { CardConfig, Hass, TvApp } from "./types";

// PROTOTYPE (2026-11-23): prototype_switch default.
const DEFAULTS: Partial<CardConfig> = { layout: "a", show_screenshot: false, haptics: true, prototype_switch: true };

/** Visual editor built on HA's ha-form; app pickers are filled from the TV's app list. */
export class AndroidTvPilotCardEditor extends LitElement {
  @property({ attribute: false }) hass?: Hass;
  @state() private config?: CardConfig;
  @state() private apps: TvApp[] = [];
  private appsFor: string | null = null;

  setConfig(config: CardConfig): void {
    this.config = config;
  }

  protected willUpdate(changed: PropertyValues): void {
    if (!this.hass || !this.config?.entity) return;
    if (!changed.has("hass") && !changed.has("config")) return;
    const entryId = this.hass.states[this.config.entity]?.attributes.entry_id;
    if (entryId && entryId !== this.appsFor) {
      this.appsFor = entryId;
      new TvApi(() => this.hass, entryId)
        .apps()
        .then((apps) => (this.apps = apps))
        .catch(() => (this.apps = []));
    }
  }

  private get t() {
    return translator(pickLanguage(this.hass?.locale?.language ?? this.hass?.language));
  }

  private schema() {
    const t = this.t;
    const appOptions = this.apps
      .slice()
      .sort((a, b) => a.label.localeCompare(b.label))
      .map((a) => ({ value: a.package, label: `${a.label} — ${a.package}` }));
    const appSelect = { select: { multiple: true, custom_value: true, mode: "dropdown", options: appOptions } };
    return [
      { name: "entity", required: true, selector: { entity: { filter: { domain: "media_player", integration: "android_tv_pilot" } } } },
      { name: "name", selector: { text: {} } },
      {
        name: "layout",
        selector: {
          select: {
            mode: "dropdown",
            options: [
              { value: "a", label: t("ed_layout_a") },
              { value: "b", label: t("ed_layout_b") },
              { value: "c", label: t("ed_layout_c") },
            ],
          },
        },
      },
      { name: "volume_entity", selector: { entity: { filter: { domain: "media_player" } } } },
      { name: "pinned_apps", selector: appSelect },
      { name: "hidden_apps", selector: appSelect },
      {
        type: "grid",
        name: "",
        schema: [
          { name: "show_screenshot", selector: { boolean: {} } },
          { name: "haptics", selector: { boolean: {} } },
          // PROTOTYPE (2026-11-23)
          { name: "prototype_switch", selector: { boolean: {} } },
        ],
      },
    ];
  }

  private label = (field: { name: string }): string => {
    const map: Record<string, StringKey> = {
      entity: "ed_entity",
      name: "ed_name",
      layout: "ed_layout",
      volume_entity: "ed_volume_entity",
      pinned_apps: "ed_pinned",
      hidden_apps: "ed_hidden",
      show_screenshot: "ed_screenshot",
      haptics: "ed_haptics",
      // PROTOTYPE (2026-11-23)
      prototype_switch: "ed_proto",
    };
    return map[field.name] ? this.t(map[field.name]) : field.name;
  };

  private changed(e: CustomEvent<{ value: Record<string, unknown> }>): void {
    e.stopPropagation();
    const value = { ...e.detail.value };
    for (const [k, v] of Object.entries(value)) {
      const empty = v === "" || v === undefined || v === null || (Array.isArray(v) && v.length === 0);
      if (empty || (k in DEFAULTS && DEFAULTS[k as keyof CardConfig] === v)) delete value[k];
    }
    const config = { type: this.config?.type ?? "custom:android-tv-pilot-card", ...value } as CardConfig;
    this.config = config;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }

  render() {
    if (!this.hass || !this.config) return nothing;
    return html`<ha-form
      .hass=${this.hass}
      .data=${{ ...DEFAULTS, ...this.config }}
      .schema=${this.schema()}
      .computeLabel=${this.label}
      @value-changed=${this.changed}
    ></ha-form>`;
  }

  static styles = css`
    :host {
      display: block;
    }
  `;
}

if (!customElements.get("android-tv-pilot-card-editor")) {
  customElements.define("android-tv-pilot-card-editor", AndroidTvPilotCardEditor);
}
