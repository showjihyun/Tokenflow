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
  latestEvent: T | null;
  status: "idle" | "connecting" | "open" | "closed";
  lastEventId: number;
  error: string | null;
}

export function useSSE<T = unknown>({
  url,
  event = "message",
  bufferSize = 10,
  parse,
  enabled = true,
}: UseSSEOptions<T>): SSEState<T> {
  const [events, setEvents] = useState<T[]>([]);
  const [latestEvent, setLatestEvent] = useState<T | null>(null);
  const [status, setStatus] = useState<SSEState<T>["status"]>("idle");
  const [lastEventId, setLastEventId] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) {
      setStatus("closed");
      return;
    }
    setStatus("connecting");
    setError(null);
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onopen = () => setStatus("open");
    source.onerror = () => setStatus("closed");

    const handler = (e: MessageEvent<string>) => {
      const id = Number(e.lastEventId) || 0;
      let parsed: T;
      try {
        parsed = parse ? parse(e.data) : (JSON.parse(e.data) as T);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to parse SSE event");
        return;
      }
      setLastEventId((prev) => Math.max(prev, id));
      setLatestEvent(parsed);
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

  return { events, latestEvent, status, lastEventId, error };
}
