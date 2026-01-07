/**
 * Tests for keyboard shortcuts system
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useKeyboardShortcuts, useKeyboardShortcut, matchesShortcut } from '../hooks/useKeyboardShortcuts';

describe('matchesShortcut', () => {
  it('should match simple key press', () => {
    const event = new KeyboardEvent('keydown', { key: 'k' });
    const shortcut = { key: 'k', handler: vi.fn() };

    expect(matchesShortcut(event, shortcut)).toBe(true);
  });

  it('should match with Ctrl modifier', () => {
    const event = new KeyboardEvent('keydown', { key: 'k', ctrlKey: true });
    const shortcut = { key: 'k', ctrl: true, handler: vi.fn() };

    expect(matchesShortcut(event, shortcut)).toBe(true);
  });

  it('should match with Meta (Command) modifier', () => {
    const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
    const shortcut = { key: 'k', meta: true, handler: vi.fn() };

    expect(matchesShortcut(event, shortcut)).toBe(true);
  });

  it('should match with Shift modifier', () => {
    const event = new KeyboardEvent('keydown', { key: '?', shiftKey: true });
    const shortcut = { key: '?', shift: true, handler: vi.fn() };

    expect(matchesShortcut(event, shortcut)).toBe(true);
  });

  it('should match with Alt modifier', () => {
    const event = new KeyboardEvent('keydown', { key: 'k', altKey: true });
    const shortcut = { key: 'k', alt: true, handler: vi.fn() };

    expect(matchesShortcut(event, shortcut)).toBe(true);
  });

  it('should match combined modifiers (Ctrl+Shift)', () => {
    const event = new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, shiftKey: true });
    const shortcut = { key: 'z', ctrl: true, shift: true, handler: vi.fn() };

    expect(matchesShortcut(event, shortcut)).toBe(true);
  });

  it('should not match when modifiers differ', () => {
    const event = new KeyboardEvent('keydown', { key: 'k', ctrlKey: false });
    const shortcut = { key: 'k', ctrl: true, handler: vi.fn() };

    expect(matchesShortcut(event, shortcut)).toBe(false);
  });

  it('should not match when keys differ', () => {
    const event = new KeyboardEvent('keydown', { key: 'a' });
    const shortcut = { key: 'k', handler: vi.fn() };

    expect(matchesShortcut(event, shortcut)).toBe(false);
  });

  it('should be case-insensitive for key matching', () => {
    const event = new KeyboardEvent('keydown', { key: 'K' });
    const shortcut = { key: 'k', handler: vi.fn() };

    expect(matchesShortcut(event, shortcut)).toBe(true);
  });
});

describe('useKeyboardShortcuts', () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement('div');
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  it('should register and trigger keyboard shortcut', () => {
    const handler = vi.fn();

    renderHook(() =>
      useKeyboardShortcuts(
        [{ key: 'k', handler }],
        true,
        document
      )
    );

    const event = new KeyboardEvent('keydown', { key: 'k' });
    document.dispatchEvent(event);

    expect(handler).toHaveBeenCalledWith(event);
  });

  it('should support multiple shortcuts', () => {
    const handler1 = vi.fn();
    const handler2 = vi.fn();

    renderHook(() =>
      useKeyboardShortcuts(
        [
          { key: 'k', handler: handler1 },
          { key: 'l', handler: handler2 },
        ],
        true,
        document
      )
    );

    const event1 = new KeyboardEvent('keydown', { key: 'k' });
    document.dispatchEvent(event1);

    const event2 = new KeyboardEvent('keydown', { key: 'l' });
    document.dispatchEvent(event2);

    expect(handler1).toHaveBeenCalledWith(event1);
    expect(handler2).toHaveBeenCalledWith(event2);
  });

  it('should not trigger when disabled', () => {
    const handler = vi.fn();

    renderHook(() =>
      useKeyboardShortcuts([{ key: 'k', handler }], false, document)
    );

    const event = new KeyboardEvent('keydown', { key: 'k' });
    document.dispatchEvent(event);

    expect(handler).not.toHaveBeenCalled();
  });

  it('should ignore events from input elements', () => {
    const handler = vi.fn();

    renderHook(() =>
      useKeyboardShortcuts([{ key: 'k', handler }], true, document)
    );

    const input = document.createElement('input');
    document.body.appendChild(input);

    const event = new KeyboardEvent('keydown', { key: 'k', bubbles: true });
    Object.defineProperty(event, 'target', { value: input, writable: false });
    input.dispatchEvent(event);

    expect(handler).not.toHaveBeenCalled();

    document.body.removeChild(input);
  });

  it('should ignore events from textarea elements', () => {
    const handler = vi.fn();

    renderHook(() =>
      useKeyboardShortcuts([{ key: 'k', handler }], true, document)
    );

    const textarea = document.createElement('textarea');
    document.body.appendChild(textarea);

    const event = new KeyboardEvent('keydown', { key: 'k', bubbles: true });
    Object.defineProperty(event, 'target', { value: textarea, writable: false });
    textarea.dispatchEvent(event);

    expect(handler).not.toHaveBeenCalled();

    document.body.removeChild(textarea);
  });

  it('should ignore events from contentEditable elements', () => {
    const handler = vi.fn();

    renderHook(() =>
      useKeyboardShortcuts([{ key: 'k', handler }], true, document)
    );

    const div = document.createElement('div');
    div.contentEditable = 'true';
    document.body.appendChild(div);

    const event = new KeyboardEvent('keydown', { key: 'k', bubbles: true });
    Object.defineProperty(event, 'target', { value: div, writable: false });
    div.dispatchEvent(event);

    expect(handler).not.toHaveBeenCalled();

    document.body.removeChild(div);
  });

  it('should prevent default on matching shortcut', () => {
    const handler = vi.fn();
    const preventDefault = vi.fn();

    renderHook(() =>
      useKeyboardShortcuts([{ key: 'k', handler }], true, document)
    );

    const event = new KeyboardEvent('keydown', { key: 'k' });
    Object.defineProperty(event, 'preventDefault', { value: preventDefault });
    document.dispatchEvent(event);

    expect(preventDefault).toHaveBeenCalled();
  });
});

describe('useKeyboardShortcut', () => {
  it('should register single keyboard shortcut', () => {
    const handler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut('k', { meta: true }, handler, true)
    );

    const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
    document.dispatchEvent(event);

    expect(handler).toHaveBeenCalledWith(event);
  });

  it('should pass description to shortcut', () => {
    const handler = vi.fn();

    renderHook(() =>
      useKeyboardShortcut('k', { meta: true }, handler, true, 'Focus search')
    );

    const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true });
    document.dispatchEvent(event);

    expect(handler).toHaveBeenCalled();
  });
});
