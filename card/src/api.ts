// Thin wrapper around the integration's WebSocket commands. Every message carries the
// config entry id taken from the media_player's `entry_id` attribute.
import type { Hass, KeyAction, TvApp, TvKey, WsError } from "./types";

export class TvApi {
  constructor(
    private readonly getHass: () => Hass | undefined,
    private readonly entryId: string,
  ) {}

  private send<T>(type: string, payload: Record<string, unknown> = {}): Promise<T> {
    const hass = this.getHass();
    if (!hass) return Promise.reject({ code: "failed", message: "Home Assistant is not connected" } satisfies WsError);
    return hass.connection.sendMessagePromise<T>({ type: `android_tv_pilot/${type}`, entry_id: this.entryId, ...payload });
  }

  apps(): Promise<TvApp[]> {
    return this.send<{ apps: TvApp[] }>("apps").then((r) => r?.apps ?? []);
  }

  key(key: TvKey, action: KeyAction = "press"): Promise<unknown> {
    return this.send("send_key", { key, action });
  }

  text(text: string, enter: boolean): Promise<unknown> {
    return this.send("send_text", { text, enter });
  }

  launch(pkg: string): Promise<unknown> {
    return this.send("launch_app", { package: pkg });
  }

  openUrl(url: string, pkg?: string): Promise<unknown> {
    return this.send("open_url", pkg ? { url, package: pkg } : { url });
  }

  screenshotUrl(): Promise<string> {
    return this.send<{ url: string }>("screenshot_url").then((r) => r.url);
  }
}

/** Normalises whatever HA rejected with into {code, message}. */
export function toWsError(err: unknown): WsError {
  if (err && typeof err === "object") {
    const e = err as Partial<WsError> & { error?: Partial<WsError> };
    const src = e.code ? e : e.error ?? e;
    return { code: String(src.code ?? "failed"), message: String(src.message ?? "") };
  }
  return { code: "failed", message: String(err ?? "") };
}
