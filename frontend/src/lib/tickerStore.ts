import { create } from "zustand";
import type { TickerEvent } from "../types";

interface TickerState {
  events: TickerEvent[];
  status: "idle" | "connecting" | "open" | "closed";
  error: string | null;
  setStatus: (status: TickerState["status"]) => void;
  setError: (error: string | null) => void;
  pushEvent: (event: TickerEvent, limit?: number) => void;
}

export const useTickerStore = create<TickerState>((set) => ({
  events: [],
  status: "idle",
  error: null,
  setStatus: (status) => set({ status }),
  setError: (error) => set({ error }),
  pushEvent: (event, limit = 10) =>
    set((state) => {
      if (state.events.some((e) => e.id === event.id)) return state;
      return { events: [event, ...state.events].slice(0, limit) };
    }),
}));
