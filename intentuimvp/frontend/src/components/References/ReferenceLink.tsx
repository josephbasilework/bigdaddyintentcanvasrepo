"use client";

import { useCallback } from "react";
import { useCanvasStore } from "@/state/canvasStore";
import { useConversationStore } from "@/state/conversationStore";

type ReferenceLinkProps = React.ComponentPropsWithoutRef<"a"> & { node?: unknown };

const parseTurnId = (href: string): number | null => {
  if (href.startsWith("#turn-")) {
    const raw = href.slice("#turn-".length);
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }
  if (href.startsWith("turn:")) {
    const raw = href.slice("turn:".length);
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
  }
  return null;
};

const parseNodeId = (href: string): string | null => {
  if (href.startsWith("#node-")) {
    const value = href.slice("#node-".length).trim();
    return value || null;
  }
  if (href.startsWith("node:")) {
    const value = href.slice("node:".length).trim();
    return value || null;
  }
  return null;
};

export const ReferenceLink = ({
  href = "",
  className,
  onClick,
  node: _node,
  ...props
}: ReferenceLinkProps) => {
  void _node;
  const nodes = useCanvasStore((state) => state.nodes);
  const selectNode = useCanvasStore((state) => state.selectNode);
  const setNodeScope = useConversationStore((state) => state.setNodeScope);

  const handleClick = useCallback(
    (event: React.MouseEvent<HTMLAnchorElement>) => {
      const turnId = parseTurnId(href);
      if (turnId !== null) {
        event.preventDefault();
        if (typeof window !== "undefined") {
          window.location.hash = `#turn-${turnId}`;
        }
        onClick?.(event);
        return;
      }

      const nodeId = parseNodeId(href);
      if (nodeId !== null) {
        event.preventDefault();
        const node = nodes.find((item) => item.id === nodeId);
        selectNode(nodeId);
        if (node) {
          setNodeScope(nodeId, node.title, Boolean(node.content));
        }
        if (typeof window !== "undefined") {
          window.location.hash = `#node-${nodeId}`;
        }
        onClick?.(event);
      }
    },
    [href, nodes, onClick, selectNode, setNodeScope]
  );

  const isReference =
    href.startsWith("#turn-") ||
    href.startsWith("#node-") ||
    href.startsWith("turn:") ||
    href.startsWith("node:");
  const mergedClassName = isReference
    ? className
      ? `${className} reference-link`
      : "reference-link"
    : className;

  if (!isReference) {
    return <a href={href} className={mergedClassName} onClick={onClick} {...props} />;
  }

  return <a href={href} className={mergedClassName} onClick={handleClick} {...props} />;
};
