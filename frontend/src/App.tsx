import { useQuery } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api/client";
import { AppShell } from "./components/AppShell";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
import { TickerSSEBridge } from "./components/TickerSSEBridge";
import { queryStaleTime } from "./lib/queryKeys";
import { TweaksPanel } from "./components/TweaksPanel";
import { useTweaks } from "./lib/tweaksStore";
import { LiveMonitor } from "./views/LiveMonitor";
import { UsageAnalytics } from "./views/UsageAnalytics";
import { WasteRadar } from "./views/WasteRadar";
import { AICoach } from "./views/AICoach";
import { SessionReplay } from "./views/SessionReplay";
import { Settings } from "./views/Settings";
import { Onboarding } from "./views/Onboarding";
import "./views/views.css";

// ViewKey maps 1:1 to pathname segments. Keep in sync with <Route path>s below
// and with the Sidebar NavLink hrefs. When adding a view: extend this type,
// add a <Route>, and add a NavItem in Sidebar.tsx.
export type ViewKey = "live" | "analytics" | "waste" | "coach" | "replay" | "settings";

const VIEW_LABELS: Record<ViewKey, string> = {
  live: "Live Monitor",
  analytics: "Usage Analytics",
  waste: "Waste Radar",
  coach: "AI Coach",
  replay: "Session Replay",
  settings: "Settings",
};

/**
 * Infer which sidebar/topbar label to show from the current pathname. Falls
 * back to Live Monitor for `/`, unknown paths, or explicit `/live`.
 */
function useActiveView(): ViewKey {
  const { pathname } = useLocation();
  const first = pathname.split("/").filter(Boolean)[0] ?? "live";
  if (first in VIEW_LABELS) return first as ViewKey;
  return "live";
}

export function Shell() {
  const activeView = useActiveView();
  const tweaks = useTweaks((s) => s.tweaks);

  const { data: onboarding, refetch: refetchOnboarding } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () => api.onboardingStatus(),
    staleTime: queryStaleTime.short,
  });

  const needsOnboarding = onboarding !== undefined && !onboarding.onboarded;

  return (
    <>
      <AppShell
        sidebar={<Sidebar />}
        topbar={<Topbar currentLabel={VIEW_LABELS[activeView]} showRangePicker={activeView === "live"} />}
        density={tweaks.density}
        sidebarPos={tweaks.sidebar_pos}
        chartStyle={tweaks.chart_style}
      >
        {/* Remount the boundary on view change so a fixed-up view starts clean. */}
        <ErrorBoundary key={activeView} label={VIEW_LABELS[activeView]}>
          <Routes>
            <Route path="/" element={<Navigate to="/live" replace />} />
            <Route path="/live" element={<LiveMonitor />} />
            <Route path="/analytics" element={<UsageAnalytics />} />
            <Route path="/waste" element={<WasteRadar />} />
            <Route path="/coach" element={<AICoach />} />
            <Route path="/replay" element={<SessionReplay />} />
            <Route path="/settings" element={<Settings />} />
            {/* Unknown URL: fall back to Live Monitor, same result as root. */}
            <Route path="*" element={<Navigate to="/live" replace />} />
          </Routes>
        </ErrorBoundary>
      </AppShell>
      <TweaksPanel />
      <TickerSSEBridge />
      {needsOnboarding && (
        <ErrorBoundary label="Onboarding">
          <Onboarding onClose={() => refetchOnboarding()} />
        </ErrorBoundary>
      )}
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}
