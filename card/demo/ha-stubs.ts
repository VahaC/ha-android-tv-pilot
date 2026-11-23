// Stand-ins for Home Assistant's own elements so the card renders outside HA.
import * as mdi from "@mdi/js";

const paths = mdi as unknown as Record<string, string>;

function pathFor(icon: string | null): string | undefined {
  if (!icon || !icon.startsWith("mdi:")) return undefined;
  const name = "mdi" + icon.slice(4).split("-").map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join("");
  return paths[name];
}

class HaIconStub extends HTMLElement {
  static observedAttributes = ["icon"];
  private root = this.attachShadow({ mode: "open" });

  set icon(value: string) {
    this.setAttribute("icon", value);
  }

  get icon(): string {
    return this.getAttribute("icon") ?? "";
  }

  connectedCallback(): void {
    this.draw();
  }

  attributeChangedCallback(): void {
    this.draw();
  }

  private draw(): void {
    const icon = this.getAttribute("icon");
    const d = pathFor(icon);
    if (icon && !d) console.warn(`[ha-icon stub] unknown icon ${icon}`);
    this.root.innerHTML = `<style>
      :host{display:inline-flex;align-items:center;justify-content:center;width:var(--mdc-icon-size,24px);height:var(--mdc-icon-size,24px);vertical-align:middle;flex:none}
      svg{width:100%;height:100%;fill:currentColor;display:block}
    </style><svg viewBox="0 0 24 24" aria-hidden="true">${d ? `<path d="${d}"></path>` : `<rect x="5" y="5" width="14" height="14" rx="3" opacity=".35"></rect>`}</svg>`;
  }
}

class HaCardStub extends HTMLElement {
  constructor() {
    super();
    // :host rules copied from the HA frontend (src/components/ha-card.ts), not simplified.
    this.attachShadow({ mode: "open" }).innerHTML = `<style>
      :host {
        background: var(--ha-card-background, var(--card-background-color, white));
        -webkit-backdrop-filter: var(--ha-card-backdrop-filter, none);
        backdrop-filter: var(--ha-card-backdrop-filter, none);
        box-shadow: var(--ha-card-box-shadow, none);
        box-sizing: border-box;
        border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
        border-width: var(--ha-card-border-width, 1px);
        border-style: solid;
        border-color: var(--ha-card-border-color, var(--divider-color, #e0e0e0));
        color: var(--primary-text-color);
        display: block;
        transition: all 0.3s ease-out;
        position: relative;
      }
    </style><slot></slot>`;
  }
}

if (!customElements.get("ha-icon")) customElements.define("ha-icon", HaIconStub);
if (!customElements.get("ha-card")) customElements.define("ha-card", HaCardStub);
