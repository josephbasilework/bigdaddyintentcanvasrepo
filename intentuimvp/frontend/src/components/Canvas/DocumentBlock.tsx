"use client";

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { MarkdownPreview } from "./MarkdownPreview";

interface DocumentBlockProps {
  nodeId: string;
  title: string;
  content: string;
  onSave: (nodeId: string, title: string, content: string) => void;
  onCancel: () => void;
}

const applyWrap = (
  value: string,
  selectionStart: number,
  selectionEnd: number,
  prefix: string,
  suffix: string,
  placeholder: string
): { nextValue: string; nextSelectionStart: number; nextSelectionEnd: number } => {
  const hasSelection = selectionStart !== selectionEnd;
  const selectedText = value.slice(selectionStart, selectionEnd);
  const nextText = hasSelection ? selectedText : placeholder;
  const nextValue =
    value.slice(0, selectionStart) +
    prefix +
    nextText +
    suffix +
    value.slice(selectionEnd);
  const nextSelectionStart = selectionStart + prefix.length;
  const nextSelectionEnd = nextSelectionStart + nextText.length;
  return { nextValue, nextSelectionStart, nextSelectionEnd };
};

const applyLinePrefix = (
  value: string,
  selectionStart: number,
  selectionEnd: number,
  prefix: string
): { nextValue: string; nextSelectionStart: number; nextSelectionEnd: number } => {
  const lineStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
  const lineEnd = value.indexOf("\n", selectionEnd);
  const end = lineEnd === -1 ? value.length : lineEnd;
  const selectedBlock = value.slice(lineStart, end);
  const lines = selectedBlock.split("\n");
  const nextLines = lines.map((line, index) => {
    const trimmed = line.trim();
    if (!trimmed && index === lines.length - 1) {
      return `${prefix}${trimmed}`.trimEnd();
    }
    return line.startsWith(prefix) ? line : `${prefix}${line}`;
  });
  const nextBlock = nextLines.join("\n");
  const nextValue = value.slice(0, lineStart) + nextBlock + value.slice(end);
  const nextSelectionStart = lineStart;
  const nextSelectionEnd = lineStart + nextBlock.length;
  return { nextValue, nextSelectionStart, nextSelectionEnd };
};

const applyOrderedList = (
  value: string,
  selectionStart: number,
  selectionEnd: number
): { nextValue: string; nextSelectionStart: number; nextSelectionEnd: number } => {
  const lineStart = value.lastIndexOf("\n", selectionStart - 1) + 1;
  const lineEnd = value.indexOf("\n", selectionEnd);
  const end = lineEnd === -1 ? value.length : lineEnd;
  const selectedBlock = value.slice(lineStart, end);
  const lines = selectedBlock.split("\n");
  const nextLines = lines.map((line, index) => {
    const cleaned = line.replace(/^\s*\d+\.\s+/, "");
    return `${index + 1}. ${cleaned}`.trimEnd();
  });
  const nextBlock = nextLines.join("\n");
  const nextValue = value.slice(0, lineStart) + nextBlock + value.slice(end);
  const nextSelectionStart = lineStart;
  const nextSelectionEnd = lineStart + nextBlock.length;
  return { nextValue, nextSelectionStart, nextSelectionEnd };
};

const applyCodeBlock = (
  value: string,
  selectionStart: number,
  selectionEnd: number
): { nextValue: string; nextSelectionStart: number; nextSelectionEnd: number } =>
  applyWrap(value, selectionStart, selectionEnd, "```\n", "\n```", "code block");

export function DocumentBlock({ nodeId, title, content, onSave, onCancel }: DocumentBlockProps) {
  const dialogTitleId = useId();
  const titleInputId = useId();
  const editorId = useId();
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const [localTitle, setLocalTitle] = useState(title);
  const [localContent, setLocalContent] = useState(content || "");

  useEffect(() => {
    setLocalTitle(title);
  }, [title]);

  useEffect(() => {
    setLocalContent(content || "");
  }, [content]);

  const focusAndSelect = useCallback((start: number, end: number) => {
    if (!textareaRef.current) return;
    textareaRef.current.focus();
    textareaRef.current.setSelectionRange(start, end);
  }, []);

  const handleApplyWrap = useCallback(
    (prefix: string, suffix: string, placeholder: string) => {
      const textarea = textareaRef.current;
      if (!textarea) return;
      const { selectionStart, selectionEnd, value } = textarea;
      const { nextValue, nextSelectionStart, nextSelectionEnd } = applyWrap(
        value,
        selectionStart,
        selectionEnd,
        prefix,
        suffix,
        placeholder
      );
      setLocalContent(nextValue);
      requestAnimationFrame(() => focusAndSelect(nextSelectionStart, nextSelectionEnd));
    },
    [focusAndSelect]
  );

  const handleApplyLinePrefix = useCallback(
    (prefix: string) => {
      const textarea = textareaRef.current;
      if (!textarea) return;
      const { selectionStart, selectionEnd, value } = textarea;
      const { nextValue, nextSelectionStart, nextSelectionEnd } = applyLinePrefix(
        value,
        selectionStart,
        selectionEnd,
        prefix
      );
      setLocalContent(nextValue);
      requestAnimationFrame(() => focusAndSelect(nextSelectionStart, nextSelectionEnd));
    },
    [focusAndSelect]
  );

  const handleApplyOrderedList = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const { selectionStart, selectionEnd, value } = textarea;
    const { nextValue, nextSelectionStart, nextSelectionEnd } = applyOrderedList(
      value,
      selectionStart,
      selectionEnd
    );
    setLocalContent(nextValue);
    requestAnimationFrame(() => focusAndSelect(nextSelectionStart, nextSelectionEnd));
  }, [focusAndSelect]);

  const handleApplyCodeBlock = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const { selectionStart, selectionEnd, value } = textarea;
    const { nextValue, nextSelectionStart, nextSelectionEnd } = applyCodeBlock(
      value,
      selectionStart,
      selectionEnd
    );
    setLocalContent(nextValue);
    requestAnimationFrame(() => focusAndSelect(nextSelectionStart, nextSelectionEnd));
  }, [focusAndSelect]);

  const handleSave = useCallback(() => {
    const trimmed = localTitle.trim();
    const nextTitle = trimmed.length > 0 ? trimmed : "Untitled";
    onSave(nodeId, nextTitle, localContent);
  }, [localContent, localTitle, nodeId, onSave]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "s") {
        event.preventDefault();
        handleSave();
      }
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleSave, onCancel]);

  if (typeof document === "undefined") {
    return null;
  }

  const hasPreview = localContent.trim().length > 0;
  const characterCount = localContent.length;

  return createPortal(
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10002,
      }}
      onClick={onCancel}
    >
      <div
        className="document-editor"
        style={{
          backgroundColor: "#111827",
          border: "1px solid rgba(148, 163, 184, 0.3)",
          borderRadius: "12px",
          width: "94%",
          maxWidth: "1100px",
          height: "86vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 18px 30px rgba(0, 0, 0, 0.45)",
        }}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={dialogTitleId}
      >
        <h2 id={dialogTitleId} className="sr-only">
          Document editor
        </h2>

        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid rgba(148, 163, 184, 0.25)",
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <label htmlFor={titleInputId} className="sr-only">
            Document title
          </label>
          <input
            id={titleInputId}
            type="text"
            value={localTitle}
            onChange={(event) => setLocalTitle(event.target.value)}
            placeholder="Document title..."
            style={{
              flex: 1,
              padding: "10px 12px",
              backgroundColor: "rgba(15, 23, 42, 0.75)",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              borderRadius: "8px",
              color: "#f8fafc",
              fontSize: "16px",
              fontWeight: 600,
            }}
          />
        </div>

        <div
          className="document-editor__toolbar"
          style={{
            padding: "10px 16px",
            borderBottom: "1px solid rgba(148, 163, 184, 0.25)",
            display: "flex",
            flexWrap: "wrap",
            gap: "6px",
            backgroundColor: "rgba(15, 23, 42, 0.85)",
          }}
        >
          <ToolbarButton
            label="Bold"
            onClick={() => handleApplyWrap("**", "**", "bold text")}
          >
            B
          </ToolbarButton>
          <ToolbarButton
            label="Italic"
            onClick={() => handleApplyWrap("*", "*", "italic text")}
          >
            I
          </ToolbarButton>
          <ToolbarButton
            label="Strike"
            onClick={() => handleApplyWrap("~~", "~~", "strike text")}
          >
            S
          </ToolbarButton>

          <div className="document-editor__divider" />

          <ToolbarButton
            label="Heading 1"
            onClick={() => handleApplyLinePrefix("# ")}
          >
            H1
          </ToolbarButton>
          <ToolbarButton
            label="Heading 2"
            onClick={() => handleApplyLinePrefix("## ")}
          >
            H2
          </ToolbarButton>
          <ToolbarButton
            label="Heading 3"
            onClick={() => handleApplyLinePrefix("### ")}
          >
            H3
          </ToolbarButton>

          <div className="document-editor__divider" />

          <ToolbarButton
            label="Bulleted list"
            onClick={() => handleApplyLinePrefix("- ")}
          >
            UL
          </ToolbarButton>
          <ToolbarButton
            label="Numbered list"
            onClick={handleApplyOrderedList}
          >
            1.
          </ToolbarButton>
          <ToolbarButton
            label="Quote"
            onClick={() => handleApplyLinePrefix("> ")}
          >
            &gt;
          </ToolbarButton>
          <ToolbarButton label="Code block" onClick={handleApplyCodeBlock}>
            &lt;/&gt;
          </ToolbarButton>

          <div className="document-editor__divider" />

          <ToolbarButton
            label="Link"
            onClick={() => handleApplyWrap("[", "](url)", "link text")}
          >
            Link
          </ToolbarButton>
          <ToolbarButton
            label="Image"
            onClick={() => handleApplyWrap("![", "](url)", "alt text")}
          >
            Img
          </ToolbarButton>
        </div>

        <div className="document-editor__layout">
          <div className="document-editor__pane">
            <label
              htmlFor={editorId}
              style={{
                display: "block",
                marginBottom: "8px",
                fontSize: "12px",
                color: "#94a3b8",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Markdown
            </label>
            <textarea
              id={editorId}
              ref={textareaRef}
              value={localContent}
              onChange={(event) => setLocalContent(event.target.value)}
              placeholder="Start writing in markdown..."
              aria-label="Document content"
              style={{
                width: "100%",
                height: "100%",
                resize: "none",
                padding: "12px",
                backgroundColor: "rgba(15, 23, 42, 0.7)",
                border: "1px solid rgba(148, 163, 184, 0.35)",
                borderRadius: "10px",
                color: "#e2e8f0",
                fontSize: "14px",
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                lineHeight: 1.5,
                outline: "none",
              }}
            />
          </div>

          <div className="document-editor__pane" aria-label="Document preview">
            <div
              style={{
                marginBottom: "8px",
                fontSize: "12px",
                color: "#94a3b8",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Live preview
            </div>
            <div
              style={{
                height: "100%",
                padding: "12px",
                borderRadius: "10px",
                border: "1px solid rgba(148, 163, 184, 0.25)",
                backgroundColor: "rgba(15, 23, 42, 0.6)",
                overflow: "auto",
                color: "#e2e8f0",
              }}
            >
              {hasPreview ? (
                <MarkdownPreview content={localContent} variant="full" />
              ) : (
                <div style={{ color: "#64748b", fontSize: "13px" }}>
                  Start typing to see the preview.
                </div>
              )}
            </div>
          </div>
        </div>

        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid rgba(148, 163, 184, 0.25)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            backgroundColor: "rgba(15, 23, 42, 0.85)",
          }}
        >
          <div style={{ fontSize: "12px", color: "#94a3b8" }}>
            {characterCount} characters
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              onClick={onCancel}
              style={{
                padding: "8px 16px",
                backgroundColor: "rgba(148, 163, 184, 0.2)",
                border: "1px solid rgba(148, 163, 184, 0.4)",
                borderRadius: "8px",
                color: "#e2e8f0",
                cursor: "pointer",
                fontSize: "13px",
              }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              aria-label="Save document"
              style={{
                padding: "8px 16px",
                backgroundColor: "rgba(56, 189, 248, 0.9)",
                border: "1px solid rgba(56, 189, 248, 0.9)",
                borderRadius: "8px",
                color: "#0f172a",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: 600,
              }}
            >
              Save (Ctrl+S)
            </button>
          </div>
        </div>

        <style jsx>{`
          .document-editor__layout {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 16px;
            padding: 16px;
            flex: 1;
            overflow: hidden;
          }

          .document-editor__pane {
            display: flex;
            flex-direction: column;
            min-height: 0;
          }

          .document-editor__divider {
            width: 1px;
            background-color: rgba(148, 163, 184, 0.3);
            margin: 0 4px;
          }

          @media (max-width: 900px) {
            .document-editor__layout {
              grid-template-columns: 1fr;
              grid-template-rows: repeat(2, minmax(0, 1fr));
            }

            .document-editor__divider {
              display: none;
            }
          }
        `}</style>
      </div>
    </div>,
    document.body
  );
}

interface ToolbarButtonProps {
  children: ReactNode;
  onClick: () => void;
  label: string;
}

function ToolbarButton({ children, onClick, label }: ToolbarButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      onMouseDown={(event) => event.preventDefault()}
      title={label}
      aria-label={label}
      style={{
        minWidth: "34px",
        height: "32px",
        padding: "0 8px",
        backgroundColor: "rgba(15, 23, 42, 0.7)",
        border: "1px solid rgba(148, 163, 184, 0.25)",
        borderRadius: "6px",
        color: "#e2e8f0",
        cursor: "pointer",
        fontSize: "12px",
        fontWeight: 600,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {children}
    </button>
  );
}
