export type ModelKey = "opus" | "sonnet" | "haiku";

export interface KPISummary {
  currentSession: { tokens: number; delta: string };
  today: { tokens: number; cost: number; delta: number; series: number[] };
  week: { tokens: number; cost: number; delta: number; series: number[] };
  efficiency: { score: number; delta: number; series: number[] };
  waste: { tokens: number; pct: number; delta: number };
  window: string;
}

export interface CurrentSession {
  id: string | null;
  startedAt: string | null;
  project: string | null;
  model: string | null;
  tokens: {
    input: number;
    output: number;
    cacheRead: number;
    cacheWrite: number;
  };
  contextWindow: number;
  contextUsed: number;
  costUSD: number;
  messages: number;
  compacted?: boolean;
  ended?: string | null;
}

export interface FlowSeries {
  key: "opus" | "sonnet" | "haiku" | "cache";
  color: string;
  data: number[];
}

export interface FlowResponse {
  labels: string[];
  series: FlowSeries[];
  window: string;
}

export interface ModelShare {
  name: string;
  key: ModelKey;
  share: number;
  tokens: number;
  cost: number;
}

export interface Budget {
  month: number;
  spent: number;
  daysLeft: number;
  dailyAvg: number;
  forecast: number;
  opusShare: number;
}

export interface Project {
  name: string;
  tokens: number;
  cost: number;
  sessions: number;
  waste: number;
  trend: "up" | "down" | "flat";
  range: string;
}

export interface ProjectTrend {
  name: string;
  range: string;
  data: number[];
}

export interface TickerEvent {
  id: number;
  t: "edited" | "read" | "grep" | "reply" | "tool" | "bash" | "waste" | "budget" | "context" | "opus" | "api_error";
  label: string;
  tk: number;
  time: string;
}
