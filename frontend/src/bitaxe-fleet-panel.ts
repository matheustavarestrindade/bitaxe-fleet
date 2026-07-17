import { css, html, LitElement } from "lit";

export const PANEL_TAG = "bitaxe-fleet-panel";
const DEVELOPMENT_STATUS =
  "The fleet panel is not available in this development build.";

export class BitaxeFleetPanel extends LitElement {
  static styles = css`
    :host {
      display: block;
      color: var(--primary-text-color);
      font-family: var(--primary-font-family);
    }

    main {
      border-inline-start: 4px solid var(--warning-color);
      margin: 1rem;
      max-inline-size: 42rem;
      padding: 1rem 1.25rem;
    }

    h1 {
      font-size: 1.25rem;
      margin: 0;
    }

    p {
      color: var(--secondary-text-color);
      margin-block: 0.5rem 0;
    }
  `;

  render() {
    return html`
      <main aria-live="polite">
        <h1>Bitaxe Fleet</h1>
        <p>${DEVELOPMENT_STATUS}</p>
      </main>
    `;
  }
}

if (customElements.get(PANEL_TAG) === undefined) {
  customElements.define(PANEL_TAG, BitaxeFleetPanel);
}
