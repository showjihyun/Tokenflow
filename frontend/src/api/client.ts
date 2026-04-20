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
  api_key: string;
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

const BASE = "/api";

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => apiFetch<HealthResponse>("/system/health"),

  // KPI (Live Monitor)
  kpiSummary: (window: "today" | "7d" | "30d" = "today") =>
    apiFetch<KPISummary>(`/kpi/summary?window=${window}`),
  kpiModels: () => apiFetch<ModelShare[]>("/kpi/models"),
  kpiBudget: () => apiFetch<Budget>("/kpi/budget"),

  // Sessions
  currentSession: () => apiFetch<CurrentSession & { active: boolean }>("/sessions/current"),
  currentSessionFlow: (window = "60m") =>
    apiFetch<FlowResponse>(`/sessions/current/flow?window=${window}`),

  // Projects
  projects: (range: "7d" | "30d" = "7d") => apiFetch<Project[]>(`/projects?range=${range}`),
  projectTrend: (name: string, range: "7d" | "30d" = "7d") =>
    apiFetch<ProjectTrend>(`/projects/${encodeURIComponent(name)}/trend?range=${range}`),

  // Analytics
  analyticsKpi: (range: Range = "7d") => apiFetch<AnalyticsKPI>(`/analytics/kpi?range=${range}`),
  analyticsDaily: (range: Range = "30d") => apiFetch<DailyResponse>(`/analytics/daily?range=${range}`),
  analyticsHeatmap: (range: Range = "7d") => apiFetch<HeatmapResponse>(`/analytics/heatmap?range=${range}`),
  analyticsCostBreakdown: (range: Range = "30d") =>
    apiFetch<CostBreakdown>(`/analytics/cost-breakdown?range=${range}`),

  // Settings
  getSettings: () => apiFetch<SettingsResponse>("/settings"),
  putBudget: (body: SettingsResponse["budget"]) =>
    apiFetch<SettingsResponse>("/settings/budget", { method: "PUT", body: JSON.stringify(body) }),
  patchTweaks: (body: Partial<SettingsResponse["tweaks"]>) =>
    apiFetch<SettingsResponse>("/settings/tweaks", { method: "PATCH", body: JSON.stringify(body) }),
  apiKeyStatus: () =>
    apiFetch<{ configured: boolean; valid: boolean; error?: string }>("/settings/api-key/status"),
  setApiKey: (key: string) =>
    apiFetch<{ configured: boolean }>("/settings/api-key", {
      method: "POST",
      body: JSON.stringify({ key }),
    }),
  deleteApiKey: () =>
    apiFetch<{ configured: boolean }>("/settings/api-key", { method: "DELETE" }),

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
    apiFetch<{ ok: boolean; outcome: string }>(`/wastes/${encodeURIComponent(id)}/apply`, { method: "POST" }),
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
  sessionReplay: (sessionId: string) =>
    apiFetch<ReplayResponse>(`/sessions/${encodeURIComponent(sessionId)}/replay`),
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
};
