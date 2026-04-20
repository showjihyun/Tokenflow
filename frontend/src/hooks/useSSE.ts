import { useEffect, useRef, useState } from "react";

interface UseSSEOptions<T> {
  url: string;
  event?: string;
  bufferSize?: number;
  parse?: (raw: string) => T;
  enabled?: boolean;
}

interface SSEState<T> {
  events: T[];
  status: "idle" | "connecting" | "open" | "closed";
  lastEventId: number;
}

export function useSSE<T = unknown>({
  url,
  event = "message",
  bufferSize = 10,
  parse,
  enabled = true,
}: UseSSEOptions<T>): SSEState<T> {
  const [events, setEvents] = useState<T[]>([]);
  const [status, setStatus] = useState<SSEState<T>["status"]>("idle");
  const [lastEventId, setLastEventId] = useState(0);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) {
      setStatus("closed");
      return;
    }
    setStatus("connecting");
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onopen = () => setStatus("open");
    source.onerror = () => setStatus("closed");

    const handler = (e: MessageEvent<string>) => {
      const id = Number(e.lastEventId) || 0;
      const parsed = parse ? parse(e.data) : (JSON.parse(e.data) as T);
      setLastEventId((prev) => Math.max(prev, id));
      setEvents((prev) => {
        const next = [parsed, ...prev];
        return next.slice(0, bufferSize);
      });
    };

    source.addEventListener(event, handler as EventListener);

    return () => {
      source.removeEventListener(event, handler as EventListener);
      source.close();
      setStatus("closed");
    };
  }, [url, event, bufferSize, parse, enabled]);

  return { events, status, lastEventId };
}
