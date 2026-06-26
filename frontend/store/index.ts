import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ActiveMeeting, HealthStatus, SidebarPage } from "@/types";

// ─── App store ───────────────────────────────────────────────────────────────

interface AppState {
  // Navigation
  currentPage: SidebarPage;
  setPage: (page: SidebarPage) => void;

  // Health
  health: HealthStatus | null;
  setHealth: (h: HealthStatus) => void;

  // Active meetings (tracked in-browser for listing)
  activeMeetings: ActiveMeeting[];
  addMeeting: (m: ActiveMeeting) => void;
  removeMeeting: (id: string) => void;
  updateMeetingStatus: (id: string, patches: Partial<ActiveMeeting>) => void;

  // HITL badge count
  pendingHitlCount: number;
  setPendingHitlCount: (n: number) => void;

  // Settings
  apiUrl: string;
  setApiUrl: (url: string) => void;
  resolvedBy: string;
  setResolvedBy: (name: string) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentPage: "dashboard",
      setPage: (page) => set({ currentPage: page }),

      health: null,
      setHealth: (h) => set({ health: h }),

      activeMeetings: [],
      addMeeting: (m) =>
        set((s) => ({
          activeMeetings: [
            m,
            ...s.activeMeetings.filter(
              (x) => x.meeting_id !== m.meeting_id
            ),
          ],
        })),
      removeMeeting: (id) =>
        set((s) => ({
          activeMeetings: s.activeMeetings.filter(
            (m) => m.meeting_id !== id
          ),
        })),
      updateMeetingStatus: (id, patches) =>
        set((s) => ({
          activeMeetings: s.activeMeetings.map((m) =>
            m.meeting_id === id ? { ...m, ...patches } : m
          ),
        })),

      pendingHitlCount: 0,
      setPendingHitlCount: (n) => set({ pendingHitlCount: n }),

      apiUrl:
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080",
      setApiUrl: (url) => set({ apiUrl: url }),

      resolvedBy: "frontend-user@meetflow.ai",
      setResolvedBy: (name) => set({ resolvedBy: name }),
    }),
    {
      name: "meetflow-app",
      partialize: (s) => ({
        activeMeetings: s.activeMeetings,
        apiUrl: s.apiUrl,
        resolvedBy: s.resolvedBy,
      }),
    }
  )
);
