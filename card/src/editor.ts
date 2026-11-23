import { LitElement, css, html, nothing, type PropertyValues } from "lit";
import { property, state } from "lit/decorators.js";
import { TvApi } from "./api";
import { pickLanguage, translator, type StringKey } from "./i18n";
import { LAYOUTS, normalizeLayout, tidyConfig } from "./logic";
import type { CardConfig, Hass, TvApp } from "./types";

/** Values shown in the form for options left out of the YAML. */
const SHOWN_DEFAULTS: Partial<CardConfig> = { layout: "remote", show_screenshot: false, haptics: true, layout_switch: false };

/**
 * Visual editor built on HA's ha-form. The layout select is the main way to choose the card's look
 * and sits right after the entity; every change fires config-changed, so the preview updates live.
 * App pickers are filled from the TV's app list.
 */
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
      {
        name: "layout",
        required: true,
        selector: {
          select: {
            mode: "list",
            options: LAYOUTS.map((id) => ({ value: id, label: t(`layout_${id}` as StringKey) })),
          },
        },
      },
      { name: "name", selector: { text: {} } },
      { name: "volume_entity", selector: { entity: { filter: { domain: "media_player" } } } },
      { name: "pinned_apps", selector: appSelect },
      { name: "hidden_apps", selector: appSelect },
      {
        type: "grid",
        name: "",
        schema: [
          { name: "show_screenshot", selector: { boolean: {} } },
          { name: "haptics", selector: { boolean: {} } },
          { name: "layout_switch", selector: { boolean: {} } },
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
      layout_switch: "ed_layout_switch",
    };
    return map[field.name] ? this.t(map[field.name]) : field.name;
  };

  /** One-line description of the selected layout under the layout select. */
  private helper = (field: { name: string }): string | undefined => {
    if (field.name !== "layout") return undefined;
    const layout = normalizeLayout(this.config?.layout) ?? "remote";
    return this.t(`layout_${layout}_help` as StringKey);
  };

  private changed(e: CustomEvent<{ value: Record<string, unknown> }>): void {
    e.stopPropagation();
    const config = {
      type: this.config?.type ?? "custom:android-tv-pilot-card",
      ...tidyConfig(e.detail.value),
    } as CardConfig;
    this.config = config;
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
  }

  render() {
    if (!this.hass || !this.config) return nothing;
    const shown = tidyConfig(this.config as unknown as Record<string, unknown>);
    return html`<ha-form
      .hass=${this.hass}
      .data=${{ ...SHOWN_DEFAULTS, ...shown }}
      .schema=${this.schema()}
      .computeLabel=${this.label}
      .computeHelper=${this.helper}
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
