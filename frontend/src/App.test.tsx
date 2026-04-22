import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

// Mock the onboarding API so Shell's useQuery resolves immediately without network.
vi.mock("./api/client", () => ({
  api: {
    onboardingStatus: vi.fn(async () => ({ onboarded: true })),
  },
}));

// Replace real views with lightweight stubs so route assertions don't touch
// TanStack Query, charts, or any other heavy dependency tree.
vi.mock("./views/LiveMonitor", () => ({
  LiveMonitor: () => <div data-testid="view-live">live-monitor</div>,
}));
vi.mock("./views/UsageAnalytics", () => ({
  UsageAnalytics: () => <div data-testid="view-analytics">usage-analytics</div>,
}));
vi.mock("./views/WasteRadar", () => ({
  WasteRadar: () => <div data-testid="view-waste">waste-radar</div>,
}));
vi.mock("./views/AICoach", () => ({
  AICoach: () => <div data-testid="view-coach">ai-coach</div>,
}));
vi.mock("./views/SessionReplay", () => ({
  SessionReplay: () => <div data-testid="view-replay">session-replay</div>,
}));
vi.mock("./views/Settings", () => ({
  Settings: () => <div data-testid="view-settings">settings</div>,
}));
vi.mock("./views/Onboarding", () => ({
  Onboarding: () => <div data-testid="view-onboarding">onboarding</div>,
}));

// Topbar/Sidebar render but we don't assert against them here.
vi.mock("./components/TickerSSEBridge", () => ({
  TickerSSEBridge: () => null,
}));
vi.mock("./components/TweaksPanel", () => ({
  TweaksPanel: () => null,
}));

import { Shell } from "./App";

function renderAt(path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Shell />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("<App> routing", () => {
  it("'/' redirects to /live", () => {
    renderAt("/");
    expect(screen.getByTestId("view-live")).toBeInTheDocument();
  });

  it("'/live' renders LiveMonitor", () => {
    renderAt("/live");
    expect(screen.getByTestId("view-live")).toBeInTheDocument();
  });

  it("'/analytics' renders UsageAnalytics", () => {
    renderAt("/analytics");
    expect(screen.getByTestId("view-analytics")).toBeInTheDocument();
  });

  it("'/waste' renders WasteRadar", () => {
    renderAt("/waste");
    expect(screen.getByTestId("view-waste")).toBeInTheDocument();
  });

  it("'/coach' renders AICoach", () => {
    renderAt("/coach");
    expect(screen.getByTestId("view-coach")).toBeInTheDocument();
  });

  it("'/replay' renders SessionReplay", () => {
    renderAt("/replay");
    expect(screen.getByTestId("view-replay")).toBeInTheDocument();
  });

  it("'/settings' renders Settings", () => {
    renderAt("/settings");
    expect(screen.getByTestId("view-settings")).toBeInTheDocument();
  });

  it("unknown paths redirect to /live (no 'not found' view)", () => {
    renderAt("/this-does-not-exist");
    expect(screen.getByTestId("view-live")).toBeInTheDocument();
    expect(screen.queryByText(/not found/i)).not.toBeInTheDocument();
  });
});
