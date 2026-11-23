import { css } from "lit";
import { keycap, tokens } from "./styles";

export const cardStyles = [
  tokens,
  keycap,
  css`
    :host {
      display: block;
      /* Fills a panel view; resolves to auto in masonry columns and section cells. */
      height: 100%;
    }
    /* ha-card is the size container (inline-size only, never size: no definite height needed),
       so rules can also adjust .wrap itself on narrow cards. */
    ha-card {
      container-type: inline-size;
      container-name: atp;
      overflow: hidden;
      position: relative;
      height: 100%;
      background:
        radial-gradient(140% 60% at 50% -10%, color-mix(in srgb, var(--atp-accent-base) 13%, transparent), transparent 60%),
        var(--atp-surface);
      transition: background 400ms;
    }
    .wrap {
      position: relative;
      padding: 14px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      color: var(--atp-text);
      min-height: 100%;
      box-sizing: border-box;
    }
    .wrap.layout-remote {
      padding-bottom: 78px;
    }
    h3 {
      margin: 0;
      font-size: 13px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--atp-muted);
    }
    .sechead {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 24px;
      margin-bottom: 8px;
    }
    .muted {
      color: var(--atp-muted);
    }
    .txt {
      font-size: 18px;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
    }

    /* ---- layout button + menu (layout_switch: true) ------------------------------------ */
    /* The menu is anchored to the whole header (not the button) so it never leaves the card. */
    .layout-wrap {
      position: static;
      flex: none;
    }
    .key.layout-btn {
      width: 44px;
      height: 44px;
      color: var(--atp-muted);
      --mdc-icon-size: 22px;
    }
    .key.layout-btn.overridden::after {
      content: "";
      position: absolute;
      top: 6px;
      right: 6px;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--atp-accent-base);
      box-shadow: 0 0 0 2px var(--atp-surface);
    }
    .layout-menu {
      position: absolute;
      right: 0;
      top: calc(100% + 8px);
      z-index: 40;
      width: min(320px, 100%);
      box-sizing: border-box;
      padding: 6px;
      border-radius: 16px;
      background: var(--atp-surface);
      box-shadow:
        0 0 0 1px var(--atp-line),
        0 18px 40px -12px color-mix(in srgb, #000 45%, transparent);
      animation: menu-in 140ms var(--atp-ease);
    }
    @keyframes menu-in {
      from {
        opacity: 0;
        transform: translateY(-4px) scale(0.98);
      }
    }
    .menu-title {
      padding: 8px 10px 6px;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--atp-muted);
    }
    .menu-item {
      all: unset;
      box-sizing: border-box;
      width: 100%;
      min-height: 48px;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 10px;
      border-radius: 12px;
      cursor: pointer;
      color: var(--atp-text);
      -webkit-tap-highlight-color: transparent;
    }
    .menu-item:hover,
    .menu-item:focus-visible {
      background: var(--atp-well);
    }
    .menu-item:focus-visible {
      outline: 2px solid var(--atp-accent-ink);
      outline-offset: -2px;
    }
    .menu-item.on {
      background: var(--atp-tint);
    }
    .mi-icon {
      flex: none;
      --mdc-icon-size: 22px;
      color: var(--atp-accent-ink);
    }
    .mi-text {
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .mi-name {
      font-size: 14px;
      font-weight: 600;
    }
    .mi-help {
      font-size: 12px;
      line-height: 1.35;
      color: var(--atp-muted);
    }
    .mi-check {
      flex: none;
      --mdc-icon-size: 20px;
      color: var(--atp-accent-ink);
      visibility: hidden;
    }
    .menu-item.on .mi-check {
      visibility: visible;
    }
    .menu-sep {
      height: 1px;
      margin: 6px 4px;
      background: var(--atp-line);
    }
    /* ---- version notice (stale tab / pending restart) ---------------------------------- */
    .version-notice {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 4px 4px 10px;
      border-radius: 12px;
      font-size: 13px;
      line-height: 1.3;
      background: color-mix(in srgb, var(--atp-warning) 12%, var(--atp-surface));
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--atp-warning) 45%, transparent);
      --mdc-icon-size: 20px;
    }
    .version-notice > ha-icon {
      flex: none;
      color: var(--atp-warning);
    }
    .vn-text {
      flex: 1;
      min-width: 0;
      padding: 6px 0;
    }
    .vn-btn,
    .vn-x {
      all: unset;
      flex: none;
      min-height: 44px;
      min-width: 44px;
      box-sizing: border-box;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 10px;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
    }
    .vn-btn {
      padding: 0 12px;
      font-weight: 600;
      color: var(--atp-on-accent-base);
      background: var(--atp-accent-base);
    }
    .vn-x {
      color: var(--atp-muted);
      --mdc-icon-size: 18px;
    }
    .vn-btn:focus-visible,
    .vn-x:focus-visible {
      outline: 2px solid var(--atp-accent-ink);
      outline-offset: 2px;
    }

    /* ---- segmented control ------------------------------------------------------------- */
    .seg {
      display: flex;
      padding: 3px;
      gap: 3px;
      border-radius: 13px;
      background: var(--atp-well);
      box-shadow: inset 0 0 0 1px var(--atp-line);
    }
    .seg-btn {
      all: unset;
      flex: 1;
      min-height: 44px;
      padding: 0 10px;
      border-radius: 10px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 500;
      color: var(--atp-muted);
      white-space: nowrap;
      transition: background 160ms, color 160ms;
      --mdc-icon-size: 18px;
      -webkit-tap-highlight-color: transparent;
    }
    .seg-btn.on {
      color: var(--atp-text);
      background: var(--atp-surface);
      box-shadow: 0 1px 0 var(--atp-line), 0 4px 10px -6px var(--atp-key-shadow);
    }
    .seg-btn:focus-visible {
      outline: 2px solid var(--atp-accent-ink);
      outline-offset: 1px;
    }

    /* ---- header ------------------------------------------------------------------------ */
    .head {
      position: relative;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .title {
      flex: 1;
      min-width: 0;
    }
    .name {
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.01em;
      line-height: 1.2;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .sub {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px 10px;
      margin-top: 6px;
      font-size: 12px;
      color: var(--atp-muted);
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      max-width: 100%;
      padding: 3px 10px 3px 3px;
      border-radius: 999px;
      background: var(--atp-tint);
      color: var(--atp-text);
      font-weight: 500;
      font-size: 13px;
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--atp-accent-base) 35%, transparent);
    }
    .chip-art,
    .mini-art {
      width: 22px;
      height: 22px;
      flex: none;
      border-radius: 50%;
      display: grid;
      place-items: center;
      overflow: hidden;
      /* The only places outside the tiles that show an app's own colour: its icon dot. */
      background: var(--brand, var(--atp-accent-base));
      color: var(--on-brand, var(--atp-on-accent-base));
      --mdc-icon-size: 14px;
      font-size: 9px;
      font-weight: 700;
    }
    .chip-art .initials,
    .mini-art .initials {
      font-size: 9px;
      letter-spacing: 0;
    }
    .chip-art img,
    .mini-art img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .chip-text {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 160px;
    }
    .state-pill {
      padding: 3px 10px;
      border-radius: 999px;
      font-weight: 600;
      font-size: 12px;
      background: var(--atp-well);
      box-shadow: inset 0 0 0 1px var(--atp-line);
      color: var(--atp-muted);
    }
    .state-pill.waking {
      color: var(--atp-accent-ink);
      box-shadow: inset 0 0 0 1px var(--atp-glow);
    }
    .state-pill.failed {
      color: var(--atp-error);
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--atp-error) 50%, transparent);
    }
    .conn {
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .conn .dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--atp-muted);
      opacity: 0.6;
    }
    .conn.ok .dot {
      background: var(--atp-success);
      opacity: 1;
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--atp-success) 20%, transparent);
    }
    .conn.down .dot {
      background: transparent;
      box-shadow: inset 0 0 0 1.5px var(--atp-muted);
    }

    .power {
      all: unset;
      position: relative;
      flex: none;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
      color: var(--atp-muted);
      background: linear-gradient(180deg, var(--atp-key-hi), var(--atp-key));
      box-shadow:
        inset 0 1px 0 color-mix(in srgb, #fff 9%, transparent),
        0 1px 0 var(--atp-line),
        0 10px 22px -14px var(--atp-key-shadow);
      transition: transform 90ms var(--atp-ease), color 200ms, box-shadow 200ms;
      --mdc-icon-size: 26px;
    }
    .power:active:not([disabled]) {
      transform: scale(0.95);
    }
    .power:focus-visible {
      outline: 2px solid var(--atp-accent-ink);
      outline-offset: 3px;
    }
    .power.on {
      color: var(--atp-on-accent-base);
      background: radial-gradient(circle at 50% 30%, color-mix(in srgb, #fff 28%, transparent), transparent 60%), var(--atp-accent-base);
      box-shadow: 0 0 0 4px var(--atp-tint), 0 12px 26px -12px var(--atp-glow);
    }
    .power.waking {
      color: var(--atp-accent-ink);
      cursor: progress;
    }
    .power.waking ha-icon {
      animation: breathe 1.6s ease-in-out infinite;
    }
    .power.failed {
      color: var(--atp-error);
      box-shadow: 0 0 0 2px color-mix(in srgb, var(--atp-error) 45%, transparent);
    }
    .power-ring {
      position: absolute;
      inset: -5px;
      width: calc(100% + 10px);
      height: calc(100% + 10px);
      transform: rotate(-90deg);
      pointer-events: none;
    }
    .power-ring circle {
      fill: none;
      stroke-width: 4;
    }
    .power-ring .track {
      stroke: transparent;
    }
    .power.waking .power-ring .track {
      stroke: var(--atp-line);
    }
    .power-ring .bar {
      stroke: var(--atp-accent-base);
      stroke-linecap: round;
      stroke-dasharray: 100;
      transition: stroke-dashoffset 250ms linear;
    }
    @keyframes breathe {
      50% {
        opacity: 0.45;
        transform: scale(0.92);
      }
    }

    /* ---- status banners ---------------------------------------------------------------- */
    .status {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 16px;
      background: var(--atp-well);
      box-shadow: inset 0 0 0 1px var(--atp-line);
      --mdc-icon-size: 26px;
    }
    .status > div {
      flex: 1;
      min-width: 0;
    }
    .status p {
      margin: 2px 0 0;
      font-size: 13px;
      line-height: 1.4;
      color: var(--atp-muted);
    }
    .status strong {
      font-size: 14px;
    }
    .status.waking {
      flex-direction: column;
      align-items: stretch;
      gap: 8px;
      box-shadow: inset 0 0 0 1px var(--atp-glow);
      background: color-mix(in srgb, var(--atp-accent-base) 7%, var(--atp-well));
    }
    .status.waking > div {
      flex: none;
    }
    .status-row {
      display: flex;
      align-items: center;
      gap: 10px;
      font-variant-numeric: tabular-nums;
    }
    .pulse {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--atp-accent-base);
      animation: pulse 1.2s ease-out infinite;
    }
    @keyframes pulse {
      0% {
        box-shadow: 0 0 0 0 var(--atp-glow);
      }
      100% {
        box-shadow: 0 0 0 12px transparent;
      }
    }
    .progress {
      height: 6px;
      border-radius: 6px;
      background: var(--atp-line);
      overflow: hidden;
    }
    .progress span {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--atp-glow), var(--atp-accent-base));
      transition: width 250ms linear;
    }
    .status.failed {
      flex-wrap: wrap;
      background: color-mix(in srgb, var(--atp-error) 9%, var(--atp-well));
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--atp-error) 40%, transparent);
      color: var(--atp-text);
    }
    .status.failed > ha-icon {
      color: var(--atp-error);
    }
    .status.warn {
      background: color-mix(in srgb, var(--atp-warning) 9%, var(--atp-well));
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--atp-warning) 40%, transparent);
    }
    .status.warn > ha-icon {
      color: var(--atp-warning);
    }
    .status.idle > ha-icon {
      color: var(--atp-muted);
    }
    .status .key {
      flex: none;
      white-space: nowrap;
    }

    /* ---- body / locked ------------------------------------------------------------------ */
    .body {
      display: flex;
      flex-direction: column;
      gap: 16px;
      transition: opacity 240ms, filter 240ms;
    }
    .body.locked {
      opacity: 0.55;
      filter: saturate(0.4);
    }

    /* ---- navigation -------------------------------------------------------------------- */
    .nav {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .nav-toggle {
      align-self: center;
      width: min(100%, 300px);
    }
    .navkeys {
      display: grid;
      grid-template-columns: repeat(6, minmax(44px, 1fr));
      gap: 8px;
    }
    .navkeys .key {
      padding: 0;
      height: 48px;
    }
    .navkeys.stack {
      grid-template-columns: repeat(3, minmax(44px, 1fr));
      align-content: center;
    }
    .split {
      display: grid;
      grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
      gap: 14px;
      align-items: center;
    }
    .split .nav-toggle {
      width: 100%;
    }
    @container atp (max-width: 340px) {
      .split {
        grid-template-columns: 1fr;
      }
      .seg-btn {
        padding: 0 6px;
        font-size: 12px;
      }
    }

    /* ---- volume + transport ------------------------------------------------------------ */
    .volume {
      display: grid;
      grid-template-columns: auto auto minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
    }
    .volume .key.muted {
      color: var(--atp-error);
    }
    .level {
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 44px;
      padding: 0 4px;
    }
    .level-num {
      width: 36px;
      text-align: right;
      font-size: 13px;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
      color: var(--atp-muted);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .meter {
      flex: 1;
      height: 8px;
      border-radius: 8px;
      background: var(--atp-line);
      overflow: hidden;
    }
    .meter span {
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--atp-glow), var(--atp-accent-base));
      border-radius: inherit;
      transition: width 200ms var(--atp-ease);
    }
    .slider {
      flex: 1;
      min-width: 0;
      height: 44px;
      margin: 0;
      background: transparent;
      appearance: none;
      -webkit-appearance: none;
      cursor: pointer;
    }
    .slider::-webkit-slider-runnable-track {
      height: 8px;
      border-radius: 8px;
      background: linear-gradient(90deg, var(--atp-accent-base) var(--fill), var(--atp-line) var(--fill));
    }
    .slider::-moz-range-track {
      height: 8px;
      border-radius: 8px;
      background: linear-gradient(90deg, var(--atp-accent-base) var(--fill), var(--atp-line) var(--fill));
    }
    .slider::-webkit-slider-thumb {
      -webkit-appearance: none;
      width: 24px;
      height: 24px;
      margin-top: -8px;
      border-radius: 50%;
      background: var(--atp-surface);
      box-shadow: 0 0 0 2px var(--atp-accent-base), 0 4px 10px -4px var(--atp-key-shadow);
    }
    .slider::-moz-range-thumb {
      width: 22px;
      height: 22px;
      border: none;
      border-radius: 50%;
      background: var(--atp-surface);
      box-shadow: 0 0 0 2px var(--atp-accent-base);
    }
    .slider:focus-visible {
      outline: none;
    }
    .slider:focus-visible::-webkit-slider-thumb {
      box-shadow: 0 0 0 2px var(--atp-accent-base), 0 0 0 6px var(--atp-glow);
    }
    .transport-wrap {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .now {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      min-width: 0;
      --mdc-icon-size: 16px;
      color: var(--atp-muted);
    }
    .now-text {
      color: var(--atp-text);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .transport {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 4px;
    }
    .transport .key.play {
      width: 58px;
      height: 58px;
      --mdc-icon-size: 28px;
    }

    /* ---- apps -------------------------------------------------------------------------- */
    .tiles {
      display: grid;
      gap: 12px 8px;
    }
    .tiles.grid {
      grid-template-columns: repeat(auto-fill, minmax(72px, 1fr));
    }
    .tiles.rail {
      grid-auto-flow: column;
      grid-auto-columns: 72px;
      overflow-x: auto;
      overscroll-behavior-x: contain;
      scroll-snap-type: x proximity;
      padding: 4px 2px 6px;
      margin: -4px -2px 0;
      scrollbar-width: none;
      -webkit-mask: linear-gradient(90deg, #000 85%, transparent);
      mask: linear-gradient(90deg, #000 85%, transparent);
    }
    .tiles.rail::-webkit-scrollbar {
      display: none;
    }
    .tile-li {
      scroll-snap-align: start;
      min-width: 0;
    }
    .tile {
      all: unset;
      position: relative;
      box-sizing: border-box;
      width: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      -webkit-tap-highlight-color: transparent;
      border-radius: 18px;
      padding: 2px 0;
    }
    .tile .art {
      width: 60px;
      height: 60px;
      border-radius: 18px;
      display: grid;
      place-items: center;
      overflow: hidden;
      color: var(--on-brand);
      background:
        radial-gradient(circle at 30% 20%, color-mix(in srgb, #fff 28%, transparent), transparent 55%),
        linear-gradient(150deg, var(--brand), color-mix(in srgb, var(--brand) 70%, #000));
      box-shadow:
        inset 0 1px 0 color-mix(in srgb, #fff 25%, transparent),
        0 10px 18px -12px color-mix(in srgb, var(--brand) 80%, #000);
      transition: transform 120ms var(--atp-ease), box-shadow 160ms;
      --mdc-icon-size: 30px;
    }
    .tile .art img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .initials {
      font-weight: 700;
      font-size: 19px;
      letter-spacing: 0.02em;
    }
    .tile .lbl {
      max-width: 100%;
      font-size: 11.5px;
      line-height: 1.2;
      text-align: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      color: var(--atp-text);
    }
    .tile:active:not([disabled]) .art {
      transform: scale(0.92);
    }
    @media (hover: hover) {
      .tile:hover:not([disabled]) .art {
        transform: translateY(-2px);
      }
    }
    .tile:focus-visible .art {
      outline: 2px solid var(--atp-accent-ink);
      outline-offset: 3px;
    }
    .tile.running .art {
      box-shadow:
        0 0 0 3px var(--atp-surface),
        0 0 0 5px var(--atp-accent-base),
        0 12px 22px -10px var(--atp-glow);
    }
    .tile.running .lbl {
      font-weight: 600;
    }
    .live {
      position: absolute;
      top: -2px;
      right: calc(50% - 34px);
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: var(--atp-success);
      box-shadow: 0 0 0 2px var(--atp-surface);
      animation: pulse 1.6s ease-out infinite;
    }
    .tile[disabled] {
      cursor: default;
    }
    .tile.skeleton .art,
    .tile.skeleton .lbl {
      background: linear-gradient(90deg, var(--atp-well), var(--atp-key-hi), var(--atp-well));
      background-size: 200% 100%;
      animation: shimmer 1.2s linear infinite;
      box-shadow: none;
    }
    .tile.skeleton .lbl {
      width: 48px;
      height: 10px;
      border-radius: 5px;
    }
    @keyframes shimmer {
      to {
        background-position: -200% 0;
      }
    }
    .empty {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 14px;
      border-radius: 14px;
      background: var(--atp-well);
      color: var(--atp-muted);
      font-size: 13px;
      --mdc-icon-size: 22px;
    }
    .empty span {
      flex: 1;
    }
    .empty small {
      display: block;
      opacity: 0.8;
    }
    .empty.error > ha-icon {
      color: var(--atp-error);
    }
    .spinner {
      width: 14px;
      height: 14px;
      border-radius: 50%;
      border: 2px solid var(--atp-line);
      border-top-color: var(--atp-accent-ink);
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to {
        transform: rotate(360deg);
      }
    }

    /* ---- in-app panel ------------------------------------------------------------------ */
    .inapp {
      padding: 12px;
      border-radius: var(--atp-radius);
      background: color-mix(in srgb, var(--atp-accent-base) 6%, var(--atp-well));
      box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--atp-accent-base) 22%, var(--atp-line));
    }
    .inapp h3 {
      color: var(--atp-text);
      text-transform: none;
      letter-spacing: 0;
      font-size: 15px;
    }
    .actions {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
      gap: 8px;
    }
    .key.act {
      justify-content: flex-start;
      padding: 0 12px;
      font-size: 13px;
      font-weight: 500;
      text-align: left;
      line-height: 1.15;
      min-height: 48px;
      --mdc-icon-size: 20px;
    }
    .key.act ha-icon {
      flex: none;
      color: var(--atp-accent-ink);
    }
    .key.act.pressed ha-icon {
      color: inherit;
    }
    .action-form,
    .kbd-form {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }
    .kbd-form {
      margin-top: 0;
    }
    .field {
      flex: 1 1 160px;
      min-width: 0;
      min-height: 46px;
      box-sizing: border-box;
      padding: 0 14px;
      border-radius: 14px;
      border: none;
      font: inherit;
      font-size: 16px; /* 16px keeps iOS from zooming the page on focus */
      color: var(--atp-text);
      background: var(--atp-surface);
      box-shadow: inset 0 0 0 1px var(--atp-line), inset 0 2px 4px -2px var(--atp-key-shadow);
    }
    .field::placeholder {
      color: var(--atp-muted);
    }
    .field:focus {
      outline: none;
      box-shadow: inset 0 0 0 2px var(--atp-accent-base);
    }
    .field-error {
      flex-basis: 100%;
      margin: 6px 0 0;
      font-size: 13px;
      line-height: 1.4;
      color: var(--atp-error);
    }
    .numpad {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-top: 10px;
      max-width: 280px;
    }
    .numpad .key {
      height: 50px;
    }

    /* ---- keyboard ---------------------------------------------------------------------- */
    .kbd {
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .kbd .sechead {
      margin-bottom: 0;
    }
    .kbd-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .spacer {
      flex: 1;
    }
    .sent {
      font-size: 12px;
      color: var(--atp-success);
      font-weight: 600;
    }
    .switch {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 44px;
      font-size: 13px;
      cursor: pointer;
      position: relative;
    }
    .switch input {
      position: absolute;
      opacity: 0;
      width: 44px;
      height: 28px;
      margin: 0;
      cursor: pointer;
    }
    .switch .track {
      width: 40px;
      height: 24px;
      border-radius: 12px;
      background: var(--atp-line);
      position: relative;
      transition: background 160ms;
      flex: none;
    }
    .switch .thumb {
      position: absolute;
      top: 3px;
      left: 3px;
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: var(--atp-surface);
      box-shadow: 0 2px 4px -1px var(--atp-key-shadow);
      transition: transform 160ms var(--atp-ease);
    }
    .switch input:checked + .track {
      background: var(--atp-accent-base);
    }
    .switch input:checked + .track .thumb {
      transform: translateX(16px);
    }
    .switch input:focus-visible + .track {
      outline: 2px solid var(--atp-accent-ink);
      outline-offset: 2px;
    }
    .fold {
      border-radius: 16px;
      background: var(--atp-well);
      box-shadow: inset 0 0 0 1px var(--atp-line);
    }
    .fold summary {
      list-style: none;
      display: flex;
      align-items: center;
      gap: 8px;
      min-height: 48px;
      padding: 0 14px;
      cursor: pointer;
      font-weight: 500;
      border-radius: 16px;
      --mdc-icon-size: 20px;
    }
    .fold summary::-webkit-details-marker {
      display: none;
    }
    .fold[open] summary {
      border-bottom: 1px solid var(--atp-line);
      border-radius: 16px 16px 0 0;
    }
    .fold .kbd {
      padding: 12px 14px 14px;
    }
    .fold .kbd .sechead {
      display: none;
    }

    /* ---- screenshot -------------------------------------------------------------------- */
    .shot-btn {
      all: unset;
      position: relative;
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      border-radius: 16px;
      overflow: hidden;
      cursor: pointer;
      background: #000;
      box-shadow: inset 0 0 0 1px var(--atp-line), 0 10px 24px -16px var(--atp-key-shadow);
    }
    .shot-btn:focus-visible {
      outline: 2px solid var(--atp-accent-ink);
      outline-offset: 2px;
    }
    .shot-btn img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }
    .shot-empty {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      color: #888;
      --mdc-icon-size: 40px;
    }
    .shot-cap {
      position: absolute;
      left: 8px;
      bottom: 8px;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 11px;
      color: #fff;
      background: rgba(0, 0, 0, 0.55);
      backdrop-filter: blur(6px);
    }
    .spinner.on-shot {
      position: absolute;
      top: 10px;
      right: 10px;
      border-color: rgba(255, 255, 255, 0.3);
      border-top-color: #fff;
    }

    /* ---- toasts ------------------------------------------------------------------------ */
    .toasts {
      position: absolute;
      left: 12px;
      right: 12px;
      bottom: 12px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      z-index: 20;
      pointer-events: none;
    }
    .layout-remote .toasts {
      bottom: 76px;
    }
    .sheet-open .toasts {
      bottom: auto;
      top: 12px;
    }
    .toast {
      pointer-events: auto;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 8px 8px 12px;
      border-radius: 14px;
      color: var(--atp-surface);
      background: color-mix(in srgb, var(--atp-text) 92%, transparent);
      box-shadow: 0 14px 28px -14px rgba(0, 0, 0, 0.6);
      font-size: 13px;
      animation: toast-in 220ms var(--atp-ease);
      --mdc-icon-size: 20px;
    }
    .toast > ha-icon {
      color: var(--atp-error);
      flex: none;
    }
    .toast-text {
      flex: 1;
      min-width: 0;
    }
    .toast-text small {
      display: block;
      opacity: 0.75;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .toast-btn,
    .toast-x {
      all: unset;
      cursor: pointer;
      min-height: 44px;
      min-width: 44px;
      display: grid;
      place-items: center;
      border-radius: 10px;
      font-weight: 600;
    }
    .toast-btn {
      padding: 0 12px;
      color: var(--atp-accent-ink);
      background: color-mix(in srgb, var(--atp-surface) 12%, transparent);
    }
    .toast-btn:focus-visible,
    .toast-x:focus-visible {
      outline: 2px solid var(--atp-accent-ink);
    }
    @keyframes toast-in {
      from {
        transform: translateY(8px);
        opacity: 0;
      }
    }

    /* ---- layout A: bottom sheet --------------------------------------------------------- */
    .scrim {
      position: absolute;
      inset: 0;
      z-index: 9;
      background: color-mix(in srgb, #000 35%, transparent);
      animation: fade 200ms;
    }
    @keyframes fade {
      from {
        opacity: 0;
      }
    }
    .sheet {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 10;
      max-height: 82%;
      display: flex;
      flex-direction: column;
      border-radius: 24px 24px 0 0;
      background: var(--atp-surface);
      box-shadow: 0 -1px 0 var(--atp-line), 0 -18px 40px -24px var(--atp-key-shadow);
      transform: translateY(calc(100% - 64px));
      transition: transform 320ms var(--atp-ease);
    }
    .sheet.open {
      transform: none;
    }
    .handle {
      all: unset;
      flex: none;
      display: flex;
      flex-direction: column;
      align-items: stretch;
      gap: 6px;
      padding: 8px 16px 10px;
      min-height: 46px;
      cursor: pointer;
      border-radius: 24px 24px 0 0;
      -webkit-tap-highlight-color: transparent;
    }
    .handle:focus-visible {
      outline: 2px solid var(--atp-accent-ink);
      outline-offset: -2px;
    }
    .grabber {
      align-self: center;
      width: 40px;
      height: 4px;
      border-radius: 2px;
      background: var(--atp-line);
    }
    .handle-row {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 600;
      font-size: 14px;
    }
    .handle-text {
      flex: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .handle .chev {
      color: var(--atp-muted);
      transition: transform 240ms var(--atp-ease);
    }
    .sheet.open .chev {
      transform: rotate(180deg);
    }
    .sheet-body {
      overflow-y: auto;
      overscroll-behavior: contain;
      padding: 0 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .tabs {
      display: flex;
      gap: 6px;
      position: sticky;
      top: 0;
      background: var(--atp-surface);
      padding-bottom: 4px;
      z-index: 1;
    }
    .tab {
      all: unset;
      flex: 1;
      min-height: 44px;
      min-width: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      border-radius: 12px;
      cursor: pointer;
      font-size: 13px;
      color: var(--atp-muted);
      --mdc-icon-size: 18px;
    }
    .tab span {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .tab.on {
      color: var(--atp-text);
      background: var(--atp-well);
      box-shadow: inset 0 0 0 1px var(--atp-line);
    }
    .tab:focus-visible {
      outline: 2px solid var(--atp-accent-ink);
    }
    .sheet .inapp {
      background: transparent;
      box-shadow: none;
      padding: 0;
    }
    .sheet .inapp > .sechead {
      display: none;
    }

    /* ---- layout C: columns ------------------------------------------------------------- */
    .cols {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 18px;
    }
    .col {
      display: flex;
      flex-direction: column;
      gap: 16px;
      min-width: 0;
    }
    @container atp (min-width: 620px) {
      .cols {
        grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      }
      .col-pad {
        grid-column: 2;
        grid-row: 1 / span 2;
      }
      .col-apps {
        grid-column: 1;
      }
      .col-app {
        grid-column: 1;
      }
    }
    @container atp (min-width: 940px) {
      .cols {
        grid-template-columns: minmax(0, 1fr) minmax(300px, 0.95fr) minmax(0, 1.1fr);
      }
      .col-apps {
        grid-column: 1;
        grid-row: 1;
      }
      .col-pad {
        grid-column: 2;
        grid-row: 1;
      }
      .col-app {
        grid-column: 3;
        grid-row: 1;
      }
      .col-pad {
        padding: 0 4px;
        border-inline: 1px solid var(--atp-line);
        padding-inline: 18px;
      }
    }
    @container atp (max-width: 340px) {
      .navkeys {
        gap: 5px;
      }
      .volume {
        gap: 5px;
      }
      .level-num {
        width: 28px;
      }
    }

    /* ---- narrow cards (half a section, masonry column, small phones) -------------------- */
    @container atp (max-width: 340px) {
      .navkeys {
        grid-template-columns: repeat(3, minmax(44px, 1fr));
      }
      .chip-text {
        max-width: 100%;
      }
    }
    @container atp (max-width: 300px) {
      .wrap {
        padding: 10px;
        gap: 12px;
      }
      .wrap.layout-remote {
        padding-bottom: 74px;
      }
      .name {
        white-space: normal;
        overflow-wrap: anywhere;
        font-size: 18px;
      }
      .head {
        gap: 8px;
        align-items: flex-start;
      }
      .sub {
        gap: 4px 8px;
      }
      /* Banner: icon + text on one row, the action as a full-width button below. */
      .status {
        flex-wrap: wrap;
        padding: 10px 12px;
        gap: 8px 10px;
      }
      .status > div {
        flex: 1 1 0;
      }
      .status .key {
        flex: 1 1 100%;
      }
      .nav-toggle .seg-label {
        display: none;
      }
      .volume {
        gap: 6px;
      }
      .level-num {
        display: none;
      }
      .transport {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr)) auto repeat(2, minmax(0, 1fr));
        gap: 2px;
      }
      .transport .key {
        min-width: 0;
        padding: 0;
      }
      .transport .key.play {
        width: 52px;
        height: 52px;
      }
      .version-notice {
        flex-wrap: wrap;
      }
      .vn-text {
        flex: 1 1 calc(100% - 80px);
      }
    }  `,
];
