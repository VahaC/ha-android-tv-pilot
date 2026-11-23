import { css } from "lit";

/**
 * Design tokens. Surfaces and text come from the HA theme, and so does the accent: always the
 * theme's --primary-color (never an app colour). --atp-on-accent is set by the card from a contrast
 * check of --text-primary-color against the primary; --atp-accent-ink is the accent nudged towards
 * the text colour, for accent-coloured icons, text and outlines on card surfaces (keeps a light
 * primary such as yellow readable on white, and a dark one readable on a dark theme).
 */
export const tokens = css`
  :host {
    --atp-accent-base: var(--primary-color, #03a9f4);
    --atp-on-accent-base: var(--atp-on-accent, var(--text-primary-color, #fff));
    --atp-accent-ink: color-mix(in srgb, var(--atp-accent-base) 72%, var(--atp-text));
    --atp-surface: var(--ha-card-background, var(--card-background-color, #fff));
    --atp-text: var(--primary-text-color, #1c1c1c);
    --atp-muted: var(--secondary-text-color, #6b6b6b);
    --atp-line: color-mix(in srgb, var(--atp-text) 12%, transparent);
    --atp-well: color-mix(in srgb, var(--atp-text) 5%, var(--atp-surface));
    --atp-key: color-mix(in srgb, var(--atp-text) 7%, var(--atp-surface));
    --atp-key-hi: color-mix(in srgb, var(--atp-text) 11%, var(--atp-surface));
    --atp-key-shadow: color-mix(in srgb, #000 22%, transparent);
    --atp-tint: color-mix(in srgb, var(--atp-accent-base) 16%, transparent);
    --atp-glow: color-mix(in srgb, var(--atp-accent-base) 50%, transparent);
    --atp-error: var(--error-color, #db4437);
    --atp-warning: var(--warning-color, #ffa600);
    --atp-success: var(--success-color, #43a047);
    --atp-radius: 20px;
    --atp-ease: cubic-bezier(0.2, 0.8, 0.2, 1);
  }
`;

/** Tactile key cap used by every button on the remote. */
export const keycap = css`
  .key {
    -webkit-tap-highlight-color: transparent;
    -webkit-touch-callout: none;
    user-select: none;
    appearance: none;
    border: none;
    margin: 0;
    font: inherit;
    color: var(--atp-text);
    min-width: 44px;
    min-height: 44px;
    padding: 0 12px;
    border-radius: 14px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    cursor: pointer;
    background: linear-gradient(180deg, var(--atp-key-hi), var(--atp-key));
    box-shadow:
      inset 0 1px 0 color-mix(in srgb, #fff 9%, transparent),
      0 1px 0 var(--atp-line),
      0 6px 14px -10px var(--atp-key-shadow);
    transition: transform 90ms var(--atp-ease), box-shadow 120ms var(--atp-ease), background 160ms;
    touch-action: manipulation;
    position: relative;
  }
  .key ha-icon {
    --mdc-icon-size: 22px;
    pointer-events: none;
  }
  @media (hover: hover) {
    .key:hover:not([disabled]) {
      background: linear-gradient(180deg, color-mix(in srgb, var(--atp-accent-base) 10%, var(--atp-key-hi)), var(--atp-key));
    }
  }
  .key:active:not([disabled]),
  .key.pressed {
    transform: translateY(1px) scale(0.97);
    background: linear-gradient(180deg, var(--atp-tint), color-mix(in srgb, var(--atp-accent-base) 22%, var(--atp-key)));
    box-shadow: inset 0 2px 6px -2px var(--atp-key-shadow), 0 0 0 1px var(--atp-glow);
  }
  .key:focus-visible,
  .focusable:focus-visible {
    outline: 2px solid var(--atp-accent-ink);
    outline-offset: 2px;
  }
  .key[disabled] {
    cursor: default;
    opacity: 0.5;
    box-shadow: none;
  }
  .key.round {
    border-radius: 999px;
    padding: 0;
    width: 48px;
    height: 48px;
  }
  .key.accent {
    color: var(--atp-on-accent-base);
    background: linear-gradient(180deg, color-mix(in srgb, #fff 14%, var(--atp-accent-base)), var(--atp-accent-base));
    box-shadow: 0 8px 18px -10px var(--atp-glow), inset 0 1px 0 color-mix(in srgb, #fff 25%, transparent);
  }
  .key.accent:active:not([disabled]) {
    background: var(--atp-accent-base);
  }
  .key.ghost {
    background: transparent;
    box-shadow: none;
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.001ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.001ms !important;
    }
  }
`;
