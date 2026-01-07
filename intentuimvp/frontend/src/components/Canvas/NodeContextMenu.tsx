"use client";

import { useEffect, useRef } from "react";

interface ContextMenuProps {
  x: number;
  y: number;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onDuplicate?: () => void;
  onConnect?: () => void;
}

/**
 * NodeContextMenu component that displays a context menu for node operations.
 *
 * Provides options for:
 * - Edit node title and content
 * - Delete node
 * - Duplicate node
 * - Connect to another node
 */
export function NodeContextMenu({
  x,
  y,
  onClose,
  onEdit,
  onDelete,
  onDuplicate,
  onConnect,
}: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const positionComputedRef = useRef(false);

  // Adjust position after mount to keep menu within viewport
  useEffect(() => {
    if (menuRef.current && !positionComputedRef.current) {
      const rect = menuRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      let needsAdjustment = false;
      let adjustedX = x;
      let adjustedY = y;

      if (x + rect.width > viewportWidth) {
        adjustedX = viewportWidth - rect.width - 10;
        needsAdjustment = true;
      }
      if (y + rect.height > viewportHeight) {
        adjustedY = viewportHeight - rect.height - 10;
        needsAdjustment = true;
      }

      if (needsAdjustment) {
        menuRef.current.style.left = `${adjustedX}px`;
        menuRef.current.style.top = `${adjustedY}px`;
      }

      positionComputedRef.current = true;
    }
  }, [x, y]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [onClose]);

  const handleAction = (action: () => void) => {
    action();
    onClose();
  };

  return (
    <div
      ref={menuRef}
      style={{
        position: "fixed",
        left: x,
        top: y,
        zIndex: 10000,
        minWidth: "160px",
      }}
      className="node-context-menu"
    >
      <div
        style={{
          backgroundColor: "#1a202c",
          border: "1px solid #2d3748",
          borderRadius: "6px",
          boxShadow: "0 4px 12px rgba(0, 0, 0, 0.5)",
          overflow: "hidden",
        }}
      >
        <MenuItem onClick={() => handleAction(onEdit)}>✏️ Edit</MenuItem>
        {onDuplicate && <MenuItem onClick={() => handleAction(onDuplicate)}>📋 Duplicate</MenuItem>}
        {onConnect && <MenuItem onClick={() => handleAction(onConnect)}>🔗 Connect...</MenuItem>}
        <div
          style={{
            height: "1px",
            backgroundColor: "#2d3748",
            margin: "4px 0",
          }}
        />
        <MenuItem onClick={() => handleAction(onDelete)} danger>
          🗑️ Delete
        </MenuItem>
      </div>
      <style jsx>{`
        .node-context-menu :global(.menu-item) {
          padding: 8px 12px;
          cursor: pointer;
          display: flex;
          align-items: "center";
          gap: "8px";
          fontSize: "13px";
          color: "#e2e8f0";
          transition: "background-color 0.1s";
        }
        .node-context-menu :global(.menu-item:hover) {
          backgroundColor: "#2d3748";
        }
        .node-context-menu :global(.menu-item.danger:hover) {
          backgroundColor: "#742a2a";
          color: "#feb2b2";
        }
      `}</style>
    </div>
  );
}

interface MenuItemProps {
  children: React.ReactNode;
  onClick: () => void;
  danger?: boolean;
}

function MenuItem({ children, onClick, danger = false }: MenuItemProps) {
  return (
    <div
      className={`menu-item ${danger ? "danger" : ""}`}
      onClick={onClick}
      style={{
        padding: "8px 12px",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        gap: "8px",
        fontSize: "13px",
        color: "#e2e8f0",
      }}
    >
      {children}
    </div>
  );
}
