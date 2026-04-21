import type { Range } from "../api/client";

export const queryKeys = {
  apiKeyStatus: ["api-key-status"] as const,
  kpiSummary: (window: "today" | "7d" | "30d") => ["kpi-summary", window] as const,
  kpiModels: ["kpi-models"] as const,
  kpiBudget: ["kpi-budget"] as const,
  notifications: ["notifications"] as const,
  notificationEvents: ["notification-events"] as const,
  notificationUnreadCount: ["notification-unread-count"] as const,
  projects: (range: "7d" | "30d") => ["projects", range] as const,
  sessionCurrent: ["session-current"] as const,
  analyticsOverview: (range: Range, project: string) => ["analytics-overview", range, project] as const,
  analyticsKpi: (range: Range, project: string) => ["analytics-kpi", range, project] as const,
  analyticsDaily: (range: Range, project: string) => ["analytics-daily", range, project] as const,
  analyticsHeatmap: (range: Range, project: string) => ["analytics-heatmap", range, project] as const,
  analyticsCost: (range: Range, project: string) => ["analytics-cost", range, project] as const,
  analyticsTopWastes: (range: Range, project: string) => ["analytics-top-wastes", range, project] as const,
};

export const queryStaleTime = {
  live: 5_000,
  realtime: 10_000,
  short: 30_000,
  analytics: 60_000,
  config: 5 * 60_000,
} as const;
