import { afterEach, describe, expect, it, vi } from "vitest";

import {
  BitaxeFleetPanel,
  PANEL_TAG,
  createHistoryPath,
  parseDiscoveryListResponse,
  parseFleetListResponse,
  parseIncidentsListResponse,
  parseMinerTelemetryHistory,
} from "./bitaxe-fleet-panel";
import type { HomeAssistant, WebSocketCommand } from "./bitaxe-fleet-panel";

function scanDto(): Record<string, unknown> {
  return {
    completed_at: null,
    completed_hosts: 0,
    discovered_candidates: 0,
    error: null,
    network: null,
    running: false,
    started_at: null,
    total_hosts: 0,
  };
}

function minerDto(): Record<string, unknown> {
  return {
    enabled: true,
    endpoint: "192.168.1.42",
    firmware: "2.1.4",
    health: {
      hardware_fault: false,
      mining_paused: false,
      overheat_mode: 0,
      power_fault: false,
    },
    last_success_at: "2026-07-17T09:00:00+00:00",
    miner_id: "aa:bb:cc:dd:ee:ff",
    model: "Bitaxe Supra",
    name: "Rack A-01",
    online: true,
    policy: {
      automatic_profile_restore_enabled: true,
      automatic_recovery_enabled: true,
      consecutive_unhealthy_required: 3,
      cooldown_seconds: 600,
      max_attempts: 3,
      overheat_policy: "keep_safe_values",
      post_restart_timeout_seconds: 180,
      rolling_window_seconds: 3600,
      startup_grace_seconds: 180,
      verification_timeout_seconds: 60,
    },
    profile: {
      automatic_fan_speed: true,
      core_voltage_mv: 1200,
      frequency_mhz: 525,
      minimum_fan_speed_percent: 35,
      overclock_enabled: false,
      target_temperature_c: 60,
    },
    telemetry: {
      hashrate_gh_s: 700,
      power_w: 18.5,
      temperature_c: 51.2,
    },
  };
}

function fleetDto(miner = minerDto()): Record<string, unknown> {
  return {
    miners: [miner],
    scan: scanDto(),
    schema_version: 1,
  };
}

function discoveryDto(): Record<string, unknown> {
  return {
    candidates: [
      {
        endpoint: "192.168.1.57",
        firmware: "2.1.4",
        last_seen_at: "2026-07-17T09:03:00+00:00",
        miner_id: "11:22:33:44:55:66",
        model: "Bitaxe Gamma",
        name: "Pending rack miner",
        source: "active_scan",
      },
    ],
    scan: scanDto(),
  };
}

function incidentsDto(): Record<string, unknown> {
  return {
    incidents: [
      {
        cause: "overheat",
        detail: "Cooling recovered after the safety threshold was reached.",
        id: "incident-1",
        miner_id: "aa:bb:cc:dd:ee:ff",
        occurred_at: "2026-07-17T08:55:00+00:00",
        outcome: "recovered",
      },
    ],
  };
}

function historyDto(): Record<string, unknown> {
  return {
    available: true,
    end_at: "2026-07-17T09:00:00+00:00",
    miner_id: "aa:bb:cc:dd:ee:ff",
    schema_version: 1,
    series: {
      hashrate_gh_s: [
        { at: "2026-07-17T08:00:00+00:00", value: 650 },
        { at: "2026-07-17T08:30:00+00:00", value: null },
        { at: "2026-07-17T09:00:00+00:00", value: 700 },
      ],
      power_w: [
        { at: "2026-07-17T08:00:00+00:00", value: 17.2 },
        { at: "2026-07-17T09:00:00+00:00", value: 18.5 },
      ],
      temperature_c: [
        { at: "2026-07-17T08:00:00+00:00", value: 50.5 },
        { at: "2026-07-17T09:00:00+00:00", value: 51.2 },
      ],
    },
    start_at: "2026-07-17T08:00:00+00:00",
  };
}

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void } {
  let resolvePromise: ((value: T) => void) | null = null;
  const promise = new Promise<T>((resolve) => {
    resolvePromise = resolve;
  });
  return {
    promise,
    resolve: (value) => {
      if (resolvePromise === null) {
        throw new Error("Deferred promise was not initialized");
      }
      resolvePromise(value);
    },
  };
}

function dashboardResponse(
  message: WebSocketCommand,
  scan = scanDto(),
): unknown {
  switch (message.type) {
    case "bitaxe_fleet/fleet/list":
      return { ...fleetDto(), scan };
    case "bitaxe_fleet/discovery/list":
      return { ...discoveryDto(), scan };
    case "bitaxe_fleet/incidents/list":
      return incidentsDto();
    default:
      throw new Error(`Unexpected dashboard request: ${message.type}`);
  }
}

function buttonWithText(root: ShadowRoot | null, text: string): HTMLButtonElement {
  const button = Array.from(root?.querySelectorAll<HTMLButtonElement>("button") ?? []).find(
    (candidate) => candidate.textContent?.trim() === text,
  );
  if (button === undefined) {
    throw new Error(`Expected a ${text} button`);
  }
  return button;
}

afterEach(() => {
  document.body.replaceChildren();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("BitaxeFleetPanel DTO boundary", () => {
  it("accepts the versioned DTO shape and rejects malformed nested values", () => {
    const fleet = parseFleetListResponse(fleetDto());

    expect(fleet.schema_version).toBe(1);
    expect(fleet.miners[0]?.telemetry?.hashrate_gh_s).toBe(700);
    expect(fleet.miners[0]?.policy.overheat_policy).toBe("keep_safe_values");
    expect(parseDiscoveryListResponse(discoveryDto()).candidates).toHaveLength(1);
    expect(parseIncidentsListResponse(incidentsDto()).incidents).toHaveLength(1);
    expect(parseMinerTelemetryHistory(historyDto()).series.hashrate_gh_s).toHaveLength(3);

    const partialMiner = minerDto();
    partialMiner["firmware"] = null;
    partialMiner["model"] = null;
    partialMiner["health"] = {
      hardware_fault: false,
      mining_paused: null,
      overheat_mode: 0,
      power_fault: false,
    };
    partialMiner["telemetry"] = {
      hashrate_gh_s: null,
      power_w: null,
      temperature_c: null,
    };
    const partialFleet = parseFleetListResponse(fleetDto(partialMiner));
    expect(partialFleet.miners[0]?.model).toBeNull();
    expect(partialFleet.miners[0]?.telemetry?.temperature_c).toBeNull();

    const invalidMiner = minerDto();
    invalidMiner["telemetry"] = {
      hashrate_gh_s: "not-a-number",
      power_w: 18.5,
      temperature_c: 51.2,
    };
    const invalidFleet = fleetDto();
    invalidFleet["miners"] = [invalidMiner];

    expect(() => parseFleetListResponse(invalidFleet)).toThrow(
      "Unexpected Bitaxe Fleet response",
    );
    expect(() =>
      parseDiscoveryListResponse({
        candidates: [
          {
            endpoint: "192.168.1.57",
            firmware: "2.1.4",
            last_seen_at: "not-a-timestamp",
            miner_id: "11:22:33:44:55:66",
            model: "Bitaxe Gamma",
            name: "Pending rack miner",
            source: "active_scan",
          },
        ],
        scan: scanDto(),
      }),
    ).toThrow("Unexpected Bitaxe Fleet response");

    const invalidHistory = historyDto();
    const series = invalidHistory["series"] as Record<string, unknown>;
    series["power_w"] = [{ at: "not-a-timestamp", value: 18.5 }];
    expect(() => parseMinerTelemetryHistory(invalidHistory)).toThrow(
      "Unexpected Bitaxe Fleet response",
    );
  });

  it("creates disconnected graph segments for unavailable history points", () => {
    expect(
      createHistoryPath([
        { at: "2026-07-17T08:00:00+00:00", value: 650 },
        { at: "2026-07-17T08:30:00+00:00", value: null },
        { at: "2026-07-17T09:00:00+00:00", value: 700 },
      ]),
    ).toMatch(/^M.* M/);
  });
});

describe("BitaxeFleetPanel", () => {
  it("registers the panel and renders validated WebSocket data as text", async () => {
    const unsafeName = "<img src=x onerror=alert(1)>";
    const miner = minerDto();
    miner["name"] = unsafeName;
    miner["last_success_at"] = "2020-01-01T00:00:00+00:00";
    const fleet = fleetDto(miner);

    const calls: WebSocketCommand[] = [];
    const responses: Record<string, unknown> = {
      "bitaxe_fleet/discovery/list": discoveryDto(),
      "bitaxe_fleet/fleet/list": fleet,
      "bitaxe_fleet/incidents/list": incidentsDto(),
      "bitaxe_fleet/logs/get": "<script>window.pwned = true</script>",
    };
    const hass: HomeAssistant = {
      callWS(message) {
        calls.push(message);
        if (message.type === "bitaxe_fleet/logs/get") {
          return Promise.resolve({ text: responses[message.type] });
        }
        return Promise.resolve(responses[message.type]);
      },
    };
    const element = new BitaxeFleetPanel();
    element.hass = hass;
    document.body.append(element);

    await vi.waitFor(() => {
      expect(element.shadowRoot?.textContent).toContain(unsafeName);
    });

    const root = element.shadowRoot;
    expect(customElements.get(PANEL_TAG)).toBe(BitaxeFleetPanel);
    expect(root?.textContent).toContain("Administrator console");
    expect(root?.textContent).toContain("admin endpoint");
    expect(root?.textContent).toContain("Stale");
    expect(root?.querySelector("img")).toBeNull();
    expect(calls.map((call) => call.type)).toEqual(
      expect.arrayContaining([
        "bitaxe_fleet/fleet/list",
        "bitaxe_fleet/discovery/list",
        "bitaxe_fleet/incidents/list",
      ]),
    );

    const loadLogsButton = Array.from(root?.querySelectorAll("button") ?? []).find(
      (button) => button.textContent?.trim() === "Load logs",
    );
    expect(loadLogsButton).toBeDefined();
    loadLogsButton?.click();

    await vi.waitFor(() => {
      expect(root?.textContent).toContain("<script>window.pwned = true</script>");
    });
    expect(root?.querySelector("script")).toBeNull();
  });

  it("keeps loaded fleet state without refetching when hass is replaced", async () => {
    const calls: WebSocketCommand[] = [];
    const callWS = (message: WebSocketCommand): Promise<unknown> => {
      calls.push(message);
      return Promise.resolve(dashboardResponse(message));
    };
    const element = new BitaxeFleetPanel();
    element.hass = { callWS };
    document.body.append(element);

    await vi.waitFor(() => {
      expect(element.shadowRoot?.textContent).toContain("Rack A-01");
    });
    expect(calls).toHaveLength(3);

    element.hass = { callWS };
    await element.updateComplete;

    expect(element.shadowRoot?.textContent).toContain("Rack A-01");
    expect(calls).toHaveLength(3);
  });

  it("keeps an in-flight dashboard load when hass is replaced", async () => {
    const fleet = deferred<unknown>();
    const discovery = deferred<unknown>();
    const incidents = deferred<unknown>();
    const calls: WebSocketCommand[] = [];
    const callWS = (message: WebSocketCommand): Promise<unknown> => {
      calls.push(message);
      switch (message.type) {
        case "bitaxe_fleet/fleet/list":
          return fleet.promise;
        case "bitaxe_fleet/discovery/list":
          return discovery.promise;
        case "bitaxe_fleet/incidents/list":
          return incidents.promise;
        default:
          throw new Error(`Unexpected dashboard request: ${message.type}`);
      }
    };
    const element = new BitaxeFleetPanel();
    element.hass = { callWS };
    document.body.append(element);

    await vi.waitFor(() => {
      expect(calls).toHaveLength(3);
    });

    element.hass = { callWS };
    await element.updateComplete;
    expect(calls).toHaveLength(3);

    fleet.resolve(fleetDto());
    discovery.resolve(discoveryDto());
    incidents.resolve(incidentsDto());

    await vi.waitFor(() => {
      expect(element.shadowRoot?.textContent).toContain("Rack A-01");
    });
    expect(calls).toHaveLength(3);
  });

  it("keeps pending miner actions protected when hass is replaced", async () => {
    const action = deferred<unknown>();
    const calls: WebSocketCommand[] = [];
    const callWS = (message: WebSocketCommand): Promise<unknown> => {
      calls.push(message);
      if (message.type === "bitaxe_fleet/miner/action") {
        return action.promise;
      }
      return Promise.resolve(dashboardResponse(message));
    };
    const element = new BitaxeFleetPanel();
    element.hass = { callWS };
    document.body.append(element);

    await vi.waitFor(() => {
      expect(element.shadowRoot?.textContent).toContain("Rack A-01");
    });

    vi.spyOn(window, "confirm").mockReturnValue(true);
    buttonWithText(element.shadowRoot, "Restart").click();
    await element.updateComplete;
    expect(buttonWithText(element.shadowRoot, "Restart").disabled).toBe(true);
    expect(
      calls.filter((call) => call.type === "bitaxe_fleet/miner/action"),
    ).toHaveLength(1);

    element.hass = { callWS };
    await element.updateComplete;

    expect(buttonWithText(element.shadowRoot, "Restart").disabled).toBe(true);
    expect(calls).toHaveLength(4);

    action.resolve({});

    await vi.waitFor(() => {
      expect(buttonWithText(element.shadowRoot, "Restart").disabled).toBe(false);
    });
  });

  it("loads and refreshes recorder history only after an administrator requests it", async () => {
    const calls: WebSocketCommand[] = [];
    const callWS = (message: WebSocketCommand): Promise<unknown> => {
      calls.push(message);
      if (message.type === "bitaxe_fleet/miner/history") {
        return Promise.resolve(historyDto());
      }
      return Promise.resolve(dashboardResponse(message));
    };
    const element = new BitaxeFleetPanel();
    element.hass = { callWS };
    document.body.append(element);

    await vi.waitFor(() => {
      expect(element.shadowRoot?.textContent).toContain("Rack A-01");
    });
    expect(
      calls.filter((call) => call.type === "bitaxe_fleet/miner/history"),
    ).toHaveLength(0);

    buttonWithText(element.shadowRoot, "History").click();
    await vi.waitFor(() => {
      expect(element.shadowRoot?.textContent).toContain("History: Rack A-01");
      expect(element.shadowRoot?.querySelectorAll(".history-chart")).toHaveLength(3);
    });
    expect(
      calls.filter((call) => call.type === "bitaxe_fleet/miner/history"),
    ).toHaveLength(1);

    buttonWithText(element.shadowRoot, "Refresh history").click();
    await vi.waitFor(() => {
      expect(
        calls.filter((call) => call.type === "bitaxe_fleet/miner/history"),
      ).toHaveLength(2);
    });
  });

  it("keeps scan polling active when hass is replaced", async () => {
    vi.useFakeTimers();
    const runningScan = {
      ...scanDto(),
      completed_hosts: 1,
      network: "192.168.1.0/24",
      running: true,
      total_hosts: 4,
    };
    const calls: WebSocketCommand[] = [];
    const callWS = (message: WebSocketCommand): Promise<unknown> => {
      calls.push(message);
      return Promise.resolve(dashboardResponse(message, runningScan));
    };
    const element = new BitaxeFleetPanel();
    element.hass = { callWS };
    document.body.append(element);

    await vi.advanceTimersByTimeAsync(0);
    await element.updateComplete;
    expect(element.shadowRoot?.textContent).toContain("Scanning 192.168.1.0/24");
    expect(calls).toHaveLength(3);

    element.hass = { callWS };
    await element.updateComplete;
    expect(calls).toHaveLength(3);

    await vi.advanceTimersByTimeAsync(2_500);
    expect(calls).toHaveLength(6);
  });
});
