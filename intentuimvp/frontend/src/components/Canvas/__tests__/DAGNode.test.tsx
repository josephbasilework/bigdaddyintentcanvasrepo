import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DAGNode } from "../DAGNode";
import type { DAGData } from "../../../state/canvasStore";

describe("DAGNode", () => {
  it("renders empty state message when no tasks", () => {
    const dag: DAGData = {
      tasks: [],
    };

    render(<DAGNode dag={dag} />);

    expect(screen.getByText("No tasks in this DAG")).toBeInTheDocument();
  });

  it("renders tasks with titles", () => {
    const dag: DAGData = {
      tasks: [
        { id: "task-1", title: "Setup project", status: "completed" },
        { id: "task-2", title: "Write tests", status: "in_progress" },
        { id: "task-3", title: "Deploy", status: "pending" },
      ],
    };

    render(<DAGNode dag={dag} />);

    expect(
      screen.getByRole("group", { name: /task: setup project/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: /task: write tests/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: /task: deploy/i })
    ).toBeInTheDocument();
  });

  it("renders task descriptions when provided", () => {
    const dag: DAGData = {
      tasks: [
        {
          id: "task-1",
          title: "Task One",
          description: "Short description",
          status: "pending",
        },
      ],
    };

    render(<DAGNode dag={dag} />);

    expect(screen.getByText("Short description")).toBeInTheDocument();
  });

  it("truncates long titles", () => {
    const dag: DAGData = {
      tasks: [
        {
          id: "task-1",
          title: "This is a very long task title that should be truncated",
          status: "pending",
        },
      ],
    };

    render(<DAGNode dag={dag} />);

    expect(screen.getByText("This is a very…")).toBeInTheDocument();
  });

  it("displays status icons for different statuses", () => {
    const dag: DAGData = {
      tasks: [
        { id: "task-1", title: "Pending", status: "pending" },
        { id: "task-2", title: "In Progress", status: "in_progress" },
        { id: "task-3", title: "Completed", status: "completed" },
        { id: "task-4", title: "Blocked", status: "blocked" },
      ],
    };

    render(<DAGNode dag={dag} />);

    expect(screen.getByText("○")).toBeInTheDocument();
    expect(screen.getByText("◐")).toBeInTheDocument();
    expect(screen.getByText("●")).toBeInTheDocument();
    expect(screen.getByText("⊘")).toBeInTheDocument();
  });

  it("renders estimated effort badge", () => {
    const dag: DAGData = {
      tasks: [
        {
          id: "task-1",
          title: "Quick task",
          status: "pending",
          estimatedEffort: "30 mins",
        },
      ],
    };

    render(<DAGNode dag={dag} />);

    expect(screen.getByText("30 mins")).toBeInTheDocument();
  });

  it("renders priority labels", () => {
    const dag: DAGData = {
      tasks: [
        { id: "task-1", title: "High Priority", status: "pending", priority: "high" },
        { id: "task-2", title: "Medium Priority", status: "pending", priority: "medium" },
        { id: "task-3", title: "Low Priority", status: "pending", priority: "low" },
      ],
    };

    render(<DAGNode dag={dag} />);

    expect(screen.getByText("H")).toBeInTheDocument();
    expect(screen.getByText("M")).toBeInTheDocument();
    expect(screen.getByText("L")).toBeInTheDocument();
  });

  it("renders calendar badge when task includes calendar suggestion", () => {
    const dag: DAGData = {
      tasks: [
        {
          id: "task-1",
          title: "Schedule kickoff",
          status: "pending",
          calendarSuggestion: { summary: "Kickoff" },
        },
      ],
    };

    render(<DAGNode dag={dag} />);

    expect(screen.getByText("CAL")).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: /calendar suggested/i })
    ).toBeInTheDocument();
  });

  it("calls onTaskClick when task is clicked", () => {
    const onTaskClick = vi.fn();
    const dag: DAGData = {
      tasks: [{ id: "task-123", title: "Clickable Task", status: "pending" }],
    };

    render(<DAGNode dag={dag} onTaskClick={onTaskClick} />);

    const taskButton = screen.getByRole("button", {
      name: /task: clickable task/i,
    });
    fireEvent.click(taskButton);

    expect(onTaskClick).toHaveBeenCalledWith("task-123");
  });

  it("calls onTaskStatusChange when status toggle is activated", () => {
    const onTaskStatusChange = vi.fn();
    const dag: DAGData = {
      tasks: [{ id: "task-1", title: "Toggle Task", status: "pending" }],
    };

    render(<DAGNode dag={dag} onTaskStatusChange={onTaskStatusChange} />);

    const toggle = screen.getByRole("button", {
      name: /advance status for toggle task to in progress/i,
    });
    fireEvent.click(toggle);

    expect(onTaskStatusChange).toHaveBeenCalledWith("task-1", "in_progress");
  });

  it("handles keyboard activation on task nodes", () => {
    const onTaskClick = vi.fn();
    const dag: DAGData = {
      tasks: [{ id: "task-kb", title: "Keyboard Task", status: "pending" }],
    };

    render(<DAGNode dag={dag} onTaskClick={onTaskClick} />);

    const taskButton = screen.getByRole("button", {
      name: /task: keyboard task/i,
    });

    fireEvent.keyDown(taskButton, { key: "Enter" });
    expect(onTaskClick).toHaveBeenCalledWith("task-kb");

    onTaskClick.mockClear();

    fireEvent.keyDown(taskButton, { key: " " });
    expect(onTaskClick).toHaveBeenCalledWith("task-kb");
  });

  it("renders legend with status indicators", () => {
    const dag: DAGData = {
      tasks: [{ id: "task-1", title: "Task", status: "pending" }],
    };

    render(<DAGNode dag={dag} />);

    expect(screen.getByText("○ Pending")).toBeInTheDocument();
    expect(screen.getByText("◐ In Progress")).toBeInTheDocument();
    expect(screen.getByText("● Complete")).toBeInTheDocument();
    expect(screen.getByText("⊘ Blocked")).toBeInTheDocument();
  });

  it("has accessible region role with task count", () => {
    const dag: DAGData = {
      tasks: [
        { id: "task-1", title: "Task 1", status: "pending" },
        { id: "task-2", title: "Task 2", status: "pending" },
      ],
    };

    render(<DAGNode dag={dag} />);

    expect(
      screen.getByRole("region", { name: /task dag with 2 tasks/i })
    ).toBeInTheDocument();
  });

  it("renders tasks with dependencies in hierarchical order", () => {
    const dag: DAGData = {
      tasks: [
        { id: "task-1", title: "First Task", status: "completed" },
        { id: "task-2", title: "Second Task", status: "in_progress" },
        { id: "task-3", title: "Third Task", status: "pending" },
      ],
      dependencies: [
        { taskId: "task-2", dependsOnTaskId: "task-1", type: "hard" },
        { taskId: "task-3", dependsOnTaskId: "task-2", type: "hard" },
      ],
    };

    render(<DAGNode dag={dag} />);

    expect(
      screen.getByRole("group", { name: /task: first task/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: /task: second task/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("group", { name: /task: third task/i })
    ).toBeInTheDocument();
  });

  it("renders connections for dependencies", () => {
    const dag: DAGData = {
      tasks: [
        { id: "task-a", title: "Task A", status: "completed" },
        { id: "task-b", title: "Task B", status: "pending" },
      ],
      dependencies: [{ taskId: "task-b", dependsOnTaskId: "task-a", type: "hard" }],
    };

    const { container } = render(<DAGNode dag={dag} />);

    const paths = container.querySelectorAll("path");
    expect(paths.length).toBeGreaterThan(0);
  });

  it("marks tasks as ready when dependencies are completed", () => {
    const dag: DAGData = {
      tasks: [
        { id: "task-a", title: "Task A", status: "completed" },
        { id: "task-b", title: "Task B", status: "pending" },
      ],
      dependencies: [{ taskId: "task-b", dependsOnTaskId: "task-a", type: "hard" }],
    };

    render(<DAGNode dag={dag} />);

    expect(screen.getByText("READY")).toBeInTheDocument();
  });

  it("renders soft dependencies with dashed style", () => {
    const dag: DAGData = {
      tasks: [
        { id: "task-x", title: "Task X", status: "completed" },
        { id: "task-y", title: "Task Y", status: "pending" },
      ],
      dependencies: [{ taskId: "task-y", dependsOnTaskId: "task-x", type: "soft" }],
    };

    const { container } = render(<DAGNode dag={dag} />);

    const dashedPath = container.querySelector('path[stroke-dasharray="4,4"]');
    expect(dashedPath).toBeInTheDocument();
  });
});
