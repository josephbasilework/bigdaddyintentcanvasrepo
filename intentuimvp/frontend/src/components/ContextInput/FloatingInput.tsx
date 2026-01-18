"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Image from "next/image";
import { NodeContextBanner } from "./NodeContextBanner";
import type { ConversationScope } from "@/state/conversationStore";
import type { AttachmentItem } from "@/lib/attachments";
import { formatBytes } from "@/lib/attachments";

interface FloatingInputProps {
  /** Callback when user submits input (pressed Enter) */
  onSubmit?: (value: string) => void;
  /** Callback when files are dropped on the input */
  onFilesDrop?: (files: File[]) => void;
  /** Callback when input value changes */
  onValueChange?: (value: string) => void;
  /** Optional list of attachments to display */
  attachments?: AttachmentItem[];
  /** Optional list of selection scope labels to display */
  selection?: SelectionScopeItem[];
  /** Callback to remove an attachment by id */
  onRemoveAttachment?: (id: string) => void;
  /** Callback to clear the selection scope */
  onClearSelection?: () => void;
  /** Placeholder text for the input */
  placeholder?: string;
  /** Whether to auto-focus on mount */
  autoFocus?: boolean;
  /** Maximum length of input */
  maxLength?: number;
  /** Optional panel content rendered above the input stack */
  panelContent?: ReactNode;
  /** Optional toggle config for the panel */
  panelToggle?: PanelToggleConfig;
  /** Optional toggle configs for multiple panels */
  panelToggles?: PanelToggleConfig[];
  /** Current conversation scope (global or node-specific) */
  conversationScope?: ConversationScope;
  /** Callback when user clears the node context */
  onClearContext?: () => void;
}

interface SelectionScopeItem {
  id: string;
  label: string;
  /** Whether this node has content that will be used as context */
  hasContent?: boolean;
}

interface PanelToggleConfig {
  label: string;
  activeLabel?: string;
  ariaControls?: string;
  isOpen: boolean;
  onToggle: () => void;
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
  onFilesDrop,
  onValueChange,
  attachments,
  selection,
  onRemoveAttachment,
  onClearSelection,
  placeholder = "Type a command...",
  autoFocus = true,
  maxLength = 1000,
  panelContent,
  panelToggle,
  panelToggles,
  conversationScope,
  onClearContext,
}: FloatingInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);
  const selectionItems = selection ?? [];
  const selectionCount = selectionItems.length;
  const maxSelectionChips = 4;
  const visibleSelection = selectionItems.slice(0, maxSelectionChips);
  const overflowSelectionCount = Math.max(selectionCount - visibleSelection.length, 0);

  const formatSelectionLabel = (label: string) => {
    const maxLength = 28;
    if (label.length <= maxLength) {
      return label;
    }
    return `${label.slice(0, maxLength - 3).trimEnd()}...`;
  };

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
      onValueChange?.("");
    }
  };

  const applyTemplate = (template: SlashTemplate) => {
    const nextValue = template.stub.slice(0, maxLength);
    setValue(nextValue);
    onValueChange?.(nextValue);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    if (!onFilesDrop) return;
    event.preventDefault();
    setIsDragActive(true);
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    if (!onFilesDrop) return;
    event.preventDefault();
    setIsDragActive(false);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    if (!onFilesDrop) return;
    event.preventDefault();
    setIsDragActive(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
      onFilesDrop(files);
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
  const buildAttachmentMeta = (attachment: AttachmentItem): string => {
    const parts = [];
    if (attachment.attachmentType) {
      parts.push(attachment.attachmentType);
    }
    if (attachment.sizeBytes) {
      parts.push(formatBytes(attachment.sizeBytes));
    }
    return parts.join(" • ");
  };

  const renderAttachmentPreview = (attachment: AttachmentItem) => {
    const previewUrl = attachment.previewUrl;
    const mimeType = attachment.mimeType ?? "";
    if (previewUrl && mimeType.startsWith("image/")) {
      return (
        <Image
          src={previewUrl}
          alt={attachment.name}
          width={64}
          height={64}
          className="attachment-preview-image"
          unoptimized
        />
      );
    }
    if (mimeType.startsWith("audio/")) {
      return (
        <div className="attachment-preview-placeholder" aria-hidden="true">
          Audio
        </div>
      );
    }
    if (previewUrl && mimeType === "application/pdf") {
      return (
        <embed
          src={previewUrl}
          type="application/pdf"
          className="attachment-preview-pdf"
        />
      );
    }
    if (attachment.textPreview) {
      return <div className="attachment-preview-text">{attachment.textPreview}</div>;
    }
    if (attachment.descriptionPreview) {
      return (
        <div className="attachment-preview-text">{attachment.descriptionPreview}</div>
      );
    }
    return (
      <div className="attachment-preview-placeholder" aria-hidden="true">
        File
      </div>
    );
  };
  const resolvedToggles =
    panelToggles && panelToggles.length > 0
      ? panelToggles
      : panelToggle
        ? [panelToggle]
        : [];

  return (
    <div
      className={`floating-input-container${isDragActive ? " is-drag-active" : ""}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDragActive && (
        <div className="drop-hint" role="status" aria-live="polite">
          Drop files to attach
        </div>
      )}
      {panelContent && <div className="floating-panel">{panelContent}</div>}
      {conversationScope && (
        <NodeContextBanner
          scope={conversationScope}
          onClearContext={onClearContext}
        />
      )}
      {selectionCount > 0 && (
        <div className="selection-scope" role="region" aria-label="Selection scope">
          <div className="selection-scope-header">
            <span className="selection-scope-title">Selection scope</span>
            <div className="selection-scope-actions">
              <span className="selection-scope-count">
                {selectionCount} node{selectionCount === 1 ? "" : "s"}
              </span>
              {onClearSelection && (
                <button
                  type="button"
                  className="selection-clear"
                  onClick={onClearSelection}
                  aria-label="Clear selection"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
          <div className="selection-scope-chips" role="list" aria-label="Selected nodes">
            {visibleSelection.map((item) => (
              <div
                key={item.id}
                className={`selection-chip${item.hasContent ? " has-context" : ""}`}
                role="listitem"
                title={item.hasContent ? `${item.label} (content as context)` : item.label}
              >
                {item.hasContent && <span className="context-indicator" aria-hidden="true" />}
                {formatSelectionLabel(item.label)}
              </div>
            ))}
            {overflowSelectionCount > 0 && (
              <div
                className="selection-chip selection-chip-more"
                role="listitem"
                title={`${overflowSelectionCount} more selected nodes`}
              >
                +{overflowSelectionCount} more
              </div>
            )}
          </div>
        </div>
      )}
      {attachments && attachments.length > 0 && (
        <div className="attachment-list" role="list" aria-label="Attached files">
          {attachments.map((attachment) => (
            <div key={attachment.id} className="attachment-card" role="listitem">
              <div className="attachment-preview">{renderAttachmentPreview(attachment)}</div>
              <div className="attachment-body">
                <div className="attachment-header">
                  <span className="attachment-name" title={attachment.name}>
                    {attachment.name}
                  </span>
                  <span className="attachment-status">{attachment.status}</span>
                </div>
                <div className="attachment-meta">{buildAttachmentMeta(attachment)}</div>
                {attachment.previewUrl && attachment.mimeType.startsWith("audio/") && (
                  <audio controls preload="metadata" className="attachment-audio-inline">
                    <source src={attachment.previewUrl} type={attachment.mimeType} />
                    Your browser does not support audio playback.
                  </audio>
                )}
                {attachment.errorMessage && (
                  <div className="attachment-error">{attachment.errorMessage}</div>
                )}
              </div>
              {onRemoveAttachment && (
                <button
                  type="button"
                  className="attachment-remove"
                  onClick={() => onRemoveAttachment(attachment.id)}
                  aria-label={`Remove ${attachment.name}`}
                >
                  x
                </button>
              )}
            </div>
          ))}
        </div>
      )}
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
              role="option"
              aria-label={`${template.command} ${template.label}: ${template.description}`}
              aria-selected={false}
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
      {resolvedToggles.length > 0 && (
        <div className="panel-toggle">
          {resolvedToggles.map((toggle) => (
            <button
              key={toggle.label}
              type="button"
              className={`panel-toggle-button${toggle.isOpen ? " is-active" : ""}`}
              onClick={toggle.onToggle}
              aria-expanded={toggle.isOpen}
              aria-controls={toggle.ariaControls}
            >
              <span className="panel-toggle-label">
                {toggle.isOpen ? toggle.activeLabel ?? toggle.label : toggle.label}
              </span>
              {toggle.isOpen && <span className="panel-toggle-arrow" aria-hidden="true" />}
            </button>
          ))}
        </div>
      )}
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => {
          const nextValue = e.target.value;
          setValue(nextValue);
          onValueChange?.(nextValue);
        }}
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

        .floating-input-container.is-drag-active .floating-input {
          border-color: #38bdf8;
          box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.25);
        }

        .drop-hint {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          text-align: center;
          background: rgba(15, 23, 42, 0.85);
          border: 1px dashed #38bdf8;
          border-radius: 0.75rem;
          color: #e2e8f0;
          font-size: 0.85rem;
          pointer-events: none;
        }

        .floating-panel {
          margin-bottom: 0.75rem;
          display: flex;
          flex-direction: column;
          align-items: stretch;
          gap: 0.75rem;
          width: 100%;
          transform-origin: bottom center;
          animation: panel-rise 0.2s ease-out;
        }

        .selection-scope {
          display: flex;
          flex-direction: column;
          gap: 0.4rem;
          margin-bottom: 0.5rem;
          padding: 0.5rem 0.7rem;
          border-radius: 0.75rem;
          background-color: rgba(15, 23, 42, 0.85);
          border: 1px solid rgba(51, 65, 85, 0.7);
          color: #e2e8f0;
        }

        .selection-scope-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.75rem;
        }

        .selection-scope-title {
          font-size: 0.65rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: #94a3b8;
        }

        .selection-scope-actions {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .selection-scope-count {
          font-size: 0.75rem;
          color: #e2e8f0;
          font-weight: 600;
        }

        .selection-clear {
          padding: 0.2rem 0.5rem;
          border: 1px solid rgba(71, 85, 105, 0.6);
          border-radius: 0.35rem;
          background: transparent;
          color: #94a3b8;
          font-size: 0.7rem;
          cursor: pointer;
          transition: all 0.15s ease-in-out;
        }

        .selection-clear:hover {
          border-color: #64748b;
          color: #e2e8f0;
        }

        .selection-clear:focus-visible {
          outline: 2px solid var(--focus-ring);
          outline-offset: 2px;
        }

        .selection-scope-chips {
          display: flex;
          flex-wrap: wrap;
          gap: 0.35rem;
        }

        .selection-chip {
          display: inline-flex;
          align-items: center;
          gap: 0.3rem;
          padding: 0.3rem 0.55rem;
          border-radius: 999px;
          background-color: rgba(15, 23, 42, 0.9);
          border: 1px solid rgba(71, 85, 105, 0.6);
          color: #e2e8f0;
          font-size: 0.75rem;
          max-width: 200px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .selection-chip.has-context {
          border-color: rgba(56, 189, 248, 0.5);
          background-color: rgba(15, 23, 42, 0.95);
        }

        .context-indicator {
          display: inline-block;
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background-color: #38bdf8;
          flex-shrink: 0;
        }

        .selection-chip-more {
          color: #94a3b8;
          border-style: dashed;
        }

        .attachment-list {
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
          margin-bottom: 0.5rem;
        }

        .attachment-card {
          display: grid;
          grid-template-columns: 64px 1fr auto;
          align-items: center;
          gap: 0.6rem;
          padding: 0.5rem 0.6rem;
          border-radius: 0.75rem;
          background-color: #111827;
          border: 1px solid #2a2a2a;
          color: #e5e5e5;
          font-size: 0.78rem;
        }

        .attachment-preview {
          width: 64px;
          height: 64px;
          border-radius: 0.6rem;
          overflow: hidden;
          background: rgba(15, 23, 42, 0.8);
          border: 1px solid rgba(51, 65, 85, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .attachment-preview-image,
        .attachment-preview-pdf {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .attachment-preview-text {
          padding: 0.4rem;
          font-size: 0.65rem;
          color: #cbd5f5;
          line-height: 1.3;
          max-height: 56px;
          overflow: hidden;
        }

        .attachment-preview-placeholder {
          color: #94a3b8;
          font-size: 0.7rem;
        }

        .attachment-body {
          display: flex;
          flex-direction: column;
          gap: 0.2rem;
          min-width: 0;
        }

        .attachment-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.4rem;
        }

        .attachment-name {
          font-weight: 600;
          max-width: 100%;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .attachment-status {
          text-transform: uppercase;
          font-size: 0.6rem;
          letter-spacing: 0.08em;
          color: #93c5fd;
        }

        .attachment-meta {
          color: #9ca3af;
          font-size: 0.7rem;
        }

        .attachment-audio-inline {
          width: 100%;
          margin-top: 0.2rem;
        }

        .attachment-error {
          color: #fca5a5;
          font-size: 0.65rem;
        }

        .attachment-remove {
          border: none;
          background: transparent;
          color: #9ca3af;
          cursor: pointer;
          padding: 0;
          font-size: 1rem;
        }

        .attachment-remove:hover {
          color: #e5e5e5;
        }

        .attachment-remove:focus-visible {
          outline: 2px solid var(--focus-ring);
          outline-offset: 2px;
        }

        .panel-toggle {
          display: flex;
          justify-content: center;
          gap: 0.4rem;
          flex-wrap: wrap;
          margin-bottom: 0.5rem;
        }

        .panel-toggle-button {
          display: inline-flex;
          align-items: center;
          gap: 0.35rem;
          padding: 0.35rem 0.75rem;
          border-radius: 999px;
          border: 1px solid #2a2a2a;
          background: rgba(15, 23, 42, 0.9);
          color: #e2e8f0;
          font-size: 0.75rem;
          letter-spacing: 0.02em;
          text-transform: uppercase;
          cursor: pointer;
        }

        .panel-toggle-arrow {
          width: 0;
          height: 0;
          border-left: 4px solid transparent;
          border-right: 4px solid transparent;
          border-bottom: 6px solid currentColor;
          display: inline-block;
          transform: translateY(-1px);
        }

        .panel-toggle-button.is-active {
          border-color: #38bdf8;
          color: #e0f2fe;
          box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.35);
        }

        .panel-toggle-button:hover {
          border-color: #475569;
        }

        .panel-toggle-button:focus-visible {
          outline: 2px solid var(--focus-ring);
          outline-offset: 2px;
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

        .slash-template-item:hover {
          border-color: #3d3d3d;
          background-color: #1a1a1a;
        }

        .slash-template-item:focus-visible {
          border-color: #3d3d3d;
          background-color: #1a1a1a;
          outline: 2px solid var(--focus-ring);
          outline-offset: 2px;
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

        .floating-input:focus-visible {
          outline: 2px solid var(--focus-ring);
          outline-offset: 2px;
        }

        .floating-input::placeholder {
          color: #94a3b8;
        }

        @media (max-width: 640px) {
          .floating-input-container {
            bottom: 1rem;
            width: 95%;
          }

          .selection-scope {
            padding: 0.45rem 0.6rem;
          }

          .selection-scope-title {
            font-size: 0.6rem;
          }

          .selection-scope-count {
            font-size: 0.7rem;
          }

          .attachment-name {
            max-width: 160px;
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

        @keyframes panel-rise {
          from {
            opacity: 0;
            transform: translateY(10px) scale(0.98);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .floating-panel {
            animation: none;
          }
        }
      `}</style>
    </div>
  );
}
