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

interface SlashTemplate {
  command: string;
  label: string;
  description: string;
  stub: string;
}

const SLASH_TEMPLATES: SlashTemplate[] = [
  {
    command: "/research",
    label: "Research",
    description: "Explore a topic or question",
    stub: "/research ",
  },
  {
    command: "/judge",
    label: "Judge",
    description: "Evaluate tradeoffs or decisions",
    stub: "/judge ",
  },
  {
    command: "/plan",
    label: "Plan",
    description: "Draft a plan with steps",
    stub: "/plan ",
  },
  {
    command: "/dashboard",
    label: "Dashboard",
    description: "Summarize the current workspace",
    stub: "/dashboard ",
  },
  {
    command: "/graph",
    label: "Graph",
    description: "Map relationships on the canvas",
    stub: "/graph ",
  },
  {
    command: "/export",
    label: "Export",
    description: "Package outputs for sharing",
    stub: "/export ",
  },
];

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

  const applyTemplate = (template: SlashTemplate) => {
    const nextValue = template.stub.slice(0, maxLength);
    setValue(nextValue);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const trimmedValue = value.trimStart();
  const hasCommandArgs = trimmedValue.includes(" ");
  const commandToken = trimmedValue.split(/\s+/)[0];
  const shouldShowTemplates = trimmedValue.startsWith("/") && !hasCommandArgs;
  const templateQuery = commandToken.slice(1).toLowerCase();
  const visibleTemplates = shouldShowTemplates
    ? SLASH_TEMPLATES.filter((template) =>
        template.command.slice(1).startsWith(templateQuery)
      )
    : [];

  return (
    <div className="floating-input-container">
      {visibleTemplates.length > 0 && (
        <div className="slash-templates" role="listbox" aria-label="Slash command templates">
          {visibleTemplates.map((template) => (
            <button
              key={template.command}
              type="button"
              className="slash-template-item"
              onMouseDown={(event) => {
                event.preventDefault();
                applyTemplate(template);
              }}
            >
              <div className="template-row">
                <span className="template-command">{template.command}</span>
                <span className="template-label">{template.label}</span>
              </div>
              <span className="template-description">{template.description}</span>
            </button>
          ))}
        </div>
      )}
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

        .slash-templates {
          position: absolute;
          bottom: calc(100% + 0.5rem);
          left: 0;
          right: 0;
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
          padding: 0.6rem;
          background-color: #0f0f0f;
          border: 1px solid #2a2a2a;
          border-radius: 0.75rem;
          box-shadow: 0 12px 24px rgba(0, 0, 0, 0.4),
            0 0 0 1px rgba(255, 255, 255, 0.04);
          max-height: 260px;
          overflow-y: auto;
        }

        .slash-template-item {
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          gap: 0.2rem;
          padding: 0.6rem 0.75rem;
          border: 1px solid transparent;
          border-radius: 0.6rem;
          background: transparent;
          color: #e5e5e5;
          font-family: inherit;
          text-align: left;
          cursor: pointer;
        }

        .slash-template-item:hover,
        .slash-template-item:focus-visible {
          border-color: #3d3d3d;
          background-color: #1a1a1a;
        }

        .template-row {
          display: flex;
          gap: 0.5rem;
          align-items: center;
        }

        .template-command {
          font-weight: 600;
          letter-spacing: 0.02em;
        }

        .template-label {
          font-size: 0.85rem;
          color: #b0b0b0;
        }

        .template-description {
          font-size: 0.8rem;
          color: #8a8a8a;
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

          .slash-templates {
            padding: 0.5rem;
            max-height: 220px;
          }

          .slash-template-item {
            padding: 0.5rem 0.65rem;
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
