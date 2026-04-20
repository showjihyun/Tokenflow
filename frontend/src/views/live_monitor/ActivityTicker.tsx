import { useQuery } from "@tanstack/react-query";
import { Zap } from "lucide-react";
import { useEffect, useRef } from "react";
import { api } from "../../api/client";
import { Badge } from "../../components/Badge";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { LivePill } from "../../components/LivePill";
import { useSSE } from "../../hooks/useSSE";
import { useNotificationStore } from "../../lib/notificationStore";
import type { TickerEvent } from "../../types";

const TYPE_TO_BADGE: Record<string, "haiku" | "sonnet" | "neutral"> = {
  tool: "haiku",
  bash: "haiku",
  reply: "sonnet",
  waste: "sonnet",
  budget: "sonnet",
  context: "sonnet",
  opus: "sonnet",
  api_error: "sonnet",
  edited: "neutral",
  read: "neutral",
  grep: "neutral",
};

export function ActivityTicker() {
  const lastNotified = useRef<string | null>(null);
  const addNotice = useNotificationStore((s) => s.addNotice);
  const { events, status } = useSSE<TickerEvent>({
    url: "/api/events/stream",
    event: "ticker",
    bufferSize: 10,
  });
  const { data: notifications } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => api.listNotifications(),
  });

  const latest = events[0];
  useEffect(() => {
    const notice = systemNoticeFor(latest);
    if (!latest || !notice) return;
    const dedupeKey = `${notice.prefKey}:${latest.id}`;
    if (dedupeKey === lastNotified.current) return;
    const pref = notifications?.find((p) => p.key === notice.prefKey);
    lastNotified.current = dedupeKey;
    if (!pref?.enabled) return;
    if (pref.channel === "in_app") {
      addNotice({
        id: dedupeKey,
        prefKey: notice.prefKey,
        title: notice.title,
        body: notice.body,
        time: latest.time,
      });
      return;
    }
    if (pref.channel !== "system") return;
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    new Notification(notice.title, { body: notice.body });
  }, [latest, notifications, addNotice]);

  const tone = status === "open" ? "green" : status === "connecting" ? "amber" : "red";
  const pillLabel = status === "open" ? "streaming" : status === "connecting" ? "connecting" : "disconnected";

  return (
    <Card>
      <CardHeader
        title="Live Activity"
        icon={<Zap size={13} strokeWidth={1.6} />}
        action={<LivePill tone={tone}>{pillLabel}</LivePill>}
      />
      <CardBody flush className="flush">
        <div style={{ maxHeight: 280, overflowY: "auto" }}>
          {events.length === 0 && <div className="lm-ticker-empty">Waiting for activity...</div>}
          {events.map((ev) => (
            <div key={ev.id} className="lm-ticker-row">
              <span className="lm-ticker-time">{ev.time}</span>
              <Badge kind={TYPE_TO_BADGE[ev.t] ?? "neutral"}>{ev.t}</Badge>
              <span className="lm-ticker-label">{ev.label}</span>
              <span className="lm-ticker-tk tnum">+{ev.tk}</span>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

function systemNoticeFor(event: TickerEvent | undefined) {
  if (!event) return null;
  if (event.t === "waste") {
    return { prefKey: "waste_high", title: "Token Flow waste detected", body: event.label };
  }
  if (event.t === "budget") {
    return { prefKey: "budget_threshold", title: "Token Flow budget alert", body: event.label };
  }
  if (event.t === "context") {
    return { prefKey: "context_saturation", title: "Token Flow context alert", body: event.label };
  }
  if (event.t === "opus") {
    return { prefKey: "opus_overuse", title: "Token Flow Opus alert", body: event.label };
  }
  if (event.t === "api_error") {
    return { prefKey: "api_error", title: "Token Flow API error", body: event.label };
  }
  if (event.t === "tool" && event.label === "SessionEnd") {
    return { prefKey: "session_summary", title: "Token Flow session ended", body: "Session summary is ready." };
  }
  return null;
}
