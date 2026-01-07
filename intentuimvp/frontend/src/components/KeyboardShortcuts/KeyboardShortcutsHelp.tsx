'use client';

import { useEffect, useState } from 'react';

interface ShortcutGroup {
  title: string;
  shortcuts: Array<{
    keys: string[];
    description: string;
  }>;
}

const isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform);

const shortcutGroups: ShortcutGroup[] = [
  {
    title: 'Command Input',
    shortcuts: [{ keys: [isMac ? 'Cmd' : 'Ctrl', 'K'], description: 'Focus command input' }],
  },
  {
    title: 'Edit',
    shortcuts: [
      { keys: [isMac ? 'Cmd' : 'Ctrl', 'Z'], description: 'Undo' },
      { keys: [isMac ? 'Cmd' : 'Ctrl', 'Shift', 'Z'], description: 'Redo' },
      { keys: ['Backspace'], description: 'Delete selected' },
    ],
  },
  {
    title: 'View',
    shortcuts: [
      { keys: [isMac ? 'Cmd' : 'Ctrl', '='], description: 'Zoom in' },
      { keys: [isMac ? 'Cmd' : 'Ctrl', '-'], description: 'Zoom out' },
      { keys: [isMac ? 'Cmd' : 'Ctrl', '0'], description: 'Reset zoom' },
    ],
  },
  {
    title: 'Help',
    shortcuts: [{ keys: ['Shift', '?'], description: 'Show this help' }],
  },
];

interface KeyboardShortcutsHelpProps {
  onClose: () => void;
}

export function KeyboardShortcutsHelp({ onClose }: KeyboardShortcutsHelpProps) {
  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 text-white rounded-lg shadow-xl max-w-lg w-full mx-4 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Keyboard Shortcuts</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-6">
          {shortcutGroups.map((group) => (
            <div key={group.title}>
              <h3 className="text-sm font-medium text-gray-400 mb-2">{group.title}</h3>
              <div className="space-y-2">
                {group.shortcuts.map((shortcut, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <span className="text-sm text-gray-300">{shortcut.description}</span>
                    <div className="flex gap-1">
                      {shortcut.keys.map((key) => (
                        <kbd
                          key={key}
                          className="px-2 py-1 text-xs font-medium text-gray-900 bg-gray-700 rounded border border-gray-600"
                        >
                          {key}
                        </kbd>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 pt-4 border-t border-gray-700">
          <p className="text-xs text-gray-500 text-center">
            Press <kbd className="px-1 py-0.5 bg-gray-700 rounded">Esc</kbd> to close
          </p>
        </div>
      </div>
    </div>
  );
}

export function KeyboardShortcutsTrigger() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 p-2 bg-gray-800 hover:bg-gray-700 text-white rounded-full shadow-lg transition-colors"
        aria-label="Show keyboard shortcuts"
        title="Show keyboard shortcuts (?)"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </button>
      {isOpen && <KeyboardShortcutsHelp onClose={() => setIsOpen(false)} />}
    </>
  );
}
