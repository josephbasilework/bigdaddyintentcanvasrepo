"use client";

import { useEffect, useRef, useState } from "react";

interface FloatingInputProps {
  /** Callback when user submits input (pressed Enter) */
  onSubmit?: (value: string) => void;
  /** Placeholder text for the input */
  placeholder?: string;
  /** Whether to auto-focus on mount */
  autoFocus?: boolean;
  /** Maximum length of input */
  maxLength?: number;
}

/**
 * Floating text input component for context/command injection.
 *
 * Positioned fixed at bottom center of viewport with:
 * - Auto-focus on load
 * - Enter key submits
 * - Cmd+K focuses input
 * - Input sanitization
 */
export function FloatingInput({
  onSubmit,
  placeholder = "Type a command...",
  autoFocus = true,
  maxLength = 1000,
}: FloatingInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");

  // Auto-focus on mount
  useEffect(() => {
    if (autoFocus && inputRef.current) {
      inputRef.current.focus();
    }
  }, [autoFocus]);

  // Cmd+K / Ctrl+K to focus input
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Basic sanitization: trim and limit length
  const sanitizeInput = (input: string): string => {
    return input.trim().slice(0, maxLength);
  };

  const handleSubmit = () => {
    const sanitized = sanitizeInput(value);
    if (sanitized) {
      onSubmit?.(sanitized);
      setValue("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="floating-input-container">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        maxLength={maxLength}
        className="floating-input"
        aria-label="Command input"
      />
      <style jsx>{`
        .floating-input-container {
          position: fixed;
          bottom: 2rem;
          left: 50%;
          transform: translateX(-50%);
          z-index: 1000;
          width: 90%;
          max-width: 600px;
        }

        .floating-input {
          width: 100%;
          padding: 0.875rem 1.25rem;
          font-size: 1rem;
          font-family: inherit;
          line-height: 1.5;
          color: #e5e5e5;
          background-color: #1a1a1a;
          border: 1px solid #333;
          border-radius: 0.5rem;
          outline: none;
          transition: all 0.15s ease-in-out;
          box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3),
            0 0 0 1px rgba(255, 255, 255, 0.05);
        }

        .floating-input:hover {
          border-color: #444;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4),
            0 0 0 1px rgba(255, 255, 255, 0.08);
        }

        .floating-input:focus {
          border-color: #666;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5),
            0 0 0 2px rgba(255, 255, 255, 0.1);
        }

        .floating-input::placeholder {
          color: #666;
        }

        @media (max-width: 640px) {
          .floating-input-container {
            bottom: 1rem;
            width: 95%;
          }

          .floating-input {
            padding: 0.75rem 1rem;
            font-size: 0.9375rem;
          }
        }
      `}</style>
    </div>
  );
}
