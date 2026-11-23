// Shared types for the Android TV Pilot card. The attribute and WebSocket shapes mirror the
// contract with the android_tv_pilot integration; do not rename fields here without changing it.

export type LayoutId = "a" | "b" | "c";

export interface CardConfig {
  type: string;
  entity: string;
  name?: string;
  layout?: LayoutId;
  volume_entity?: string;
  pinned_apps?: string[];
  hidden_apps?: string[];
  show_screenshot?: boolean;
  haptics?: boolean;
  /** PROTOTYPE (2026-11-23): shows the temporary A/B/C layout switch (default true). */
  prototype_switch?: boolean;
}

export type PowerState = "off" | "waking" | "on" | "asleep";
export type WakeState = "idle" | "waking" | "failed";

export interface TvAttributes {
  friendly_name?: string;
  volume_level?: number;
  is_volume_muted?: boolean;
  source?: string;
  source_list?: string[];
  media_title?: string;
  media_artist?: string;
  supported_features?: number;
  entry_id?: string;
  power_state?: PowerState;
  wake_state?: WakeState;
  wake_started_at?: string | null;
  wake_timeout?: number;
  app_id?: string | null;
  app_name?: string | null;
  app_activity?: string | null;
  adb_connected?: boolean;
  remote_connected?: boolean;
  volume_entity?: string | null;
  has_wake_button?: boolean;
  [key: string]: unknown;
}

export interface HassEntity {
  entity_id: string;
  state: string;
  attributes: TvAttributes;
  last_changed?: string;
  last_updated?: string;
}

export interface HassConnection {
  sendMessagePromise<T = unknown>(message: Record<string, unknown>): Promise<T>;
}

export interface Hass {
  states: Record<string, HassEntity>;
  locale?: { language: string };
  language?: string;
  themes?: { darkMode?: boolean };
  connection: HassConnection;
  callService(domain: string, service: string, data?: Record<string, unknown>): Promise<unknown>;
}

export interface TvApp {
  package: string;
  label: string;
  color: string | null;
  icon: string | null;
  icon_url: string | null;
  hidden: boolean;
  system: boolean;
}

export type KeyAction = "press" | "long" | "down" | "up";

export type TvKey =
  | "UP" | "DOWN" | "LEFT" | "RIGHT" | "CENTER" | "BACK" | "HOME" | "MENU" | "SETTINGS"
  | "POWER" | "WAKEUP" | "SLEEP" | "VOLUME_UP" | "VOLUME_DOWN" | "MUTE" | "PLAY" | "PAUSE"
  | "PLAY_PAUSE" | "STOP" | "NEXT" | "PREVIOUS" | "REWIND" | "FAST_FORWARD" | "CHANNEL_UP"
  | "CHANNEL_DOWN" | "INFO" | "GUIDE" | "SEARCH" | "ASSIST" | "TV" | "INPUT" | "CAPTIONS"
  | "DELETE" | "ENTER" | "TAB" | "ESCAPE"
  | "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"
  | "RED" | "GREEN" | "YELLOW" | "BLUE"
  /** Raw Android key codes are passed straight through by the integration. */
  | `KEYCODE_${string}`;

/** Error shape that HA's WebSocket layer rejects with. */
export interface WsError {
  code: string;
  message: string;
}

export type ErrorCode = "not_found" | "tv_unreachable" | "unsupported" | "failed";
