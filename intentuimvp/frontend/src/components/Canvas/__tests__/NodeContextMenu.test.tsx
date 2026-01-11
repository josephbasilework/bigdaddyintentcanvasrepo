import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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

  it("closes on escape or outside click", () => {
    const onClose = vi.fn();

    render(
      <NodeContextMenu
        x={120}
        y={80}
        onClose={onClose}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
        onDuplicate={vi.fn()}
        onConnect={vi.fn()}
      />
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.mouseDown(document.body);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
