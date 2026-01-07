"use client";

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { useEffect, useCallback, useState } from "react";

interface DocumentBlockProps {
  nodeId: string;
  title: string;
  content: string;
  onSave: (nodeId: string, title: string, content: string) => void;
  onCancel: () => void;
}

/**
 * DocumentBlock component with rich text editing using Tiptap.
 *
 * Provides a WYSIWYG editor with:
 * - Bold, italic, underline, strike
 * - Headings (h1, h2, h3)
 * - Bullet and numbered lists
 * - Blockquotes
 * - Code blocks
 * - Undo/redo
 */
export function DocumentBlock({ nodeId, title, content, onSave, onCancel }: DocumentBlockProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: {
          levels: [1, 2, 3],
        },
      }),
      Placeholder.configure({
        placeholder: "Start typing your document...",
      }),
    ],
    content: content || "",
    editorProps: {
      attributes: {
        class: "prose prose-invert max-w-none focus:outline-none",
      },
    },
  });

  // Sync initial content when component mounts
  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      editor.commands.setContent(content || "");
    }
  }, [content, editor]);

  const [localTitle, setLocalTitle] = useState(title);

  const handleSave = useCallback(() => {
    if (editor) {
      onSave(nodeId, localTitle, editor.getHTML());
    }
  }, [editor, nodeId, localTitle, onSave]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + S to save
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        handleSave();
      }
      // Escape to cancel
      if (e.key === "Escape") {
        onCancel();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleSave, onCancel]);

  if (!editor) {
    return null;
  }

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.8)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10002,
      }}
      onClick={onCancel}
    >
      <div
        style={{
          backgroundColor: "#1a202c",
          border: "1px solid #2d3748",
          borderRadius: "8px",
          width: "90%",
          maxWidth: "900px",
          height: "85vh",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid #2d3748",
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          <input
            type="text"
            value={localTitle}
            onChange={(e) => setLocalTitle(e.target.value)}
            placeholder="Document title..."
            style={{
              flex: 1,
              padding: "8px 12px",
              backgroundColor: "#2d3748",
              border: "1px solid #4a5568",
              borderRadius: "4px",
              color: "#fff",
              fontSize: "16px",
              fontWeight: 600,
            }}
          />
        </div>

        {/* Toolbar */}
        <div
          style={{
            padding: "8px 16px",
            borderBottom: "1px solid #2d3748",
            display: "flex",
            gap: "4px",
            flexWrap: "wrap",
            backgroundColor: "#162032",
          }}
        >
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBold().run()}
            active={editor.isActive("bold")}
            label="Bold"
          >
            <strong>B</strong>
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleItalic().run()}
            active={editor.isActive("italic")}
            label="Italic"
          >
            <em>I</em>
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleStrike().run()}
            active={editor.isActive("strike")}
            label="Strike"
          >
            <s>S</s>
          </ToolbarButton>

          <div style={{ width: "1px", backgroundColor: "#2d3748", margin: "0 4px" }} />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            active={editor.isActive("heading", { level: 1 })}
            label="H1"
          >
            H1
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            active={editor.isActive("heading", { level: 2 })}
            label="H2"
          >
            H2
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
            active={editor.isActive("heading", { level: 3 })}
            label="H3"
          >
            H3
          </ToolbarButton>

          <div style={{ width: "1px", backgroundColor: "#2d3748", margin: "0 4px" }} />

          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            active={editor.isActive("bulletList")}
            label="Bullet list"
          >
            •
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            active={editor.isActive("orderedList")}
            label="Numbered list"
          >
            1.
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleBlockquote().run()}
            active={editor.isActive("blockquote")}
            label="Quote"
          >
            &quot;
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().toggleCodeBlock().run()}
            active={editor.isActive("codeBlock")}
            label="Code"
          >
            &lt;/&gt;
          </ToolbarButton>

          <div style={{ width: "1px", backgroundColor: "#2d3748", margin: "0 4px" }} />

          <ToolbarButton
            onClick={() => editor.chain().focus().undo().run()}
            disabled={!editor.can().undo()}
            label="Undo"
          >
            ↶
          </ToolbarButton>
          <ToolbarButton
            onClick={() => editor.chain().focus().redo().run()}
            disabled={!editor.can().redo()}
            label="Redo"
          >
            ↷
          </ToolbarButton>
        </div>

        {/* Editor */}
        <div
          style={{
            flex: 1,
            overflow: "auto",
            padding: "20px",
          }}
        >
          <EditorContent editor={editor} />
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "12px 20px",
            borderTop: "1px solid #2d3748",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            backgroundColor: "#162032",
          }}
        >
          <div style={{ fontSize: "12px", color: "#718096" }}>
            {editor.storage.characterCount?.characters() || 0} characters
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={onCancel}
              style={{
                padding: "8px 16px",
                backgroundColor: "#4a5568",
                border: "none",
                borderRadius: "4px",
                color: "#fff",
                cursor: "pointer",
                fontSize: "13px",
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              style={{
                padding: "8px 16px",
                backgroundColor: "#4299e1",
                border: "none",
                borderRadius: "4px",
                color: "#fff",
                cursor: "pointer",
                fontSize: "13px",
              }}
            >
              Save (Ctrl+S)
            </button>
          </div>
        </div>
      </div>

      <style jsx global>{`
        .ProseMirror {
          outline: none;
          color: #e2e8f0;
          font-size: 15px;
          line-height: 1.6;
        }

        .ProseMirror p.is-editor-empty:first-child::before {
          color: #718096;
          content: attr(data-placeholder);
          float: left;
          height: 0;
          pointer-events: none;
        }

        .ProseMirror h1 {
          font-size: 2em;
          font-weight: bold;
          margin-top: 1em;
          margin-bottom: 0.5em;
          color: #fff;
        }

        .ProseMirror h2 {
          font-size: 1.5em;
          font-weight: bold;
          margin-top: 1em;
          margin-bottom: 0.5em;
          color: #fff;
        }

        .ProseMirror h3 {
          font-size: 1.25em;
          font-weight: bold;
          margin-top: 1em;
          margin-bottom: 0.5em;
          color: #fff;
        }

        .ProseMirror ul,
        .ProseMirror ol {
          padding-left: 1.5em;
          margin: 1em 0;
        }

        .ProseMirror li {
          margin: 0.25em 0;
        }

        .ProseMirror blockquote {
          border-left: 3px solid #4a5568;
          padding-left: 1em;
          margin: 1em 0;
          color: #a0aec0;
          font-style: italic;
        }

        .ProseMirror pre {
          background: #2d3748;
          border-radius: 4px;
          padding: 1em;
          margin: 1em 0;
          overflow-x: auto;
        }

        .ProseMirror code {
          background: #2d3748;
          padding: 0.2em 0.4em;
          border-radius: 3px;
          font-family: monospace;
          font-size: 0.9em;
        }

        .ProseMirror pre code {
          background: transparent;
          padding: 0;
        }

        .ProseMirror strong {
          font-weight: bold;
          color: #fff;
        }

        .ProseMirror em {
          font-style: italic;
        }

        .ProseMirror s {
          text-decoration: line-through;
        }
      `}</style>
    </div>
  );
}

interface ToolbarButtonProps {
  children: React.ReactNode;
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  label: string;
}

function ToolbarButton({ children, onClick, active = false, disabled = false, label }: ToolbarButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={label}
      style={{
        minWidth: "32px",
        height: "32px",
        padding: "0 8px",
        backgroundColor: active ? "#4299e1" : "transparent",
        border: active ? "1px solid #4299e1" : "1px solid transparent",
        borderRadius: "4px",
        color: active ? "#fff" : "#e2e8f0",
        cursor: disabled ? "not-allowed" : "pointer",
        fontSize: "14px",
        opacity: disabled ? 0.5 : 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
      onMouseEnter={(e) => {
        if (!disabled && !active) {
          e.currentTarget.style.backgroundColor = "#2d3748";
        }
      }}
      onMouseLeave={(e) => {
        if (!active) {
          e.currentTarget.style.backgroundColor = "transparent";
        }
      }}
    >
      {children}
    </button>
  );
}
