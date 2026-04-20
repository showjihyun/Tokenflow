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
  analyticsKpi: (range: Range, project: string) => ["analytics-kpi", range, project] as const,
  analyticsDaily: (range: Range, project: string) => ["analytics-daily", range, project] as const,
  analyticsHeatmap: (range: Range, project: string) => ["analytics-heatmap", range, project] as const,
  analyticsCost: (range: Range, project: string) => ["analytics-cost", range, project] as const,
  analyticsTopWastes: (range: Range, project: string) => ["analytics-top-wastes", range, project] as const,
};
