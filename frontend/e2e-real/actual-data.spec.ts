import { expect, test } from "@playwright/test";

type ProjectRow = { name: string };
type SessionRow = { project: string };

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear());
});

test("actual server renders Live Monitor from real API data", async ({ page, request }) => {
  const health = await request.get("/api/system/health");
  expect(health.ok()).toBeTruthy();

  const projectsResponse = await request.get("/api/projects?range=7d");
  expect(projectsResponse.ok()).toBeTruthy();
  const projects = (await projectsResponse.json()) as ProjectRow[];

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Live Monitor" })).toBeVisible();
  await expect(page.getByText("Efficiency Score")).toBeVisible();
  await expect(page.getByText("Token Flow - Last 60 minutes")).toBeVisible();
  await expect(page.getByText(/streaming|connecting|disconnected/i)).toBeVisible();

  if (projects.length > 0) {
    await expect(page.getByText(projects[0]!.name, { exact: true }).first()).toBeVisible();
  }
});

test("actual analytics project filter uses real project-scoped API", async ({ page, request }) => {
  const projectsResponse = await request.get("/api/projects?range=7d");
  expect(projectsResponse.ok()).toBeTruthy();
  const projects = (await projectsResponse.json()) as ProjectRow[];
  test.skip(projects.length === 0, "No real projects available in local DB");
  const project = projects[0]!.name;

  await page.goto("/");
  await page.getByRole("button", { name: "Analytics" }).click();
  await expect(page.getByRole("heading", { name: "Usage Analytics" })).toBeVisible();

  const dailyResponse = page.waitForResponse((response) => {
    const url = response.url();
    return url.includes("/api/analytics/daily") && url.includes(`project=${encodeURIComponent(project)}`) && response.ok();
  });
  await page.getByLabel("Project filter").selectOption(project);
  await dailyResponse;
  await expect(page.getByText("Daily Usage")).toBeVisible();
});

test("actual replay include-paused toggle calls real replay endpoint", async ({ page, request }) => {
  const sessionsResponse = await request.get("/api/sessions?limit=5");
  expect(sessionsResponse.ok()).toBeTruthy();
  const sessions = (await sessionsResponse.json()) as SessionRow[];
  test.skip(sessions.length === 0, "No real sessions available in local DB");

  await page.goto("/");
  await page.getByRole("button", { name: "Session Replay" }).click();
  await expect(page.getByRole("heading", { name: "Session Replay" })).toBeVisible();
  await expect(page.getByText(sessions[0]!.project, { exact: true }).first()).toBeVisible();

  const replayResponse = page.waitForResponse((response) =>
    response.url().includes("/replay?include_paused=true") && response.ok(),
  );
  await page.getByLabel("Include paused transcript messages").click();
  await replayResponse;
});

test("actual onboarding state matches real server status", async ({ page, request }) => {
  const statusResponse = await request.get("/api/onboarding/status");
  expect(statusResponse.ok()).toBeTruthy();
  const status = (await statusResponse.json()) as { onboarded: boolean };

  await page.goto("/");
  if (status.onboarded) {
    await expect(page.getByRole("heading", { name: "Live Monitor" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Welcome to Token Flow" })).toHaveCount(0);
  } else {
    await expect(page.getByRole("heading", { name: "Welcome to Token Flow" })).toBeVisible();
  }
});
