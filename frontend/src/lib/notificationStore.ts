import { create } from "zustand";

export interface InAppNotice {
  id: string;
  prefKey: string;
  title: string;
  body: string;
  time: string;
}

interface NotificationState {
  notices: InAppNotice[];
  addNotice: (notice: InAppNotice) => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationState>((set) => ({
  notices: [],
  addNotice: (notice) =>
    set((state) => {
      if (state.notices.some((n) => n.id === notice.id)) return state;
      return { notices: [notice, ...state.notices].slice(0, 10) };
    }),
  clearAll: () => set({ notices: [] }),
}));
