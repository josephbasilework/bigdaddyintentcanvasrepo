import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AssumptionsPanel } from "../AssumptionsPanel";
import type { Assumption, AssumptionSet } from "../types";

const mockAssumptions: Assumption[] = [
  {
    id: "1",
    originalText: "You want to search for recent Python documentation",
    text: "You want to search for recent Python documentation",
    confidence: 0.95,
    category: "intent",
    status: "pending",
    explanation: "Based on the query 'Python docs'",
  },
  {
    id: "2",
    originalText: "Focus on Python 3.12+ features",
    text: "Focus on Python 3.12+ features",
    confidence: 0.7,
    category: "context",
    status: "pending",
  },
  {
    id: "3",
    originalText: "Include code examples in results",
    text: "Include code examples in results",
    confidence: 0.85,
    category: "parameter",
    status: "accepted",
  },
];

const mockAssumptionSet: AssumptionSet = {
  intent: "Deep research",
  intentDescription: "Compile recent findings on vector databases.",
  confidence: 0.82,
  reasoning: "The prompt mentions research and sources.",
  alternatives: [
    {
      name: "Plan",
      confidence: 0.48,
      description: "Generate a step-by-step plan.",
    },
    {
      name: "Summarize",
      confidence: 0.36,
      description: "Summarize existing notes and materials.",
    },
  ],
};

describe("AssumptionsPanel", () => {
  it("renders null when no assumptions provided", () => {
    const { container } = render(
      <AssumptionsPanel
        assumptions={[]}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );
    expect(container.firstChild).toBe(null);
  });

  it("renders assumptions correctly", () => {
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    // Check title
    expect(screen.getByText("Please Review These Assumptions")).toBeInTheDocument();

    // Check assumption texts
    expect(
      screen.getByText("You want to search for recent Python documentation")
    ).toBeInTheDocument();
    expect(screen.getByText("Focus on Python 3.12+ features")).toBeInTheDocument();
    expect(screen.getByText("Include code examples in results")).toBeInTheDocument();

    // Check counts
    expect(screen.getByText("3 assumptions")).toBeInTheDocument();
    expect(screen.getByText("✓ 1 accepted")).toBeInTheDocument();
  });

  it("calls onAccept when Confirm button is clicked", () => {
    const onAccept = vi.fn();
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={onAccept}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    const confirmButtons = screen.getAllByText("Confirm");
    fireEvent.click(confirmButtons[0]);

    expect(onAccept).toHaveBeenCalledWith("1");
  });

  it("calls onReject when Reject button is clicked", () => {
    const onReject = vi.fn();
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={vi.fn()}
        onReject={onReject}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    const rejectButtons = screen.getAllByText("Reject");
    fireEvent.click(rejectButtons[1]);

    expect(onReject).toHaveBeenCalledWith("2");
  });

  it("calls onEdit when Save button is clicked", () => {
    const onEdit = vi.fn();
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={onEdit}
        onConfirm={vi.fn()}
      />
    );

    fireEvent.click(screen.getAllByText("Edit")[0]);

    const editor = screen.getByLabelText("Edit assumption");
    fireEvent.change(editor, { target: { value: "Updated assumption text" } });

    const saveButton = screen.getByText("Save");
    fireEvent.click(saveButton);

    expect(onEdit).toHaveBeenCalledWith("1", "Updated assumption text");
  });

  it("disables confirm button when not all assumptions are resolved", () => {
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    const confirmButton = screen.queryByText("Continue with Execution");
    expect(confirmButton).not.toBeInTheDocument();
    expect(
      screen.getByText("Please confirm or reject all assumptions to continue")
    ).toBeInTheDocument();
  });

  it("enables confirm button when all assumptions are resolved", () => {
    const resolvedAssumptions: Assumption[] = [
      { ...mockAssumptions[0], status: "accepted" as const },
      { ...mockAssumptions[1], status: "rejected" as const },
      { ...mockAssumptions[2], status: "accepted" as const },
    ];

    const onConfirm = vi.fn();
    render(
      <AssumptionsPanel
        assumptions={resolvedAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={onConfirm}
      />
    );

    const confirmButton = screen.getByText("Continue with Execution (2 accepted)");
    expect(confirmButton).toBeInTheDocument();
    expect(confirmButton).not.toBeDisabled();

    fireEvent.click(confirmButton);
    expect(onConfirm).toHaveBeenCalled();
  });

  it("displays correct category badges", () => {
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText("Intent")).toBeInTheDocument();
    expect(screen.getByText("Context")).toBeInTheDocument();
    expect(screen.getByText("Parameter")).toBeInTheDocument();
  });

  it("displays confidence scores", () => {
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText("Confidence: 95%")).toBeInTheDocument();
    expect(screen.getByText("Confidence: 70%")).toBeInTheDocument();
    expect(screen.getByText("Confidence: 85%")).toBeInTheDocument();
  });

  it("displays explanation when provided", () => {
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText("Based on the query 'Python docs'")).toBeInTheDocument();
  });

  it("calls onDismiss when dismiss button is clicked", () => {
    const onDismiss = vi.fn();
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
        onDismiss={onDismiss}
      />
    );

    const dismissButton = screen.getByLabelText("Dismiss");
    fireEvent.click(dismissButton);

    expect(onDismiss).toHaveBeenCalled();
  });

  it("shows accepted/rejected status correctly", () => {
    const resolvedAssumptions: Assumption[] = [
      { ...mockAssumptions[0], status: "accepted" as const },
      { ...mockAssumptions[1], status: "rejected" as const },
    ];

    render(
      <AssumptionsPanel
        assumptions={resolvedAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText("✓ Accepted")).toBeInTheDocument();
    expect(screen.getByText("✗ Rejected")).toBeInTheDocument();
  });

  it("updates summary counts when assumptions change status", () => {
    const { rerender } = render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText("✓ 1 accepted")).toBeInTheDocument();

    const updatedAssumptions = mockAssumptions.map((a) =>
      a.id === "1" ? { ...a, status: "accepted" as const } : a
    );

    rerender(
      <AssumptionsPanel
        assumptions={updatedAssumptions}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText("✓ 2 accepted")).toBeInTheDocument();
  });

  it("renders intent summary details when provided", () => {
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        assumptionSet={mockAssumptionSet}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(screen.getByText("Deep research")).toBeInTheDocument();
    expect(
      screen.getByText("Compile recent findings on vector databases.")
    ).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
  });

  it("toggles reasoning and alternatives when explain is clicked", () => {
    render(
      <AssumptionsPanel
        assumptions={mockAssumptions}
        assumptionSet={mockAssumptionSet}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onEdit={vi.fn()}
        onConfirm={vi.fn()}
      />
    );

    expect(
      screen.queryByText("The prompt mentions research and sources.")
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Explain" }));

    expect(
      screen.getByText("The prompt mentions research and sources.")
    ).toBeInTheDocument();
    expect(screen.getByText("Alternate interpretations")).toBeInTheDocument();
    expect(screen.getByText("Plan")).toBeInTheDocument();
  });
});
