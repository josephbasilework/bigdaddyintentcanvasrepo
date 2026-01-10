import { useEffect, useRef } from 'react';

/**
 * Keyboard shortcut definition
 */
export interface KeyboardShortcut {
  key: string;
  ctrl?: boolean;
  meta?: boolean; // Command key on Mac
  shift?: boolean;
  alt?: boolean;
  handler: (event: KeyboardEvent) => void;
  description?: string;
}

/**
 * Check if a keyboard event matches a shortcut
 */
export function matchesShortcut(event: KeyboardEvent, shortcut: KeyboardShortcut): boolean {
  const isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform);
  const wantsCtrl = !!shortcut.ctrl;
  const wantsMeta = !!shortcut.meta;
  const wantsShift = !!shortcut.shift;
  const wantsAlt = !!shortcut.alt;
  const ctrlPressed = event.ctrlKey;
  const metaPressed = event.metaKey;
  const shiftPressed = event.shiftKey;
  const altPressed = event.altKey;

  // Normalize key (handle special cases)
  const normalizedKey = event.key.toLowerCase();
  const shortcutKey = shortcut.key.toLowerCase();

  const metaMatches = wantsMeta
    ? (isMac ? metaPressed : metaPressed || ctrlPressed)
    : !metaPressed;
  const ctrlMatches = wantsCtrl
    ? ctrlPressed
    : !(ctrlPressed && !(wantsMeta && !isMac));
  const shiftMatches = wantsShift ? shiftPressed : !shiftPressed;
  const altMatches = wantsAlt ? altPressed : !altPressed;

  return (
    normalizedKey === shortcutKey &&
    ctrlMatches &&
    metaMatches &&
    shiftMatches &&
    altMatches
  );
}

/**
 * Hook to register keyboard shortcuts
 *
 * @param shortcuts - Array of keyboard shortcuts to register
 * @param enabled - Whether shortcuts are enabled (default: true)
 * @param target - Target element (default: document)
 *
 * @example
 * ```tsx
 * useKeyboardShortcuts([
 *   {
 *     key: 'k',
 *     meta: true,
 *     handler: () => console.log('Command+K pressed'),
 *     description: 'Focus search',
 *   },
 *   {
 *     key: 'z',
 *     meta: true,
 *     handler: () => console.log('Undo'),
 *     description: 'Undo last action',
 *   },
 * ]);
 * ```
 */
export function useKeyboardShortcuts(
  shortcuts: KeyboardShortcut[],
  enabled: boolean = true,
  target: HTMLElement | Document | null = typeof document !== 'undefined' ? document : null
) {
  const shortcutsRef = useRef<KeyboardShortcut[]>(shortcuts);

  // Update ref when shortcuts change
  useEffect(() => {
    shortcutsRef.current = shortcuts;
  }, [shortcuts]);

  useEffect(() => {
    if (!enabled || !target) return;

    const handleKeyDown = (event: Event) => {
      const keyboardEvent = event as KeyboardEvent;
      // Ignore events from input fields, textareas, and contentEditable elements
      const eventTarget = keyboardEvent.target;
      if (eventTarget instanceof HTMLElement) {
        const contentEditable = eventTarget.getAttribute('contenteditable');
        const isContentEditable =
          eventTarget.isContentEditable ||
          eventTarget.contentEditable === 'true' ||
          contentEditable === 'true' ||
          contentEditable === '';

        if (
          eventTarget.tagName === 'INPUT' ||
          eventTarget.tagName === 'TEXTAREA' ||
          isContentEditable
        ) {
          return;
        }
      }

      // Find matching shortcut
      const matchingShortcut = shortcutsRef.current.find((shortcut) =>
        matchesShortcut(keyboardEvent, shortcut)
      );

      if (matchingShortcut) {
        keyboardEvent.preventDefault();
        keyboardEvent.stopPropagation();
        matchingShortcut.handler(keyboardEvent);
      }
    };

    target.addEventListener('keydown', handleKeyDown);

    return () => {
      target.removeEventListener('keydown', handleKeyDown);
    };
  }, [enabled, target]);
}

/**
 * Hook to register a single keyboard shortcut
 *
 * @example
 * ```tsx
 * useKeyboardShortcut('k', { meta: true }, () => {
 *   focusInput();
 * });
 * ```
 */
export function useKeyboardShortcut(
  key: string,
  modifiers: { ctrl?: boolean; meta?: boolean; shift?: boolean; alt?: boolean },
  handler: (event: KeyboardEvent) => void,
  enabled: boolean = true,
  description?: string
) {
  return useKeyboardShortcuts(
    [{ key, ...modifiers, handler, description }],
    enabled
  );
}

/**
 * Common keyboard shortcut presets for the canvas workspace
 */
export const canvasShortcuts = {
  // Navigation
  focusCommandInput: {
    key: 'k',
    meta: true,
    description: 'Focus command input',
  },

  // Edit actions
  undo: {
    key: 'z',
    meta: true,
    description: 'Undo last action',
  },
  redo: {
    key: 'z',
    meta: true,
    shift: true,
    description: 'Redo last action',
  },
  delete: {
    key: 'backspace',
    description: 'Delete selected node',
  },
  deleteAlt: {
    key: 'delete',
    description: 'Delete selected node (alt)',
  },

  // View
  zoomIn: {
    key: '=',
    meta: true,
    description: 'Zoom in',
  },
  zoomOut: {
    key: '-',
    meta: true,
    description: 'Zoom out',
  },
  resetZoom: {
    key: '0',
    meta: true,
    description: 'Reset zoom',
  },

  // Canvas
  selectAll: {
    key: 'a',
    meta: true,
    description: 'Select all',
  },
  deselectAll: {
    key: 'a',
    meta: true,
    shift: true,
    description: 'Deselect all',
  },

  // Help
  showHelp: {
    key: '?',
    shift: true,
    description: 'Show keyboard shortcuts',
  },
} as const;
