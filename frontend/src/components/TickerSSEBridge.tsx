import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "../api/client";
import { useSSE } from "../hooks/useSSE";
import { queryKeys } from "../lib/queryKeys";
import { useTickerStore } from "../lib/tickerStore";
import type { TickerEvent } from "../types";

export function TickerSSEBridge() {
  const qc = useQueryClient();
  const handledInApp = useRef<Set<string>>(new Set());
  const handledSystem = useRef<Set<string>>(new Set());
  const lastInvalidatedAt = useRef(0);
  const { latestEvent, status, error } = useSSE<TickerEvent>({
    url: "/api/events/stream?replay=false",
    event: "ticker",
    bufferSize: 10,
  });
  const setStatus = useTickerStore((s) => s.setStatus);
  const setError = useTickerStore((s) => s.setError);
  const pushEvent = useTickerStore((s) => s.pushEvent);
  const { data: notifications } = useQuery({
    queryKey: queryKeys.notifications,
    queryFn: () => api.listNotifications(),
  });
  const createNotice = useMutation({
    mutationFn: api.createNotificationEvent,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.notificationEvents });
      qc.invalidateQueries({ queryKey: queryKeys.notificationUnreadCount });
    },
  });

  useEffect(() => {
    setStatus(status);
  }, [status, setStatus]);

  useEffect(() => {
    setError(error);
  }, [error, setError]);

  useEffect(() => {
    if (!latestEvent) return;
    pushEvent(latestEvent, 10);
    const now = Date.now();
    if (now - lastInvalidatedAt.current > 5_000) {
      lastInvalidatedAt.current = now;
      qc.invalidateQueries({ queryKey: queryKeys.kpiSummary("today") });
      qc.invalidateQueries({ queryKey: queryKeys.kpiModels });
      qc.invalidateQueries({ queryKey: queryKeys.kpiBudget });
      qc.invalidateQueries({ queryKey: queryKeys.projects("7d") });
    }

    if (!notifications) return;
    const notice = noticeFor(latestEvent);
    if (!notice) return;
    const pref = notifications.find((p) => p.key === notice.prefKey);
    if (!pref?.enabled) return;

    const id = `${notice.prefKey}:${latestEvent.id}`;
    if (pref.channel === "in_app") {
      if (handledInApp.current.has(id)) return;
      handledInApp.current.add(id);
      createNotice.mutate({
        id,
        ...notice,
        createdAt: new Date().toISOString(),
      });
      return;
    }

    if (pref.channel === "system") {
      if (handledSystem.current.has(id)) return;
      if (!("Notification" in window) || Notification.permission !== "granted") return;
      handledSystem.current.add(id);
      new Notification(notice.title, { body: notice.body });
    }
  }, [latestEvent, pushEvent, qc, notifications, createNotice]);

  return null;
}

function noticeFor(event: TickerEvent | undefined) {
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
