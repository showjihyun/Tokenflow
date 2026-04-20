import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useTickerStore } from "../lib/tickerStore";
import { TickerSSEBridge } from "./TickerSSEBridge";

type Listener = (event: MessageEvent<string>) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private listeners = new Map<string, Listener>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(event: string, listener: EventListener) {
    this.listeners.set(event, listener as Listener);
  }

  removeEventListener(event: string) {
    this.listeners.delete(event);
  }

  close() {}

  emit(event: string, data: unknown, id = "1") {
    this.listeners.get(event)?.({ data: JSON.stringify(data), lastEventId: id } as MessageEvent<string>);
  }
}

function renderBridge() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const invalidateSpy = vi.spyOn(client, "invalidateQueries");
  render(
    <QueryClientProvider client={client}>
      <TickerSSEBridge />
    </QueryClientProvider>,
  );
  return { client, invalidateSpy };
}

describe("<TickerSSEBridge>", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    vi.stubGlobal("EventSource", FakeEventSource);
    useTickerStore.setState({ events: [], status: "idle", error: null });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("persists in-app notification events from ticker SSE", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/settings/notifications")) {
        return Response.json([{ key: "waste_high", enabled: true, channel: "in_app" }]);
      }
      if (url.endsWith("/notifications")) {
        expect(init?.method).toBe("POST");
        return Response.json({ ok: true, stored: true });
      }
      return Response.json({});
    });
    vi.stubGlobal("fetch", fetchMock);

    renderBridge();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/settings/notifications", expect.anything()));

    FakeEventSource.instances[0]!.emit("ticker", {
      id: 7,
      t: "waste",
      label: "high context-bloat",
      tk: 0,
      time: "12:00:00",
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/notifications",
        expect.objectContaining({ method: "POST" }),
      );
    });
    expect(useTickerStore.getState().events[0]?.id).toBe(7);
  });

  // TODO: fix fake-timer + waitFor interaction; RTL waitFor uses real timers
  // so the fake-timer effect loop never advances. Needs rewrite with
  // vi.advanceTimersByTimeAsync() instead of waitFor.
  it.skip("throttles live query invalidation for rapid ticker events", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(10_000);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        if (String(input).endsWith("/settings/notifications")) return Response.json([]);
        return Response.json({});
      }),
    );
    const { invalidateSpy } = renderBridge();
    await vi.runOnlyPendingTimersAsync();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));

    FakeEventSource.instances[0]!.emit("ticker", { id: 1, t: "reply", label: "assistant", tk: 3, time: "12:00:00" });
    FakeEventSource.instances[0]!.emit("ticker", { id: 2, t: "reply", label: "assistant", tk: 4, time: "12:00:01" }, "2");

    await waitFor(() => expect(useTickerStore.getState().events[0]?.id).toBe(2));
    expect(invalidateSpy.mock.calls.filter((call) => call[0]?.queryKey?.[0] === "kpi-summary")).toHaveLength(1);
    vi.useRealTimers();
  });
});
