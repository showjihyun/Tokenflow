import { useQuery } from "@tanstack/react-query";
import { Bell, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useSSE } from "../hooks/useSSE";
import { useNotificationStore } from "../lib/notificationStore";
import { useTweaks } from "../lib/tweaksStore";
import type { TickerEvent } from "../types";
import "./Topbar.css";

interface TopbarProps {
  currentLabel: string;
  showRangePicker?: boolean;
}

export function Topbar({ currentLabel, showRangePicker = false }: TopbarProps) {
  const [bellOpen, setBellOpen] = useState(false);
  const lastInApp = useRef<string | null>(null);
  const togglePanel = useTweaks((s) => s.togglePanel);
  const notices = useNotificationStore((s) => s.notices);
  const addNotice = useNotificationStore((s) => s.addNotice);
  const clearAll = useNotificationStore((s) => s.clearAll);
  const { data: health } = useQuery({
    queryKey: ["system-health"],
    queryFn: () => api.health(),
    refetchInterval: 10_000,
  });
  const { data: notifications } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.listNotifications(),
  });
  const { events } = useSSE<TickerEvent>({
    url: "/api/events/stream",
    event: "ticker",
    bufferSize: 1,
  });

  const latest = events[0];
  useEffect(() => {
    const notice = inAppNoticeFor(latest);
    if (!latest || !notice) return;
    const id = `${notice.prefKey}:${latest.id}`;
    if (id === lastInApp.current) return;
    const pref = notifications?.find((p) => p.key === notice.prefKey);
    if (!pref?.enabled || pref.channel !== "in_app") return;
    lastInApp.current = id;
    addNotice({ id, ...notice, time: latest.time });
  }, [latest, notifications, addNotice]);

  const status =
    health?.hook === "active" || health?.hook === "ok"
      ? "ok"
      : health?.hook === "not-connected" || health?.hook === "disconnected"
        ? "disconnected"
        : "stale";
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
      <div className="bell-wrap">
        <button
          className="icon-btn"
          aria-label="Notifications"
          onClick={() => setBellOpen((open) => !open)}
        >
          <Bell size={15} strokeWidth={1.6} />
          {notices.length > 0 && <span className="bell-dot">{notices.length}</span>}
        </button>
        {bellOpen && (
          <div className="bell-menu">
            <div className="bell-menu-head">
              <span>Notifications</span>
              <button onClick={clearAll} disabled={notices.length === 0}>
                Clear all
              </button>
            </div>
            <div className="bell-list">
              {notices.length === 0 ? (
                <div className="bell-empty">No recent notifications.</div>
              ) : (
                notices.map((notice) => (
                  <div key={notice.id} className="bell-item">
                    <div className="bell-item-top">
                      <span>{notice.title}</span>
                      <time>{notice.time}</time>
                    </div>
                    <div className="bell-item-body">{notice.body}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
      <button className="icon-btn" aria-label="Tweaks" onClick={togglePanel} title="Toggle Tweaks (⌘,)">
        <SlidersHorizontal size={15} strokeWidth={1.6} />
      </button>
    </header>
  );
}

function inAppNoticeFor(event: TickerEvent | undefined) {
  if (!event) return null;
  if (event.t === "waste") return { prefKey: "waste_high", title: "Waste detected", body: event.label };
  if (event.t === "budget") return { prefKey: "budget_threshold", title: "Budget alert", body: event.label };
  if (event.t === "context") return { prefKey: "context_saturation", title: "Context alert", body: event.label };
  if (event.t === "opus") return { prefKey: "opus_overuse", title: "Opus alert", body: event.label };
  if (event.t === "api_error") return { prefKey: "api_error", title: "API error", body: event.label };
  if (event.t === "tool" && event.label === "SessionEnd") {
    return { prefKey: "session_summary", title: "Session ended", body: "Session summary is ready." };
  }
  return null;
}
