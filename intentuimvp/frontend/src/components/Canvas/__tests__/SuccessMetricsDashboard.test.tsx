/**
 * Tests for SuccessMetricsDashboard component
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SuccessMetricsDashboard } from "../SuccessMetricsDashboard";

// Mock the useSuccessMetrics hook
vi.mock("../../../hooks/useSuccessMetrics", () => ({
  useSuccessMetrics: vi.fn(),
  METRIC_CONFIG: {
    task_completion_rate: {
      label: "Task Completion Rate",
      description: "% of intents executed successfully",
      targetDisplay: "> 80%",
      formatValue: (v: number) => `${v.toFixed(1)}%`,
      color: "#34d399",
      higherIsBetter: true,
    },
    assumption_accuracy: {
      label: "Assumption Accuracy",
      description: "% of assumptions accepted without modification",
      targetDisplay: "> 70%",
      formatValue: (v: number) => `${v.toFixed(1)}%`,
      color: "#38bdf8",
      higherIsBetter: true,
    },
    time_to_value: {
      label: "Time-to-Value",
      description: "Avg time from command to useful output",
      targetDisplay: "< 30s",
      formatValue: (v: number) => `${(v / 1000).toFixed(1)}s`,
      color: "#fbbf24",
      higherIsBetter: false,
    },
    session_continuity: {
      label: "Session Continuity",
      description: "% of users resuming previous workspace",
      targetDisplay: "> 60%",
      formatValue: (v: number) => `${v.toFixed(1)}%`,
      color: "#a78bfa",
      higherIsBetter: true,
    },
    research_job_completion: {
      label: "Research Job Completion",
      description: "% of deep research jobs completed",
      targetDisplay: "> 75%",
      formatValue: (v: number) => `${v.toFixed(1)}%`,
      color: "#f97316",
      higherIsBetter: true,
    },
    command_vs_chat_ratio: {
      label: "Command vs. Chat Ratio",
      description: "Ratio of command to chat interactions",
      targetDisplay: "> 3:1",
      formatValue: (v: number) => `${v.toFixed(1)}:1`,
      color: "#22d3ee",
      higherIsBetter: true,
    },
    mcp_adoption: {
      label: "MCP Adoption",
      description: "% of users with at least one MCP configured",
      targetDisplay: "> 30%",
      formatValue: (v: number) => `${v.toFixed(1)}%`,
      color: "#f472b6",
      higherIsBetter: true,
    },
  },
}));

import { useSuccessMetrics } from "../../../hooks/useSuccessMetrics";

const mockedUseSuccessMetrics = vi.mocked(useSuccessMetrics);

describe("SuccessMetricsDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render loading state", () => {
    mockedUseSuccessMetrics.mockReturnValue({
      taskCompletionRate: null,
      assumptionAccuracy: null,
      timeToValue: null,
      sessionContinuity: null,
      researchJobCompletion: null,
      commandVsChatRatio: null,
      mcpAdoption: null,
      lastUpdated: null,
      window: "24h",
      isLoading: true,
      error: null,
      refetch: vi.fn(),
      setWindow: vi.fn(),
    });

    render(<SuccessMetricsDashboard />);

    expect(screen.getByText("Success Metrics")).toBeInTheDocument();
    expect(screen.getByText("PRD §5.2 — Product Health Indicators")).toBeInTheDocument();
  });

  it("should render error state", () => {
    mockedUseSuccessMetrics.mockReturnValue({
      taskCompletionRate: null,
      assumptionAccuracy: null,
      timeToValue: null,
      sessionContinuity: null,
      researchJobCompletion: null,
      commandVsChatRatio: null,
      mcpAdoption: null,
      lastUpdated: null,
      window: "24h",
      isLoading: false,
      error: new Error("Failed to fetch"),
      refetch: vi.fn(),
      setWindow: vi.fn(),
    });

    render(<SuccessMetricsDashboard />);

    expect(screen.getByText("Error loading metrics")).toBeInTheDocument();
    expect(screen.getByText("Failed to fetch")).toBeInTheDocument();
  });

  it("should render all 7 metrics when data is loaded", () => {
    const mockMetrics = {
      taskCompletionRate: {
        metric_name: "task_completion_rate",
        value: 85.5,
        target: 80.0,
        window: "24h",
        sample_size: 100,
        meets_target: true,
      },
      assumptionAccuracy: {
        metric_name: "assumption_accuracy",
        value: 75.0,
        target: 70.0,
        window: "24h",
        sample_size: 50,
        meets_target: true,
      },
      timeToValue: {
        metric_name: "time_to_value",
        value: 25000,
        target: 30000,
        window: "24h",
        sample_size: 80,
        meets_target: true,
        unit: "ms",
      },
      sessionContinuity: {
        metric_name: "session_continuity",
        value: 65.0,
        target: 60.0,
        window: "24h",
        sample_size: 200,
        meets_target: true,
      },
      researchJobCompletion: {
        metric_name: "research_job_completion",
        value: 80.0,
        target: 75.0,
        window: "24h",
        sample_size: 20,
        meets_target: true,
      },
      commandVsChatRatio: {
        metric_name: "command_vs_chat_ratio",
        value: 4.5,
        target: 3.0,
        window: "24h",
        sample_size: 300,
        meets_target: true,
      },
      mcpAdoption: {
        metric_name: "mcp_adoption",
        value: 35.0,
        target: 30.0,
        window: "24h",
        sample_size: 100,
        meets_target: true,
      },
      lastUpdated: new Date(),
      window: "24h",
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      setWindow: vi.fn(),
    };

    mockedUseSuccessMetrics.mockReturnValue(mockMetrics);

    render(<SuccessMetricsDashboard />);

    expect(screen.getByText("Success Metrics")).toBeInTheDocument();
    expect(screen.getByText("Task Completion Rate")).toBeInTheDocument();
    expect(screen.getByText("Assumption Accuracy")).toBeInTheDocument();
    expect(screen.getByText("Time-to-Value")).toBeInTheDocument();
    expect(screen.getByText("Session Continuity")).toBeInTheDocument();
    expect(screen.getByText("Research Job Completion")).toBeInTheDocument();
    expect(screen.getByText("Command vs. Chat Ratio")).toBeInTheDocument();
    expect(screen.getByText("MCP Adoption")).toBeInTheDocument();
  });

  it("should render metric values correctly", () => {
    const mockMetrics = {
      taskCompletionRate: {
        metric_name: "task_completion_rate",
        value: 85.5,
        target: 80.0,
        window: "24h",
        sample_size: 100,
        meets_target: true,
      },
      assumptionAccuracy: null,
      timeToValue: null,
      sessionContinuity: null,
      researchJobCompletion: null,
      commandVsChatRatio: null,
      mcpAdoption: null,
      lastUpdated: new Date(),
      window: "24h",
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      setWindow: vi.fn(),
    };

    mockedUseSuccessMetrics.mockReturnValue(mockMetrics);

    render(<SuccessMetricsDashboard />);

    expect(screen.getByText("85.5%")).toBeInTheDocument();
    expect(screen.getByText("✓ On target")).toBeInTheDocument();
  });

  it("should render below target status when metric does not meet target", () => {
    const mockMetrics = {
      taskCompletionRate: {
        metric_name: "task_completion_rate",
        value: 75.5,
        target: 80.0,
        window: "24h",
        sample_size: 100,
        meets_target: false,
      },
      assumptionAccuracy: null,
      timeToValue: null,
      sessionContinuity: null,
      researchJobCompletion: null,
      commandVsChatRatio: null,
      mcpAdoption: null,
      lastUpdated: new Date(),
      window: "24h",
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      setWindow: vi.fn(),
    };

    mockedUseSuccessMetrics.mockReturnValue(mockMetrics);

    render(<SuccessMetricsDashboard />);

    expect(screen.getByText("75.5%")).toBeInTheDocument();
    expect(screen.getByText("↓ Below target")).toBeInTheDocument();
  });

  it("should allow window switching", () => {
    const setWindowMock = vi.fn();
    const mockMetrics = {
      taskCompletionRate: null,
      assumptionAccuracy: null,
      timeToValue: null,
      sessionContinuity: null,
      researchJobCompletion: null,
      commandVsChatRatio: null,
      mcpAdoption: null,
      lastUpdated: null,
      window: "24h",
      isLoading: true,
      error: null,
      refetch: vi.fn(),
      setWindow: setWindowMock,
    };

    mockedUseSuccessMetrics.mockReturnValue(mockMetrics);

    render(<SuccessMetricsDashboard />);

    const button24h = screen.getByRole("button", { name: "24h" });
    const button7d = screen.getByRole("button", { name: "7d" });

    expect(button24h).toBeInTheDocument();
    expect(button7d).toBeInTheDocument();

    button7d.click();
    expect(setWindowMock).toHaveBeenCalledWith("7d");
  });

  it("should display last updated timestamp", () => {
    const now = new Date("2026-01-13T12:00:00Z");
    const mockMetrics = {
      taskCompletionRate: null,
      assumptionAccuracy: null,
      timeToValue: null,
      sessionContinuity: null,
      researchJobCompletion: null,
      commandVsChatRatio: null,
      mcpAdoption: null,
      lastUpdated: now,
      window: "24h",
      isLoading: false,
      error: null,
      refetch: vi.fn(),
      setWindow: vi.fn(),
    };

    mockedUseSuccessMetrics.mockReturnValue(mockMetrics);

    render(<SuccessMetricsDashboard />);

    expect(screen.getByText(/Updated:/)).toBeInTheDocument();
  });
});
