import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// Types for user preferences
export interface PanelLayout {
  id: string;
  position: { x: number; y: number };
  size: { width: number; height: number };
  visible: boolean;
}

export interface Preferences {
  theme: 'light' | 'dark' | 'auto';
  zoom_level: number;
  panel_layouts: Record<string, PanelLayout>;
}

// Store state interface
interface PreferencesState {
  // State
  preferences: Preferences;
  isLoading: boolean;
  isDirty: boolean;

  // Actions
  setTheme: (theme: Preferences['theme']) => void;
  setZoomLevel: (zoom: number) => void;
  setPanelLayout: (panelId: string, layout: PanelLayout) => void;
  updatePreferences: (updates: Partial<Preferences>) => void;
  resetToDefaults: () => void;
  loadFromAPI: () => Promise<void>;
  saveToAPI: () => Promise<void>;
  clearDirty: () => void;
}

// Default preferences
const DEFAULT_PREFERENCES: Preferences = {
  theme: 'light',
  zoom_level: 1.0,
  panel_layouts: {},
};

// API base URL (for MVP, using localhost)
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create the store with localStorage persistence
export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set, get) => ({
      // Initial state
      preferences: DEFAULT_PREFERENCES,
      isLoading: false,
      isDirty: false,

      // Set theme preference
      setTheme: (theme) => {
        set((state) => ({
          preferences: { ...state.preferences, theme },
          isDirty: true,
        }));
        // Trigger auto-save after a short delay
        void get().saveToAPI();
      },

      // Set zoom level preference
      setZoomLevel: (zoom) => {
        // Clamp zoom level between 0.5 and 2.0
        const clamped = Math.max(0.5, Math.min(2.0, zoom));
        set((state) => ({
          preferences: { ...state.preferences, zoom_level: clamped },
          isDirty: true,
        }));
        // Trigger auto-save after a short delay
        void get().saveToAPI();
      },

      // Set panel layout for a specific panel
      setPanelLayout: (panelId, layout) => {
        set((state) => ({
          preferences: {
            ...state.preferences,
            panel_layouts: {
              ...state.preferences.panel_layouts,
              [panelId]: layout,
            },
          },
          isDirty: true,
        }));
        // Trigger auto-save after a short delay
        void get().saveToAPI();
      },

      // Update multiple preferences at once
      updatePreferences: (updates) => {
        set((state) => ({
          preferences: { ...state.preferences, ...updates },
          isDirty: true,
        }));
        // Trigger auto-save after a short delay
        void get().saveToAPI();
      },

      // Reset preferences to defaults
      resetToDefaults: () => {
        set({
          preferences: DEFAULT_PREFERENCES,
          isDirty: true,
        });
        // Trigger auto-save after a short delay
        void get().saveToAPI();
      },

      // Load preferences from the API
      loadFromAPI: async () => {
        const state = get();
        if (state.isLoading) return;

        set({ isLoading: true });
        try {
          const response = await fetch(`${API_BASE}/api/preferences`);
          if (response.ok) {
            const data = await response.json();
            set({
              preferences: data.preferences,
              isDirty: false,
            });
          } else {
            // If no preferences exist, use local defaults
            console.warn('Failed to load preferences from API, using local defaults');
          }
        } catch (error) {
          console.error('Failed to load preferences from API:', error);
        } finally {
          set({ isLoading: false });
        }
      },

      // Save preferences to the API (debounced)
      saveToAPI: async () => {
        const state = get();
        if (!state.isDirty || state.isLoading) return;

        set({ isLoading: true });
        try {
          const response = await fetch(`${API_BASE}/api/preferences`, {
            method: 'PUT',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              preferences: state.preferences,
            }),
          });

          if (response.ok) {
            set({ isDirty: false });
          } else {
            console.error('Failed to save preferences to API');
          }
        } catch (error) {
          console.error('Failed to save preferences to API:', error);
        } finally {
          set({ isLoading: false });
        }
      },

      // Clear dirty flag (useful after manual save)
      clearDirty: () => {
        set({ isDirty: false });
      },
    }),
    {
      name: 'intentui-preferences', // localStorage key
      // Only persist the preferences, not the loading states
      partialize: (state) => ({ preferences: state.preferences }),
    }
  )
);
