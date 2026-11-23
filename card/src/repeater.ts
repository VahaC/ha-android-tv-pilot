// Press-and-hold for remote keys, shared by the D-pad, the touchpad's keyboard arrows and every
// hold button on the card (volume, seek, delete, channel).
//
// Repeatable keys use the contract's `down` / `up`: `down` on press, `up` on release, and the
// integration repeats on the TV side (it awaits each press, so nothing queues up). This class makes
// sure exactly one `up` follows every `down`: on pointer up/cancel, lost capture, focus loss, the
// page being hidden, the window losing focus, and when the owner cancels (disabled, disconnected).
//
// Keys that are not repeatable but have a long press (OK) send `press` on a short release and
// `long` once the hold passes LONG_MS.

import type { KeyAction, TvKey } from "./types";

export const LONG_MS = 550;

export type HoldSend = (key: TvKey, action: KeyAction) => void;
export type HoldMode = "repeat" | "long";

export class HoldButton {
  private key: TvKey | null = null;
  private mode: HoldMode | null = null;
  private longTimer: ReturnType<typeof setTimeout> | null = null;
  private longFired = false;
  private listening = false;
  private readonly onHidden = () => {
    if (document.visibilityState !== "visible") this.cancel();
  };
  private readonly onBlur = () => this.cancel();

  /**
   * @param send   delivers the key action
   * @param change optional callback for visual state (held key, long-press "charging" start)
   */
  constructor(
    private readonly send: HoldSend,
    private readonly change?: (key: TvKey | null) => void,
  ) {}

  get heldKey(): TvKey | null {
    return this.key;
  }

  /** Starts a hold. A second start without a release first ends the previous hold cleanly. */
  start(key: TvKey, mode: HoldMode): void {
    if (this.key) this.cancel();
    this.key = key;
    this.mode = mode;
    this.longFired = false;
    this.listen(true);
    this.change?.(key);
    if (mode === "repeat") {
      this.send(key, "down");
    } else {
      this.longTimer = setTimeout(() => {
        this.longTimer = null;
        this.longFired = true;
        this.send(key, "long");
      }, LONG_MS);
    }
  }

  /** Normal release: `up` for a repeat hold, `press` for a short long-capable hold. */
  release(): void {
    const { key, mode, longFired } = this;
    if (!key) return;
    this.clear();
    if (mode === "repeat") this.send(key, "up");
    else if (!longFired) this.send(key, "press");
  }

  /** Aborted hold: still sends `up` for a repeat hold (never leave a key down), nothing else. */
  cancel(): void {
    const { key, mode } = this;
    if (!key) return;
    this.clear();
    if (mode === "repeat") this.send(key, "up");
  }

  private clear(): void {
    if (this.longTimer) clearTimeout(this.longTimer);
    this.longTimer = null;
    this.key = null;
    this.mode = null;
    this.listen(false);
    this.change?.(null);
  }

  private listen(on: boolean): void {
    if (on === this.listening || typeof window === "undefined") return;
    this.listening = on;
    const method = on ? "addEventListener" : "removeEventListener";
    document[method]("visibilitychange", this.onHidden);
    window[method]("blur", this.onBlur);
  }
}

export interface HoldHandlers {
  pointerdown: (e: PointerEvent) => void;
  pointerup: () => void;
  pointercancel: () => void;
  lostpointercapture: () => void;
  keydown: (e: KeyboardEvent) => void;
  keyup: (e: KeyboardEvent) => void;
  blur: () => void;
  contextmenu: (e: Event) => void;
}

/**
 * Event handlers that bind one button to a HoldButton. Pointer capture keeps the hold alive while
 * the finger slides off the button; Enter/Space hold works the same from the keyboard.
 */
export function holdHandlers(hold: HoldButton, key: TvKey, mode: HoldMode, isDisabled: () => boolean): HoldHandlers {
  const mine = () => hold.heldKey === key;
  return {
    pointerdown: (e) => {
      if (isDisabled() || e.button > 0) return;
      e.preventDefault();
      try {
        (e.currentTarget as Element).setPointerCapture(e.pointerId);
      } catch {
        /* synthetic or already-gone pointer: pointerup still ends the hold */
      }
      hold.start(key, mode);
    },
    pointerup: () => mine() && hold.release(),
    pointercancel: () => mine() && hold.cancel(),
    lostpointercapture: () => mine() && hold.release(),
    keydown: (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      if (!e.repeat && !isDisabled()) hold.start(key, mode);
    },
    keyup: (e) => {
      if ((e.key === "Enter" || e.key === " ") && mine()) hold.release();
    },
    blur: () => mine() && hold.cancel(),
    contextmenu: (e) => e.preventDefault(),
  };
}

/** Keys the integration repeats server-side while held (sent as down/up). */
export const REPEATABLE_KEYS: ReadonlySet<string> = new Set([
  "UP", "DOWN", "LEFT", "RIGHT", "VOLUME_UP", "VOLUME_DOWN", "DELETE",
  "CHANNEL_UP", "CHANNEL_DOWN", "REWIND", "FAST_FORWARD",
]);
