import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { FloatingInput } from "../ContextInput/FloatingInput";
import type { AttachmentItem } from "@/lib/attachments";

describe("FloatingInput", () => {
  beforeEach(() => {
    // Clear window focus to test auto-focus
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  });

  it("renders the input with placeholder", () => {
    render(<FloatingInput />);
    const input = screen.getByPlaceholderText("Type a command...");
    expect(input).toBeInTheDocument();
  });

  it("accepts custom placeholder", () => {
    render(<FloatingInput placeholder="Enter text..." />);
    expect(screen.getByPlaceholderText("Enter text...")).toBeInTheDocument();
  });

  it("auto-focuses on mount by default", () => {
    render(<FloatingInput />);
    const input = screen.getByRole("textbox");
    // Note: In jsdom, focus behavior may differ from real browser
    expect(input).toHaveFocus();
  });

  it("does not auto-focus when disabled", () => {
    render(<FloatingInput autoFocus={false} />);
    const input = screen.getByRole("textbox");
    expect(input).not.toHaveFocus();
  });

  it("calls onSubmit with sanitized input when Enter is pressed", () => {
    const handleSubmit = vi.fn();
    render(<FloatingInput onSubmit={handleSubmit} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "  test command  " } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(handleSubmit).toHaveBeenCalledWith("test command");
  });

  it("clears input after submission", () => {
    const handleSubmit = vi.fn();
    render(<FloatingInput onSubmit={handleSubmit} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(input).toHaveValue("");
  });

  it("does not submit empty input", () => {
    const handleSubmit = vi.fn();
    render(<FloatingInput onSubmit={handleSubmit} />);

    const input = screen.getByRole("textbox");
    fireEvent.keyDown(input, { key: "Enter" });

    expect(handleSubmit).not.toHaveBeenCalled();
  });

  it("does not submit whitespace-only input", () => {
    const handleSubmit = vi.fn();
    render(<FloatingInput onSubmit={handleSubmit} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(handleSubmit).not.toHaveBeenCalled();
  });

  it("trims whitespace from input before submission", () => {
    const handleSubmit = vi.fn();
    render(<FloatingInput onSubmit={handleSubmit} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "  hello world  " } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(handleSubmit).toHaveBeenCalledWith("hello world");
  });

  it("respects maxLength prop", () => {
    render(<FloatingInput maxLength={10} />);

    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.maxLength).toBe(10);
  });

  it("allows Shift+Enter for new lines (does not submit)", () => {
    const handleSubmit = vi.fn();
    render(<FloatingInput onSubmit={handleSubmit} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "line1" } });
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

    // Should not submit on Shift+Enter
    expect(handleSubmit).not.toHaveBeenCalled();
    // Note: Input type="text" doesn't actually support multiline,
    // but this tests the key combination logic
  });

  it("responds to Cmd+K by focusing the input", () => {
    render(<FloatingInput />);
    const input = screen.getByRole("textbox");

    // Blur the input first
    input.blur();
    expect(input).not.toHaveFocus();

    // Simulate Cmd+K
    fireEvent.keyDown(window, { key: "k", metaKey: true });

    // The input should be focused after Cmd+K
    expect(input).toHaveFocus();
  });

  it("responds to Ctrl+K by focusing the input (Windows/Linux)", () => {
    render(<FloatingInput />);
    const input = screen.getByRole("textbox");

    // Blur the input first
    input.blur();
    expect(input).not.toHaveFocus();

    // Simulate Ctrl+K
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });

    expect(input).toHaveFocus();
  });

  it("shows slash templates when typing /", () => {
    render(<FloatingInput />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "/" } });

    expect(screen.getByText("/research")).toBeInTheDocument();
    expect(screen.getByText("/export")).toBeInTheDocument();
  });

  it("filters slash templates as the query narrows", () => {
    render(<FloatingInput />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "/pl" } });

    expect(screen.getByText("/plan")).toBeInTheDocument();
    expect(screen.queryByText("/research")).not.toBeInTheDocument();
  });

  it("inserts the template stub when a template is selected", () => {
    render(<FloatingInput />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "/" } });

    const template = screen.getByText("/graph");
    const button = template.closest("button");
    expect(button).not.toBeNull();
    fireEvent.mouseDown(button as HTMLElement);

    expect(input).toHaveValue("/graph ");
  });

  it("submits a selected template command", () => {
    const handleSubmit = vi.fn();
    render(<FloatingInput onSubmit={handleSubmit} />);

    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "/research " } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(handleSubmit).toHaveBeenCalledWith("/research");
  });

  it("calls onFilesDrop when files are dropped", () => {
    const handleFilesDrop = vi.fn();
    render(<FloatingInput onFilesDrop={handleFilesDrop} />);

    const input = screen.getByRole("textbox");
    const file = new File(["content"], "notes.txt", { type: "text/plain" });
    fireEvent.drop(input, { dataTransfer: { files: [file] } });

    expect(handleFilesDrop).toHaveBeenCalledWith([file]);
  });

  it("renders attachments and allows removal", () => {
    const handleRemove = vi.fn();
    const attachments: AttachmentItem[] = [
      {
        id: "att-1",
        name: "spec.pdf",
        mimeType: "application/pdf",
        sizeBytes: 1200,
        attachmentType: "document",
        status: "ready",
      },
    ];
    render(
      <FloatingInput
        attachments={attachments}
        onRemoveAttachment={handleRemove}
      />
    );

    expect(screen.getByText("spec.pdf")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove spec.pdf" }));

    expect(handleRemove).toHaveBeenCalledWith("att-1");
  });

  it("shows selection scope context when selection is provided", () => {
    render(
      <FloatingInput
        selection={[
          { id: "node-1", label: "First node" },
          { id: "node-2", label: "Second node" },
        ]}
      />
    );

    const selectionScope = screen.getByRole("region", { name: /selection scope/i });
    expect(within(selectionScope).getByText("Selection scope")).toBeInTheDocument();
    expect(within(selectionScope).getByText("2 nodes")).toBeInTheDocument();
    expect(within(selectionScope).getByText("First node")).toBeInTheDocument();
  });

  it("collapses selection chips when too many items are selected", () => {
    const selection = Array.from({ length: 6 }, (_, index) => ({
      id: `node-${index}`,
      label: `Node ${index}`,
    }));

    render(<FloatingInput selection={selection} />);

    const selectionScope = screen.getByRole("region", { name: /selection scope/i });
    expect(within(selectionScope).getByText("+2 more")).toBeInTheDocument();
  });

  it("renders panel toggles with an active indicator", () => {
    const handleToggle = vi.fn();
    render(
      <FloatingInput
        panelToggles={[
          { label: "Chat", isOpen: true, onToggle: handleToggle },
          { label: "Events", isOpen: false, onToggle: handleToggle },
        ]}
      />
    );

    const chatButton = screen.getByRole("button", { name: "Chat" });
    const eventsButton = screen.getByRole("button", { name: "Events" });

    expect(chatButton).toBeInTheDocument();
    expect(eventsButton).toBeInTheDocument();
    expect(chatButton.querySelector(".panel-toggle-arrow")).not.toBeNull();
    expect(eventsButton.querySelector(".panel-toggle-arrow")).toBeNull();
  });

  it("shows Clear button when selection and onClearSelection are provided", () => {
    const handleClear = vi.fn();
    render(
      <FloatingInput
        selection={[{ id: "node-1", label: "First node" }]}
        onClearSelection={handleClear}
      />
    );

    const clearButton = screen.getByRole("button", { name: /clear selection/i });
    expect(clearButton).toBeInTheDocument();
  });

  it("does not show Clear button when onClearSelection is not provided", () => {
    render(
      <FloatingInput
        selection={[{ id: "node-1", label: "First node" }]}
      />
    );

    const clearButton = screen.queryByRole("button", { name: /clear selection/i });
    expect(clearButton).not.toBeInTheDocument();
  });

  it("calls onClearSelection when Clear button is clicked", () => {
    const handleClear = vi.fn();
    render(
      <FloatingInput
        selection={[{ id: "node-1", label: "First node" }]}
        onClearSelection={handleClear}
      />
    );

    const clearButton = screen.getByRole("button", { name: /clear selection/i });
    fireEvent.click(clearButton);

    expect(handleClear).toHaveBeenCalledTimes(1);
  });
});
