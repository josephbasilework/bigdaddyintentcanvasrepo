import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PlanNode } from "../PlanNode";
import type { PlanData } from "../../../state/canvasStore";

describe("PlanNode", () => {
  it("renders goal and approach", () => {
    const plan: PlanData = {
      goal: "Build a new feature",
      approach: "Use incremental development with testing",
    };

    render(<PlanNode plan={plan} />);

    expect(screen.getByText("Build a new feature")).toBeInTheDocument();
    expect(
      screen.getByText("Use incremental development with testing")
    ).toBeInTheDocument();
    expect(screen.getByText("Goal")).toBeInTheDocument();
    expect(screen.getByText("Approach")).toBeInTheDocument();
  });

  it("renders estimated total effort when provided", () => {
    const plan: PlanData = {
      goal: "Complete project",
      approach: "Agile methodology",
      estimatedTotalEffort: "3 days",
    };

    render(<PlanNode plan={plan} />);

    expect(screen.getByText("Estimated Effort")).toBeInTheDocument();
    expect(screen.getByText("3 days")).toBeInTheDocument();
  });

  it("does not render estimated effort section when not provided", () => {
    const plan: PlanData = {
      goal: "Simple goal",
      approach: "Simple approach",
    };

    render(<PlanNode plan={plan} />);

    expect(screen.queryByText("Estimated Effort")).not.toBeInTheDocument();
  });

  it("renders assumptions list when provided", () => {
    const plan: PlanData = {
      goal: "Build API",
      approach: "REST-first design",
      assumptions: [
        "Team has REST experience",
        "Database schema is finalized",
        "Third-party APIs are stable",
      ],
    };

    render(<PlanNode plan={plan} />);

    expect(screen.getByText("Assumptions")).toBeInTheDocument();
    expect(screen.getByText("Team has REST experience")).toBeInTheDocument();
    expect(screen.getByText("Database schema is finalized")).toBeInTheDocument();
    expect(screen.getByText("Third-party APIs are stable")).toBeInTheDocument();
  });

  it("does not render assumptions section when empty", () => {
    const plan: PlanData = {
      goal: "Goal",
      approach: "Approach",
      assumptions: [],
    };

    render(<PlanNode plan={plan} />);

    expect(screen.queryByText("Assumptions")).not.toBeInTheDocument();
  });

  it("renders risks list when provided", () => {
    const plan: PlanData = {
      goal: "Launch product",
      approach: "Phased rollout",
      risks: [
        "Timeline might slip",
        "Resource constraints",
      ],
    };

    render(<PlanNode plan={plan} />);

    expect(screen.getByText("Risks")).toBeInTheDocument();
    expect(screen.getByText("Timeline might slip")).toBeInTheDocument();
    expect(screen.getByText("Resource constraints")).toBeInTheDocument();
  });

  it("does not render risks section when empty", () => {
    const plan: PlanData = {
      goal: "Goal",
      approach: "Approach",
      risks: [],
    };

    render(<PlanNode plan={plan} />);

    expect(screen.queryByText("Risks")).not.toBeInTheDocument();
  });

  it("renders all fields together", () => {
    const plan: PlanData = {
      goal: "Complete Q1 objectives",
      approach: "Break into sprints",
      estimatedTotalEffort: "2 weeks",
      assumptions: ["Team is available", "Requirements are clear"],
      risks: ["Dependencies on other teams"],
    };

    render(<PlanNode plan={plan} />);

    expect(screen.getByText("Complete Q1 objectives")).toBeInTheDocument();
    expect(screen.getByText("Break into sprints")).toBeInTheDocument();
    expect(screen.getByText("2 weeks")).toBeInTheDocument();
    expect(screen.getByText("Team is available")).toBeInTheDocument();
    expect(screen.getByText("Requirements are clear")).toBeInTheDocument();
    expect(screen.getByText("Dependencies on other teams")).toBeInTheDocument();
  });

  it("has accessible region role", () => {
    const plan: PlanData = {
      goal: "Test goal",
      approach: "Test approach",
    };

    render(<PlanNode plan={plan} />);

    expect(screen.getByRole("region", { name: /plan details/i })).toBeInTheDocument();
  });
});
