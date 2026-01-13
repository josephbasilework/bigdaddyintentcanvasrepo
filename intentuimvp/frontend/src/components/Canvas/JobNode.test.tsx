import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { JobNode } from "./JobNode";
import type { JobData } from "../../state/canvasStore";

// Mock the useJobProgress hook
vi.mock("../../hooks/useJobProgress", () => ({
  useJobProgress: vi.fn(),
}));

import { useJobProgress } from "../../hooks/useJobProgress";

describe("JobNode", () => {
  const mockJobData: JobData = {
    jobId: "test-job-id-123",
    jobType: "deep_research",
    status: "in_progress",
    progressPercent: 45,
    currentStep: "Researching sources",
    stepNumber: 2,
    stepsTotal: 5,
    data: undefined,
  };

  const defaultProps = {
    id: "node-1",
    title: "Deep Research Task",
    jobData: mockJobData,
    isSelected: false,
    onSelect: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock return value for useJobProgress
    (useJobProgress as ReturnType<typeof vi.fn>).mockReturnValue({
      jobData: null,
      isConnected: false,
      error: null,
    });
  });

  it("should render job node with title", () => {
    render(<JobNode {...defaultProps} />);

    expect(screen.getByText("Deep Research Task")).toBeInTheDocument();
  });

  it("should display formatted job type", () => {
    render(<JobNode {...defaultProps} />);

    expect(screen.getByText("Deep Research")).toBeInTheDocument();
  });

  it("should display status text", () => {
    render(<JobNode {...defaultProps} />);

    expect(screen.getByText("In progress")).toBeInTheDocument();
  });

  it("should display progress percentage", () => {
    render(<JobNode {...defaultProps} />);

    expect(screen.getByText("45%")).toBeInTheDocument();
  });

  it("should display current step", () => {
    render(<JobNode {...defaultProps} />);

    expect(screen.getByText("Researching sources")).toBeInTheDocument();
  });

  it("should display step counter when available", () => {
    render(<JobNode {...defaultProps} />);

    expect(screen.getByText("Step 2 of 5")).toBeInTheDocument();
  });

  it("should display job ID (truncated)", () => {
    render(<JobNode {...defaultProps} />);

    expect(screen.getByText(/ID: test-job\.\.\./)).toBeInTheDocument();
  });

  it("should show ring when selected", () => {
    const { container } = render(<JobNode {...defaultProps} isSelected={true} />);

    const nodeElement = container.querySelector(".job-node");
    expect(nodeElement).toHaveClass("ring-2", "ring-blue-500", "ring-offset-2");
  });

  it("should not show ring when not selected", () => {
    const { container } = render(<JobNode {...defaultProps} isSelected={false} />);

    const nodeElement = container.querySelector(".job-node");
    expect(nodeElement).not.toHaveClass("ring-2", "ring-blue-500", "ring-offset-2");
  });

  it("should call onSelect when clicked", () => {
    const onSelect = vi.fn();
    render(<JobNode {...defaultProps} onSelect={onSelect} />);

    const nodeElement = screen.getByRole("button", { name: /Deep Research Task/ });
    nodeElement.click();

    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  describe("status colors", () => {
    it("should show gray status dot for queued status", () => {
      render(<JobNode {...defaultProps} jobData={{ ...mockJobData, status: "queued" }} />);

      const statusDot = screen.getByTitle("queued");
      expect(statusDot).toHaveClass("bg-gray-200");
    });

    it("should show blue status dot for in_progress status", () => {
      render(<JobNode {...defaultProps} jobData={{ ...mockJobData, status: "in_progress" }} />);

      const statusDot = screen.getByTitle("in_progress");
      expect(statusDot).toHaveClass("bg-blue-500");
    });

    it("should show green status dot for complete status", () => {
      render(<JobNode {...defaultProps} jobData={{ ...mockJobData, status: "complete" }} />);

      const statusDot = screen.getByTitle("complete");
      expect(statusDot).toHaveClass("bg-green-500");
    });

    it("should show red status dot for failed status", () => {
      render(<JobNode {...defaultProps} jobData={{ ...mockJobData, status: "failed" }} />);

      const statusDot = screen.getByTitle("failed");
      expect(statusDot).toHaveClass("bg-red-500");
    });

    it("should show gray status dot for cancelled status", () => {
      render(<JobNode {...defaultProps} jobData={{ ...mockJobData, status: "cancelled" }} />);

      const statusDot = screen.getByTitle("cancelled");
      expect(statusDot).toHaveClass("bg-gray-400");
    });
  });

  describe("job type formatting", () => {
    it("should format deep_research as 'Deep Research'", () => {
      render(<JobNode {...defaultProps} jobData={{ ...mockJobData, jobType: "deep_research" }} />);

      expect(screen.getByText("Deep Research")).toBeInTheDocument();
    });

    it("should format perspective_gather as 'Perspective Gather'", () => {
      render(<JobNode {...defaultProps} jobData={{ ...mockJobData, jobType: "perspective_gather" }} />);

      expect(screen.getByText("Perspective Gather")).toBeInTheDocument();
    });

    it("should format synthesis as 'Synthesis'", () => {
      render(<JobNode {...defaultProps} jobData={{ ...mockJobData, jobType: "synthesis" }} />);

      expect(screen.getByText("Synthesis")).toBeInTheDocument();
    });

    it("should format export as 'Export'", () => {
      render(<JobNode {...defaultProps} jobData={{ ...mockJobData, jobType: "export" }} />);

      expect(screen.getByText("Export")).toBeInTheDocument();
    });
  });

  describe("live progress updates", () => {
    it("should display live progress data when available", () => {
      const liveProgressData = {
        job_id: "live-job-123",
        job_type: "deep_research",
        status: "in_progress",
        progress_percent: 75,
        current_step: "Analyzing results",
        step_number: 4,
        steps_total: 5,
        data: null,
        timestamp: new Date().toISOString(),
      };

      (useJobProgress as ReturnType<typeof vi.fn>).mockReturnValue({
        jobData: liveProgressData,
        isConnected: true,
        error: null,
      });

      render(<JobNode {...defaultProps} />);

      expect(screen.getByText("75%")).toBeInTheDocument();
      expect(screen.getByText("Analyzing results")).toBeInTheDocument();
    });

    it("should show live indicator when connected", () => {
      (useJobProgress as ReturnType<typeof vi.fn>).mockReturnValue({
        jobData: {
          job_id: "live-job-123",
          job_type: "deep_research",
          status: "in_progress",
          progress_percent: 75,
          current_step: "Analyzing results",
          step_number: 4,
          steps_total: 5,
          data: null,
          timestamp: new Date().toISOString(),
        },
        isConnected: true,
        error: null,
      });

      const { container } = render(<JobNode {...defaultProps} />);

      const liveIndicator = container.querySelector('.bg-green-400[title="Live"]');
      expect(liveIndicator).toBeInTheDocument();
    });
  });

  describe("FR-012: Multi-Judge Compute - Rerun with more compute", () => {
    it("should show rerun button for completed perspective_analysis jobs", () => {
      const perspectiveJobData: JobData = {
        jobId: "perspective-job-123",
        jobType: "perspective_analysis",
        status: "complete",
        progressPercent: 100,
        data: undefined,
      };

      const onRerun = vi.fn();

      render(
        <JobNode
          {...defaultProps}
          jobData={perspectiveJobData}
          onRerunWithMoreCompute={onRerun}
        />
      );

      const rerunButton = screen.getByRole("button", { name: /Rerun with more compute/i });
      expect(rerunButton).toBeInTheDocument();
    });

    it("should not show rerun button for in-progress perspective_analysis jobs", () => {
      const perspectiveJobData: JobData = {
        jobId: "perspective-job-123",
        jobType: "perspective_analysis",
        status: "in_progress",
        progressPercent: 50,
        data: undefined,
      };

      render(
        <JobNode {...defaultProps} jobData={perspectiveJobData} onRerunWithMoreCompute={vi.fn()} />
      );

      expect(screen.queryByRole("button", { name: /Rerun with more compute/i })).not.toBeInTheDocument();
    });

    it("should not show rerun button when onRerunWithMoreCompute is not provided", () => {
      const perspectiveJobData: JobData = {
        jobId: "perspective-job-123",
        jobType: "perspective_analysis",
        status: "complete",
        progressPercent: 100,
        data: undefined,
      };

      render(<JobNode {...defaultProps} jobData={perspectiveJobData} />);

      expect(screen.queryByRole("button", { name: /Rerun with more compute/i })).not.toBeInTheDocument();
    });

    it("should call onRerunWithMoreCompute when rerun button is clicked", () => {
      const perspectiveJobData: JobData = {
        jobId: "perspective-job-123",
        jobType: "perspective_analysis",
        status: "complete",
        progressPercent: 100,
        data: undefined,
      };

      const onRerun = vi.fn();

      render(
        <JobNode
          {...defaultProps}
          jobData={perspectiveJobData}
          onRerunWithMoreCompute={onRerun}
        />
      );

      const rerunButton = screen.getByRole("button", { name: /Rerun with more compute/i });
      rerunButton.click();

      expect(onRerun).toHaveBeenCalledTimes(1);
    });

    it("should stop propagation when rerun button is clicked", () => {
      const perspectiveJobData: JobData = {
        jobId: "perspective-job-123",
        jobType: "perspective_analysis",
        status: "complete",
        progressPercent: 100,
        data: undefined,
      };

      const onRerun = vi.fn();
      const onSelect = vi.fn();

      render(
        <JobNode
          {...defaultProps}
          jobData={perspectiveJobData}
          onRerunWithMoreCompute={onRerun}
          onSelect={onSelect}
        />
      );

      const rerunButton = screen.getByRole("button", { name: /Rerun with more compute/i });
      rerunButton.click();

      expect(onRerun).toHaveBeenCalledTimes(1);
      expect(onSelect).not.toHaveBeenCalled();
    });

    it("should not show rerun button for non-perspective_analysis jobs", () => {
      const researchJobData: JobData = {
        jobId: "research-job-123",
        jobType: "deep_research",
        status: "complete",
        progressPercent: 100,
        data: undefined,
      };

      render(
        <JobNode {...defaultProps} jobData={researchJobData} onRerunWithMoreCompute={vi.fn()} />
      );

      expect(screen.queryByRole("button", { name: /Rerun with more compute/i })).not.toBeInTheDocument();
    });
  });
});
