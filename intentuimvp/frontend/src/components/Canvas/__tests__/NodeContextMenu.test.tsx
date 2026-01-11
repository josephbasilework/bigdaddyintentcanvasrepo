import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NodeContextMenu } from "../NodeContextMenu";

describe("NodeContextMenu", () => {
  it("exposes menu items with accessible labels", () => {
    const onClose = vi.fn();
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    const onDuplicate = vi.fn();
    const onConnect = vi.fn();

    render(
      <NodeContextMenu
        x={120}
        y={80}
        onClose={onClose}
        onEdit={onEdit}
        onDelete={onDelete}
        onDuplicate={onDuplicate}
        onConnect={onConnect}
      />
    );

    expect(screen.getByRole("menu", { name: /node actions/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /edit node/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /duplicate node/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /connect node/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /delete node/i })).toBeInTheDocument();
  });
});
