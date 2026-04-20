import { Zap } from "lucide-react";
import { Badge } from "../../components/Badge";
import { Card, CardBody, CardHeader } from "../../components/Card";
import { LivePill } from "../../components/LivePill";
import { useTickerStore } from "../../lib/tickerStore";

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
  const events = useTickerStore((s) => s.events);
  const status = useTickerStore((s) => s.status);
  const error = useTickerStore((s) => s.error);

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
          {error && <div className="lm-ticker-empty">Stream event error: {error}</div>}
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
