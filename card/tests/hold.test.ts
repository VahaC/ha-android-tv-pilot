import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HoldButton, LONG_MS, REPEATABLE_KEYS } from "../src/repeater";
import type { KeyAction, TvKey } from "../src/types";

describe("HoldButton", () => {
  let sent: string[];
  let hold: HoldButton;

  beforeEach(() => {
    vi.useFakeTimers();
    sent = [];
    hold = new HoldButton((key: TvKey, action: KeyAction) => sent.push(`${key}:${action}`));
  });
  afterEach(() => vi.useRealTimers());

  it("sends down on press and exactly one up on release, nothing in between", () => {
    hold.start("UP", "repeat");
    vi.advanceTimersByTime(2000);
    hold.release();
    hold.release();
    expect(sent).toEqual(["UP:down", "UP:up"]);
  });

  it("still sends up when the hold is cancelled", () => {
    hold.start("VOLUME_UP", "repeat");
    hold.cancel();
    hold.cancel();
    expect(sent).toEqual(["VOLUME_UP:down", "VOLUME_UP:up"]);
  });

  it("ends the previous hold before a new one starts", () => {
    hold.start("LEFT", "repeat");
    hold.start("RIGHT", "repeat");
    hold.release();
    expect(sent).toEqual(["LEFT:down", "LEFT:up", "RIGHT:down", "RIGHT:up"]);
  });

  it("long-capable keys: short hold = press, long hold = long only", () => {
    hold.start("CENTER", "long");
    vi.advanceTimersByTime(100);
    hold.release();
    hold.start("CENTER", "long");
    vi.advanceTimersByTime(LONG_MS + 10);
    hold.release();
    expect(sent).toEqual(["CENTER:press", "CENTER:long"]);
  });

  it("a cancelled long-capable hold sends nothing", () => {
    hold.start("CENTER", "long");
    hold.cancel();
    vi.advanceTimersByTime(LONG_MS * 2);
    expect(sent).toEqual([]);
  });

  it("marks the contract's repeatable keys", () => {
    for (const k of ["UP", "VOLUME_DOWN", "DELETE", "CHANNEL_UP", "REWIND", "FAST_FORWARD"]) expect(REPEATABLE_KEYS.has(k)).toBe(true);
    for (const k of ["CENTER", "BACK", "HOME", "PLAY_PAUSE"]) expect(REPEATABLE_KEYS.has(k)).toBe(false);
  });
});
