import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type WheelActorGroup = "user" | "system" | "job";
export type WheelTurnCategory = "input" | "response" | "proposal" | "crud" | "other";
export type EventActorGroup = "user" | "system" | "job" | "external";

export type WheelFilters = {
  actorFilters: WheelActorGroup[];
  typeFilter: WheelTurnCategory | "all";
};

export type EventsFilters = {
  actorFilters: EventActorGroup[];
  typeFilters: string[];
  nodeFilter: string;
};

type ViewFiltersState = {
  wheel: WheelFilters;
  events: EventsFilters;
  setWheelActorFilters: (actorFilters: WheelActorGroup[]) => void;
  setWheelTypeFilter: (typeFilter: WheelTurnCategory | "all") => void;
  setEventsActorFilters: (actorFilters: EventActorGroup[]) => void;
  setEventsTypeFilters: (typeFilters: string[]) => void;
  setEventsNodeFilter: (nodeFilter: string) => void;
  resetWheelFilters: () => void;
  resetEventsFilters: () => void;
};

export const DEFAULT_WHEEL_FILTERS: WheelFilters = {
  actorFilters: ["user", "system", "job"],
  typeFilter: "all",
};

export const DEFAULT_EVENTS_FILTERS: EventsFilters = {
  actorFilters: ["user", "system", "job", "external"],
  typeFilters: [],
  nodeFilter: "",
};

const cloneWheelFilters = (): WheelFilters => ({
  actorFilters: [...DEFAULT_WHEEL_FILTERS.actorFilters],
  typeFilter: DEFAULT_WHEEL_FILTERS.typeFilter,
});

const cloneEventsFilters = (): EventsFilters => ({
  actorFilters: [...DEFAULT_EVENTS_FILTERS.actorFilters],
  typeFilters: [...DEFAULT_EVENTS_FILTERS.typeFilters],
  nodeFilter: DEFAULT_EVENTS_FILTERS.nodeFilter,
});

const getSessionStorage = (): Storage => {
  if (typeof window === "undefined") {
    return {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
    } as Storage;
  }
  return window.sessionStorage;
};

export const useViewFiltersStore = create<ViewFiltersState>()(
  persist(
    (set) => ({
      wheel: cloneWheelFilters(),
      events: cloneEventsFilters(),
      setWheelActorFilters: (actorFilters) =>
        set((state) => ({
          wheel: { ...state.wheel, actorFilters },
        })),
      setWheelTypeFilter: (typeFilter) =>
        set((state) => ({
          wheel: { ...state.wheel, typeFilter },
        })),
      setEventsActorFilters: (actorFilters) =>
        set((state) => ({
          events: { ...state.events, actorFilters },
        })),
      setEventsTypeFilters: (typeFilters) =>
        set((state) => ({
          events: { ...state.events, typeFilters },
        })),
      setEventsNodeFilter: (nodeFilter) =>
        set((state) => ({
          events: { ...state.events, nodeFilter },
        })),
      resetWheelFilters: () => set({ wheel: cloneWheelFilters() }),
      resetEventsFilters: () => set({ events: cloneEventsFilters() }),
    }),
    {
      name: "intentui-view-filters",
      storage: createJSONStorage(getSessionStorage),
      partialize: (state) => ({ wheel: state.wheel, events: state.events }),
    }
  )
);
