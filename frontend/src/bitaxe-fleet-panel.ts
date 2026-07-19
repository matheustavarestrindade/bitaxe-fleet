import { css, html, LitElement, nothing } from "lit";
import type { PropertyValues } from "lit";

export const PANEL_TAG = "bitaxe-fleet-panel";
export const CARD_TAG = "bitaxe-fleet-graph-card";
export const OVERVIEW_CARD_TAG = "bitaxe-fleet-overview-card";

const CARD_REFRESH_INTERVAL_MS = 30_000;
const STALE_AFTER_MS = 90_000;
const STALE_CLOCK_INTERVAL_MS = 15_000;
const SCAN_POLL_INTERVAL_MS = 2_500;

export type MinerAction = "restart" | "pause" | "resume" | "identify";
export type OverheatPolicy =
  | "keep_safe_values"
  | "restore_after_cooldown"
  | "log_only";

export interface HomeAssistant {
  callWS(message: WebSocketCommand): Promise<unknown>;
}

export interface Telemetry {
  best_difficulty: number | null;
  best_session_difficulty: number | null;
  hashrate_gh_s: number | null;
  power_w: number | null;
  temperature_c: number | null;
}

export interface MinerHealth {
  mining_paused: boolean | null;
  overheat_mode: boolean | number | null;
  power_fault: boolean;
  hardware_fault: boolean;
}

export interface MinerProfile {
  automatic_fan_speed: boolean;
  core_voltage_mv: number;
  frequency_mhz: number;
  minimum_fan_speed_percent: number;
  overclock_enabled: boolean;
  target_temperature_c: number;
}

export interface RecoveryPolicy {
  automatic_profile_restore_enabled: boolean;
  automatic_recovery_enabled: boolean;
  consecutive_unhealthy_required: number;
  cooldown_seconds: number;
  max_attempts: number;
  overheat_policy: OverheatPolicy;
  post_restart_timeout_seconds: number;
  rolling_window_seconds: number;
  startup_grace_seconds: number;
  verification_timeout_seconds: number;
}

export interface Miner {
  miner_id: string;
  name: string;
  model: string | null;
  firmware: string | null;
  endpoint: string;
  enabled: boolean;
  online: boolean;
  last_success_at: string | null;
  telemetry: Telemetry | null;
  health: MinerHealth | null;
  profile: MinerProfile | null;
  policy: RecoveryPolicy;
}

export interface Scan {
  completed_at: string | null;
  completed_hosts: number;
  discovered_candidates: number;
  error: string | null;
  network: string | null;
  running: boolean;
  started_at: string | null;
  total_hosts: number;
}

export interface FleetAggregates {
  best_difficulty: number | null;
  best_difficulty_coverage: number;
  best_session_difficulty: number | null;
  best_session_difficulty_coverage: number;
  efficiency_j_th: number | null;
  enabled_miners: number;
  hashrate_coverage: number;
  online_miners: number;
  overheat_coverage: number;
  overheating_miners: number | null;
  power_coverage: number;
  total_hashrate_gh_s: number | null;
  total_hashrate_th_s: number | null;
  total_power_w: number | null;
  total_uptime_seconds: number | null;
  unhealthy_coverage: number;
  unhealthy_miners: number | null;
  uptime_coverage: number;
}

export interface FleetListResponse {
  aggregates: FleetAggregates | null;
  schema_version: 1;
  miners: Miner[];
  scan: Scan;
}

export interface DiscoveryCandidate {
  miner_id: string;
  name: string;
  model: string | null;
  firmware: string | null;
  endpoint: string;
  source: string;
  last_seen_at: string;
}

export interface DiscoveryListResponse {
  candidates: DiscoveryCandidate[];
  scan: Scan;
}

export interface Incident {
  cause: string;
  detail: string;
  id: string;
  miner_id: string;
  occurred_at: string;
  outcome: string;
}

export interface IncidentsListResponse {
  incidents: Incident[];
}

export interface TelemetryHistoryPoint {
  at: string;
  value: number | null;
}

export interface MinerTelemetryHistory {
  available: boolean;
  end_at: string;
  miner_id: string;
  schema_version: 1;
  series: {
    hashrate_gh_s: TelemetryHistoryPoint[];
    power_w: TelemetryHistoryPoint[];
    temperature_c: TelemetryHistoryPoint[];
  };
  start_at: string;
}

export type FleetHistoryMetric = "efficiency" | "hashrate" | "power";

export interface FleetTelemetryHistory {
  available: boolean;
  end_at: string;
  metric: FleetHistoryMetric;
  schema_version: 1;
  series: TelemetryHistoryPoint[];
  start_at: string;
}

export interface BitaxeFleetGraphCardConfig {
  metric: FleetHistoryMetric;
  name?: string;
}

export interface BitaxeFleetOverviewCardConfig {
  name?: string;
}

export type WebSocketCommand =
  | { type: "bitaxe_fleet/fleet/list" }
  | { type: "bitaxe_fleet/discovery/list" }
  | { type: "bitaxe_fleet/discovery/scan"; network: string }
  | { type: "bitaxe_fleet/discovery/approve"; miner_id: string }
  | { type: "bitaxe_fleet/discovery/reject"; miner_id: string }
  | {
      type: "bitaxe_fleet/miner/action";
      miner_id: string;
      action: MinerAction;
    }
  | { type: "bitaxe_fleet/profile/capture"; miner_id: string }
  | { type: "bitaxe_fleet/profile/apply"; miner_id: string }
  | {
      type: "bitaxe_fleet/policy/update";
      miner_id: string;
      policy: RecoveryPolicy;
    }
  | { type: "bitaxe_fleet/logs/get"; miner_id: string }
  | { type: "bitaxe_fleet/incidents/list" }
  | { type: "bitaxe_fleet/fleet/history"; metric: FleetHistoryMetric }
  | { type: "bitaxe_fleet/miner/history"; miner_id: string };

interface ScanStartResponse {
  scan: Scan;
}

interface ProfileCaptureResponse {
  profile: MinerProfile;
}

interface PolicyUpdateResponse {
  policy: RecoveryPolicy;
}

interface LogsResponse {
  text: string;
}

interface ApprovalResponse {
  miner: Miner;
}

interface Feedback {
  tone: "error" | "success";
  text: string;
}

class DtoValidationError extends Error {
  public constructor() {
    super("Unexpected Bitaxe Fleet response");
    this.name = "DtoValidationError";
  }
}

function invalidDto(): never {
  throw new DtoValidationError();
}

function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    invalidDto();
  }
  return value as Record<string, unknown>;
}

function asArray(value: unknown): unknown[] {
  if (!Array.isArray(value)) {
    invalidDto();
  }
  return value;
}

function readString(record: Record<string, unknown>, key: string): string {
  const value = record[key];
  if (typeof value !== "string") {
    invalidDto();
  }
  return value;
}

function readNullableString(
  record: Record<string, unknown>,
  key: string,
): string | null {
  const value = record[key];
  if (value !== null && typeof value !== "string") {
    invalidDto();
  }
  return value;
}

function readBoolean(record: Record<string, unknown>, key: string): boolean {
  const value = record[key];
  if (typeof value !== "boolean") {
    invalidDto();
  }
  return value;
}

function readFiniteNumber(record: Record<string, unknown>, key: string): number {
  const value = record[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    invalidDto();
  }
  return value;
}

function readNullableFiniteNumber(
  record: Record<string, unknown>,
  key: string,
): number | null {
  const value = record[key];
  if (value !== null && (typeof value !== "number" || !Number.isFinite(value))) {
    invalidDto();
  }
  return value;
}

function readOptionalNullableFiniteNumber(
  record: Record<string, unknown>,
  key: string,
): number | null {
  if (record[key] === undefined) {
    return null;
  }
  return readNullableFiniteNumber(record, key);
}

function readNullableBoolean(
  record: Record<string, unknown>,
  key: string,
): boolean | null {
  const value = record[key];
  if (value !== null && typeof value !== "boolean") {
    invalidDto();
  }
  return value;
}

function readOverheatMode(
  record: Record<string, unknown>,
  key: string,
): boolean | number | null {
  const value = record[key];
  if (value === null || typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number" && Number.isFinite(value) && Number.isInteger(value)) {
    return value;
  }
  return invalidDto();
}

function readNonNegativeInteger(
  record: Record<string, unknown>,
  key: string,
): number {
  const value = readFiniteNumber(record, key);
  if (!Number.isInteger(value) || value < 0) {
    invalidDto();
  }
  return value;
}

function readOptionalNonNegativeInteger(
  record: Record<string, unknown>,
  key: string,
): number {
  if (record[key] === undefined) {
    return 0;
  }
  return readNonNegativeInteger(record, key);
}

function readNullableNonNegativeInteger(
  record: Record<string, unknown>,
  key: string,
): number | null {
  const value = readNullableFiniteNumber(record, key);
  if (value !== null && (!Number.isInteger(value) || value < 0)) {
    invalidDto();
  }
  return value;
}

function readTimestamp(record: Record<string, unknown>, key: string): string | null {
  const value = readNullableString(record, key);
  if (value !== null && Number.isNaN(Date.parse(value))) {
    invalidDto();
  }
  return value;
}

function readRequiredTimestamp(
  record: Record<string, unknown>,
  key: string,
): string {
  const value = readString(record, key);
  if (Number.isNaN(Date.parse(value))) {
    invalidDto();
  }
  return value;
}

function parseOverheatPolicy(value: unknown): OverheatPolicy {
  if (value === "keep_safe_values") {
    return value;
  }
  if (value === "restore_after_cooldown") {
    return value;
  }
  if (value === "log_only") {
    return value;
  }
  return invalidDto();
}

function parseTelemetry(value: unknown): Telemetry | null {
  if (value === null) {
    return null;
  }
  const record = asRecord(value);
  return {
    best_difficulty: readNullableFiniteNumber(record, "best_difficulty"),
    best_session_difficulty: readOptionalNullableFiniteNumber(
      record,
      "best_session_difficulty",
    ),
    hashrate_gh_s: readNullableFiniteNumber(record, "hashrate_gh_s"),
    power_w: readNullableFiniteNumber(record, "power_w"),
    temperature_c: readNullableFiniteNumber(record, "temperature_c"),
  };
}

function parseHealth(value: unknown): MinerHealth | null {
  if (value === null) {
    return null;
  }
  const record = asRecord(value);
  return {
    mining_paused: readNullableBoolean(record, "mining_paused"),
    overheat_mode: readOverheatMode(record, "overheat_mode"),
    power_fault: readBoolean(record, "power_fault"),
    hardware_fault: readBoolean(record, "hardware_fault"),
  };
}

function parseProfile(value: unknown): MinerProfile | null {
  if (value === null) {
    return null;
  }
  const record = asRecord(value);
  return {
    automatic_fan_speed: readBoolean(record, "automatic_fan_speed"),
    core_voltage_mv: readFiniteNumber(record, "core_voltage_mv"),
    frequency_mhz: readFiniteNumber(record, "frequency_mhz"),
    minimum_fan_speed_percent: readFiniteNumber(
      record,
      "minimum_fan_speed_percent",
    ),
    overclock_enabled: readBoolean(record, "overclock_enabled"),
    target_temperature_c: readFiniteNumber(record, "target_temperature_c"),
  };
}

function parsePolicy(value: unknown): RecoveryPolicy {
  const record = asRecord(value);
  return {
    automatic_profile_restore_enabled: readBoolean(
      record,
      "automatic_profile_restore_enabled",
    ),
    automatic_recovery_enabled: readBoolean(
      record,
      "automatic_recovery_enabled",
    ),
    consecutive_unhealthy_required: readNonNegativeInteger(
      record,
      "consecutive_unhealthy_required",
    ),
    cooldown_seconds: readNonNegativeInteger(record, "cooldown_seconds"),
    max_attempts: readNonNegativeInteger(record, "max_attempts"),
    overheat_policy: parseOverheatPolicy(record["overheat_policy"]),
    post_restart_timeout_seconds: readNonNegativeInteger(
      record,
      "post_restart_timeout_seconds",
    ),
    rolling_window_seconds: readNonNegativeInteger(
      record,
      "rolling_window_seconds",
    ),
    startup_grace_seconds: readNonNegativeInteger(
      record,
      "startup_grace_seconds",
    ),
    verification_timeout_seconds: readNonNegativeInteger(
      record,
      "verification_timeout_seconds",
    ),
  };
}

function parseScan(value: unknown): Scan {
  const record = asRecord(value);
  return {
    completed_at: readTimestamp(record, "completed_at"),
    completed_hosts: readNonNegativeInteger(record, "completed_hosts"),
    discovered_candidates: readNonNegativeInteger(record, "discovered_candidates"),
    error: readNullableString(record, "error"),
    network: readNullableString(record, "network"),
    running: readBoolean(record, "running"),
    started_at: readTimestamp(record, "started_at"),
    total_hosts: readNonNegativeInteger(record, "total_hosts"),
  };
}

function parseFleetAggregates(value: unknown): FleetAggregates | null {
  if (value === undefined) {
    return null;
  }
  const record = asRecord(value);
  return {
    best_difficulty: readNullableFiniteNumber(record, "best_difficulty"),
    best_difficulty_coverage: readNonNegativeInteger(record, "best_difficulty_coverage"),
    best_session_difficulty: readOptionalNullableFiniteNumber(
      record,
      "best_session_difficulty",
    ),
    best_session_difficulty_coverage: readOptionalNonNegativeInteger(
      record,
      "best_session_difficulty_coverage",
    ),
    efficiency_j_th: readNullableFiniteNumber(record, "efficiency_j_th"),
    enabled_miners: readNonNegativeInteger(record, "enabled_miners"),
    hashrate_coverage: readNonNegativeInteger(record, "hashrate_coverage"),
    online_miners: readNonNegativeInteger(record, "online_miners"),
    overheat_coverage: readNonNegativeInteger(record, "overheat_coverage"),
    overheating_miners: readNullableNonNegativeInteger(record, "overheating_miners"),
    power_coverage: readNonNegativeInteger(record, "power_coverage"),
    total_hashrate_gh_s: readNullableFiniteNumber(record, "total_hashrate_gh_s"),
    total_hashrate_th_s: readNullableFiniteNumber(record, "total_hashrate_th_s"),
    total_power_w: readNullableFiniteNumber(record, "total_power_w"),
    total_uptime_seconds: readNullableNonNegativeInteger(record, "total_uptime_seconds"),
    unhealthy_coverage: readNonNegativeInteger(record, "unhealthy_coverage"),
    unhealthy_miners: readNullableNonNegativeInteger(record, "unhealthy_miners"),
    uptime_coverage: readNonNegativeInteger(record, "uptime_coverage"),
  };
}

function parseMiner(value: unknown): Miner {
  const record = asRecord(value);
  return {
    miner_id: readString(record, "miner_id"),
    name: readString(record, "name"),
    model: readNullableString(record, "model"),
    firmware: readNullableString(record, "firmware"),
    endpoint: readString(record, "endpoint"),
    enabled: readBoolean(record, "enabled"),
    online: readBoolean(record, "online"),
    last_success_at: readTimestamp(record, "last_success_at"),
    telemetry: parseTelemetry(record["telemetry"]),
    health: parseHealth(record["health"]),
    profile: parseProfile(record["profile"]),
    policy: parsePolicy(record["policy"]),
  };
}

export function parseFleetListResponse(value: unknown): FleetListResponse {
  const record = asRecord(value);
  if (readFiniteNumber(record, "schema_version") !== 1) {
    invalidDto();
  }
  return {
    aggregates: parseFleetAggregates(record["aggregates"]),
    schema_version: 1,
    miners: asArray(record["miners"]).map(parseMiner),
    scan: parseScan(record["scan"]),
  };
}

export function parseDiscoveryListResponse(value: unknown): DiscoveryListResponse {
  const record = asRecord(value);
  return {
    candidates: asArray(record["candidates"]).map((candidate) => {
      const item = asRecord(candidate);
      return {
        miner_id: readString(item, "miner_id"),
        name: readString(item, "name"),
        model: readNullableString(item, "model"),
        firmware: readNullableString(item, "firmware"),
        endpoint: readString(item, "endpoint"),
        source: readString(item, "source"),
        last_seen_at: readRequiredTimestamp(item, "last_seen_at"),
      };
    }),
    scan: parseScan(record["scan"]),
  };
}

export function parseIncidentsListResponse(value: unknown): IncidentsListResponse {
  const record = asRecord(value);
  return {
    incidents: asArray(record["incidents"]).map((incident) => {
      const item = asRecord(incident);
      return {
        cause: readString(item, "cause"),
        detail: readString(item, "detail"),
        id: readString(item, "id"),
        miner_id: readString(item, "miner_id"),
        occurred_at: readRequiredTimestamp(item, "occurred_at"),
        outcome: readString(item, "outcome"),
      };
    }),
  };
}

function parseTelemetryHistoryPoint(value: unknown): TelemetryHistoryPoint {
  const record = asRecord(value);
  return {
    at: readRequiredTimestamp(record, "at"),
    value: readNullableFiniteNumber(record, "value"),
  };
}

export function parseMinerTelemetryHistory(value: unknown): MinerTelemetryHistory {
  const record = asRecord(value);
  if (readFiniteNumber(record, "schema_version") !== 1) {
    invalidDto();
  }
  const startAt = readRequiredTimestamp(record, "start_at");
  const endAt = readRequiredTimestamp(record, "end_at");
  if (Date.parse(endAt) < Date.parse(startAt)) {
    invalidDto();
  }
  const series = asRecord(record["series"]);
  return {
    available: readBoolean(record, "available"),
    end_at: endAt,
    miner_id: readString(record, "miner_id"),
    schema_version: 1,
    series: {
      hashrate_gh_s: asArray(series["hashrate_gh_s"]).map(parseTelemetryHistoryPoint),
      power_w: asArray(series["power_w"]).map(parseTelemetryHistoryPoint),
      temperature_c: asArray(series["temperature_c"]).map(parseTelemetryHistoryPoint),
    },
    start_at: startAt,
  };
}

function parseFleetHistoryMetric(value: unknown): FleetHistoryMetric {
  if (value === "efficiency" || value === "hashrate" || value === "power") {
    return value;
  }
  return invalidDto();
}

export function parseFleetTelemetryHistory(value: unknown): FleetTelemetryHistory {
  const record = asRecord(value);
  if (readFiniteNumber(record, "schema_version") !== 1) {
    invalidDto();
  }
  const startAt = readRequiredTimestamp(record, "start_at");
  const endAt = readRequiredTimestamp(record, "end_at");
  if (Date.parse(endAt) < Date.parse(startAt)) {
    invalidDto();
  }
  return {
    available: readBoolean(record, "available"),
    end_at: endAt,
    metric: parseFleetHistoryMetric(record["metric"]),
    schema_version: 1,
    series: asArray(record["series"]).map(parseTelemetryHistoryPoint),
    start_at: startAt,
  };
}

function parseScanStartResponse(value: unknown): ScanStartResponse {
  return { scan: parseScan(asRecord(value)["scan"]) };
}

function parseProfileCaptureResponse(value: unknown): ProfileCaptureResponse {
  const profile = parseProfile(asRecord(value)["profile"]);
  if (profile === null) {
    invalidDto();
  }
  return { profile };
}

function parsePolicyUpdateResponse(value: unknown): PolicyUpdateResponse {
  return { policy: parsePolicy(asRecord(value)["policy"]) };
}

function parseLogsResponse(value: unknown): LogsResponse {
  const record = asRecord(value);
  return { text: readString(record, "text") };
}

function parseApprovalResponse(value: unknown): ApprovalResponse {
  return { miner: parseMiner(asRecord(value)["miner"]) };
}

function formatNumber(value: number, maximumFractionDigits = 1): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits }).format(value);
}

export function formatHashrate(value: number | null): string {
  if (value === null) {
    return "-- GH/s";
  }
  if (value >= 1_000) {
    return `${formatNumber(value / 1_000, 2)} TH/s`;
  }
  return `${formatNumber(value, 2)} GH/s`;
}

export function formatDifficulty(value: number | null): string {
  if (value === null) {
    return "--";
  }
  const units: ReadonlyArray<readonly [number, string]> = [
    [1_000_000_000_000, "T"],
    [1_000_000_000, "G"],
    [1_000_000, "M"],
    [1_000, "K"],
  ];
  const unit = units.find(([threshold]) => value >= threshold);
  if (unit === undefined) {
    return formatNumber(value, 2);
  }
  return `${formatNumber(value / unit[0], 2)}${unit[1]}`;
}

function formatTimestamp(value: string | null): string {
  if (value === null) {
    return "Never";
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return "Unknown";
  }
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    year: "numeric",
  }).format(timestamp);
}

function formatRelativeTime(value: string | null): string {
  if (value === null) {
    return "Never";
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return "Unknown";
  }
  const elapsedSeconds = Math.round((Date.now() - timestamp) / 1_000);
  if (elapsedSeconds < 10) {
    return "just now";
  }
  if (elapsedSeconds < 60) {
    return `${elapsedSeconds}s ago`;
  }
  const elapsedMinutes = Math.round(elapsedSeconds / 60);
  if (elapsedMinutes < 60) {
    return `${elapsedMinutes}m ago`;
  }
  const elapsedHours = Math.round(elapsedMinutes / 60);
  if (elapsedHours < 48) {
    return `${elapsedHours}h ago`;
  }
  return `${Math.round(elapsedHours / 24)}d ago`;
}

function isStaleTimestamp(value: string | null): boolean {
  if (value === null) {
    return false;
  }
  return Date.now() - Date.parse(value) > STALE_AFTER_MS;
}

function displayMinerName(miner: Miner): string {
  return miner.name.trim().length > 0 ? miner.name : miner.miner_id;
}

interface MinerStatus {
  label: string;
  tone: "disabled" | "offline" | "online" | "stale";
}

function minerStatus(miner: Miner): MinerStatus {
  if (!miner.enabled) {
    return { label: "Disabled", tone: "disabled" };
  }
  if (!miner.online) {
    return { label: "Offline", tone: "offline" };
  }
  if (isStaleTimestamp(miner.last_success_at)) {
    return { label: "Stale", tone: "stale" };
  }
  return { label: "Online", tone: "online" };
}

function displayMinerMetadata(
  model: string | null,
  firmware: string | null,
): string {
  const modelText = model === null || model.trim().length === 0 ? "Unknown model" : model;
  const firmwareText =
    firmware === null || firmware.trim().length === 0
      ? "firmware unknown"
      : `firmware ${firmware}`;
  return `${modelText} / ${firmwareText}`;
}

function formatMeasurement(value: number | null, unit: string): string {
  return value === null ? `-- ${unit}` : `${formatNumber(value)} ${unit}`;
}

function formatUptime(value: number | null): string {
  return value === null ? "--" : `${formatNumber(value / 3_600, 2)} h`;
}

function formatCoverage(coverage: number, enabled: number): string {
  return `${formatNumber(coverage, 0)}/${formatNumber(enabled, 0)} reporting`;
}

function formatAggregateCount(value: number | null): string {
  return value === null ? "--" : formatNumber(value, 0);
}

const CHART_WIDTH = 640;
const CHART_HEIGHT = 168;
const CHART_PADDING = 12;
const HISTORY_GAP_MS = 10 * 60 * 1_000;

interface ChartPoint {
  at: number;
  value: number | null;
}

interface HistorySummary {
  latest: number;
  maximum: number;
  minimum: number;
}

function chartPoints(points: readonly TelemetryHistoryPoint[]): ChartPoint[] {
  return points
    .map((point) => ({ at: Date.parse(point.at), value: point.value }))
    .filter((point) => Number.isFinite(point.at));
}

function historySummary(
  points: readonly TelemetryHistoryPoint[],
): HistorySummary | null {
  const values = points.flatMap((point) => point.value === null ? [] : [point.value]);
  if (values.length === 0) {
    return null;
  }
  return {
    latest: values.at(-1) ?? values[0] ?? 0,
    maximum: Math.max(...values),
    minimum: Math.min(...values),
  };
}

export function createHistoryPath(
  points: readonly TelemetryHistoryPoint[],
): string {
  const chartData = chartPoints(points);
  const values = chartData.flatMap((point) => point.value === null ? [] : [point.value]);
  if (values.length === 0) {
    return "";
  }

  const timestamps = chartData.map((point) => point.at);
  const firstAt = Math.min(...timestamps);
  const lastAt = Math.max(...timestamps);
  const timeRange = Math.max(lastAt - firstAt, 1);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const valueRange = Math.max(maximum - minimum, Math.abs(maximum) * 0.1, 1);
  const valueFloor = (minimum + maximum - valueRange) / 2;
  const plotWidth = CHART_WIDTH - CHART_PADDING * 2;
  const plotHeight = CHART_HEIGHT - CHART_PADDING * 2;
  let previousAt: number | null = null;
  let hasPath = false;
  let path = "";

  for (const point of chartData) {
    if (point.value === null) {
      previousAt = null;
      continue;
    }
    const x = CHART_PADDING + ((point.at - firstAt) / timeRange) * plotWidth;
    const y =
      CHART_HEIGHT - CHART_PADDING - ((point.value - valueFloor) / valueRange) * plotHeight;
    const command = !hasPath || previousAt === null || point.at - previousAt > HISTORY_GAP_MS
      ? "M"
      : "L";
    path += `${command}${x.toFixed(2)} ${y.toFixed(2)} `;
    previousAt = point.at;
    hasPath = true;
  }
  return path.trim();
}

function parseGraphCardConfig(value: unknown): BitaxeFleetGraphCardConfig {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Bitaxe Fleet graph card configuration must be an object.");
  }
  const config = value as Record<string, unknown>;
  const requestedMetric = config["metric"];
  const metric = requestedMetric === undefined ? "hashrate" : graphCardMetric(requestedMetric);
  const requestedName = config["name"];
  if (requestedName !== undefined && typeof requestedName !== "string") {
    throw new Error("Bitaxe Fleet graph card name must be text.");
  }
  if (requestedName === undefined || requestedName.trim().length === 0) {
    return { metric };
  }
  return { metric, name: requestedName };
}

function parseOverviewCardConfig(value: unknown): BitaxeFleetOverviewCardConfig {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Bitaxe Fleet overview card configuration must be an object.");
  }
  const requestedName = (value as Record<string, unknown>)["name"];
  if (requestedName !== undefined && typeof requestedName !== "string") {
    throw new Error("Bitaxe Fleet overview card name must be text.");
  }
  if (requestedName === undefined || requestedName.trim().length === 0) {
    return {};
  }
  return { name: requestedName };
}

function graphCardMetric(value: unknown): FleetHistoryMetric {
  if (value === "efficiency" || value === "hashrate" || value === "power") {
    return value;
  }
  throw new Error(
    "Bitaxe Fleet graph card metric must be hashrate, power, or efficiency.",
  );
}

interface FleetGraphMetricDefinition {
  title: string;
  value: (number: number) => string;
}

function fleetGraphMetric(metric: FleetHistoryMetric): FleetGraphMetricDefinition {
  switch (metric) {
    case "hashrate":
      return { title: "Fleet hashrate", value: formatHashrate };
    case "power":
      return {
        title: "Fleet power",
        value: (number) => `${formatNumber(number, 2)} W`,
      };
    case "efficiency":
      return {
        title: "Fleet efficiency",
        value: (number) => `${formatNumber(number, 2)} J/TH`,
      };
  }
}

function actionLabel(action: MinerAction): string {
  switch (action) {
    case "restart":
      return "Restart";
    case "pause":
      return "Pause";
    case "resume":
      return "Resume";
    case "identify":
      return "Identify";
  }
}

function actionConfirmation(action: MinerAction, miner: Miner): string {
  const name = displayMinerName(miner);
  switch (action) {
    case "restart":
      return `Restart ${name}? Mining will be interrupted while the device reboots.`;
    case "pause":
      return `Pause mining on ${name}?`;
    case "resume":
      return `Resume mining on ${name}?`;
    case "identify":
      return `Run the identify action on ${name}?`;
  }
}

function readBoundedInteger(
  value: FormDataEntryValue | null,
  minimum: number,
  maximum: number,
): number | null {
  if (typeof value !== "string") {
    return null;
  }
  const parsed = Number(value);
  if (
    !Number.isInteger(parsed) ||
    parsed < minimum ||
    parsed > maximum
  ) {
    return null;
  }
  return parsed;
}

function isOverheatPolicy(value: string): value is OverheatPolicy {
  return (
    value === "keep_safe_values" ||
    value === "restore_after_cooldown" ||
    value === "log_only"
  );
}

function readPolicyForm(form: HTMLFormElement): RecoveryPolicy | null {
  const data = new FormData(form);
  const consecutiveUnhealthyRequired = readBoundedInteger(
    data.get("consecutive_unhealthy_required"),
    1,
    20,
  );
  const cooldownSeconds = readBoundedInteger(
    data.get("cooldown_seconds"),
    0,
    86_400,
  );
  const maxAttempts = readBoundedInteger(data.get("max_attempts"), 1, 20);
  const postRestartTimeoutSeconds = readBoundedInteger(
    data.get("post_restart_timeout_seconds"),
    30,
    3_600,
  );
  const rollingWindowSeconds = readBoundedInteger(
    data.get("rolling_window_seconds"),
    60,
    604_800,
  );
  const startupGraceSeconds = readBoundedInteger(
    data.get("startup_grace_seconds"),
    0,
    3_600,
  );
  const verificationTimeoutSeconds = readBoundedInteger(
    data.get("verification_timeout_seconds"),
    10,
    3_600,
  );
  const overheatPolicy = data.get("overheat_policy");

  if (
    consecutiveUnhealthyRequired === null ||
    cooldownSeconds === null ||
    maxAttempts === null ||
    postRestartTimeoutSeconds === null ||
    rollingWindowSeconds === null ||
    startupGraceSeconds === null ||
    verificationTimeoutSeconds === null ||
    typeof overheatPolicy !== "string" ||
    !isOverheatPolicy(overheatPolicy)
  ) {
    return null;
  }

  return {
    automatic_profile_restore_enabled: data.has(
      "automatic_profile_restore_enabled",
    ),
    automatic_recovery_enabled: data.has("automatic_recovery_enabled"),
    consecutive_unhealthy_required: consecutiveUnhealthyRequired,
    cooldown_seconds: cooldownSeconds,
    max_attempts: maxAttempts,
    overheat_policy: overheatPolicy,
    post_restart_timeout_seconds: postRestartTimeoutSeconds,
    rolling_window_seconds: rollingWindowSeconds,
    startup_grace_seconds: startupGraceSeconds,
    verification_timeout_seconds: verificationTimeoutSeconds,
  };
}

export class BitaxeFleetPanel extends LitElement {
  public static override properties = {
    hass: { attribute: false },
  };

  public declare hass: HomeAssistant | undefined;

  private fleet: FleetListResponse | null = null;
  private discovery: DiscoveryListResponse | null = null;
  private incidents: IncidentsListResponse | null = null;
  private scan: Scan | null = null;
  private feedback: Feedback | null = null;
  private loadedAt: number | null = null;
  private loading = false;
  private loadFailed = false;
  private logError = false;
  private logPending = false;
  private logs: string | null = null;
  private scanNetwork = "";
  private scanPending = false;
  private selectedMinerId: string | null = null;
  private selectedHistoryMinerId: string | null = null;
  private historyByMinerId = new Map<string, MinerTelemetryHistory>();
  private historyErrorMinerIds = new Set<string>();
  private historyPendingMinerIds = new Set<string>();
  private pendingCandidateIds = new Set<string>();
  private pendingMinerIds = new Set<string>();
  private initialLoadStarted = false;
  private refreshPromise: Promise<void> | undefined;
  private scanPollTimer: number | undefined;
  private staleClock: number | undefined;

  public static styles = css`
    :host {
      --fleet-border: var(--divider-color, rgba(127, 127, 127, 0.32));
      --fleet-canvas: var(--primary-background-color, #f5f7f8);
      --fleet-muted: var(--secondary-text-color, #65717b);
      --fleet-surface: var(--card-background-color, #ffffff);
      --fleet-accent: var(--primary-color, #0b6e69);
      --fleet-danger: var(--error-color, #c62828);
      --fleet-warning: var(--warning-color, #b26a00);
      --fleet-success: #25734d;
      color: var(--primary-text-color, #17212b);
      display: block;
      font-family: var(--primary-font-family, system-ui, sans-serif);
      min-block-size: 100%;
    }

    * {
      box-sizing: border-box;
    }

    main {
      margin: 0 auto;
      max-inline-size: 96rem;
      padding: clamp(1rem, 2.5vw, 2rem);
    }

    h1,
    h2,
    h3,
    p {
      margin: 0;
    }

    button,
    input,
    select {
      font: inherit;
    }

    button {
      background: transparent;
      border: 1px solid var(--fleet-border);
      border-radius: 0.4rem;
      color: inherit;
      cursor: pointer;
      font-size: 0.82rem;
      font-weight: 650;
      min-block-size: 2.15rem;
      padding: 0.38rem 0.68rem;
    }

    button:hover:not(:disabled) {
      border-color: var(--fleet-accent);
      color: var(--fleet-accent);
    }

    button:focus-visible,
    input:focus-visible,
    select:focus-visible,
    summary:focus-visible {
      outline: 2px solid var(--fleet-accent);
      outline-offset: 2px;
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.5;
    }

    .page-header {
      align-items: flex-start;
      border-block-end: 1px solid var(--fleet-border);
      display: flex;
      gap: 1.25rem;
      justify-content: space-between;
      margin-block-end: 1.25rem;
      padding-block-end: 1.1rem;
    }

    .eyebrow {
      color: var(--fleet-accent);
      font-size: 0.7rem;
      font-weight: 750;
      letter-spacing: 0.12em;
      margin-block-end: 0.35rem;
      text-transform: uppercase;
    }

    h1 {
      font-size: clamp(1.5rem, 3vw, 2rem);
      letter-spacing: -0.025em;
      line-height: 1.1;
    }

    h2 {
      font-size: 1rem;
      letter-spacing: -0.01em;
    }

    .subhead {
      color: var(--fleet-muted);
      font-size: 0.88rem;
      line-height: 1.45;
      margin-block-start: 0.45rem;
      max-inline-size: 46rem;
    }

    .header-actions {
      align-items: flex-end;
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
      white-space: nowrap;
    }

    .admin-badge {
      background: color-mix(in srgb, var(--fleet-warning) 12%, transparent);
      border: 1px solid color-mix(in srgb, var(--fleet-warning) 46%, transparent);
      border-radius: 99rem;
      color: var(--fleet-warning);
      font-size: 0.68rem;
      font-weight: 750;
      letter-spacing: 0.08em;
      padding: 0.28rem 0.55rem;
      text-transform: uppercase;
    }

    .primary-button {
      background: var(--fleet-accent);
      border-color: var(--fleet-accent);
      color: var(--text-primary-color, #ffffff);
    }

    .primary-button:hover:not(:disabled) {
      color: var(--text-primary-color, #ffffff);
      filter: brightness(1.08);
    }

    .notice,
    .state,
    .empty-state {
      border: 1px solid var(--fleet-border);
      border-radius: 0.5rem;
      font-size: 0.88rem;
      line-height: 1.45;
      margin-block-end: 1rem;
      padding: 0.75rem 0.9rem;
    }

    .notice {
      align-items: center;
      display: flex;
      gap: 0.55rem;
      justify-content: space-between;
    }

    .notice.success {
      border-inline-start: 4px solid var(--fleet-success);
    }

    .notice.error,
    .state.error {
      border-inline-start: 4px solid var(--fleet-danger);
    }

    .notice.warning {
      border-inline-start: 4px solid var(--fleet-warning);
    }

    .state,
    .empty-state {
      color: var(--fleet-muted);
    }

    .state button {
      margin-block-start: 0.55rem;
    }

    .section {
      background: var(--fleet-surface);
      border: 1px solid var(--fleet-border);
      border-radius: 0.65rem;
      margin-block: 1rem;
      overflow: hidden;
    }

    .section-header {
      align-items: baseline;
      display: flex;
      gap: 1rem;
      justify-content: space-between;
      padding: 1rem 1rem 0.8rem;
    }

    .section-description,
    .count,
    .muted {
      color: var(--fleet-muted);
      font-size: 0.8rem;
    }

    .section-description {
      line-height: 1.4;
      margin-block-start: 0.25rem;
    }

    .count {
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    .scan-layout {
      border-block-start: 1px solid var(--fleet-border);
      display: grid;
      gap: 1rem;
      grid-template-columns: minmax(16rem, 0.85fr) minmax(18rem, 1.15fr);
      padding: 1rem;
    }

    .scan-form {
      align-items: end;
      display: grid;
      gap: 0.65rem;
      grid-template-columns: minmax(0, 1fr) auto;
    }

    label {
      color: var(--fleet-muted);
      display: grid;
      font-size: 0.75rem;
      font-weight: 650;
      gap: 0.3rem;
      letter-spacing: 0.015em;
    }

    input,
    select {
      background: var(--fleet-canvas);
      border: 1px solid var(--fleet-border);
      border-radius: 0.35rem;
      color: var(--primary-text-color, #17212b);
      min-block-size: 2.2rem;
      padding: 0.35rem 0.5rem;
    }

    .form-help {
      color: var(--fleet-muted);
      font-size: 0.72rem;
      grid-column: 1 / -1;
      line-height: 1.35;
    }

    .scan-progress {
      border-inline-start: 2px solid var(--fleet-border);
      display: grid;
      gap: 0.5rem;
      padding-inline-start: 1rem;
    }

    .scan-progress strong {
      font-size: 0.88rem;
    }

    progress {
      accent-color: var(--fleet-accent);
      block-size: 0.48rem;
      inline-size: 100%;
    }

    .scan-error {
      color: var(--fleet-danger);
      font-size: 0.78rem;
    }

    .table-scroll {
      border-block-start: 1px solid var(--fleet-border);
      overflow-x: auto;
    }

    table {
      border-collapse: collapse;
      inline-size: 100%;
      min-inline-size: 70rem;
    }

    th,
    td {
      border-block-end: 1px solid var(--fleet-border);
      padding: 0.8rem 0.85rem;
      text-align: start;
      vertical-align: top;
    }

    tr:last-child td {
      border-block-end: 0;
    }

    th {
      background: color-mix(in srgb, var(--fleet-canvas) 82%, transparent);
      color: var(--fleet-muted);
      font-size: 0.68rem;
      font-weight: 750;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      white-space: nowrap;
    }

    td {
      font-size: 0.82rem;
    }

    .miner-name {
      display: block;
      font-size: 0.9rem;
      line-height: 1.2;
      margin-block-end: 0.2rem;
    }

    .miner-meta {
      color: var(--fleet-muted);
      display: block;
      font-size: 0.73rem;
      line-height: 1.35;
    }

    code {
      color: var(--fleet-muted);
      display: inline-block;
      font-family: var(--code-font-family, ui-monospace, monospace);
      font-size: 0.72rem;
      margin-block-start: 0.35rem;
      overflow-wrap: anywhere;
    }

    .endpoint-context {
      color: var(--fleet-muted);
      font-size: 0.66rem;
      margin-inline-start: 0.25rem;
      text-transform: uppercase;
    }

    .status-pill,
    .health-pill,
    .profile-pill {
      align-items: center;
      border: 1px solid currentColor;
      border-radius: 99rem;
      display: inline-flex;
      font-size: 0.68rem;
      font-weight: 700;
      gap: 0.3rem;
      line-height: 1;
      padding: 0.28rem 0.45rem;
      white-space: nowrap;
    }

    .status-pill::before {
      background: currentColor;
      border-radius: 50%;
      content: "";
      inline-size: 0.42rem;
      block-size: 0.42rem;
    }

    .online,
    .healthy,
    .profile-ready {
      color: var(--fleet-success);
    }

    .offline,
    .fault {
      color: var(--fleet-danger);
    }

    .stale,
    .attention,
    .profile-missing {
      color: var(--fleet-warning);
    }

    .disabled,
    .unknown {
      color: var(--fleet-muted);
    }

    .status-time {
      color: var(--fleet-muted);
      display: block;
      font-size: 0.72rem;
      margin-block-start: 0.4rem;
      white-space: nowrap;
    }

    .metric {
      display: block;
      font-variant-numeric: tabular-nums;
      line-height: 1.45;
      white-space: nowrap;
    }

    .fleet-summary {
      border-block-start: 1px solid var(--fleet-border);
      display: grid;
      grid-template-columns: minmax(13rem, 0.7fr) minmax(0, 2.3fr);
    }

    .fleet-summary-primary {
      background: color-mix(in srgb, var(--fleet-accent) 8%, transparent);
      display: grid;
      gap: 0.25rem;
      padding: 1rem;
    }

    .fleet-summary-primary span,
    .fleet-summary-metrics dt,
    .fleet-summary small {
      color: var(--fleet-muted);
      font-size: 0.68rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }

    .fleet-summary-primary strong {
      font-size: 1.45rem;
      letter-spacing: -0.03em;
      line-height: 1.1;
    }

    .fleet-summary-metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin: 0;
    }

    .fleet-summary-metrics > div {
      border-inline-start: 1px solid var(--fleet-border);
      display: grid;
      gap: 0.22rem;
      min-inline-size: 0;
      padding: 0.8rem;
    }

    .fleet-summary-metrics dt,
    .fleet-summary-metrics dd,
    .fleet-summary-metrics small {
      margin: 0;
    }

    .fleet-summary-metrics dd {
      font-size: 0.9rem;
      font-variant-numeric: tabular-nums;
      font-weight: 700;
      line-height: 1.25;
      overflow-wrap: anywhere;
    }

    .fleet-summary small {
      font-size: 0.62rem;
      letter-spacing: 0.025em;
      text-transform: none;
    }

    .history-panel {
      border-block-start: 1px solid var(--fleet-border);
      padding: 1rem;
    }

    .history-header {
      align-items: flex-start;
      display: flex;
      gap: 1rem;
      justify-content: space-between;
      margin-block-end: 0.85rem;
    }

    .history-header h3 {
      font-size: 0.92rem;
    }

    .history-header p {
      color: var(--fleet-muted);
      font-size: 0.76rem;
      line-height: 1.4;
      margin-block-start: 0.2rem;
    }

    .history-grid {
      display: grid;
      gap: 0.75rem;
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .history-chart {
      background: color-mix(in srgb, var(--fleet-canvas) 64%, transparent);
      border: 1px solid var(--fleet-border);
      border-radius: 0.45rem;
      margin: 0;
      min-inline-size: 0;
      overflow: hidden;
      padding: 0.7rem;
    }

    .history-chart figcaption {
      align-items: baseline;
      display: flex;
      gap: 0.5rem;
      justify-content: space-between;
      margin-block-end: 0.5rem;
    }

    .history-chart strong {
      font-size: 0.78rem;
    }

    .history-chart-summary {
      color: var(--fleet-muted);
      font-size: 0.67rem;
      font-variant-numeric: tabular-nums;
      text-align: end;
    }

    .history-chart svg {
      block-size: auto;
      display: block;
      inline-size: 100%;
      min-inline-size: 13rem;
    }

    .history-gridline {
      stroke: color-mix(in srgb, var(--fleet-border) 85%, transparent);
      stroke-width: 1;
    }

    .history-line {
      fill: none;
      stroke: var(--fleet-accent);
      stroke-linecap: round;
      stroke-linejoin: round;
      stroke-width: 3;
    }

    .history-chart.power .history-line {
      stroke: var(--fleet-warning);
    }

    .history-chart.temperature .history-line {
      stroke: var(--fleet-danger);
    }

    .history-empty {
      color: var(--fleet-muted);
      font-size: 0.78rem;
      line-height: 1.4;
      padding-block: 1rem;
    }

    .health-list,
    .actions,
    .profile-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
    }

    .health-list {
      min-inline-size: 9rem;
    }

    .profile-actions {
      margin-block-start: 0.45rem;
    }

    .actions {
      min-inline-size: 12rem;
    }

    .danger-button:hover:not(:disabled) {
      border-color: var(--fleet-danger);
      color: var(--fleet-danger);
    }

    details {
      margin-block-start: 0.55rem;
    }

    summary {
      color: var(--fleet-muted);
      cursor: pointer;
      font-size: 0.72rem;
      font-weight: 650;
      width: fit-content;
    }

    .policy-form {
      border-block-start: 1px dashed var(--fleet-border);
      display: grid;
      gap: 0.65rem;
      margin-block-start: 0.55rem;
      padding-block-start: 0.65rem;
    }

    .policy-toggles {
      display: grid;
      gap: 0.45rem;
    }

    .policy-toggles label {
      align-items: center;
      display: flex;
      font-size: 0.72rem;
      gap: 0.42rem;
    }

    .policy-toggles input {
      min-block-size: auto;
    }

    .policy-grid {
      display: grid;
      gap: 0.5rem;
      grid-template-columns: repeat(2, minmax(8rem, 1fr));
    }

    .policy-grid label {
      min-inline-size: 0;
    }

    .policy-grid input,
    .policy-grid select {
      inline-size: 100%;
      min-inline-size: 0;
    }

    .candidate-table {
      min-inline-size: 52rem;
    }

    .diagnostics {
      border: 0;
      background: transparent;
      overflow: visible;
    }

    .diagnostics > .section-header {
      padding-inline: 0;
    }

    .diagnostics-grid {
      display: grid;
      gap: 1rem;
      grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
    }

    .diagnostic-card {
      background: var(--fleet-surface);
      border: 1px solid var(--fleet-border);
      border-radius: 0.65rem;
      min-inline-size: 0;
      overflow: hidden;
    }

    .diagnostic-card header {
      align-items: center;
      border-block-end: 1px solid var(--fleet-border);
      display: flex;
      gap: 0.65rem;
      justify-content: space-between;
      padding: 0.85rem 0.9rem;
    }

    .log-controls {
      align-items: center;
      display: flex;
      gap: 0.45rem;
      min-inline-size: 0;
    }

    .log-controls select {
      max-inline-size: 14rem;
      min-inline-size: 8rem;
    }

    .log-state,
    .incident-empty {
      color: var(--fleet-muted);
      font-size: 0.8rem;
      line-height: 1.45;
      padding: 0.9rem;
    }

    pre {
      background: color-mix(in srgb, var(--fleet-canvas) 78%, transparent);
      color: var(--primary-text-color, #17212b);
      font-family: var(--code-font-family, ui-monospace, monospace);
      font-size: 0.75rem;
      line-height: 1.45;
      margin: 0;
      max-block-size: 25rem;
      overflow: auto;
      padding: 0.9rem;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .incidents-table {
      min-inline-size: 38rem;
    }

    .incident-detail {
      color: var(--fleet-muted);
      display: block;
      font-size: 0.72rem;
      margin-block-start: 0.22rem;
      overflow-wrap: anywhere;
    }

    @media (max-width: 780px) {
      main {
        padding: 1rem;
      }

      .page-header,
      .section-header,
      .diagnostic-card header {
        align-items: flex-start;
        flex-direction: column;
      }

      .header-actions {
        align-items: flex-start;
        flex-direction: row;
        flex-wrap: wrap;
      }

      .scan-layout,
      .diagnostics-grid,
      .fleet-summary,
      .history-grid {
        grid-template-columns: 1fr;
      }

      .fleet-summary-metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .scan-progress {
        border-block-start: 1px solid var(--fleet-border);
        border-inline-start: 0;
        padding-block-start: 0.9rem;
        padding-inline-start: 0;
      }

      .log-controls {
        inline-size: 100%;
      }

      .history-header {
        flex-direction: column;
      }

      .log-controls select {
        flex: 1;
        max-inline-size: none;
      }
    }

    @media (max-width: 460px) {
      .scan-form {
        grid-template-columns: 1fr;
      }

      .fleet-summary-metrics {
        grid-template-columns: 1fr;
      }

      .policy-grid {
        grid-template-columns: 1fr;
      }
    }
  `;

  public override connectedCallback(): void {
    super.connectedCallback();
    this.staleClock = window.setInterval(() => this.requestUpdate(), STALE_CLOCK_INTERVAL_MS);
    this.loadWhenHassAvailable();
  }

  public override disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this.staleClock !== undefined) {
      window.clearInterval(this.staleClock);
      this.staleClock = undefined;
    }
    this.clearScanPoll();
  }

  protected override updated(changedProperties: PropertyValues<this>): void {
    if (!changedProperties.has("hass")) {
      return;
    }

    if (this.hass === undefined) {
      this.initialLoadStarted = false;
      this.clearScanPoll();
      return;
    }

    this.loadWhenHassAvailable();
  }

  protected override render() {
    return html`
      <main>
        ${this.renderHeader()} ${this.renderFeedback()} ${this.renderDataState()}
        ${this.renderScanSection()} ${this.renderFleetSection()}
        ${this.renderCandidatesSection()} ${this.renderDiagnosticsSection()}
      </main>
    `;
  }

  private renderHeader() {
    return html`
      <header class="page-header">
        <div>
          <p class="eyebrow">Administrator console</p>
          <h1>Bitaxe Fleet</h1>
          <p class="subhead">
            Operational controls use Home Assistant's administrator-only WebSocket
            boundary. Endpoints are shown for identification only and are never
            fetched directly by this panel.
          </p>
        </div>
        <div class="header-actions">
          <span class="admin-badge">Admin only</span>
          <button
            class="primary-button"
            ?disabled=${this.loading || this.hass === undefined}
            @click=${this.handleRefresh}
          >
            ${this.loading ? "Refreshing..." : "Refresh fleet"}
          </button>
        </div>
      </header>
    `;
  }

  private renderFeedback() {
    if (this.feedback === null) {
      return nothing;
    }
    return html`
      <div class="notice ${this.feedback.tone}" role="status">
        <span>${this.feedback.text}</span>
        <button @click=${this.clearFeedback}>Dismiss</button>
      </div>
    `;
  }

  private renderDataState() {
    if (this.hass === undefined) {
      return html`
        <div class="state" role="status">
          Waiting for the Home Assistant connection before loading fleet data.
        </div>
      `;
    }

    if (!this.hasLoadedData() && this.loading) {
      return html`
        <div class="state" role="status">
          Loading enrolled miners, pending discovery candidates, and incident history...
        </div>
      `;
    }

    if (!this.hasLoadedData() && this.loadFailed) {
      return html`
        <div class="state error" role="alert">
          The panel could not load data from the Bitaxe Fleet integration.
          <br />
          <button @click=${this.handleRefresh}>Try again</button>
        </div>
      `;
    }

    if (this.hasLoadedData() && this.dataIsStale()) {
      return html`
        <div class="notice warning" role="status">
          <span>
            Showing cached fleet data. Refresh it before making a time-sensitive
            operational decision.
          </span>
          <button @click=${this.handleRefresh}>Refresh</button>
        </div>
      `;
    }

    return nothing;
  }

  private renderScanSection() {
    const scan = this.scan;
    const scanning = scan?.running === true;
    return html`
      <section class="section" aria-labelledby="scan-title">
        <header class="section-header">
          <div>
            <h2 id="scan-title">Private-network discovery</h2>
            <p class="section-description">
              Scan a bounded private CIDR for candidates that still require an
              administrator's approval.
            </p>
          </div>
          <span class="count">${scan?.discovered_candidates ?? 0} found</span>
        </header>
        <div class="scan-layout">
          <form class="scan-form" @submit=${this.handleScanSubmit}>
            <label>
              CIDR network
              <input
                aria-describedby="scan-help"
                autocomplete="off"
                inputmode="text"
                name="network"
                placeholder="192.168.1.0/24"
                .value=${this.scanNetwork}
                @input=${this.handleScanInput}
              />
            </label>
            <button
              class="primary-button"
              type="submit"
              ?disabled=${
                this.hass === undefined || this.scanPending || scanning
              }
            >
              ${this.scanPending || scanning ? "Scanning..." : "Start scan"}
            </button>
            <span class="form-help" id="scan-help">
              Only private networks accepted by the integration can be scanned.
            </span>
          </form>
          ${this.renderScanProgress(scan)}
        </div>
      </section>
    `;
  }

  private renderScanProgress(scan: Scan | null) {
    if (scan === null || scan.network === null) {
      return html`
        <div class="scan-progress" aria-live="polite">
          <strong>No scan is running</strong>
          <span class="muted">Enter a private CIDR to begin discovery.</span>
        </div>
      `;
    }

    if (scan.running) {
      const completed = Math.min(scan.completed_hosts, scan.total_hosts);
      return html`
        <div class="scan-progress" aria-live="polite">
          <strong>Scanning ${scan.network}</strong>
          <progress max=${Math.max(scan.total_hosts, 1)} value=${completed}></progress>
          <span class="muted">
            ${formatNumber(completed, 0)} of ${formatNumber(scan.total_hosts, 0)}
            hosts checked, ${formatNumber(scan.discovered_candidates, 0)} candidates found
          </span>
        </div>
      `;
    }

    return html`
      <div class="scan-progress" aria-live="polite">
        <strong>Last scan: ${scan.network}</strong>
        <span class="muted">
          ${formatNumber(scan.completed_hosts, 0)} hosts checked, completed
          ${formatRelativeTime(scan.completed_at)}
        </span>
        ${
          scan.error === null
            ? nothing
            : html`<span class="scan-error">Scan reported: ${scan.error}</span>`
        }
      </div>
    `;
  }

  private renderFleetSection() {
    return html`
      <section class="section" aria-labelledby="fleet-title">
        <header class="section-header">
          <div>
            <h2 id="fleet-title">Enrolled fleet</h2>
            <p class="section-description">
              Current coordinator state, bounded telemetry, recovery profiles, and
              explicit miner actions.
            </p>
          </div>
          <span class="count">${this.fleet?.miners.length ?? 0} miners</span>
        </header>
        ${this.renderFleetBody()}
      </section>
    `;
  }

  private renderFleetBody() {
    if (this.fleet === null) {
      return this.renderUnavailable("enrolled miners");
    }
    if (this.fleet.miners.length === 0) {
      return html`
        <div class="empty-state">
          No miners are enrolled yet. Run discovery, then approve a verified candidate
          to add it to the fleet.
        </div>
      `;
    }
    return html`
      ${this.renderFleetSummary(this.fleet.aggregates)}
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Miner</th>
              <th scope="col">Coordinator</th>
              <th scope="col">Telemetry</th>
              <th scope="col">Safety state</th>
              <th scope="col">Profile &amp; recovery</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${this.fleet.miners.map((miner) => this.renderMinerRow(miner))}
          </tbody>
        </table>
      </div>
      ${this.renderHistoryPanel()}
    `;
  }

  private renderFleetSummary(aggregates: FleetAggregates | null) {
    if (aggregates === null) {
      return nothing;
    }
    return html`
      <div class="fleet-summary" aria-label="Fleet performance summary">
        <div class="fleet-summary-primary">
          <span>Fleet hashrate</span>
          <strong>${formatHashrate(aggregates.total_hashrate_gh_s)}</strong>
          <small>
            ${formatCoverage(aggregates.hashrate_coverage, aggregates.enabled_miners)}
          </small>
        </div>
        <dl class="fleet-summary-metrics">
          <div>
            <dt>Power</dt>
            <dd>${formatMeasurement(aggregates.total_power_w, "W")}</dd>
            <small>${formatCoverage(aggregates.power_coverage, aggregates.enabled_miners)}</small>
          </div>
          <div>
            <dt>Efficiency</dt>
            <dd>${formatMeasurement(aggregates.efficiency_j_th, "J/TH")}</dd>
            <small>
              ${formatNumber(aggregates.hashrate_coverage, 0)} hash / ${formatNumber(
                aggregates.power_coverage,
                0,
              )} power
            </small>
          </div>
          <div>
            <dt>Best difficulty</dt>
            <dd>${formatDifficulty(aggregates.best_difficulty)}</dd>
            <small>
              ${formatCoverage(
                aggregates.best_difficulty_coverage,
                aggregates.enabled_miners,
              )}
            </small>
          </div>
          <div>
            <dt>Cumulative uptime</dt>
            <dd>${formatUptime(aggregates.total_uptime_seconds)}</dd>
            <small>${formatCoverage(aggregates.uptime_coverage, aggregates.enabled_miners)}</small>
          </div>
          <div>
            <dt>Online</dt>
            <dd>
              ${formatNumber(aggregates.online_miners, 0)} / ${formatNumber(
                aggregates.enabled_miners,
                0,
              )}
            </dd>
            <small>fresh coordinators</small>
          </div>
          <div>
            <dt>Safety</dt>
            <dd>
              ${formatAggregateCount(aggregates.unhealthy_miners)} unhealthy / ${formatAggregateCount(
                aggregates.overheating_miners,
              )} hot
            </dd>
            <small>
              ${formatNumber(aggregates.unhealthy_coverage, 0)} health / ${formatNumber(
                aggregates.overheat_coverage,
                0,
              )} thermal
            </small>
          </div>
        </dl>
      </div>
    `;
  }

  private renderMinerRow(miner: Miner) {
    const busy = this.pendingMinerIds.has(miner.miner_id);
    const status = minerStatus(miner);
    const paused = miner.health?.mining_paused;
    return html`
      <tr>
        <td>
          <strong class="miner-name">${displayMinerName(miner)}</strong>
          <span class="miner-meta">
            ${displayMinerMetadata(miner.model, miner.firmware)}
          </span>
          <code title="Shown for identification only; the panel does not contact this endpoint directly."
            >${miner.endpoint}</code
          >
          <span class="endpoint-context">admin endpoint</span>
        </td>
        <td>
          <span class="status-pill ${status.tone}">${status.label}</span>
          <span class="status-time" title=${formatTimestamp(miner.last_success_at)}>
            Last success: ${formatRelativeTime(miner.last_success_at)}
          </span>
        </td>
        <td>${this.renderTelemetry(miner.telemetry)}</td>
        <td>${this.renderHealth(miner.health)}</td>
        <td>
          <span
            class="profile-pill ${
              miner.profile === null ? "profile-missing" : "profile-ready"
            }"
          >
            ${miner.profile === null ? "No saved profile" : "Profile captured"}
          </span>
          <div class="profile-actions">
            <button
              ?disabled=${busy}
              @click=${() => void this.captureProfile(miner)}
            >
              Capture
            </button>
            <button
              ?disabled=${busy || miner.profile === null}
              @click=${() => void this.applyProfile(miner)}
            >
              Apply
            </button>
          </div>
          ${this.renderPolicyEditor(miner, busy)}
        </td>
        <td>
          <div class="actions">
            <button @click=${() => void this.toggleHistory(miner)}>
              ${this.selectedHistoryMinerId === miner.miner_id ? "Hide history" : "History"}
            </button>
            <button
              class="danger-button"
              ?disabled=${busy}
              @click=${() => void this.runMinerAction(miner, "restart")}
            >
              Restart
            </button>
            <button
              ?disabled=${busy || paused === true}
              @click=${() => void this.runMinerAction(miner, "pause")}
            >
              Pause
            </button>
            <button
              ?disabled=${busy || paused === false}
              @click=${() => void this.runMinerAction(miner, "resume")}
            >
              Resume
            </button>
            <button
              ?disabled=${busy}
              @click=${() => void this.runMinerAction(miner, "identify")}
            >
              Identify
            </button>
          </div>
        </td>
      </tr>
    `;
  }

  private renderTelemetry(telemetry: Telemetry | null) {
    if (telemetry === null) {
      return html`<span class="muted">Awaiting telemetry</span>`;
    }
    return html`
      <span class="metric">${formatHashrate(telemetry.hashrate_gh_s)}</span>
      <span class="metric">${formatMeasurement(telemetry.power_w, "W")}</span>
      <span class="metric">${formatMeasurement(telemetry.temperature_c, "deg C")}</span>
      <span class="metric">Best difficulty: ${formatDifficulty(telemetry.best_difficulty)}</span>
    `;
  }

  private renderHistoryPanel() {
    const miner = this.fleet?.miners.find(
      (candidate) => candidate.miner_id === this.selectedHistoryMinerId,
    );
    if (miner === undefined) {
      return nothing;
    }
    const history = this.historyByMinerId.get(miner.miner_id);
    const pending = this.historyPendingMinerIds.has(miner.miner_id);
    const failed = this.historyErrorMinerIds.has(miner.miner_id);
    return html`
      <section class="history-panel" aria-labelledby="history-title">
        <header class="history-header">
          <div>
            <h3 id="history-title">History: ${displayMinerName(miner)}</h3>
            <p>
              Recorder-backed telemetry for the past 24 hours. Missing readings are
              shown as gaps rather than zero.
            </p>
          </div>
          <button
            ?disabled=${pending || this.hass === undefined}
            @click=${() => void this.loadHistory(miner)}
          >
            ${pending ? "Loading history..." : "Refresh history"}
          </button>
        </header>
        ${
          pending
            ? html`<p class="history-empty" role="status">Loading recorder history...</p>`
            : failed
              ? html`
                  <p class="history-empty" role="alert">
                    History could not be loaded. Check Recorder availability and try again.
                  </p>
                `
              : history === undefined
                ? html`<p class="history-empty">History has not been requested yet.</p>`
                : !history.available
                  ? html`
                      <p class="history-empty">
                        Home Assistant Recorder is unavailable, so no historical data can be
                        shown.
                      </p>
                    `
                  : this.renderHistoryCharts(history)
        }
      </section>
    `;
  }

  private renderHistoryCharts(history: MinerTelemetryHistory) {
    const series = history.series;
    if (
      historySummary(series.hashrate_gh_s) === null &&
      historySummary(series.power_w) === null &&
      historySummary(series.temperature_c) === null
    ) {
      return html`
        <p class="history-empty">
          No recorded history is available yet. Home Assistant starts recording after these
          sensors are added and only retains data allowed by its Recorder settings.
        </p>
      `;
    }
    return html`
      <div class="history-grid">
        ${this.renderHistoryChart(
          "Hashrate",
          "GH/s",
          "hashrate",
          series.hashrate_gh_s,
          formatHashrate,
        )}
        ${this.renderHistoryChart("Power", "W", "power", series.power_w)}
        ${this.renderHistoryChart(
          "Temperature",
          "deg C",
          "temperature",
          series.temperature_c,
        )}
      </div>
    `;
  }

  private renderHistoryChart(
    title: string,
    unit: string,
    tone: "hashrate" | "power" | "temperature",
    points: readonly TelemetryHistoryPoint[],
    formatter?: (value: number) => string,
  ) {
    const summary = historySummary(points);
    if (summary === null) {
      return html`
        <figure class="history-chart ${tone}">
          <figcaption><strong>${title}</strong></figcaption>
          <p class="history-empty">No recorded data.</p>
        </figure>
      `;
    }
    const path = createHistoryPath(points);
    const formatValue = formatter ?? ((value: number) => formatMeasurement(value, unit));
    return html`
      <figure class="history-chart ${tone}">
        <figcaption>
          <strong>${title}</strong>
          <span class="history-chart-summary">
            ${formatValue(summary.latest)} latest
          </span>
        </figcaption>
        <svg
          aria-label=${`${title} history`}
          role="img"
          viewBox="0 0 ${CHART_WIDTH} ${CHART_HEIGHT}"
        >
          <line
            class="history-gridline"
            x1=${CHART_PADDING}
            x2=${CHART_WIDTH - CHART_PADDING}
            y1=${CHART_HEIGHT / 2}
            y2=${CHART_HEIGHT / 2}
          ></line>
          <path class="history-line" d=${path}></path>
        </svg>
        <span class="history-chart-summary">
          Min ${formatValue(summary.minimum)} / max ${formatValue(summary.maximum)}
        </span>
      </figure>
    `;
  }

  private renderHealth(health: MinerHealth | null) {
    if (health === null) {
      return html`<span class="health-pill unknown">Unknown</span>`;
    }
    const states: Array<{ label: string; tone: "attention" | "fault" }> = [];
    if (health.mining_paused === true) {
      states.push({ label: "Mining paused", tone: "attention" });
    }
    if (
      health.overheat_mode === true ||
      (typeof health.overheat_mode === "number" && health.overheat_mode !== 0)
    ) {
      states.push({ label: "Overheat mode", tone: "attention" });
    }
    if (health.power_fault) {
      states.push({ label: "Power fault", tone: "fault" });
    }
    if (health.hardware_fault) {
      states.push({ label: "Hardware fault", tone: "fault" });
    }
    if (states.length === 0) {
      if (health.mining_paused === null && health.overheat_mode === null) {
        return html`<span class="health-pill unknown">Unknown</span>`;
      }
      return html`<span class="health-pill healthy">Nominal</span>`;
    }
    return html`
      <div class="health-list">
        ${states.map(
          (state) => html`<span class="health-pill ${state.tone}">
            ${state.label}
          </span>`,
        )}
      </div>
    `;
  }

  private renderPolicyEditor(miner: Miner, busy: boolean) {
    const policy = miner.policy;
    return html`
      <details>
        <summary>Recovery policy</summary>
        <form
          class="policy-form"
          @submit=${(event: Event) => this.handlePolicySubmit(event, miner)}
        >
          <div class="policy-toggles">
            <label>
              <input
                name="automatic_recovery_enabled"
                type="checkbox"
                ?checked=${policy.automatic_recovery_enabled}
              />
              Enable automatic recovery
            </label>
            <label>
              <input
                name="automatic_profile_restore_enabled"
                type="checkbox"
                ?checked=${policy.automatic_profile_restore_enabled}
              />
              Restore saved profile after recovery
            </label>
          </div>
          <div class="policy-grid">
            <label>
              Startup grace (s)
              <input
                max="3600"
                min="0"
                name="startup_grace_seconds"
                required
                step="1"
                type="number"
                .value=${String(policy.startup_grace_seconds)}
              />
            </label>
            <label>
              Unhealthy checks
              <input
                max="20"
                min="1"
                name="consecutive_unhealthy_required"
                required
                step="1"
                type="number"
                .value=${String(policy.consecutive_unhealthy_required)}
              />
            </label>
            <label>
              Cooldown (s)
              <input
                max="86400"
                min="0"
                name="cooldown_seconds"
                required
                step="1"
                type="number"
                .value=${String(policy.cooldown_seconds)}
              />
            </label>
            <label>
              Maximum attempts
              <input
                max="20"
                min="1"
                name="max_attempts"
                required
                step="1"
                type="number"
                .value=${String(policy.max_attempts)}
              />
            </label>
            <label>
              Rolling window (s)
              <input
                max="604800"
                min="60"
                name="rolling_window_seconds"
                required
                step="1"
                type="number"
                .value=${String(policy.rolling_window_seconds)}
              />
            </label>
            <label>
              Restart timeout (s)
              <input
                max="3600"
                min="30"
                name="post_restart_timeout_seconds"
                required
                step="1"
                type="number"
                .value=${String(policy.post_restart_timeout_seconds)}
              />
            </label>
            <label>
              Verify timeout (s)
              <input
                max="3600"
                min="10"
                name="verification_timeout_seconds"
                required
                step="1"
                type="number"
                .value=${String(policy.verification_timeout_seconds)}
              />
            </label>
            <label>
              Overheat behavior
              <select name="overheat_policy" .value=${policy.overheat_policy}>
                <option value="keep_safe_values">Keep safe values</option>
                <option value="restore_after_cooldown">Restore after cooldown</option>
                <option value="log_only">Log only</option>
              </select>
            </label>
          </div>
          <button type="submit" ?disabled=${busy}>Save recovery policy</button>
        </form>
      </details>
    `;
  }

  private renderCandidatesSection() {
    return html`
      <section class="section" aria-labelledby="candidates-title">
        <header class="section-header">
          <div>
            <h2 id="candidates-title">Pending approval</h2>
            <p class="section-description">
              Candidates have passed discovery identity checks but are not enrolled
              until an administrator approves them.
            </p>
          </div>
          <span class="count">${this.discovery?.candidates.length ?? 0} pending</span>
        </header>
        ${this.renderCandidatesBody()}
      </section>
    `;
  }

  private renderCandidatesBody() {
    if (this.discovery === null) {
      return this.renderUnavailable("pending candidates");
    }
    if (this.discovery.candidates.length === 0) {
      return html`
        <div class="empty-state">
          No candidates need approval. Start a private-network scan to look for
          additional devices.
        </div>
      `;
    }
    return html`
      <div class="table-scroll">
        <table class="candidate-table">
          <thead>
            <tr>
              <th scope="col">Candidate</th>
              <th scope="col">Endpoint</th>
              <th scope="col">Discovery</th>
              <th scope="col">Approval</th>
            </tr>
          </thead>
          <tbody>
            ${this.discovery.candidates.map((candidate) => {
              const busy = this.pendingCandidateIds.has(candidate.miner_id);
              return html`
                <tr>
                  <td>
                    <strong class="miner-name">${candidate.name}</strong>
                    <span class="miner-meta"
                      >${displayMinerMetadata(candidate.model, candidate.firmware)}</span
                    >
                  </td>
                  <td>
                    <code>${candidate.endpoint}</code>
                    <span class="endpoint-context">admin endpoint</span>
                  </td>
                  <td>
                    <span class="metric">${candidate.source}</span>
                    <span
                      class="miner-meta"
                      title=${formatTimestamp(candidate.last_seen_at)}
                    >
                      Seen ${formatRelativeTime(candidate.last_seen_at)}
                    </span>
                  </td>
                  <td>
                    <div class="actions">
                      <button
                        class="primary-button"
                        ?disabled=${busy}
                        @click=${() => void this.approveCandidate(candidate)}
                      >
                        Approve
                      </button>
                      <button
                        class="danger-button"
                        ?disabled=${busy}
                        @click=${() => void this.rejectCandidate(candidate)}
                      >
                        Reject
                      </button>
                    </div>
                  </td>
                </tr>
              `;
            })}
          </tbody>
        </table>
      </div>
    `;
  }

  private renderDiagnosticsSection() {
    return html`
      <section class="section diagnostics" aria-labelledby="diagnostics-title">
        <header class="section-header">
          <div>
            <h2 id="diagnostics-title">Diagnostics</h2>
            <p class="section-description">
              Redacted firmware logs and bounded incident summaries are available to
              administrators here.
            </p>
          </div>
        </header>
        <div class="diagnostics-grid">
          ${this.renderLogsCard()} ${this.renderIncidentsCard()}
        </div>
      </section>
    `;
  }

  private renderLogsCard() {
    const miners = this.fleet?.miners ?? [];
    return html`
      <article class="diagnostic-card" aria-labelledby="logs-title">
        <header>
          <h3 id="logs-title">Miner logs</h3>
          <div class="log-controls">
            <select
              aria-label="Miner for logs"
              .value=${this.selectedMinerId ?? ""}
              ?disabled=${miners.length === 0}
              @change=${this.handleSelectedMinerChange}
            >
              <option value="">Select miner</option>
              ${miners.map(
                (miner) => html`
                  <option value=${miner.miner_id}>${displayMinerName(miner)}</option>
                `,
              )}
            </select>
            <button
              ?disabled=${
                this.selectedMinerId === null || this.logPending || miners.length === 0
              }
              @click=${this.handleLoadLogs}
            >
              ${this.logPending ? "Loading..." : "Load logs"}
            </button>
          </div>
        </header>
        ${this.renderLogsBody()}
      </article>
    `;
  }

  private renderLogsBody() {
    if (this.logPending) {
      return html`<p class="log-state" role="status">Loading redacted miner logs...</p>`;
    }
    if (this.logError) {
      return html`
        <p class="log-state" role="alert">
          Logs could not be loaded for the selected miner. Try again after refreshing
          the fleet.
        </p>
      `;
    }
    if (this.logs === null) {
      return html`
        <p class="log-state">Select an enrolled miner, then request its redacted logs.</p>
      `;
    }
    if (this.logs.length === 0) {
      return html`<p class="log-state">The miner returned no log lines.</p>`;
    }
    return html`<pre aria-label="Redacted miner logs">${this.logs}</pre>`;
  }

  private renderIncidentsCard() {
    return html`
      <article class="diagnostic-card" aria-labelledby="incidents-title">
        <header>
          <h3 id="incidents-title">Recent incidents</h3>
          <span class="count">${this.incidents?.incidents.length ?? 0} recorded</span>
        </header>
        ${this.renderIncidentsBody()}
      </article>
    `;
  }

  private renderIncidentsBody() {
    if (this.incidents === null) {
      if (this.hass === undefined) {
        return html`
          <p class="incident-empty" role="status">
            Waiting for the Home Assistant connection before loading incidents.
          </p>
        `;
      }
      if (this.loading) {
        return html`<p class="incident-empty" role="status">Loading incident history...</p>`;
      }
      return html`
        <p class="incident-empty" role="alert">
          Incident history is unavailable until the panel can refresh it.
        </p>
      `;
    }
    if (this.incidents.incidents.length === 0) {
      return html`<p class="incident-empty">No incidents have been recorded.</p>`;
    }
    return html`
      <div class="table-scroll">
        <table class="incidents-table">
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Miner</th>
              <th scope="col">Incident</th>
              <th scope="col">Outcome</th>
            </tr>
          </thead>
          <tbody>
            ${this.incidents.incidents.map(
              (incident) => html`
                <tr>
                  <td title=${formatTimestamp(incident.occurred_at)}>
                    ${formatRelativeTime(incident.occurred_at)}
                  </td>
                  <td><code>${incident.miner_id}</code></td>
                  <td>
                    <strong>${incident.cause}</strong>
                    <span class="incident-detail">${incident.detail}</span>
                  </td>
                  <td>${incident.outcome}</td>
                </tr>
              `,
            )}
          </tbody>
        </table>
      </div>
    `;
  }

  private renderUnavailable(subject: string) {
    if (this.hass === undefined) {
      return html`
        <div class="state" role="status">
          Waiting for the Home Assistant connection before loading ${subject}.
        </div>
      `;
    }
    if (this.loading) {
      return html`<div class="state" role="status">Loading ${subject}...</div>`;
    }
    return html`
      <div class="state error" role="alert">
        ${subject} are unavailable because their WebSocket response could not be
        validated.
      </div>
    `;
  }

  private hasLoadedData(): boolean {
    return this.fleet !== null || this.discovery !== null || this.incidents !== null;
  }

  private dataIsStale(): boolean {
    return (
      this.loadFailed ||
      (this.loadedAt !== null && Date.now() - this.loadedAt > STALE_AFTER_MS)
    );
  }

  private readonly handleRefresh = (): void => {
    void this.refresh();
  };

  private readonly clearFeedback = (): void => {
    this.feedback = null;
    this.requestUpdate();
  };

  private readonly handleScanInput = (event: Event): void => {
    if (event.target instanceof HTMLInputElement) {
      this.scanNetwork = event.target.value;
    }
  };

  private readonly handleScanSubmit = (event: Event): void => {
    event.preventDefault();
    void this.startScan();
  };

  private readonly handleSelectedMinerChange = (event: Event): void => {
    if (!(event.target instanceof HTMLSelectElement)) {
      return;
    }
    this.selectedMinerId = event.target.value || null;
    this.logs = null;
    this.logError = false;
    this.requestUpdate();
  };

  private readonly handleLoadLogs = (): void => {
    void this.loadLogs();
  };

  private async toggleHistory(miner: Miner): Promise<void> {
    if (this.selectedHistoryMinerId === miner.miner_id) {
      this.selectedHistoryMinerId = null;
      this.requestUpdate();
      return;
    }
    this.selectedHistoryMinerId = miner.miner_id;
    this.requestUpdate();
    if (!this.historyByMinerId.has(miner.miner_id)) {
      await this.loadHistory(miner);
    }
  }

  private async loadHistory(miner: Miner): Promise<void> {
    if (this.historyPendingMinerIds.has(miner.miner_id)) {
      return;
    }
    const hass = this.hass;
    if (hass === undefined) {
      return;
    }

    this.historyPendingMinerIds.add(miner.miner_id);
    this.historyErrorMinerIds.delete(miner.miner_id);
    this.requestUpdate();
    try {
      const response = parseMinerTelemetryHistory(
        await hass.callWS({
          type: "bitaxe_fleet/miner/history",
          miner_id: miner.miner_id,
        }),
      );
      if (response.miner_id !== miner.miner_id) {
        invalidDto();
      }
      if (this.hass === undefined) {
        return;
      }
      this.historyByMinerId.set(miner.miner_id, response);
    } catch {
      if (this.hass !== undefined) {
        this.historyErrorMinerIds.add(miner.miner_id);
      }
    } finally {
      this.historyPendingMinerIds.delete(miner.miner_id);
      this.requestUpdate();
    }
  }

  private loadWhenHassAvailable(): void {
    if (this.hass === undefined || this.initialLoadStarted) {
      return;
    }
    this.initialLoadStarted = true;
    void this.refresh();
  }

  private refresh(): Promise<void> {
    const hass = this.hass;
    if (hass === undefined) {
      return Promise.resolve();
    }
    if (this.refreshPromise !== undefined) {
      return this.refreshPromise;
    }

    const request = this.loadDashboard(hass);
    this.refreshPromise = request;
    void request.then(
      () => this.clearRefresh(request),
      () => this.clearRefresh(request),
    );
    return request;
  }

  private clearRefresh(request: Promise<void>): void {
    if (this.refreshPromise === request) {
      this.refreshPromise = undefined;
    }
  }

  private async loadDashboard(hass: HomeAssistant): Promise<void> {
    this.loading = true;
    this.loadFailed = false;
    this.requestUpdate();

    const [fleetResult, discoveryResult, incidentsResult] = await Promise.allSettled([
      this.requestFleet(hass),
      this.requestDiscovery(hass),
      this.requestIncidents(hass),
    ]);

    if (this.hass === undefined) {
      this.loading = false;
      this.requestUpdate();
      return;
    }

    let receivedData = false;
    let failed = false;

    if (fleetResult.status === "fulfilled") {
      this.fleet = fleetResult.value;
      this.scan = fleetResult.value.scan;
      receivedData = true;
    } else {
      failed = true;
    }

    if (discoveryResult.status === "fulfilled") {
      this.discovery = discoveryResult.value;
      this.scan = discoveryResult.value.scan;
      receivedData = true;
    } else {
      failed = true;
    }

    if (incidentsResult.status === "fulfilled") {
      this.incidents = incidentsResult.value;
      receivedData = true;
    } else {
      failed = true;
    }

    if (receivedData) {
      this.loadedAt = Date.now();
    }
    if (
      this.scan !== null &&
      this.scan.network !== null &&
      this.scanNetwork.length === 0
    ) {
      this.scanNetwork = this.scan.network;
    }

    this.loading = false;
    this.loadFailed = failed;
    this.reconcileSelectedMiner();
    this.updateScanPolling();
    this.requestUpdate();
  }

  private async requestFleet(hass: HomeAssistant): Promise<FleetListResponse> {
    const response = await hass.callWS({ type: "bitaxe_fleet/fleet/list" });
    return parseFleetListResponse(response);
  }

  private async requestDiscovery(
    hass: HomeAssistant,
  ): Promise<DiscoveryListResponse> {
    const response = await hass.callWS({ type: "bitaxe_fleet/discovery/list" });
    return parseDiscoveryListResponse(response);
  }

  private async requestIncidents(
    hass: HomeAssistant,
  ): Promise<IncidentsListResponse> {
    const response = await hass.callWS({ type: "bitaxe_fleet/incidents/list" });
    return parseIncidentsListResponse(response);
  }

  private reconcileSelectedMiner(): void {
    if (this.fleet === null) {
      this.selectedMinerId = null;
      this.selectedHistoryMinerId = null;
      return;
    }
    if (
      this.selectedMinerId === null ||
      !this.fleet.miners.some((miner) => miner.miner_id === this.selectedMinerId)
    ) {
      this.selectedMinerId = this.fleet.miners[0]?.miner_id ?? null;
    }
    if (
      this.selectedHistoryMinerId !== null &&
      !this.fleet.miners.some(
        (miner) => miner.miner_id === this.selectedHistoryMinerId,
      )
    ) {
      this.selectedHistoryMinerId = null;
    }
  }

  private async startScan(): Promise<void> {
    const network = this.scanNetwork.trim();
    if (network.length === 0) {
      this.feedback = {
        tone: "error",
        text: "Enter a private CIDR before starting discovery.",
      };
      this.requestUpdate();
      return;
    }
    const hass = this.hass;
    if (hass === undefined || this.scanPending || this.scan?.running === true) {
      return;
    }

    this.scanPending = true;
    this.feedback = null;
    this.requestUpdate();
    try {
      const response = parseScanStartResponse(
        await hass.callWS({
          type: "bitaxe_fleet/discovery/scan",
          network,
        }),
      );
      if (this.hass === undefined) {
        return;
      }
      this.scan = response.scan;
      this.scanNetwork = network;
      this.feedback = {
        tone: "success",
        text: "Discovery scan started. Progress will update while it is running.",
      };
      this.updateScanPolling();
    } catch {
      if (this.hass !== undefined) {
        this.feedback = {
          tone: "error",
          text: "The discovery scan could not be started. Check the private CIDR and try again.",
        };
      }
    } finally {
      this.scanPending = false;
      this.requestUpdate();
    }
  }

  private updateScanPolling(): void {
    if (this.scan === null || !this.scan.running || !this.isConnected) {
      this.clearScanPoll();
      return;
    }
    if (this.scanPollTimer !== undefined) {
      return;
    }
    this.scanPollTimer = window.setTimeout(() => {
      this.scanPollTimer = undefined;
      void this.refresh().then(
        () => this.updateScanPolling(),
        () => this.updateScanPolling(),
      );
    }, SCAN_POLL_INTERVAL_MS);
  }

  private clearScanPoll(): void {
    if (this.scanPollTimer !== undefined) {
      window.clearTimeout(this.scanPollTimer);
      this.scanPollTimer = undefined;
    }
  }

  private async runMinerAction(miner: Miner, action: MinerAction): Promise<void> {
    if (this.pendingMinerIds.has(miner.miner_id)) {
      return;
    }
    if (!window.confirm(actionConfirmation(action, miner))) {
      return;
    }
    const hass = this.hass;
    if (hass === undefined) {
      return;
    }

    this.setMinerPending(miner.miner_id, true);
    try {
      await hass.callWS({
        type: "bitaxe_fleet/miner/action",
        miner_id: miner.miner_id,
        action,
      });
      if (this.hass === undefined) {
        return;
      }
      this.feedback = {
        tone: "success",
        text: `${actionLabel(action)} was requested for ${displayMinerName(miner)}.`,
      };
      await this.refresh();
    } catch {
      if (this.hass !== undefined) {
        this.feedback = {
          tone: "error",
          text: `The ${actionLabel(action).toLowerCase()} request could not be completed.`,
        };
      }
    } finally {
      this.setMinerPending(miner.miner_id, false);
    }
  }

  private async captureProfile(miner: Miner): Promise<void> {
    if (this.pendingMinerIds.has(miner.miner_id)) {
      return;
    }
    const hass = this.hass;
    if (hass === undefined) {
      return;
    }

    this.setMinerPending(miner.miner_id, true);
    try {
      const response = parseProfileCaptureResponse(
        await hass.callWS({
          type: "bitaxe_fleet/profile/capture",
          miner_id: miner.miner_id,
        }),
      );
      if (this.hass === undefined) {
        return;
      }
      this.replaceMiner(miner.miner_id, (current) => ({
        ...current,
        profile: response.profile,
      }));
      this.feedback = {
        tone: "success",
        text: `Captured a recovery profile for ${displayMinerName(miner)}.`,
      };
      await this.refresh();
    } catch {
      if (this.hass !== undefined) {
        this.feedback = {
          tone: "error",
          text: "The recovery profile could not be captured.",
        };
      }
    } finally {
      this.setMinerPending(miner.miner_id, false);
    }
  }

  private async applyProfile(miner: Miner): Promise<void> {
    if (miner.profile === null || this.pendingMinerIds.has(miner.miner_id)) {
      return;
    }
    if (
      !window.confirm(
        `Apply the saved recovery profile to ${displayMinerName(miner)}? This changes device settings.`,
      )
    ) {
      return;
    }
    const hass = this.hass;
    if (hass === undefined) {
      return;
    }

    this.setMinerPending(miner.miner_id, true);
    try {
      await hass.callWS({
        type: "bitaxe_fleet/profile/apply",
        miner_id: miner.miner_id,
      });
      if (this.hass === undefined) {
        return;
      }
      this.feedback = {
        tone: "success",
        text: `Applied the saved recovery profile to ${displayMinerName(miner)}.`,
      };
      await this.refresh();
    } catch {
      if (this.hass !== undefined) {
        this.feedback = {
          tone: "error",
          text: "The saved recovery profile could not be applied.",
        };
      }
    } finally {
      this.setMinerPending(miner.miner_id, false);
    }
  }

  private handlePolicySubmit(event: Event, miner: Miner): void {
    event.preventDefault();
    if (!(event.currentTarget instanceof HTMLFormElement)) {
      return;
    }
    const policy = readPolicyForm(event.currentTarget);
    if (policy === null) {
      this.feedback = {
        tone: "error",
        text: "Enter valid recovery policy values before saving.",
      };
      this.requestUpdate();
      return;
    }
    void this.savePolicy(miner, policy);
  }

  private async savePolicy(miner: Miner, policy: RecoveryPolicy): Promise<void> {
    if (this.pendingMinerIds.has(miner.miner_id)) {
      return;
    }
    if (
      !window.confirm(
        `Save the recovery policy for ${displayMinerName(miner)}?`,
      )
    ) {
      return;
    }
    const hass = this.hass;
    if (hass === undefined) {
      return;
    }

    this.setMinerPending(miner.miner_id, true);
    try {
      const response = parsePolicyUpdateResponse(
        await hass.callWS({
          type: "bitaxe_fleet/policy/update",
          miner_id: miner.miner_id,
          policy,
        }),
      );
      if (this.hass === undefined) {
        return;
      }
      this.replaceMiner(miner.miner_id, (current) => ({
        ...current,
        policy: response.policy,
      }));
      this.feedback = {
        tone: "success",
        text: `Updated the recovery policy for ${displayMinerName(miner)}.`,
      };
      await this.refresh();
    } catch {
      if (this.hass !== undefined) {
        this.feedback = {
          tone: "error",
          text: "The recovery policy could not be updated.",
        };
      }
    } finally {
      this.setMinerPending(miner.miner_id, false);
    }
  }

  private async approveCandidate(candidate: DiscoveryCandidate): Promise<void> {
    if (this.pendingCandidateIds.has(candidate.miner_id)) {
      return;
    }
    if (
      !window.confirm(
        `Approve ${candidate.name || candidate.miner_id} and add it to the fleet?`,
      )
    ) {
      return;
    }
    const hass = this.hass;
    if (hass === undefined) {
      return;
    }

    this.setCandidatePending(candidate.miner_id, true);
    try {
      const response = parseApprovalResponse(
        await hass.callWS({
          type: "bitaxe_fleet/discovery/approve",
          miner_id: candidate.miner_id,
        }),
      );
      if (this.hass === undefined) {
        return;
      }
      if (this.fleet !== null) {
        this.fleet = {
          ...this.fleet,
          miners: [...this.fleet.miners, response.miner],
        };
      }
      this.removeCandidate(candidate.miner_id);
      this.feedback = {
        tone: "success",
        text: `${candidate.name || candidate.miner_id} was approved and enrolled.`,
      };
      await this.refresh();
    } catch {
      if (this.hass !== undefined) {
        this.feedback = {
          tone: "error",
          text: "The candidate could not be approved.",
        };
      }
    } finally {
      this.setCandidatePending(candidate.miner_id, false);
    }
  }

  private async rejectCandidate(candidate: DiscoveryCandidate): Promise<void> {
    if (this.pendingCandidateIds.has(candidate.miner_id)) {
      return;
    }
    if (
      !window.confirm(
        `Reject ${candidate.name || candidate.miner_id}? This removes the pending candidate.`,
      )
    ) {
      return;
    }
    const hass = this.hass;
    if (hass === undefined) {
      return;
    }

    this.setCandidatePending(candidate.miner_id, true);
    try {
      await hass.callWS({
        type: "bitaxe_fleet/discovery/reject",
        miner_id: candidate.miner_id,
      });
      if (this.hass === undefined) {
        return;
      }
      this.removeCandidate(candidate.miner_id);
      this.feedback = {
        tone: "success",
        text: `${candidate.name || candidate.miner_id} was rejected.`,
      };
      await this.refresh();
    } catch {
      if (this.hass !== undefined) {
        this.feedback = {
          tone: "error",
          text: "The candidate could not be rejected.",
        };
      }
    } finally {
      this.setCandidatePending(candidate.miner_id, false);
    }
  }

  private async loadLogs(): Promise<void> {
    const minerId = this.selectedMinerId;
    const hass = this.hass;
    if (minerId === null || hass === undefined || this.logPending) {
      return;
    }

    this.logPending = true;
    this.logError = false;
    this.logs = null;
    this.requestUpdate();
    try {
      const response = parseLogsResponse(
        await hass.callWS({
          type: "bitaxe_fleet/logs/get",
          miner_id: minerId,
        }),
      );
      if (this.hass === undefined || this.selectedMinerId !== minerId) {
        return;
      }
      this.logs = response.text;
    } catch {
      if (this.hass !== undefined && this.selectedMinerId === minerId) {
        this.logError = true;
      }
    } finally {
      this.logPending = false;
      this.requestUpdate();
    }
  }

  private setMinerPending(minerId: string, pending: boolean): void {
    const next = new Set(this.pendingMinerIds);
    if (pending) {
      next.add(minerId);
    } else {
      next.delete(minerId);
    }
    this.pendingMinerIds = next;
    this.requestUpdate();
  }

  private setCandidatePending(candidateId: string, pending: boolean): void {
    const next = new Set(this.pendingCandidateIds);
    if (pending) {
      next.add(candidateId);
    } else {
      next.delete(candidateId);
    }
    this.pendingCandidateIds = next;
    this.requestUpdate();
  }

  private replaceMiner(
    minerId: string,
    transform: (miner: Miner) => Miner,
  ): void {
    if (this.fleet === null) {
      return;
    }
    this.fleet = {
      ...this.fleet,
      miners: this.fleet.miners.map((miner) =>
        miner.miner_id === minerId ? transform(miner) : miner,
      ),
    };
    this.requestUpdate();
  }

  private removeCandidate(candidateId: string): void {
    if (this.discovery === null) {
      return;
    }
    this.discovery = {
      ...this.discovery,
      candidates: this.discovery.candidates.filter(
        (candidate) => candidate.miner_id !== candidateId,
      ),
    };
    this.requestUpdate();
  }
}

interface CustomCardMetadata {
  description: string;
  name: string;
  type: string;
}

declare global {
  interface Window {
    customCards?: CustomCardMetadata[];
  }
}

export class BitaxeFleetGraphCard extends LitElement {
  public static override properties = {
    hass: { attribute: false },
  };

  public declare hass: HomeAssistant | undefined;

  private config: BitaxeFleetGraphCardConfig | null = null;
  private history: FleetTelemetryHistory | null = null;
  private historyFailed = false;
  private historyRequestId = 0;
  private loading = false;
  private requestedMetric: FleetHistoryMetric | null = null;
  private refreshTimer: number | undefined;

  public static styles = css`
    :host {
      display: block;
      min-inline-size: 0;
    }

    * {
      box-sizing: border-box;
    }

    ha-card {
      background:
        linear-gradient(
          150deg,
          color-mix(in srgb, var(--primary-color, #0b6e69) 10%, transparent),
          transparent 54%
        ),
        var(--card-background-color, #ffffff);
      color: var(--primary-text-color, #17212b);
      min-block-size: 15rem;
      overflow: hidden;
      padding: 1rem;
      position: relative;
    }

    header {
      align-items: flex-start;
      display: flex;
      gap: 0.75rem;
      justify-content: space-between;
    }

    h2,
    p {
      margin: 0;
    }

    .eyebrow,
    .window,
    .summary-label {
      color: var(--secondary-text-color, #65717b);
      font-size: 0.66rem;
      font-weight: 750;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .eyebrow {
      color: var(--primary-color, #0b6e69);
      margin-block-end: 0.18rem;
    }

    h2 {
      font-size: 1rem;
      letter-spacing: -0.01em;
      line-height: 1.2;
    }

    .header-actions {
      align-items: center;
      display: flex;
      gap: 0.35rem;
    }

    .window {
      border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.32));
      border-radius: 99rem;
      padding: 0.25rem 0.42rem;
      white-space: nowrap;
    }

    button {
      background: transparent;
      border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.32));
      border-radius: 0.35rem;
      color: var(--secondary-text-color, #65717b);
      cursor: pointer;
      font: inherit;
      font-size: 0.7rem;
      font-weight: 650;
      padding: 0.22rem 0.4rem;
    }

    button:hover:not(:disabled) {
      border-color: var(--primary-color, #0b6e69);
      color: var(--primary-color, #0b6e69);
    }

    button:focus-visible {
      outline: 2px solid var(--primary-color, #0b6e69);
      outline-offset: 2px;
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.5;
    }

    .value {
      font-size: clamp(1.6rem, 7vw, 2.25rem);
      font-variant-numeric: tabular-nums;
      font-weight: 760;
      letter-spacing: -0.045em;
      line-height: 1;
      margin-block: 1rem 0.6rem;
    }

    .value span {
      color: var(--secondary-text-color, #65717b);
      font-size: 0.7rem;
      font-weight: 650;
      letter-spacing: 0;
      margin-inline-start: 0.35rem;
    }

    svg {
      block-size: auto;
      display: block;
      inline-size: 100%;
      margin-block: 0.25rem 0.7rem;
    }

    .gridline {
      stroke: color-mix(in srgb, var(--divider-color, rgba(127, 127, 127, 0.32)) 75%, transparent);
      stroke-width: 1;
    }

    .history-line {
      fill: none;
      stroke: var(--primary-color, #0b6e69);
      stroke-linecap: round;
      stroke-linejoin: round;
      stroke-width: 3;
    }

    .summary {
      display: flex;
      font-variant-numeric: tabular-nums;
      gap: 1rem;
      justify-content: space-between;
    }

    .summary-value {
      color: var(--primary-text-color, #17212b);
      display: block;
      font-size: 0.78rem;
      font-weight: 700;
      margin-block-start: 0.16rem;
      white-space: nowrap;
    }

    .status {
      color: var(--secondary-text-color, #65717b);
      font-size: 0.82rem;
      line-height: 1.45;
      padding-block: 2.6rem 1.6rem;
    }

    .status.error {
      color: var(--error-color, #c62828);
    }
  `;

  public setConfig(config: unknown): void {
    const nextConfig = parseGraphCardConfig(config);
    const metricChanged = this.config?.metric !== nextConfig.metric;
    this.config = nextConfig;
    if (metricChanged) {
      this.history = null;
      this.historyFailed = false;
      this.requestedMetric = null;
      void this.loadHistory();
    }
    this.requestUpdate();
  }

  public getCardSize(): number {
    return 3;
  }

  public override connectedCallback(): void {
    super.connectedCallback();
    this.refreshTimer = window.setInterval(
      this.refreshHistory,
      CARD_REFRESH_INTERVAL_MS,
    );
    void this.loadHistory();
  }

  public override disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this.refreshTimer !== undefined) {
      window.clearInterval(this.refreshTimer);
      this.refreshTimer = undefined;
    }
  }

  protected override updated(changedProperties: PropertyValues<this>): void {
    if (!changedProperties.has("hass")) {
      return;
    }
    if (this.hass === undefined) {
      this.historyRequestId += 1;
      this.loading = false;
      this.requestedMetric = null;
      return;
    }
    void this.loadHistory();
  }

  protected override render() {
    const config = this.config;
    if (config === null) {
      return html`<ha-card><p class="status">Graph card configuration is required.</p></ha-card>`;
    }
    const definition = fleetGraphMetric(config.metric);
    return html`
      <ha-card>
        <header>
          <div>
            <p class="eyebrow">Bitaxe Fleet</p>
            <h2>${config.name ?? definition.title}</h2>
          </div>
          <div class="header-actions">
            <span class="window">24 h</span>
            <button
              aria-label="Refresh fleet history"
              ?disabled=${this.loading || this.hass === undefined}
              @click=${this.handleRefresh}
            >
              Refresh
            </button>
          </div>
        </header>
        ${this.renderHistory(definition)}
      </ha-card>
    `;
  }

  private renderHistory(definition: FleetGraphMetricDefinition) {
    if (this.hass === undefined || (this.loading && this.history === null)) {
      return html`<p class="status" role="status">Loading Recorder history...</p>`;
    }
    if (this.historyFailed) {
      return html`
        <p class="status error" role="alert">
          Fleet history could not be loaded. Confirm that Recorder is active and this
          dashboard is open as an administrator.
        </p>
      `;
    }
    const history = this.history;
    if (history === null || !history.available) {
      return html`
        <p class="status">
          Home Assistant Recorder is unavailable, so no fleet history can be shown.
        </p>
      `;
    }
    const summary = historySummary(history.series);
    if (summary === null) {
      return html`
        <p class="status">
          No recorded ${definition.title.toLowerCase()} data is available yet.
        </p>
      `;
    }
    return html`
      <p class="value">${definition.value(summary.latest)}<span>latest</span></p>
      <svg
        aria-label=${`${definition.title} for the last 24 hours`}
        role="img"
        viewBox="0 0 ${CHART_WIDTH} ${CHART_HEIGHT}"
      >
        <line
          class="gridline"
          x1=${CHART_PADDING}
          x2=${CHART_WIDTH - CHART_PADDING}
          y1=${CHART_HEIGHT / 2}
          y2=${CHART_HEIGHT / 2}
        ></line>
        <path class="history-line" d=${createHistoryPath(history.series)}></path>
      </svg>
      <div class="summary" aria-label="History range">
        <div>
          <span class="summary-label">Minimum</span>
          <span class="summary-value">${definition.value(summary.minimum)}</span>
        </div>
        <div>
          <span class="summary-label">Maximum</span>
          <span class="summary-value">${definition.value(summary.maximum)}</span>
        </div>
      </div>
    `;
  }

  private readonly handleRefresh = (): void => {
    this.refreshHistory();
  };

  private readonly refreshHistory = (): void => {
    this.requestedMetric = null;
    void this.loadHistory();
  };

  private async loadHistory(): Promise<void> {
    const config = this.config;
    const hass = this.hass;
    if (
      config === null ||
      hass === undefined ||
      this.requestedMetric === config.metric
    ) {
      return;
    }

    const requestId = this.historyRequestId + 1;
    this.historyRequestId = requestId;
    this.requestedMetric = config.metric;
    this.loading = true;
    this.historyFailed = false;
    this.requestUpdate();
    try {
      const response = parseFleetTelemetryHistory(
        await hass.callWS({
          type: "bitaxe_fleet/fleet/history",
          metric: config.metric,
        }),
      );
      if (response.metric !== config.metric) {
        invalidDto();
      }
      if (this.historyRequestId !== requestId) {
        return;
      }
      this.history = response;
    } catch {
      if (this.historyRequestId === requestId) {
        this.historyFailed = true;
      }
    } finally {
      if (this.historyRequestId === requestId) {
        this.loading = false;
        this.requestUpdate();
      }
    }
  }
}

export class BitaxeFleetOverviewCard extends LitElement {
  public static override properties = {
    hass: { attribute: false },
  };

  public declare hass: HomeAssistant | undefined;

  private config: BitaxeFleetOverviewCardConfig | null = null;
  private fleet: FleetListResponse | null = null;
  private initialLoadRequested = false;
  private loadFailed = false;
  private loading = false;
  private requestId = 0;
  private refreshTimer: number | undefined;

  public static styles = css`
    :host {
      display: block;
      min-inline-size: 0;
    }

    * {
      box-sizing: border-box;
    }

    ha-card {
      background:
        linear-gradient(
          140deg,
          color-mix(in srgb, var(--primary-color, #0b6e69) 11%, transparent),
          transparent 48%
        ),
        var(--card-background-color, #ffffff);
      color: var(--primary-text-color, #17212b);
      overflow: hidden;
      padding: 1rem;
    }

    header {
      align-items: flex-start;
      display: flex;
      gap: 0.75rem;
      justify-content: space-between;
      margin-block-end: 1rem;
    }

    h2,
    p {
      margin: 0;
    }

    .eyebrow,
    .metric-label,
    .miner-heading,
    .refresh-window {
      color: var(--secondary-text-color, #65717b);
      font-size: 0.66rem;
      font-weight: 750;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .eyebrow {
      color: var(--primary-color, #0b6e69);
      margin-block-end: 0.18rem;
    }

    h2 {
      font-size: 1rem;
      letter-spacing: -0.01em;
      line-height: 1.2;
    }

    .header-actions {
      align-items: center;
      display: flex;
      gap: 0.35rem;
    }

    .refresh-window {
      border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.32));
      border-radius: 99rem;
      padding: 0.25rem 0.42rem;
      white-space: nowrap;
    }

    button {
      background: transparent;
      border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.32));
      border-radius: 0.35rem;
      color: var(--secondary-text-color, #65717b);
      cursor: pointer;
      font: inherit;
      font-size: 0.7rem;
      font-weight: 650;
      padding: 0.22rem 0.4rem;
    }

    button:hover:not(:disabled) {
      border-color: var(--primary-color, #0b6e69);
      color: var(--primary-color, #0b6e69);
    }

    button:focus-visible {
      outline: 2px solid var(--primary-color, #0b6e69);
      outline-offset: 2px;
    }

    button:disabled {
      cursor: not-allowed;
      opacity: 0.5;
    }

    .fleet-summary {
      display: grid;
      gap: 0.65rem;
      grid-template-columns: minmax(11rem, 1.45fr) repeat(2, minmax(7rem, 1fr));
      margin-block-end: 1.15rem;
    }

    .fleet-total,
    .metric {
      border: 1px solid var(--divider-color, rgba(127, 127, 127, 0.32));
      border-radius: 0.55rem;
      min-inline-size: 0;
      padding: 0.75rem;
    }

    .fleet-total {
      background: color-mix(in srgb, var(--primary-color, #0b6e69) 8%, transparent);
    }

    .fleet-total strong,
    .metric strong {
      display: block;
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.025em;
      margin-block: 0.22rem;
    }

    .fleet-total strong {
      font-size: clamp(1.35rem, 5vw, 1.85rem);
      line-height: 1;
    }

    .metric strong {
      font-size: 1.05rem;
    }

    .fleet-total small,
    .metric small,
    .miner-time {
      color: var(--secondary-text-color, #65717b);
      display: block;
      font-size: 0.72rem;
      line-height: 1.35;
    }

    .miners-title {
      align-items: baseline;
      display: flex;
      gap: 0.5rem;
      justify-content: space-between;
      margin-block: 0.2rem 0.45rem;
    }

    .miners-title h3 {
      font-size: 0.88rem;
      margin: 0;
    }

    .miners-title span {
      color: var(--secondary-text-color, #65717b);
      font-size: 0.72rem;
    }

    .miner-heading,
    .miner-row {
      display: grid;
      gap: 0.7rem;
      grid-template-columns: minmax(10rem, 1.35fr) repeat(3, minmax(6.5rem, 1fr));
    }

    .miner-heading {
      padding: 0.4rem 0.6rem;
    }

    .miner-row {
      align-items: center;
      border-block-start: 1px solid var(--divider-color, rgba(127, 127, 127, 0.32));
      padding: 0.7rem 0.6rem;
    }

    .miner-name {
      min-inline-size: 0;
    }

    .miner-name strong {
      display: block;
      font-size: 0.86rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .status {
      border-radius: 99rem;
      display: inline-block;
      font-size: 0.65rem;
      font-weight: 750;
      line-height: 1;
      margin-block: 0.28rem;
      padding: 0.25rem 0.4rem;
    }

    .status.online {
      background: color-mix(in srgb, #2e7d32 17%, transparent);
      color: #2e7d32;
    }

    .status.stale {
      background: color-mix(in srgb, #ed6c02 17%, transparent);
      color: #b75500;
    }

    .status.offline,
    .status.disabled {
      background: color-mix(in srgb, var(--secondary-text-color, #65717b) 15%, transparent);
      color: var(--secondary-text-color, #65717b);
    }

    .miner-metric strong {
      display: block;
      font-size: 0.86rem;
      font-variant-numeric: tabular-nums;
      margin-block-start: 0.16rem;
      white-space: nowrap;
    }

    .status-message {
      color: var(--secondary-text-color, #65717b);
      font-size: 0.82rem;
      line-height: 1.45;
      padding-block: 1.6rem;
    }

    .status-message.error,
    .refresh-error {
      color: var(--error-color, #c62828);
    }

    .refresh-error {
      font-size: 0.76rem;
      line-height: 1.35;
      margin-block-end: 0.65rem;
    }

    @media (max-width: 700px) {
      .fleet-summary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .fleet-total {
        grid-column: 1 / -1;
      }

      .miner-heading {
        display: none;
      }

      .miner-row {
        align-items: start;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .miner-name {
        grid-column: 1 / -1;
      }

      .miner-metric:last-child {
        grid-column: 1 / -1;
      }

      .metric-label {
        display: block;
      }
    }

    @media (min-width: 701px) {
      .miner-metric .metric-label {
        display: none;
      }
    }
  `;

  public setConfig(config: unknown): void {
    this.config = parseOverviewCardConfig(config);
    this.initialLoadRequested = false;
    void this.loadFleet();
    this.requestUpdate();
  }

  public getCardSize(): number {
    return 5;
  }

  public override connectedCallback(): void {
    super.connectedCallback();
    this.refreshTimer = window.setInterval(
      this.refreshFleet,
      CARD_REFRESH_INTERVAL_MS,
    );
    void this.loadFleet();
  }

  public override disconnectedCallback(): void {
    super.disconnectedCallback();
    if (this.refreshTimer !== undefined) {
      window.clearInterval(this.refreshTimer);
      this.refreshTimer = undefined;
    }
  }

  protected override updated(changedProperties: PropertyValues<this>): void {
    if (!changedProperties.has("hass")) {
      return;
    }
    if (this.hass === undefined) {
      this.initialLoadRequested = false;
      this.loading = false;
      this.requestId += 1;
      return;
    }
    void this.loadFleet();
  }

  protected override render() {
    const config = this.config;
    if (config === null) {
      return html`<ha-card><p class="status-message">Card configuration is required.</p></ha-card>`;
    }
    return html`
      <ha-card>
        <header>
          <div>
            <p class="eyebrow">Bitaxe Fleet</p>
            <h2>${config.name ?? "Fleet performance"}</h2>
          </div>
          <div class="header-actions">
            <span class="refresh-window">30 s</span>
            <button
              aria-label="Refresh fleet performance"
              ?disabled=${this.loading || this.hass === undefined}
              @click=${this.handleRefresh}
            >
              Refresh
            </button>
          </div>
        </header>
        ${this.renderFleet()}
      </ha-card>
    `;
  }

  private renderFleet() {
    if (this.hass === undefined) {
      return html`<p class="status-message" role="status">Waiting for Home Assistant...</p>`;
    }
    if (this.fleet === null) {
      if (this.loading) {
        return html`<p class="status-message" role="status">Loading fleet performance...</p>`;
      }
      return html`
        <p class="status-message error" role="alert">
          Fleet performance could not be loaded. Confirm that this dashboard is open
          as an administrator.
        </p>
      `;
    }
    const aggregates = this.fleet.aggregates;
    if (aggregates === null) {
      return html`<p class="status-message">Fleet aggregate data is unavailable.</p>`;
    }
    return html`
      ${this.loadFailed
        ? html`
            <p class="refresh-error" role="alert">
              The latest refresh failed. Showing the last successful fleet data.
            </p>
          `
        : nothing}
      <section class="fleet-summary" aria-label="Fresh enabled fleet summary">
        <div class="fleet-total">
          <span class="metric-label">Fresh enabled fleet</span>
          <strong>${formatHashrate(aggregates.total_hashrate_gh_s)}</strong>
          <small>
            ${formatNumber(aggregates.online_miners, 0)} / ${formatNumber(
              aggregates.enabled_miners,
              0,
            )} online · ${formatCoverage(
              aggregates.hashrate_coverage,
              aggregates.enabled_miners,
            )}
          </small>
        </div>
        <div class="metric">
          <span class="metric-label">Best overall</span>
          <strong>${formatDifficulty(aggregates.best_difficulty)}</strong>
          <small>
            ${formatCoverage(
              aggregates.best_difficulty_coverage,
              aggregates.enabled_miners,
            )}
          </small>
        </div>
        <div class="metric">
          <span class="metric-label">Best session</span>
          <strong>${formatDifficulty(aggregates.best_session_difficulty)}</strong>
          <small>
            ${formatCoverage(
              aggregates.best_session_difficulty_coverage,
              aggregates.enabled_miners,
            )}
          </small>
        </div>
      </section>
      ${this.renderMiners(this.fleet.miners)}
    `;
  }

  private renderMiners(miners: readonly Miner[]) {
    if (miners.length === 0) {
      return html`<p class="status-message">No miners have been enrolled yet.</p>`;
    }
    return html`
      <section aria-label="Individual miner performance">
        <div class="miners-title">
          <h3>Individual miners</h3>
          <span>All enrolled miners</span>
        </div>
        <div class="miner-heading" aria-hidden="true">
          <span>Miner</span>
          <span>Hashrate</span>
          <span>Best overall</span>
          <span>Best session</span>
        </div>
        ${miners.map((miner) => this.renderMiner(miner))}
      </section>
    `;
  }

  private renderMiner(miner: Miner) {
    const status = minerStatus(miner);
    const telemetry = miner.telemetry;
    return html`
      <div class="miner-row">
        <div class="miner-name">
          <strong title=${displayMinerName(miner)}>${displayMinerName(miner)}</strong>
          <span class="status ${status.tone}">${status.label}</span>
          <span class="miner-time" title=${formatTimestamp(miner.last_success_at)}>
            Last success: ${formatRelativeTime(miner.last_success_at)}
          </span>
        </div>
        <div class="miner-metric">
          <span class="metric-label">Hashrate</span>
          <strong>${formatHashrate(telemetry?.hashrate_gh_s ?? null)}</strong>
        </div>
        <div class="miner-metric">
          <span class="metric-label">Best overall</span>
          <strong>${formatDifficulty(telemetry?.best_difficulty ?? null)}</strong>
        </div>
        <div class="miner-metric">
          <span class="metric-label">Best session</span>
          <strong>${formatDifficulty(telemetry?.best_session_difficulty ?? null)}</strong>
        </div>
      </div>
    `;
  }

  private readonly handleRefresh = (): void => {
    this.refreshFleet();
  };

  private readonly refreshFleet = (): void => {
    void this.loadFleet(true);
  };

  private async loadFleet(force = false): Promise<void> {
    const config = this.config;
    const hass = this.hass;
    if (
      config === null ||
      hass === undefined ||
      this.loading ||
      (!force && this.initialLoadRequested)
    ) {
      return;
    }

    const requestId = this.requestId + 1;
    this.requestId = requestId;
    this.initialLoadRequested = true;
    this.loading = true;
    this.loadFailed = false;
    this.requestUpdate();
    try {
      const response = parseFleetListResponse(
        await hass.callWS({ type: "bitaxe_fleet/fleet/list" }),
      );
      if (this.requestId !== requestId) {
        return;
      }
      this.fleet = response;
    } catch {
      if (this.requestId === requestId) {
        this.loadFailed = true;
      }
    } finally {
      if (this.requestId === requestId) {
        this.loading = false;
        this.requestUpdate();
      }
    }
  }
}

if (customElements.get(PANEL_TAG) === undefined) {
  customElements.define(PANEL_TAG, BitaxeFleetPanel);
}

if (customElements.get(CARD_TAG) === undefined) {
  customElements.define(CARD_TAG, BitaxeFleetGraphCard);
}

if (customElements.get(OVERVIEW_CARD_TAG) === undefined) {
  customElements.define(OVERVIEW_CARD_TAG, BitaxeFleetOverviewCard);
}

const registeredCards = window.customCards ?? [];
if (!registeredCards.some((card) => card.type === CARD_TAG)) {
  registeredCards.push({
    type: CARD_TAG,
    name: "Bitaxe Fleet graph",
    description: "Recorder-backed 24-hour fleet hashrate, power, or efficiency.",
  });
}
if (!registeredCards.some((card) => card.type === OVERVIEW_CARD_TAG)) {
  registeredCards.push({
    type: OVERVIEW_CARD_TAG,
    name: "Bitaxe Fleet performance",
    description: "Current per-miner hashrate and best difficulty with fresh fleet totals.",
  });
}
window.customCards = registeredCards;
