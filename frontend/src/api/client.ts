import type {
  Budget,
  CurrentSession,
  FlowResponse,
  KPISummary,
  ModelShare,
  Project,
  ProjectTrend,
} from "../types";

export interface HealthResponse {
  status: string;
  version: string;
  db: string;
  hook: string;
  hook_detail?: {
    status: string;
    last_event_at: string | null;
    age_seconds: number | null;
  };
  api_key: string;
  api_key_detail?: {
    configured: boolean;
    valid: boolean;
    error?: string;
  };
  ingestion_paused?: boolean;
  home?: string;
}

export interface AnalyticsKPI {
  range: string;
  totalTokens: number;
  totalCost: number;
  avgSessionMinutes: number;
  costPerSession: number;
  sessions: number;
  messages: number;
}

export interface DailyResponse {
  range: string;
  labels: string[];
  series: { key: "opus" | "sonnet" | "haiku"; color: string; data: number[] }[];
}

export interface HeatmapResponse {
  range: string;
  grid: number[][];
}

export interface CostPart {
  label: string;
  value: number;
  color: string;
}

export interface CostBreakdown {
  range: string;
  total: number;
  parts: CostPart[];
}

export interface AnalyticsOverview {
  kpi: AnalyticsKPI;
  daily: DailyResponse;
  heatmap: HeatmapResponse;
  cost: CostBreakdown;
  topWastes: WastePattern[];
}

export type LLMModel = "claude-sonnet-4-6" | "claude-opus-4-7";

export interface SettingsResponse {
  budget: {
    monthly_budget_usd: number;
    alert_thresholds_pct: number[];
    hard_block: boolean;
  };
  tweaks: {
    theme: string;
    density: string;
    chart_style: string;
    sidebar_pos: string;
    alert_level: string;
    lang: string;
    better_prompt_mode: string;
    llm_model: LLMModel;
  };
  llm: {
    model: LLMModel;
    supported: LLMModel[];
  };
}

export interface OnboardingStatus {
  onboarded: boolean;
  hook: {
    status: "not_installed" | "partial" | "installed" | "unknown";
    settings_path: string;
    installed_events: string[];
    missing_events: string[];
    settings_exists: boolean;
  };
  api_key_configured: boolean;
  api_key?: { configured: boolean; valid: boolean; error?: string };
  ccprophet: { candidate_path: string; exists: boolean };
}

export type Range = "24h" | "7d" | "30d" | "90d" | "all";

export type WasteKind = "big-file-load" | "repeat-question" | "wrong-model" | "context-bloat" | "tool-loop";
export type WasteSeverity = "high" | "med" | "low";

export interface WastePattern {
  id: string;
  kind: WasteKind;
  severity: WasteSeverity;
  title: string;
  meta: string;
  body_html: string;
  save_tokens: number;
  save_usd: number;
  sessions: number;
  session_id: string | null;
  context: Record<string, unknown>;
  detected_at: string | null;
  dismissed_at: string | null;
  applied_at: string | null;
}

export interface CoachThread {
  id: string;
  title: string | null;
  started_at: string | null;
  last_msg_at: string | null;
  cost_usd_total: number;
}

export interface CoachMessage {
  id: string;
  role: "me" | "ai" | "system";
  content: string;
  ts: string | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
}

export interface ReplayEvent {
  idx: number;
  id: string;
  t: string;
  ts: string | null;
  role: "user" | "assistant" | "system" | "tool";
  model: string | null;
  tokens_in: number;
  tokens_out: number;
  cache_read: number;
  cost_usd: number;
  preview: string;
}

export interface SessionSummary {
  id: string;
  project: string;
  started_at: string | null;
  ended_at: string | null;
  model: string | null;
  tokens: number;
  cost: number;
  messages: number;
  wastes: number;
}

export interface ReplayResponse {
  session_id: string;
  events: ReplayEvent[];
  summary: { messages: number; tokens: number; cost: number };
}

export interface BetterPromptResponse {
  suggested_text: string;
  est_save_tokens: number;
  mode: "static" | "llm";
  cached?: boolean;
  model?: string;
}

export interface RoutingRule {
  id: string;
  condition_pattern: string;
  target_model: string;
  enabled: boolean;
  priority: number;
}

export interface NotificationPref {
  key: string;
  enabled: boolean;
  channel: "in_app" | "system";
}

export interface NotificationEvent {
  id: string;
  prefKey: string;
  title: string;
  body: string;
  createdAt: string | null;
  readAt: string | null;
}

const BASE = "/api";

export class ApiError extends Error {
  status: number;
  statusText: string;
  detail: unknown;

  constructor(status: number, statusText: string, detail: unknown) {
    super(formatApiError(status, statusText, detail));
    this.name = "ApiError";
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
  }
}

function analyticsParams(range: Range, project?: string) {
  const params = new URLSearchParams({ range });
  if (project) params.set("project", project);
  return params;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    throw new ApiError(res.status, res.statusText, await parseErrorBody(res));
  }
  return (await res.json()) as T;
}

async function guardedFetch<T>(path: string, guard: (value: unknown) => value is T): Promise<T> {
  const value = await apiFetch<unknown>(path);
  if (!guard(value)) {
    throw new Error(`Invalid API response for ${path}`);
  }
  return value;
}

async function parseErrorBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function formatApiError(status: number, statusText: string, detail: unknown) {
  if (typeof detail === "string") return `${status} ${statusText}: ${detail}`;
  if (detail && typeof detail === "object") {
    const record = detail as Record<string, unknown>;
    const message = record.detail ?? record.error ?? record.message;
    if (typeof message === "string") return `${status} ${statusText}: ${message}`;
  }
  return `${status} ${statusText}`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object";
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNumberArray(value: unknown): value is number[] {
  return Array.isArray(value) && value.every(isNumber);
}

function isKpiSummary(value: unknown): value is KPISummary {
  if (!isRecord(value)) return false;
  const currentSession = value.currentSession;
  const today = value.today;
  const efficiency = value.efficiency;
  const waste = value.waste;
  return (
    isRecord(currentSession) &&
    isNumber(currentSession.tokens) &&
    isRecord(today) &&
    isNumber(today.tokens) &&
    isNumber(today.cost) &&
    isNumber(today.delta) &&
    isNumberArray(today.series) &&
    isRecord(efficiency) &&
    isNumber(efficiency.score) &&
    isNumber(efficiency.delta) &&
    isNumberArray(efficiency.series) &&
    isRecord(waste) &&
    isNumber(waste.tokens) &&
    isNumber(waste.pct) &&
    isNumber(waste.delta) &&
    typeof value.window === "string"
  );
}

function isCurrentSession(value: unknown): value is CurrentSession & { active: boolean } {
  if (!isRecord(value)) return false;
  const tokens = value.tokens;
  return (
    typeof value.active === "boolean" &&
    (typeof value.id === "string" || value.id === null) &&
    isRecord(tokens) &&
    isNumber(tokens.input) &&
    isNumber(tokens.output) &&
    isNumber(tokens.cacheRead) &&
    isNumber(tokens.cacheWrite) &&
    isNumber(value.contextWindow) &&
    isNumber(value.contextUsed) &&
    isNumber(value.costUSD) &&
    isNumber(value.messages)
  );
}

export const api = {
  health: () => apiFetch<HealthResponse>("/system/health"),

  // KPI (Live Monitor)
  kpiSummary: (window: "today" | "7d" | "30d" = "today") =>
    guardedFetch<KPISummary>(`/kpi/summary?window=${window}`, isKpiSummary),
  kpiModels: () => apiFetch<ModelShare[]>("/kpi/models"),
  kpiBudget: () => apiFetch<Budget>("/kpi/budget"),

  // Sessions
  currentSession: () => guardedFetch<CurrentSession & { active: boolean }>("/sessions/current", isCurrentSession),
  currentSessionFlow: (window = "60m") =>
    apiFetch<FlowResponse>(`/sessions/current/flow?window=${window}`),

  // Projects
  projects: (range: "7d" | "30d" = "7d") => apiFetch<Project[]>(`/projects?range=${range}`),
  projectTrend: (name: string, range: "7d" | "30d" = "7d") =>
    apiFetch<ProjectTrend>(`/projects/${encodeURIComponent(name)}/trend?range=${range}`),

  // Analytics
  analyticsKpi: (range: Range = "7d", project?: string) =>
    apiFetch<AnalyticsKPI>(`/analytics/kpi?${analyticsParams(range, project)}`),
  analyticsDaily: (range: Range = "30d", project?: string) =>
    apiFetch<DailyResponse>(`/analytics/daily?${analyticsParams(range, project)}`),
  analyticsHeatmap: (range: Range = "7d", project?: string) =>
    apiFetch<HeatmapResponse>(`/analytics/heatmap?${analyticsParams(range, project)}`),
  analyticsCostBreakdown: (range: Range = "30d", project?: string) =>
    apiFetch<CostBreakdown>(`/analytics/cost-breakdown?${analyticsParams(range, project)}`),
  analyticsTopWastes: (range: Range = "30d", limit = 4, project?: string) => {
    const params = analyticsParams(range, project);
    params.set("limit", String(limit));
    return apiFetch<WastePattern[]>(`/analytics/top-wastes?${params.toString()}`);
  },
  analyticsOverview: (range: Range = "7d", limit = 4, project?: string) => {
    const params = analyticsParams(range, project);
    params.set("limit", String(limit));
    return apiFetch<AnalyticsOverview>(`/analytics/overview?${params.toString()}`);
  },

  // Settings
  getSettings: () => apiFetch<SettingsResponse>("/settings"),
  putBudget: (body: SettingsResponse["budget"]) =>
    apiFetch<SettingsResponse>("/settings/budget", { method: "PUT", body: JSON.stringify(body) }),
  patchTweaks: (body: Partial<SettingsResponse["tweaks"]>) =>
    apiFetch<SettingsResponse>("/settings/tweaks", { method: "PATCH", body: JSON.stringify(body) }),
  apiKeyStatus: () =>
    apiFetch<{ configured: boolean; valid: boolean; error?: string }>(
      "/settings/api-key/status",
    ),
  setApiKey: (key: string) =>
    apiFetch<{ configured: boolean }>("/settings/api-key", {
      method: "POST",
      body: JSON.stringify({ key }),
    }),
  deleteApiKey: () =>
    apiFetch<{ configured: boolean }>("/settings/api-key", { method: "DELETE" }),
  pauseIngestion: (paused: boolean) =>
    apiFetch<{ paused: boolean }>("/system/ingestion-pause", {
      method: "POST",
      body: JSON.stringify({ paused }),
    }),
  listBackups: () =>
    apiFetch<{ name: string; path: string; bytes: number; mtime: string }[]>("/system/backups"),
  vacuum: () =>
    apiFetch<{
      ok: boolean;
      before_bytes: number;
      after_bytes: number;
      backup: { name: string; path: string; bytes: number } | null;
      retention: { rolled_messages: number; retention_days: number };
    }>("/system/vacuum", { method: "POST" }),
  importCcprophet: (path: string) =>
    apiFetch<{ job_id: string; state: string }>("/import/ccprophet", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
  importCcprophetStatus: (jobId: string) =>
    apiFetch<{
      job_id: string;
      state: "queued" | "running" | "done" | "failed";
      path: string;
      imported: number;
      skipped: number;
      errors: string[];
      total: number;
      counts: Record<string, number>;
      created_at: string;
      updated_at: string;
    }>(`/import/ccprophet/status/${encodeURIComponent(jobId)}`),

  // Onboarding
  onboardingStatus: () => apiFetch<OnboardingStatus>("/onboarding/status"),
  installHook: (dryRun = false) =>
    apiFetch<{ dry_run: boolean; added_events: string[]; settings_path: string }>(
      `/onboarding/install-hook${dryRun ? "?dry_run=true" : ""}`,
      { method: "POST" },
    ),
  onboardingComplete: () =>
    apiFetch<{ onboarded: boolean }>("/onboarding/complete", { method: "POST" }),

  // Waste Radar
  listWastes: (status: "active" | "dismissed" = "active") =>
    apiFetch<WastePattern[]>(`/wastes?status=${status}`),
  dismissWaste: (id: string) =>
    apiFetch<{ ok: boolean }>(`/wastes/${encodeURIComponent(id)}/dismiss`, { method: "POST" }),
  applyWaste: (id: string) =>
    apiFetch<{
      ok: boolean;
      outcome: string;
      preview: { path: string; title: string; diff: string } | null;
    }>(`/wastes/${encodeURIComponent(id)}/apply`, { method: "POST" }),
  confirmWasteFix: (id: string) =>
    apiFetch<{ ok: boolean; applied: boolean; path?: string; reason?: string }>(
      `/wastes/${encodeURIComponent(id)}/apply-confirm`,
      { method: "POST" },
    ),
  scanWastes: (sessionId?: string) =>
    apiFetch<{ new: string[] }>(`/wastes/scan${sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ""}`, {
      method: "POST",
    }),
  sweepWastes: () => apiFetch<{ new: string[] }>("/wastes/sweep", { method: "POST" }),

  // Coach
  listCoachThreads: () => apiFetch<CoachThread[]>("/coach/threads"),
  createCoachThread: (title?: string) =>
    apiFetch<CoachThread>("/coach/threads", { method: "POST", body: JSON.stringify({ title }) }),
  listCoachMessages: (threadId: string) =>
    apiFetch<CoachMessage[]>(`/coach/threads/${encodeURIComponent(threadId)}/messages`),
  sendCoachMessage: (threadId: string, content: string) =>
    apiFetch<CoachMessage & { role: "ai" }>(
      `/coach/threads/${encodeURIComponent(threadId)}/messages`,
      { method: "POST", body: JSON.stringify({ content }) },
    ),
  coachSuggestions: () => apiFetch<string[]>("/coach/suggestions"),
  queryQuality: (query: string, context: Record<string, unknown> = {}) =>
    apiFetch<{ grade: "A" | "B" | "C" | "D"; score: number; signals: Record<string, number> }>(
      "/coach/query-quality",
      { method: "POST", body: JSON.stringify({ query, context }) },
    ),

  // Session replay
  listSessions: (opts: { project?: string; has_waste?: boolean; q?: string; limit?: number } = {}) => {
    const params = new URLSearchParams();
    if (opts.project) params.set("project", opts.project);
    if (opts.has_waste) params.set("has_waste", "true");
    if (opts.q) params.set("q", opts.q);
    if (opts.limit) params.set("limit", String(opts.limit));
    const qs = params.toString();
    return apiFetch<SessionSummary[]>(`/sessions${qs ? `?${qs}` : ""}`);
  },
  sessionReplay: (sessionId: string, includePaused = false) =>
    apiFetch<ReplayResponse>(
      `/sessions/${encodeURIComponent(sessionId)}/replay${includePaused ? "?include_paused=true" : ""}`,
    ),
  exportSession: (sessionId: string, includePaused = false) =>
    apiFetch<{ schema: string; session_id: string; summary: ReplayResponse["summary"]; events: ReplayEvent[] }>(
      `/sessions/${encodeURIComponent(sessionId)}/export${includePaused ? "?include_paused=true" : ""}`,
    ),
  betterPrompt: (sessionId: string, idx: number, mode: "static" | "llm", wasteReason?: string) => {
    const params = new URLSearchParams({ mode });
    if (wasteReason) params.set("waste_reason", wasteReason);
    return apiFetch<BetterPromptResponse>(
      `/sessions/${encodeURIComponent(sessionId)}/messages/${idx}/better-prompt?${params.toString()}`,
      { method: "POST" },
    );
  },

  // Routing rules + Notifications
  listRoutingRules: () => apiFetch<RoutingRule[]>("/settings/routing-rules"),
  createRoutingRule: (body: Omit<RoutingRule, "id">) =>
    apiFetch<RoutingRule>("/settings/routing-rules", { method: "POST", body: JSON.stringify(body) }),
  updateRoutingRule: (id: string, body: Omit<RoutingRule, "id">) =>
    apiFetch<RoutingRule>(`/settings/routing-rules/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteRoutingRule: (id: string) =>
    apiFetch<{ ok: boolean }>(`/settings/routing-rules/${encodeURIComponent(id)}`, { method: "DELETE" }),
  listNotifications: () => apiFetch<NotificationPref[]>("/settings/notifications"),
  patchNotification: (key: string, body: Partial<Pick<NotificationPref, "enabled" | "channel">>) =>
    apiFetch<NotificationPref>(`/settings/notifications/${encodeURIComponent(key)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  listNotificationEvents: (limit = 10) => apiFetch<NotificationEvent[]>(`/notifications?limit=${limit}`),
  unreadNotificationCount: () => apiFetch<{ count: number }>("/notifications/unread-count"),
  createNotificationEvent: (body: {
    id: string;
    prefKey: string;
    title: string;
    body: string;
    createdAt?: string;
  }) =>
    apiFetch<{ ok: boolean; stored: boolean }>("/notifications", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  clearNotificationEvents: () =>
    apiFetch<{ ok: boolean; deleted: number }>("/notifications", { method: "DELETE" }),
  markNotificationRead: (id: string) =>
    apiFetch<NotificationEvent>(`/notifications/${encodeURIComponent(id)}/read`, { method: "PATCH" }),
  markAllNotificationsRead: () =>
    apiFetch<{ ok: boolean; updated: number }>("/notifications/read-all", { method: "POST" }),
};
