// Entry point: registers the card, its editor and the card-picker entry.
import { AndroidTvPilotCard, setCardVersion } from "./card";
import "./editor";
import { translator } from "./i18n";
import type { CardConfig, Hass } from "./types";

export const CARD_TAG = "android-tv-pilot-card";
export const CARD_VERSION = "0.1.2";
// The card compares this with the integration's `integration_version` attribute.
setCardVersion(CARD_VERSION);

class RegisteredCard extends AndroidTvPilotCard {
  static getConfigElement(): HTMLElement {
    return document.createElement("android-tv-pilot-card-editor");
  }

  /** Picks the first media_player that exposes the integration's attributes. */
  static getStubConfig(hass: Hass): Partial<CardConfig> {
    const match = Object.values(hass?.states ?? {}).find(
      (s) => s.entity_id.startsWith("media_player.") && "entry_id" in s.attributes && "power_state" in s.attributes,
    );
    return { entity: match?.entity_id ?? "" };
  }
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, RegisteredCard);
}

declare global {
  interface Window {
    customCards?: Array<Record<string, unknown>>;
  }
}

const t = translator("en");
window.customCards = window.customCards ?? [];
if (!window.customCards.some((c) => c.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: t("card_name"),
    description: t("card_description"),
    preview: true,
  });
}

console.info(`%c ANDROID-TV-PILOT-CARD %c ${CARD_VERSION} `, "color:#fff;background:#3d5afe;font-weight:700", "color:#3d5afe");
