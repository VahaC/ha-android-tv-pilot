import { LitElement, css, html, nothing } from "lit";
import { property, state } from "lit/decorators.js";
import { HoldButton, holdHandlers } from "./repeater";
import { keycap, tokens } from "./styles";
import type { KeyAction, TvKey } from "./types";

export interface KeyEventDetail {
  key: TvKey;
  action: KeyAction;
  repeat?: boolean;
  /** Set by the receiver for client-side repeats: called with the send promise (backpressure). */
  ack?: (sent: Promise<unknown>) => void;
}

export interface PadLabels {
  up: string;
  down: string;
  left: string;
  right: string;
  center: string;
}

type Dir = "UP" | "DOWN" | "LEFT" | "RIGHT";
const ARROW_KEYS: Record<string, TvKey> = { ArrowUp: "UP", ArrowDown: "DOWN", ArrowLeft: "LEFT", ArrowRight: "RIGHT" };
const ANGLE: Record<Dir, number> = { UP: 0, RIGHT: 90, DOWN: 180, LEFT: 270 };

export function emitKey(el: HTMLElement, detail: KeyEventDetail): void {
  el.dispatchEvent(new CustomEvent<KeyEventDetail>("atp-key", { detail, bubbles: true, composed: true }));
}

/** Circular D-pad: four wedge buttons around an OK button, with hold-to-repeat and long OK. */
export class AtpDpad extends LitElement {
  @property({ type: Boolean }) disabled = false;
  @property({ type: Boolean, reflect: true }) compact = false;
  @property({ attribute: false }) labels: PadLabels = { up: "Up", down: "Down", left: "Left", right: "Right", center: "OK" };

  @state() private pressed: TvKey | null = null;
  @state() private charging = false;

  private chargeTimer: ReturnType<typeof setTimeout> | null = null;
  private hold = new HoldButton(
    (key, action) => emitKey(this, { key, action }),
    (key) => {
      this.pressed = key;
      if (this.chargeTimer) clearTimeout(this.chargeTimer);
      this.chargeTimer = null;
      this.charging = false;
      if (key === "CENTER") this.chargeTimer = setTimeout(() => (this.charging = true), 150);
    },
  );

  disconnectedCallback(): void {
    super.disconnectedCallback();
    this.hold.cancel();
  }

  protected updated(changed: Map<string, unknown>): void {
    if (changed.has("disabled") && this.disabled) this.hold.cancel();
  }

  /** Arrow keys on any focused pad button hold that direction until keyup. */
  private onArrowDown(e: KeyboardEvent): void {
    const arrow = ARROW_KEYS[e.key];
    if (!arrow || this.disabled) return;
    e.preventDefault();
    if (!e.repeat) this.hold.start(arrow, "repeat");
  }

  private onArrowUp(e: KeyboardEvent): void {
    const arrow = ARROW_KEYS[e.key];
    if (arrow && this.hold.heldKey === arrow) this.hold.release();
  }

  private button(key: TvKey, cls: string, label: string, content: unknown) {
    const h = holdHandlers(this.hold, key, key === "CENTER" ? "long" : "repeat", () => this.disabled);
    return html`<button
      class="${cls} ${this.pressed === key ? "pressed" : ""}"
      aria-label=${label}
      ?disabled=${this.disabled}
      @pointerdown=${h.pointerdown}
      @pointerup=${h.pointerup}
      @pointercancel=${h.pointercancel}
      @lostpointercapture=${h.lostpointercapture}
      @keydown=${(e: KeyboardEvent) => (ARROW_KEYS[e.key] ? this.onArrowDown(e) : h.keydown(e))}
      @keyup=${(e: KeyboardEvent) => (ARROW_KEYS[e.key] ? this.onArrowUp(e) : h.keyup(e))}
      @blur=${h.blur}
      @contextmenu=${h.contextmenu}
    >
      ${content}
    </button>`;
  }

  private wedge(dir: Dir, label: string) {
    const icon = { UP: "mdi:chevron-up", DOWN: "mdi:chevron-down", LEFT: "mdi:chevron-left", RIGHT: "mdi:chevron-right" }[dir];
    return this.button(dir, `wedge ${dir.toLowerCase()}`, label, html`<ha-icon icon=${icon}></ha-icon>`);
  }
  render() {
    const dir = this.pressed && this.pressed !== "CENTER" ? (this.pressed as Dir) : null;
    return html`
      <div class="pad ${this.disabled ? "off" : ""}" style=${dir ? `--glow-angle:${ANGLE[dir]}deg` : ""}>
        <div class="ring" aria-hidden="true"></div>
        <div class="glow ${dir ? "on" : ""}" aria-hidden="true"></div>
        ${this.wedge("UP", this.labels.up)} ${this.wedge("RIGHT", this.labels.right)}
        ${this.wedge("DOWN", this.labels.down)} ${this.wedge("LEFT", this.labels.left)}
        ${this.button(
          "CENTER",
          `center ${this.charging ? "charging" : ""}`,
          this.labels.center,
          html`<span class="ok">OK</span>
            ${this.charging
              ? html`<svg class="charge" viewBox="0 0 100 100" aria-hidden="true">
                  <circle cx="50" cy="50" r="48" pathLength="100"></circle>
                </svg>`
              : nothing}`,
        )}
      </div>
    `;
  }

  static styles = [
    tokens,
    keycap,
    css`
      :host {
        display: block;
        --pad-size: min(100%, 260px);
      }
      :host([compact]) {
        --pad-size: min(100%, 188px);
      }
      .pad {
        position: relative;
        width: var(--pad-size);
        aspect-ratio: 1;
        margin: 0 auto;
        touch-action: none;
        user-select: none;
        -webkit-user-select: none;
        -webkit-touch-callout: none;
      }
      .ring {
        position: absolute;
        inset: 0;
        border-radius: 50%;
        background:
          radial-gradient(circle at 50% 30%, color-mix(in srgb, #fff 7%, transparent), transparent 60%),
          linear-gradient(180deg, var(--atp-key-hi), var(--atp-key));
        box-shadow:
          inset 0 1px 0 color-mix(in srgb, #fff 10%, transparent),
          inset 0 -10px 24px -14px var(--atp-key-shadow),
          0 1px 0 var(--atp-line),
          0 18px 40px -24px var(--atp-key-shadow);
      }
      .ring::after {
        content: "";
        position: absolute;
        inset: 0;
        border-radius: 50%;
        background: repeating-conic-gradient(from 44.5deg, var(--atp-line) 0 1deg, transparent 1deg 90deg);
        -webkit-mask: radial-gradient(circle, transparent 33%, #000 34%, #000 92%, transparent 93%);
        mask: radial-gradient(circle, transparent 33%, #000 34%, #000 92%, transparent 93%);
      }
      .glow {
        position: absolute;
        inset: -4px;
        border-radius: 50%;
        pointer-events: none;
        opacity: 0;
        background: conic-gradient(
          from calc(var(--glow-angle, 0deg) - 45deg),
          var(--atp-glow) 0deg,
          var(--atp-accent-base) 45deg,
          var(--atp-glow) 90deg,
          transparent 90deg
        );
        -webkit-mask: radial-gradient(circle, transparent 60%, #000 62%, #000 70%, transparent 71%);
        mask: radial-gradient(circle, transparent 60%, #000 62%, #000 70%, transparent 71%);
        transition: opacity 140ms var(--atp-ease);
        filter: blur(0.5px);
      }
      .glow.on {
        opacity: 1;
      }
      .wedge {
        all: unset;
        position: absolute;
        inset: 0;
        display: flex;
        cursor: pointer;
        color: var(--atp-muted);
        -webkit-tap-highlight-color: transparent;
        transition: background 120ms, color 120ms;
        border-radius: 50%;
      }
      .wedge ha-icon {
        --mdc-icon-size: 30px;
        pointer-events: none;
      }
      .wedge.up {
        clip-path: polygon(0 0, 100% 0, 50% 50%);
        justify-content: center;
        align-items: flex-start;
        padding-top: 7%;
      }
      .wedge.down {
        clip-path: polygon(0 100%, 100% 100%, 50% 50%);
        justify-content: center;
        align-items: flex-end;
        padding-bottom: 7%;
      }
      .wedge.left {
        clip-path: polygon(0 0, 0 100%, 50% 50%);
        align-items: center;
        justify-content: flex-start;
        padding-left: 7%;
      }
      .wedge.right {
        clip-path: polygon(100% 0, 100% 100%, 50% 50%);
        align-items: center;
        justify-content: flex-end;
        padding-right: 7%;
      }
      .wedge.pressed {
        color: var(--atp-accent-base);
        background: radial-gradient(circle, transparent 34%, var(--atp-tint) 35%, transparent 92%);
      }
      @media (hover: hover) {
        .wedge:hover:not([disabled]) {
          color: var(--atp-text);
        }
      }
      .wedge:focus-visible {
        color: var(--atp-accent-base);
        background: radial-gradient(circle, transparent 34%, var(--atp-tint) 35%, transparent 92%);
      }
      .wedge[disabled] {
        cursor: default;
      }
      .center {
        all: unset;
        position: absolute;
        left: 50%;
        top: 50%;
        width: 40%;
        aspect-ratio: 1;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        display: grid;
        place-items: center;
        cursor: pointer;
        color: var(--atp-on-accent-base);
        font-weight: 700;
        letter-spacing: 0.08em;
        font-size: clamp(14px, 4cqi, 18px);
        -webkit-tap-highlight-color: transparent;
        background:
          radial-gradient(circle at 50% 28%, color-mix(in srgb, #fff 30%, transparent), transparent 55%),
          var(--atp-accent-base);
        box-shadow:
          0 0 0 6px var(--atp-surface),
          0 0 0 7px var(--atp-line),
          0 14px 26px -12px var(--atp-glow),
          inset 0 -6px 14px -6px color-mix(in srgb, #000 35%, transparent);
        transition: transform 90ms var(--atp-ease), box-shadow 140ms;
      }
      .center.pressed {
        transform: translate(-50%, -50%) scale(0.95);
        box-shadow:
          0 0 0 6px var(--atp-surface),
          0 0 0 7px var(--atp-accent-base),
          0 0 26px 2px var(--atp-glow),
          inset 0 3px 10px -2px color-mix(in srgb, #000 35%, transparent);
      }
      .center:focus-visible {
        outline: 3px solid var(--atp-accent-base);
        outline-offset: 9px;
      }
      .center[disabled] {
        cursor: default;
        filter: grayscale(0.7);
      }
      .ok {
        pointer-events: none;
      }
      .charge {
        position: absolute;
        inset: -10px;
        width: calc(100% + 20px);
        height: calc(100% + 20px);
        pointer-events: none;
        transform: rotate(-90deg);
        overflow: visible;
      }
      .charge circle {
        fill: none;
        stroke: var(--atp-accent-base);
        stroke-width: 4;
        stroke-linecap: round;
        stroke-dasharray: 100;
        stroke-dashoffset: 100;
        animation: charge 400ms linear forwards;
      }
      @keyframes charge {
        to {
          stroke-dashoffset: 0;
        }
      }
      .pad.off {
        opacity: 0.55;
        filter: grayscale(0.6);
      }
    `,
  ];
}

if (!customElements.get("atp-dpad")) customElements.define("atp-dpad", AtpDpad);
