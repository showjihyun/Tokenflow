import { expect, test, type Page } from "@playwright/test";

const apiCalls: string[] = [];

test.beforeEach(async ({ page }) => {
  apiCalls.length = 0;
  await page.addInitScript(() => localStorage.clear());
  await mockApi(page);
});

test("SPEC core dashboard renders live monitor and accessible bell menu", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Live Monitor" })).toBeVisible();
  await expect(page.getByText("sess-1")).toBeVisible();
  await expect(page.getByText("Efficiency Score")).toBeVisible();
  await expect(page.getByText("Token Flow - Last 60 minutes")).toBeVisible();
  await expect(page.getByText("alpha", { exact: true })).toBeVisible();

  const bell = page.getByRole("button", { name: "Notifications" });
  await expect(bell).toHaveAttribute("aria-expanded", "false");
  await bell.click();
  await expect(bell).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("menu", { name: "Notifications" })).toBeVisible();
  await expect(page.getByText("Waste detected")).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu", { name: "Notifications" })).toBeHidden();
  await expect(bell).toBeFocused();
  expect(apiCalls).toContain("POST /api/notifications/read-all");
});

test("SPEC analytics project filter calls project-scoped APIs", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Analytics" }).click();

  await expect(page.getByRole("heading", { name: "Usage Analytics" })).toBeVisible();
  await page.getByLabel("Project filter").selectOption("alpha");
  await expect(page.getByText("Daily Usage")).toBeVisible();
  await expect.poll(() => apiCalls.some((call) => call.includes("/api/analytics/daily") && call.includes("project=alpha"))).toBe(true);
  await expect.poll(() => apiCalls.some((call) => call.includes("/api/analytics/top-wastes") && call.includes("project=alpha"))).toBe(true);
});

test("SPEC replay include-paused toggle reloads replay endpoint", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Session Replay" }).click();

  await expect(page.getByRole("heading", { name: "Session Replay" })).toBeVisible();
  await expect(page.getByText("hello from replay", { exact: true })).toBeVisible();
  await page.getByLabel("Include paused transcript messages").click();
  await expect.poll(() => apiCalls.some((call) => call.includes("/api/sessions/sess-1/replay?include_paused=true"))).toBe(true);
});

test("SPEC onboarding can be completed from first-run overlay", async ({ page }) => {
  await mockApi(page, { onboarded: false });
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Welcome to Token Flow" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Install the hook in Claude Code" })).toBeVisible();
  await page.getByRole("button", { name: "Skip all" }).click();
  await expect.poll(() => apiCalls).toContain("POST /api/onboarding/complete");
});

async function mockApi(page: Page, options: { onboarded?: boolean } = {}) {
  const onboarded = options.onboarded ?? true;
  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/")) return route.fallback();
    apiCalls.push(`${request.method()} ${url.pathname}${url.search}`);
    const path = url.pathname.replace("/api", "");

    if (path === "/events/stream") {
      return route.fulfill({ status: 200, contentType: "text/event-stream", body: ": connected\n\n" });
    }
    if (path === "/sessions/current/flow/stream") {
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body:
          'event: flow\ndata: {"labels":["60m","50m","40m","30m","20m","10m","now"],"series":[{"key":"opus","color":"var(--violet)","data":[1,2,3,4,3,2,1]},{"key":"sonnet","color":"var(--amber)","data":[2,3,4,5,4,3,2]},{"key":"haiku","color":"var(--blue)","data":[1,1,1,2,1,1,1]},{"key":"cache","color":"var(--green)","data":[0,1,0,1,0,1,0]}],"window":"60m"}\n\n',
      });
    }

    if (path === "/onboarding/status") {
      return json(route, {
        onboarded,
        hook: {
          status: "installed",
          settings_path: "settings.json",
          installed_events: ["PreToolUse"],
          missing_events: [],
          settings_exists: true,
        },
        api_key_configured: true,
        ccprophet: { candidate_path: "events.duckdb", exists: false },
      });
    }
    if (path === "/onboarding/complete") return json(route, { onboarded: true });
    if (path === "/system/health") return json(route, { status: "ok", version: "test", db: "ok", hook: "active", api_key: "configured" });
    if (path === "/settings/notifications") return json(route, [{ key: "waste_high", enabled: true, channel: "in_app" }]);
    if (path === "/notifications/unread-count") return json(route, { count: 1 });
    if (path === "/notifications") {
      if (request.method() === "DELETE") return json(route, { ok: true, deleted: 1 });
      return json(route, [{ id: "n1", prefKey: "waste_high", title: "Waste detected", body: "high context-bloat", createdAt: "2026-04-21T00:00:00Z", readAt: null }]);
    }
    if (path === "/notifications/read-all") return json(route, { ok: true, updated: 1 });
    if (path.startsWith("/notifications/")) return json(route, { id: "n1", prefKey: "waste_high", title: "Waste detected", body: "high context-bloat", createdAt: "2026-04-21T00:00:00Z", readAt: "2026-04-21T00:01:00Z" });
    if (path === "/sessions/current") {
      return json(route, {
        active: true,
        id: "sess-1",
        startedAt: "2026-04-21T00:00:00Z",
        project: "alpha",
        model: "claude-sonnet-4-6",
        tokens: { input: 1200, output: 800, cacheRead: 100, cacheWrite: 0 },
        contextWindow: 200000,
        contextUsed: 42000,
        costUSD: 0.42,
        messages: 3,
      });
    }
    if (path === "/system/ingestion-pause") return json(route, { paused: true });
    if (path === "/kpi/summary") return json(route, kpiSummary());
    if (path === "/kpi/models") return json(route, [
      { key: "sonnet", name: "Sonnet", share: 0.7, tokens: 2000, cost: 0.2 },
      { key: "opus", name: "Opus", share: 0.2, tokens: 600, cost: 0.18 },
      { key: "haiku", name: "Haiku", share: 0.1, tokens: 300, cost: 0.02 },
    ]);
    if (path === "/kpi/budget") return json(route, { month: 150, spent: 12, daysLeft: 20, dailyAvg: 1, forecast: 30, opusShare: 0.12 });
    if (path === "/projects") return json(route, [{ name: "alpha", tokens: 3000, cost: 0.4, sessions: 2, waste: 0.08, trend: "up", trendData: [1, 2, 3, 4, 5, 6, 7], range: "7d" }]);
    if (path.startsWith("/analytics/")) return json(route, analyticsResponse(path));
    if (path === "/wastes") return json(route, [waste()]);
    if (path === "/coach/threads") return json(route, []);
    if (path === "/coach/suggestions") return json(route, ["How can I reduce waste?"]);
    if (path === "/settings/api-key/status") return json(route, { configured: true, valid: true });
    if (path === "/settings") return json(route, settings());
    if (path === "/sessions") return json(route, [{ id: "sess-1", project: "alpha", started_at: "2026-04-21T00:00:00Z", ended_at: null, model: "claude-sonnet-4-6", tokens: 2000, cost: 0.42, messages: 2, wastes: 1 }]);
    if (path === "/sessions/sess-1/replay") return json(route, { session_id: "sess-1", summary: { messages: 1, tokens: 2000, cost: 0.42 }, events: [{ idx: 0, id: "m1", t: "message", ts: "2026-04-21T00:00:00Z", role: "user", model: null, tokens_in: 100, tokens_out: 0, cache_read: 0, cost_usd: 0, preview: "hello from replay" }] });
    return json(route, {});
  });
}

function json(route: Parameters<Page["route"]>[1] extends (route: infer R) => unknown ? R : never, body: unknown) {
  return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
}

function kpiSummary() {
  return {
    currentSession: { tokens: 2000, delta: "" },
    today: { tokens: 3200, cost: 0.42, delta: 0, series: [1, 2, 3] },
    week: { tokens: 0, cost: 0, delta: 0, series: [] },
    efficiency: { score: 91, delta: 2, series: [90, 91, 92], attribution: { totalTokens: 3200, wastedTokens: 120, opusMisuseTokens: 20, contextBloatTokens: 100, wasteRatio: 0.03, opusMisuseRatio: 0.01, contextBloatRatio: 0.02, penalty: { waste: 1, opusMisuse: 0.5, contextBloat: 1.5, total: 3 }, byKind: [] } },
    waste: { tokens: 120, pct: 3.8, delta: 0, byKind: [{ kind: "context-bloat", findings: 1, tokens: 120, usd: 0.01 }] },
    window: "today",
  };
}

function analyticsResponse(path: string) {
  if (path === "/analytics/kpi") return { range: "7d", totalTokens: 3200, totalCost: 0.42, avgSessionMinutes: 12, costPerSession: 0.21, sessions: 2, messages: 4 };
  if (path === "/analytics/daily") return { range: "7d", labels: ["Mon"], series: [{ key: "sonnet", color: "var(--amber)", data: [10] }, { key: "opus", color: "var(--violet)", data: [5] }, { key: "haiku", color: "var(--blue)", data: [1] }] };
  if (path === "/analytics/heatmap") return { range: "7d", grid: [[0, 1, 2]] };
  if (path === "/analytics/cost-breakdown") return { range: "7d", total: 0.42, parts: [{ label: "Sonnet", value: 0.2, color: "var(--amber)" }] };
  return [waste()];
}

function waste() {
  return { id: "w1", kind: "context-bloat", severity: "high", title: "Context bloat", meta: "1 finding", body_html: "Large context", save_tokens: 120, save_usd: 0.01, sessions: 1, session_id: "sess-1", context: {}, detected_at: "2026-04-21T00:00:00Z", dismissed_at: null, applied_at: null };
}

function settings() {
  return {
    budget: { monthly_budget_usd: 150, alert_thresholds_pct: [50, 75, 90], hard_block: false },
    tweaks: { theme: "dark", density: "comfortable", chart_style: "area", sidebar_pos: "left", alert_level: "normal", lang: "en", better_prompt_mode: "static", llm_model: "claude-sonnet-4-6" },
    llm: { model: "claude-sonnet-4-6", supported: ["claude-sonnet-4-6", "claude-opus-4-7"] },
  };
}
