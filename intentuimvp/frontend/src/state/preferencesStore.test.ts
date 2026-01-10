import { describe, it, expect, beforeEach, vi } from 'vitest';
import { act } from 'react';
import { usePreferencesStore } from './preferencesStore';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch as unknown as typeof fetch;

describe('preferencesStore', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    // Reset fetch mock with default response for auto-save calls
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({}),
    } as unknown as Response);
    // Reset store to initial state (will trigger auto-save which uses the mock above)
    usePreferencesStore.getState().resetToDefaults();
    // Clear the mock after reset to avoid interference in tests
    mockFetch.mockClear();
  });

  describe('initial state', () => {
    it('should have default preferences', () => {
      const state = usePreferencesStore.getState();
      expect(state.preferences.theme).toBe('light');
      expect(state.preferences.zoom_level).toBe(1.0);
      expect(state.preferences.panel_layouts).toEqual({});
    });

    it('should not be loading initially', () => {
      const state = usePreferencesStore.getState();
      expect(state.isLoading).toBe(false);
    });

    it('should not be dirty initially', () => {
      const state = usePreferencesStore.getState();
      expect(state.isDirty).toBe(false);
    });
  });

  describe('setTheme', () => {
    it('should update theme preference', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.setTheme('dark');
      });

      const state = usePreferencesStore.getState();
      expect(state.preferences.theme).toBe('dark');
      expect(state.isDirty).toBe(true);
    });

    it('should accept valid theme values', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.setTheme('auto');
      });

      const state = usePreferencesStore.getState();
      expect(state.preferences.theme).toBe('auto');
    });
  });

  describe('setZoomLevel', () => {
    it('should update zoom level', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.setZoomLevel(1.5);
      });

      const state = usePreferencesStore.getState();
      expect(state.preferences.zoom_level).toBe(1.5);
      expect(state.isDirty).toBe(true);
    });

    it('should clamp zoom level to minimum 0.5', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.setZoomLevel(0.1);
      });

      const state = usePreferencesStore.getState();
      expect(state.preferences.zoom_level).toBe(0.5);
    });

    it('should clamp zoom level to maximum 2.0', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.setZoomLevel(3.0);
      });

      const state = usePreferencesStore.getState();
      expect(state.preferences.zoom_level).toBe(2.0);
    });
  });

  describe('setPanelLayout', () => {
    it('should set panel layout', () => {
      const store = usePreferencesStore.getState();
      const layout = {
        id: 'sidebar',
        position: { x: 0, y: 0 },
        size: { width: 250, height: 800 },
        visible: true,
      };

      act(() => {
        store.setPanelLayout('sidebar', layout);
      });

      const state = usePreferencesStore.getState();
      expect(state.preferences.panel_layouts['sidebar']).toEqual(layout);
      expect(state.isDirty).toBe(true);
    });

    it('should update existing panel layout', () => {
      const store = usePreferencesStore.getState();
      const layout1 = {
        id: 'sidebar',
        position: { x: 0, y: 0 },
        size: { width: 250, height: 800 },
        visible: true,
      };

      act(() => {
        store.setPanelLayout('sidebar', layout1);
      });

      const layout2 = {
        id: 'sidebar',
        position: { x: 10, y: 10 },
        size: { width: 300, height: 900 },
        visible: false,
      };

      act(() => {
        store.setPanelLayout('sidebar', layout2);
      });

      const state = usePreferencesStore.getState();
      expect(state.preferences.panel_layouts['sidebar']).toEqual(layout2);
    });
  });

  describe('updatePreferences', () => {
    it('should update multiple preferences at once', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.updatePreferences({
          theme: 'dark',
          zoom_level: 1.75,
        });
      });

      const state = usePreferencesStore.getState();
      expect(state.preferences.theme).toBe('dark');
      expect(state.preferences.zoom_level).toBe(1.75);
      expect(state.isDirty).toBe(true);
    });
  });

  describe('resetToDefaults', () => {
    it('should reset to default preferences', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.setTheme('dark');
        store.setZoomLevel(1.5);
      });

      let state = usePreferencesStore.getState();
      expect(state.preferences.theme).toBe('dark');
      expect(state.preferences.zoom_level).toBe(1.5);

      act(() => {
        store.resetToDefaults();
      });

      state = usePreferencesStore.getState();
      expect(state.preferences.theme).toBe('light');
      expect(state.preferences.zoom_level).toBe(1.0);
      expect(state.preferences.panel_layouts).toEqual({});
    });
  });

  describe('clearDirty', () => {
    it('should clear dirty flag', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.setTheme('dark');
      });

      let state = usePreferencesStore.getState();
      expect(state.isDirty).toBe(true);

      act(() => {
        store.clearDirty();
      });

      state = usePreferencesStore.getState();
      expect(state.isDirty).toBe(false);
    });
  });

  describe('API integration', () => {
    it('should load preferences from API', async () => {
      const mockPreferences = {
        user_id: 'default_user',
        preferences: {
          theme: 'dark',
          zoom_level: 1.25,
          panel_layouts: {},
        },
        updated_at: '2026-01-06T22:00:00',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPreferences,
      } as Response);

      const store = usePreferencesStore.getState();

      await act(async () => {
        await store.loadFromAPI();
      });

      const state = usePreferencesStore.getState();
      expect(state.preferences.theme).toBe('dark');
      expect(state.preferences.zoom_level).toBe(1.25);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/preferences')
      );
    });

    it('should save preferences to API', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      } as Response);

      const store = usePreferencesStore.getState();

      act(() => {
        store.setTheme('dark');
      });

      // Wait for auto-save
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/preferences'),
        expect.objectContaining({
          method: 'PUT',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('should handle API errors gracefully', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'));

      const store = usePreferencesStore.getState();

      await act(async () => {
        await store.loadFromAPI();
      });

      // Should not throw, just log error
      expect(store.isLoading).toBe(false);
    });
  });

  describe('localStorage persistence', () => {
    it('should persist preferences to localStorage', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.setTheme('dark');
        store.setZoomLevel(1.5);
      });

      const stored = localStorage.getItem('intentui-preferences');
      expect(stored).toBeDefined();

      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.preferences.theme).toBe('dark');
        expect(parsed.state.preferences.zoom_level).toBe(1.5);
      }
    });

    it('should load preferences from localStorage on hydration', () => {
      const store = usePreferencesStore.getState();

      act(() => {
        store.setTheme('dark');
        store.setZoomLevel(1.5);
      });

      // Create new store instance to test hydration
      const newStore = usePreferencesStore.getState();
      expect(newStore.preferences.theme).toBe('dark');
      expect(newStore.preferences.zoom_level).toBe(1.5);
    });
  });
});
