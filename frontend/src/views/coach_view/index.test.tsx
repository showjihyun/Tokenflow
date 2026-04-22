import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

// Spyable navigate() — useNavigate() returns this function. It must be hoisted
// above the vi.mock for react-router-dom so the factory can reference it.
const navigateSpy = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateSpy };
});

// Coach pulls in lots of queries on render; we only exercise the "no API key"
// branch where EmptyState + "Go to Settings" appears.
vi.mock("../../api/client", () => ({
  api: {
    apiKeyStatus: vi.fn(async () => ({ configured: false })),
    listCoachThreads: vi.fn(async () => []),
    listCoachMessages: vi.fn(async () => []),
    coachSuggestions: vi.fn(async () => []),
    currentSession: vi.fn(async () => ({ active: false, tokens: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 } })),
    kpiBudget: vi.fn(async () => ({ month: 150, spent: 0, hard_block: false })),
    listWastes: vi.fn(async () => []),
    getSettings: vi.fn(async () => ({ llm: { model: "claude-sonnet-4-6" } })),
  },
}));

import { AICoach } from "./index";

function renderCoach() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/coach"]}>
        <AICoach />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<AICoach> 'Go to Settings' CTA", () => {
  it("calls navigate('/settings') via the router hook, not window events", async () => {
    renderCoach();
    // Wait for the query to settle: keyStatus flips from undefined → { configured: false }.
    const cta = await screen.findByRole("button", { name: /go to settings/i });
    navigateSpy.mockClear();

    // Verify no legacy custom-event fallback remains.
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");

    await userEvent.click(cta);
    expect(navigateSpy).toHaveBeenCalledTimes(1);
    expect(navigateSpy).toHaveBeenCalledWith("/settings");
    // No CustomEvent('tf:navigate') is dispatched — the migration is complete.
    const dispatchedCustom = dispatchSpy.mock.calls.some(
      (call) => call[0] instanceof CustomEvent && call[0].type === "tf:navigate",
    );
    expect(dispatchedCustom).toBe(false);
    dispatchSpy.mockRestore();
  });
});
