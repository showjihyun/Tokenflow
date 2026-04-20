import { type ReactElement, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api/client";
import { AppShell } from "./components/AppShell";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";
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

export type ViewKey = "live" | "analytics" | "waste" | "coach" | "replay" | "settings";

const VIEW_LABELS: Record<ViewKey, string> = {
  live: "Live Monitor",
  analytics: "Usage Analytics",
  waste: "Waste Radar",
  coach: "AI Coach",
  replay: "Session Replay",
  settings: "Settings",
};

export default function App() {
  const [view, setView] = useState<ViewKey>(() => {
    const saved = localStorage.getItem("tf_view") as ViewKey | null;
    return saved ?? "live";
  });
  const tweaks = useTweaks((s) => s.tweaks);

  const { data: onboarding, refetch: refetchOnboarding } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () => api.onboardingStatus(),
    staleTime: 30_000,
  });

  useEffect(() => {
    localStorage.setItem("tf_view", view);
  }, [view]);

  const views: Record<ViewKey, ReactElement> = {
    live: <LiveMonitor />,
    analytics: <UsageAnalytics />,
    waste: <WasteRadar />,
    coach: <AICoach />,
    replay: <SessionReplay />,
    settings: <Settings />,
  };

  const needsOnboarding = onboarding !== undefined && !onboarding.onboarded;

  return (
    <>
      <AppShell
        sidebar={<Sidebar active={view} onSelect={setView} />}
        topbar={<Topbar currentLabel={VIEW_LABELS[view]} showRangePicker={view === "live"} />}
        density={tweaks.density}
        sidebarPos={tweaks.sidebar_pos}
        chartStyle={tweaks.chart_style}
      >
        {views[view]}
      </AppShell>
      <TweaksPanel />
      {needsOnboarding && (
        <Onboarding onClose={() => refetchOnboarding()} />
      )}
    </>
  );
}
