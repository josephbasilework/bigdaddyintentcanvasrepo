import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FloatingInput } from "../ContextInput/FloatingInput";

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
});
