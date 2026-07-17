import { describe, expect, it } from "vitest";

import { BitaxeFleetPanel, PANEL_TAG } from "./bitaxe-fleet-panel";

describe("BitaxeFleetPanel", () => {
  it("registers a development-only panel element", async () => {
    const element = new BitaxeFleetPanel();
    document.body.append(element);

    await element.updateComplete;

    expect(customElements.get(PANEL_TAG)).toBe(BitaxeFleetPanel);
    expect(element).toBeInstanceOf(BitaxeFleetPanel);
    expect(element.shadowRoot?.textContent).toContain("Bitaxe Fleet");
  });
});
