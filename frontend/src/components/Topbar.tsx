import { useQuery } from "@tanstack/react-query";
import { Bell, Search, SlidersHorizontal } from "lucide-react";
import { api } from "../api/client";
import { useTweaks } from "../lib/tweaksStore";
import "./Topbar.css";

interface TopbarProps {
  currentLabel: string;
  showRangePicker?: boolean;
}

export function Topbar({ currentLabel, showRangePicker = false }: TopbarProps) {
  const togglePanel = useTweaks((s) => s.togglePanel);
  const { data: health } = useQuery({
    queryKey: ["system-health"],
    queryFn: () => api.health(),
    refetchInterval: 10_000,
  });

  const status =
    health?.hook === "active" ? "ok" : health?.hook === "not-connected" ? "disconnected" : "stale";
  const label =
    status === "ok" ? `connected · ${health?.version ?? ""}` : status === "stale" ? "stale" : "not connected";

  return (
    <header className="topbar">
      <div className="crumbs">
        <span>Workspace</span>
        <span className="sep">/</span>
        <span className="cur">{currentLabel}</span>
      </div>
      <div className="topbar-spacer" />
      {showRangePicker && (
        <div className="range-picker" role="tablist" aria-label="Time range">
          <button>Live</button>
          <button className="active">1H</button>
          <button>Today</button>
          <button>7D</button>
        </div>
      )}
      <span className="connection-pill" data-status={status}>
        <span className="connection-dot" />
        {label}
      </span>
      <button className="icon-btn" aria-label="Search">
        <Search size={15} strokeWidth={1.6} />
      </button>
      <button className="icon-btn" aria-label="Notifications">
        <Bell size={15} strokeWidth={1.6} />
      </button>
      <button className="icon-btn" aria-label="Tweaks" onClick={togglePanel} title="Toggle Tweaks (⌘,)">
        <SlidersHorizontal size={15} strokeWidth={1.6} />
      </button>
    </header>
  );
}
