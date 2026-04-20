import { create } from "zustand";

export type Theme = "dark" | "light";
export type Density = "compact" | "normal" | "roomy";
export type ChartStyle = "bold" | "minimal" | "outlined";
export type SidebarPos = "left" | "right";
export type AlertLevel = "quiet" | "balanced" | "loud";
export type Lang = "ko" | "en";
export type BetterPromptMode = "static" | "llm";

export interface Tweaks {
  theme: Theme;
  density: Density;
  chart_style: ChartStyle;
  sidebar_pos: SidebarPos;
  alert_level: AlertLevel;
  lang: Lang;
  better_prompt_mode: BetterPromptMode;
}

const DEFAULTS: Tweaks = {
  theme: "dark",
  density: "normal",
  chart_style: "bold",
  sidebar_pos: "left",
  alert_level: "balanced",
  lang: "ko",
  better_prompt_mode: "static",
};

const LS_KEY = "tf_tweaks";

function loadLocal(): Tweaks {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return DEFAULTS;
  }
}

function applyToDOM(t: Tweaks) {
  // Only set theme here — it lives on <html> and needs to win the first paint.
  // Density/chart_style/sidebar_pos are owned by AppShell via props (see App.tsx)
  // to avoid races between React mount and this module's init.
  document.documentElement.dataset.theme = t.theme;
}

interface TweaksState {
  tweaks: Tweaks;
  panelOpen: boolean;
  setTweak: <K extends keyof Tweaks>(key: K, value: Tweaks[K]) => void;
  setAll: (tweaks: Partial<Tweaks>) => void;
  togglePanel: () => void;
  closePanel: () => void;
}

export const useTweaks = create<TweaksState>((set, get) => ({
  tweaks: loadLocal(),
  panelOpen: false,
  setTweak: (key, value) => {
    const next = { ...get().tweaks, [key]: value };
    localStorage.setItem(LS_KEY, JSON.stringify(next));
    applyToDOM(next);
    set({ tweaks: next });
    // Fire-and-forget server sync
    void fetch("/api/settings/tweaks", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [key]: value }),
    }).catch(() => undefined);
  },
  setAll: (partial) => {
    const next = { ...get().tweaks, ...partial };
    localStorage.setItem(LS_KEY, JSON.stringify(next));
    applyToDOM(next);
    set({ tweaks: next });
  },
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
  closePanel: () => set({ panelOpen: false }),
}));

// Initial paint: sync so the first pixel uses the saved theme (no FOUC).
if (typeof document !== "undefined") {
  applyToDOM(loadLocal());
}
