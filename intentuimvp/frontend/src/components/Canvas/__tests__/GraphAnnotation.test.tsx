import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { GraphAnnotation, GraphAnnotationDisplay } from "../GraphAnnotation";
import type { GraphNodeAnnotation } from "../../../state/canvasStore";

describe("GraphAnnotation", () => {
  it("renders annotation editor with empty state", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <GraphAnnotation
        annotation={undefined}
        onSave={onSave}
        onCancel={onCancel}
      />
    );

    expect(screen.getByText(/graph node annotations/i)).toBeInTheDocument();
    expect(screen.getByText(/status/i)).toBeInTheDocument();
    expect(screen.getByText(/bullet annotations/i)).toBeInTheDocument();
    expect(screen.getByText(/tags/i)).toBeInTheDocument();
  });

  it("renders with existing annotation data", () => {
    const annotation: GraphNodeAnnotation = {
      bullets: ["First point", "Second point"],
      tags: ["important", "review"],
      status: "review",
    };
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <GraphAnnotation
        annotation={annotation}
        onSave={onSave}
        onCancel={onCancel}
      />
    );

    expect(screen.getByText("First point")).toBeInTheDocument();
    expect(screen.getByText("Second point")).toBeInTheDocument();
    expect(screen.getByText("important")).toBeInTheDocument();
    // "review" appears multiple times (as status button and tag), use getAllByText
    expect(screen.getAllByText("review")).toHaveLength(2);
  });

  it("adds bullet annotation", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <GraphAnnotation
        annotation={undefined}
        onSave={onSave}
        onCancel={onCancel}
      />
    );

    const input = screen.getByPlaceholderText(/add a bullet point/i);
    const addButton = screen.getAllByText(/add/i)[0]; // First "Add" button is for bullets

    fireEvent.change(input, { target: { value: "New bullet point" } });
    fireEvent.click(addButton);

    expect(screen.getByText("New bullet point")).toBeInTheDocument();
  });

  it("removes bullet annotation", () => {
    const annotation: GraphNodeAnnotation = {
      bullets: ["Point to remove"],
    };
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <GraphAnnotation
        annotation={annotation}
        onSave={onSave}
        onCancel={onCancel}
      />
    );

    expect(screen.getByText("Point to remove")).toBeInTheDocument();

    // Find the remove button for bullets - it's within the bullet list item
    // The button has text "Remove" and is type="button"
    const removeButtons = screen.getAllByRole("button", { name: /remove/i });
    fireEvent.click(removeButtons[0]);

    expect(screen.queryByText("Point to remove")).not.toBeInTheDocument();
  });

  it("adds tag", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <GraphAnnotation
        annotation={undefined}
        onSave={onSave}
        onCancel={onCancel}
      />
    );

    const input = screen.getByPlaceholderText(/add a tag/i);
    const addButton = screen.getAllByText(/add/i)[1]; // Second "Add" button is for tags

    fireEvent.change(input, { target: { value: "newtag" } });
    fireEvent.click(addButton);

    expect(screen.getByText("newtag")).toBeInTheDocument();
  });

  it("removes tag", () => {
    const annotation: GraphNodeAnnotation = {
      tags: ["tag-to-remove"],
    };
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <GraphAnnotation
        annotation={annotation}
        onSave={onSave}
        onCancel={onCancel}
      />
    );

    expect(screen.getByText("tag-to-remove")).toBeInTheDocument();

    const removeButton = screen.getByText("×");
    fireEvent.click(removeButton);

    expect(screen.queryByText("tag-to-remove")).not.toBeInTheDocument();
  });

  it("selects status", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <GraphAnnotation
        annotation={{ status: "active" }}
        onSave={onSave}
        onCancel={onCancel}
      />
    );

    // Click the "draft" status button
    const draftButton = screen.getByRole("button", { name: /draft/i });
    fireEvent.click(draftButton);

    // Click save to verify the status is saved
    const saveButton = screen.getByRole("button", { name: /save annotations/i });
    fireEvent.click(saveButton);

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        status: "draft",
      })
    );
  });

  it("saves annotation with all fields", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <GraphAnnotation
        annotation={undefined}
        onSave={onSave}
        onCancel={onCancel}
      />
    );

    // Add a bullet
    const bulletInput = screen.getByPlaceholderText(/add a bullet point/i);
    const addBulletButton = screen.getAllByText(/add/i)[0];
    fireEvent.change(bulletInput, { target: { value: "Test bullet" } });
    fireEvent.click(addBulletButton);

    // Add a tag
    const tagInput = screen.getByPlaceholderText(/add a tag/i);
    const addTagButton = screen.getAllByText(/add/i)[1];
    fireEvent.change(tagInput, { target: { value: "test-tag" } });
    fireEvent.click(addTagButton);

    // Save
    const saveButton = screen.getByRole("button", { name: /save annotations/i });
    fireEvent.click(saveButton);

    expect(onSave).toHaveBeenCalledWith({
      bullets: ["Test bullet"],
      tags: ["test-tag"],
      status: "active", // Default status
    });
  });

  it("cancels annotation editing", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <GraphAnnotation
        annotation={undefined}
        onSave={onSave}
        onCancel={onCancel}
      />
    );

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    fireEvent.click(cancelButton);

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onSave).not.toHaveBeenCalled();
  });
});

describe("GraphAnnotationDisplay", () => {
  it("renders nothing when no annotation provided", () => {
    const onEdit = vi.fn();

    const { container } = render(
      <GraphAnnotationDisplay annotation={undefined} onEdit={onEdit} />
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders status badge", () => {
    const onEdit = vi.fn();
    const annotation: GraphNodeAnnotation = {
      status: "review",
    };

    render(
      <GraphAnnotationDisplay annotation={annotation} onEdit={onEdit} />
    );

    expect(screen.getByText("review")).toBeInTheDocument();
  });

  it("renders bullet list", () => {
    const onEdit = vi.fn();
    const annotation: GraphNodeAnnotation = {
      bullets: ["Point 1", "Point 2", "Point 3"],
    };

    render(
      <GraphAnnotationDisplay annotation={annotation} onEdit={onEdit} />
    );

    expect(screen.getByText("Point 1")).toBeInTheDocument();
    expect(screen.getByText("Point 2")).toBeInTheDocument();
    expect(screen.getByText("Point 3")).toBeInTheDocument();
  });

  it("renders tags", () => {
    const onEdit = vi.fn();
    const annotation: GraphNodeAnnotation = {
      tags: ["urgent", "frontend", "bug"],
    };

    render(
      <GraphAnnotationDisplay annotation={annotation} onEdit={onEdit} />
    );

    expect(screen.getByText("urgent")).toBeInTheDocument();
    expect(screen.getByText("frontend")).toBeInTheDocument();
    expect(screen.getByText("bug")).toBeInTheDocument();
  });

  it("renders all annotation fields together", () => {
    const onEdit = vi.fn();
    const annotation: GraphNodeAnnotation = {
      status: "draft",
      bullets: ["First item", "Second item"],
      tags: ["work-in-progress"],
    };

    render(
      <GraphAnnotationDisplay annotation={annotation} onEdit={onEdit} />
    );

    expect(screen.getByText("draft")).toBeInTheDocument();
    expect(screen.getByText("First item")).toBeInTheDocument();
    expect(screen.getByText("Second item")).toBeInTheDocument();
    expect(screen.getByText("work-in-progress")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /edit annotations/i })).toBeInTheDocument();
  });

  it("invokes onEdit callback when edit button clicked", () => {
    const onEdit = vi.fn();
    const annotation: GraphNodeAnnotation = {
      status: "active",
    };

    render(
      <GraphAnnotationDisplay annotation={annotation} onEdit={onEdit} />
    );

    const editButton = screen.getByRole("button", { name: /edit annotations/i });
    fireEvent.click(editButton);

    expect(onEdit).toHaveBeenCalledTimes(1);
  });
});
