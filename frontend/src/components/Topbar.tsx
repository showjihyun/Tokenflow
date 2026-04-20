import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Search, SlidersHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { queryKeys } from "../lib/queryKeys";
import { useTweaks } from "../lib/tweaksStore";
import "./Topbar.css";

interface TopbarProps {
  currentLabel: string;
  showRangePicker?: boolean;
}

export function Topbar({ currentLabel, showRangePicker = false }: TopbarProps) {
  const qc = useQueryClient();
  const [bellOpen, setBellOpen] = useState(false);
  const bellWrapRef = useRef<HTMLDivElement | null>(null);
  const bellButtonRef = useRef<HTMLButtonElement | null>(null);
  const bellMenuRef = useRef<HTMLDivElement | null>(null);
  const togglePanel = useTweaks((s) => s.togglePanel);
  const { data: health } = useQuery({
    queryKey: ["system-health"],
    queryFn: () => api.health(),
    refetchInterval: 10_000,
  });
  const { data: notices = [] } = useQuery({
    queryKey: queryKeys.notificationEvents,
    queryFn: () => api.listNotificationEvents(10),
  });
  const { data: unread } = useQuery({
    queryKey: queryKeys.notificationUnreadCount,
    queryFn: () => api.unreadNotificationCount(),
  });
  const clearAll = useMutation({
    mutationFn: api.clearNotificationEvents,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.notificationEvents });
      qc.invalidateQueries({ queryKey: queryKeys.notificationUnreadCount });
    },
  });
  const markRead = useMutation({
    mutationFn: api.markNotificationRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.notificationEvents });
      qc.invalidateQueries({ queryKey: queryKeys.notificationUnreadCount });
    },
  });
  const markAllRead = useMutation({
    mutationFn: api.markAllNotificationsRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.notificationEvents });
      qc.invalidateQueries({ queryKey: queryKeys.notificationUnreadCount });
    },
  });

  const unreadCount = unread?.count ?? notices.filter((n) => !n.readAt).length;
  const toggleBell = () => {
    const next = !bellOpen;
    setBellOpen(next);
    if (next && unreadCount > 0 && !markAllRead.isPending) {
      markAllRead.mutate();
    }
  };

  useEffect(() => {
    if (!bellOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (target instanceof Node && !bellWrapRef.current?.contains(target)) {
        setBellOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setBellOpen(false);
        bellButtonRef.current?.focus();
      }
      if (event.key === "Tab") {
        const focusable = bellMenuRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)");
        if (!focusable || focusable.length === 0) return;
        const first = focusable[0]!;
        const last = focusable[focusable.length - 1]!;
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [bellOpen]);

  useEffect(() => {
    if (!bellOpen) return;
    window.setTimeout(() => {
      bellMenuRef.current?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus();
    }, 0);
  }, [bellOpen]);

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
      <div className="bell-wrap" ref={bellWrapRef}>
        <button
          ref={bellButtonRef}
          className="icon-btn"
          aria-label="Notifications"
          aria-haspopup="menu"
          aria-expanded={bellOpen}
          onClick={toggleBell}
        >
          <Bell size={15} strokeWidth={1.6} />
          {unreadCount > 0 && <span className="bell-dot">{unreadCount}</span>}
        </button>
        {bellOpen && (
          <div className="bell-menu" ref={bellMenuRef} role="menu" aria-label="Notifications">
            <div className="bell-menu-head">
              <span>Notifications</span>
              <button onClick={() => clearAll.mutate()} disabled={notices.length === 0 || clearAll.isPending}>
                Clear all
              </button>
            </div>
            <div className="bell-list">
              {notices.length === 0 ? (
                <div className="bell-empty">No recent notifications.</div>
              ) : (
                notices.map((notice) => (
                  <button
                    key={notice.id}
                    className="bell-item"
                    role="menuitem"
                    data-unread={!notice.readAt}
                    onClick={() => {
                      if (!notice.readAt) markRead.mutate(notice.id);
                    }}
                  >
                    <div className="bell-item-top">
                      <span>{notice.title}</span>
                      <time>{formatNoticeTime(notice.createdAt)}</time>
                    </div>
                    <div className="bell-item-body">{notice.body}</div>
                  </button>
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

function formatNoticeTime(value: string | null) {
  if (!value) return "";
  return new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
