import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import { emitKey } from "./dpad";
import { detectSwipe, type Direction } from "./logic";
import { HoldButton } from "./repeater";
import { keycap, tokens } from "./styles";

const STEP_PX = 30;
const LONG_MS = 550;
const TAP_MAX_MS = 450;
const HOLD_REPEAT_DELAY = 500;
const HOLD_REPEAT_EVERY = 150;

const ARROW: Record<Direction, string> = {
  UP: "mdi:chevron-up",
  DOWN: "mdi:chevron-down",
  LEFT: "mdi:chevron-left",
  RIGHT: "mdi:chevron-right",
};

interface Ripple {
  id: number;
  x: number;
  y: number;
  kind: "tap" | "long" | "back";
}

/**
 * Trackpad-style navigation: every STEP_PX of drag sends one direction (so a long drag scrolls),
 * resting the finger after a swipe keeps repeating, tap = OK, hold = long OK, two-finger tap or
 * the corner button = BACK.
 */
export class AtpTouchpad extends LitElement {
  @property({ type: Boolean }) disabled = false;
  @property({ type: Boolean, reflect: true }) compact = false;
  @property() label = "Touchpad";
  @property() hint = "";
  @property() backLabel = "Back";

  @state() private flash: Direction | null = null;
  @state() private ripples: Ripple[] = [];
  @state() private active = false;

  private pointers = new Map<number, { x: number; y: number }>();
  private primary: number | null = null;
  private anchor = { x: 0, y: 0 };
  private startedAt = 0;
  private moved = false;
  private longFired = false;
  private multi = false;
  private lastDir: Direction | null = null;
  private longTimer: ReturnType<typeof setTimeout> | null = null;
  private restTimer: ReturnType<typeof setTimeout> | null = null;
  private repeatTimer: ReturnType<typeof setInterval> | null = null;
  private flashTimer: ReturnType<typeof setTimeout> | null = null;
  private rippleId = 0;
  private inFlight = false;
  private keyHold = new HoldButton((key, action) => emitKey(this, { key, action }));

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.reset();
    this.keyHold.cancel();
  }

  protected updated(changed: Map<string, unknown>): void {
    if (changed.has("disabled") && this.disabled) {
      this.reset();
      this.keyHold.cancel();
    }
  }

  private clearTimers(): void {
    if (this.longTimer) clearTimeout(this.longTimer);
    if (this.restTimer) clearTimeout(this.restTimer);
    if (this.repeatTimer) clearInterval(this.repeatTimer);
    this.longTimer = this.restTimer = this.repeatTimer = null;
  }

  private reset(): void {
    this.clearTimers();
    this.pointers.clear();
    this.primary = null;
    this.multi = false;
    this.active = false;
  }

  private local(e: PointerEvent): { x: number; y: number } {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }

  private ripple(x: number, y: number, kind: Ripple["kind"]): void {
    const id = ++this.rippleId;
    this.ripples = [...this.ripples.slice(-3), { id, x, y, kind }];
    setTimeout(() => (this.ripples = this.ripples.filter((r) => r.id !== id)), 600);
  }

  private showFlash(dir: Direction): void {
    this.flash = dir;
    if (this.flashTimer) clearTimeout(this.flashTimer);
    this.flashTimer = setTimeout(() => (this.flash = null), 260);
  }

  /**
   * Drag steps are client-side presses. A step is dropped (not queued) while the previous send is
   * still in flight, so a slow ADB link never builds a backlog that keeps moving after release.
   */
  private send(dir: Direction, repeat: boolean): void {
    if (this.inFlight) return;
    emitKey(this, {
      key: dir,
      action: "press",
      repeat,
      ack: (sent) => {
        this.inFlight = true;
        const guard = setTimeout(() => (this.inFlight = false), 3000);
        sent.finally(() => {
          clearTimeout(guard);
          this.inFlight = false;
        });
      },
    });
    this.showFlash(dir);
  }

  private onDown(e: PointerEvent): void {
    if (this.disabled) return;
    e.preventDefault();
    try {
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    } catch {
      /* pointer already gone (or synthetic); the hold still ends on pointerup */
    }
    const p = this.local(e);
    this.pointers.set(e.pointerId, p);
    if (this.pointers.size === 1) {
      this.primary = e.pointerId;
      this.anchor = p;
      this.startedAt = performance.now();
      this.moved = false;
      this.longFired = false;
      this.multi = false;
      this.active = true;
      this.longTimer = setTimeout(() => {
        if (this.moved || this.multi) return;
        this.longFired = true;
        emitKey(this, { key: "CENTER", action: "long" });
        this.ripple(p.x, p.y, "long");
      }, LONG_MS);
    } else {
      this.multi = true;
      this.clearTimers();
    }
  }

  private onMove(e: PointerEvent): void {
    if (this.disabled || e.pointerId !== this.primary || this.multi || this.longFired) return;
    const p = this.local(e);
    this.pointers.set(e.pointerId, p);
    const dir = detectSwipe(p.x - this.anchor.x, p.y - this.anchor.y, STEP_PX);
    if (!dir) return;
    this.moved = true;
    this.anchor = p;
    this.lastDir = dir;
    this.clearTimers();
    this.send(dir, false);
    // Finger resting after a swipe keeps the direction going (long lists).
    this.restTimer = setTimeout(() => {
      this.repeatTimer = setInterval(() => this.lastDir && this.send(this.lastDir, true), HOLD_REPEAT_EVERY);
    }, HOLD_REPEAT_DELAY);
  }

  private onUp(e: PointerEvent, cancelled = false): void {
    if (!this.pointers.has(e.pointerId)) return;
    const p = this.pointers.get(e.pointerId)!;
    this.pointers.delete(e.pointerId);
    if (this.pointers.size > 0) return;
    const quick = performance.now() - this.startedAt < TAP_MAX_MS;
    const wasMulti = this.multi;
    const { moved, longFired } = this;
    this.reset();
    if (cancelled || this.disabled) return;
    if (wasMulti) {
      if (!moved && quick) {
        emitKey(this, { key: "BACK", action: "press" });
        this.ripple(p.x, p.y, "back");
      }
      return;
    }
    if (!moved && !longFired) {
      emitKey(this, { key: "CENTER", action: "press" });
      this.ripple(p.x, p.y, "tap");
    }
  }

  private onKeydown(e: KeyboardEvent): void {
    if (this.disabled) return;
    const map: Record<string, Direction> = { ArrowUp: "UP", ArrowDown: "DOWN", ArrowLeft: "LEFT", ArrowRight: "RIGHT" };
    if (map[e.key]) {
      e.preventDefault();
      if (!e.repeat) this.keyHold.start(map[e.key], "repeat");
      this.showFlash(map[e.key]);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      emitKey(this, { key: "CENTER", action: "press" });
    } else if (e.key === "Backspace" || e.key === "Escape") {
      e.preventDefault();
      emitKey(this, { key: "BACK", action: "press" });
    }
  }

  render() {
    return html`
      <div class="wrap ${this.disabled ? "off" : ""}">
        <div
          class="surface focusable ${this.active ? "active" : ""}"
          role="application"
          tabindex=${this.disabled ? -1 : 0}
          aria-label=${this.label}
          aria-disabled=${this.disabled ? "true" : "false"}
          @pointerdown=${this.onDown}
          @pointermove=${this.onMove}
          @pointerup=${(e: PointerEvent) => this.onUp(e)}
          @pointercancel=${(e: PointerEvent) => this.onUp(e, true)}
          @keydown=${this.onKeydown}
          @keyup=${(e: KeyboardEvent) => e.key.startsWith("Arrow") && this.keyHold.release()}
          @blur=${() => this.keyHold.cancel()}
          @contextmenu=${(e: Event) => e.preventDefault()}
        >
          ${this.ripples.map(
            (r) => html`<span class="ripple ${r.kind}" style="left:${r.x}px;top:${r.y}px" aria-hidden="true"></span>`,
          )}
          ${this.flash
            ? html`<span class="flash ${this.flash.toLowerCase()}" aria-hidden="true">
                <ha-icon icon=${ARROW[this.flash]}></ha-icon>
              </span>`
            : nothing}
          ${this.hint ? html`<span class="hint" aria-hidden="true">${this.hint}</span>` : nothing}
        </div>
        <button
          class="key back"
          aria-label=${this.backLabel}
          ?disabled=${this.disabled}
          @click=${() => emitKey(this, { key: "BACK", action: "press" })}
        >
          <ha-icon icon="mdi:arrow-u-left-top"></ha-icon>
        </button>
      </div>
    `;
  }

  static styles = [
    tokens,
    keycap,
    css`
      :host {
        display: block;
      }
      .wrap {
        position: relative;
      }
      .surface {
        position: relative;
        height: 236px;
        border-radius: var(--atp-radius);
        overflow: hidden;
        touch-action: none;
        user-select: none;
        -webkit-user-select: none;
        -webkit-touch-callout: none;
        cursor: grab;
        background:
          radial-gradient(circle, var(--atp-line) 1px, transparent 1.5px) 0 0 / 18px 18px,
          radial-gradient(120% 90% at 50% 0%, color-mix(in srgb, var(--atp-accent-base) 9%, transparent), transparent 70%),
          var(--atp-well);
        box-shadow:
          inset 0 2px 10px -4px var(--atp-key-shadow),
          inset 0 0 0 1px var(--atp-line);
        transition: box-shadow 160ms;
      }
      :host([compact]) .surface {
        height: 180px;
      }
      .surface.active {
        cursor: grabbing;
        box-shadow:
          inset 0 2px 10px -4px var(--atp-key-shadow),
          inset 0 0 0 2px var(--atp-glow);
      }
      .hint {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 10px;
        text-align: center;
        font-size: 11px;
        letter-spacing: 0.02em;
        color: var(--atp-muted);
        pointer-events: none;
        padding: 0 56px;
      }
      .ripple {
        position: absolute;
        width: 64px;
        height: 64px;
        margin: -32px 0 0 -32px;
        border-radius: 50%;
        pointer-events: none;
        background: radial-gradient(circle, var(--atp-glow), transparent 70%);
        animation: ripple 520ms var(--atp-ease) forwards;
      }
      .ripple.long {
        box-shadow: 0 0 0 3px var(--atp-accent-base);
      }
      .ripple.back {
        background: radial-gradient(circle, color-mix(in srgb, var(--atp-text) 25%, transparent), transparent 70%);
      }
      @keyframes ripple {
        from {
          transform: scale(0.4);
          opacity: 1;
        }
        to {
          transform: scale(1.6);
          opacity: 0;
        }
      }
      .flash {
        position: absolute;
        display: grid;
        place-items: center;
        width: 56px;
        height: 56px;
        border-radius: 50%;
        color: var(--atp-on-accent-base);
        background: var(--atp-accent-base);
        box-shadow: 0 10px 24px -10px var(--atp-glow);
        pointer-events: none;
        animation: flash 260ms var(--atp-ease) forwards;
      }
      .flash ha-icon {
        --mdc-icon-size: 32px;
      }
      .flash.up {
        top: 12px;
        left: calc(50% - 28px);
      }
      .flash.down {
        bottom: 26px;
        left: calc(50% - 28px);
      }
      .flash.left {
        left: 12px;
        top: calc(50% - 28px);
      }
      .flash.right {
        right: 12px;
        top: calc(50% - 28px);
      }
      @keyframes flash {
        from {
          opacity: 0.95;
          transform: scale(0.8);
        }
        to {
          opacity: 0;
          transform: scale(1.1);
        }
      }
      .back {
        position: absolute;
        top: 8px;
        left: 8px;
        border-radius: 12px;
      }
      .off {
        opacity: 0.55;
        filter: grayscale(0.6);
      }
      .off .surface {
        cursor: default;
      }
    `,
  ];
}

if (!customElements.get("atp-touchpad")) customElements.define("atp-touchpad", AtpTouchpad);
