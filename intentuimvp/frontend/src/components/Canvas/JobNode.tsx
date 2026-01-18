"use client";

import React from "react";
import { useJobProgress, type JobProgressData } from "../../hooks/useJobProgress";
import type { JobData } from "../../state/canvasStore";

export interface JobNodeProps {
  id: string;
  title: string;
  jobData: JobData;
  isSelected: boolean;
  onSelect?: (event?: React.MouseEvent) => void;
  onDoubleClick?: () => void;
  /** Callback when user wants to rerun with more compute (FR-012) */
  onRerunWithMoreCompute?: () => void;
  /** Callback when user wants to configure result routing */
  onRouteResults?: () => void;
}

type DisplayData = JobData | JobProgressData;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

/**
 * Get job type from either camelCase or snake_case format
 */
function getJobType(data: DisplayData): string | undefined {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (data as any).jobType ?? (data as any).job_type;
}

/**
 * Get progress percent from either camelCase or snake_case format
 */
function getProgressPercent(data: DisplayData): number {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (data as any).progressPercent ?? (data as any).progress_percent;
}

/**
 * Get current step from either camelCase or snake_case format
 */
function getCurrentStep(data: DisplayData): string | null | undefined {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (data as any).currentStep ?? (data as any).current_step;
}

/**
 * Get step number from either camelCase or snake_case format
 */
function getStepNumber(data: DisplayData): number | null | undefined {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (data as any).stepNumber ?? (data as any).step_number;
}

/**
 * Get steps total from either camelCase or snake_case format
 */
function getStepsTotal(data: DisplayData): number | null | undefined {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (data as any).stepsTotal ?? (data as any).steps_total;
}

/**
 * Get job ID from either format
 */
function getJobId(data: DisplayData): string {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (data as any).jobId ?? (data as any).job_id;
}

const extractResultPayload = (
  data: Record<string, unknown> | null | undefined
): Record<string, unknown> | null => {
  if (!data) return null;
  const result = data.result;
  if (isRecord(result)) {
    return result;
  }
  if (typeof result === "string" && result.trim().length > 0) {
    return { summary: result.trim() };
  }
  return isRecord(data) ? data : null;
};

const getNestedText = (value: unknown): string | null => {
  if (typeof value === "string" && value.trim().length > 0) {
    return value.trim();
  }
  return null;
};

const buildResultPreview = (
  data: Record<string, unknown> | null | undefined,
  jobType: string | undefined
): string | null => {
  const payload = extractResultPayload(data);
  if (!payload) return null;

  const summaryCandidates: Array<string | null> = [];
  const jobTypeLower = jobType?.toLowerCase() ?? "";

  if (jobTypeLower === "deep_research" || jobTypeLower === "synthesis") {
    const synthesis = payload.judge_synthesis ?? payload.synthesis;
    if (isRecord(synthesis)) {
      summaryCandidates.push(getNestedText(synthesis.executive_summary));
    }
  }

  if (jobTypeLower === "perspective_analysis") {
    const evaluation = payload.evaluation;
    if (isRecord(evaluation)) {
      summaryCandidates.push(
        getNestedText(evaluation.summary ?? evaluation.overall_assessment)
      );
    }
  }

  if (jobTypeLower === "planner") {
    const planMeta = payload.plan_metadata;
    if (isRecord(planMeta)) {
      summaryCandidates.push(getNestedText(planMeta.goal));
    }
  }

  if (jobTypeLower === "transcription") {
    summaryCandidates.push(getNestedText(payload.transcription));
  }

  if (jobTypeLower === "export") {
    const filePath = getNestedText(payload.file_path ?? payload.filePath);
    if (filePath) {
      summaryCandidates.push(`Exported to ${filePath}`);
    }
  }

  if (jobTypeLower === "doc_generation") {
    summaryCandidates.push(getNestedText(payload.content));
  }

  summaryCandidates.push(
    getNestedText(payload.summary),
    getNestedText(payload.message),
    getNestedText(payload.content)
  );

  const preview = summaryCandidates.find((item) => item && item.length > 0);
  if (!preview) {
    const artifactId = payload.artifact_id ?? payload.artifactId;
    if (typeof artifactId === "number" || typeof artifactId === "string") {
      return `Artifact #${artifactId}`;
    }
    return null;
  }

  if (preview.length > 140) {
    return `${preview.slice(0, 137).trimEnd()}...`;
  }
  return preview;
};

/**
 * JobNode component displays a job's status and progress on the canvas.
 *
 * Shows:
 * - Job type and status
 * - Progress bar with percentage
 * - Current step description
 * - Step counter (e.g., "Step 3 of 5")
 * - Rerun with more compute button for perspective_analysis jobs (FR-012)
 */
export function JobNode({
  id,
  title,
  jobData,
  isSelected,
  onSelect,
  onDoubleClick,
  onRerunWithMoreCompute,
  onRouteResults,
}: JobNodeProps) {
  const { jobData: progressData, isConnected } = useJobProgress(jobData.jobId);

  // Use the live progress data if available, otherwise use the static jobData
  const displayData: DisplayData = progressData || jobData;
  const status = displayData.status || "queued";
  const progressPercent = getProgressPercent(displayData);
  const currentStep = getCurrentStep(displayData);
  const stepNumber = getStepNumber(displayData);
  const stepsTotal = getStepsTotal(displayData);
  const jobType = getJobType(displayData);
  const resultPreview = buildResultPreview(
    isRecord((displayData as JobProgressData).data)
      ? ((displayData as JobProgressData).data as Record<string, unknown>)
      : isRecord((displayData as JobData).data)
        ? ((displayData as JobData).data as Record<string, unknown>)
        : null,
    jobType
  );
  const safeProgressPercent = Number.isFinite(progressPercent)
    ? Math.min(100, Math.max(0, progressPercent))
    : 0;
  const hasStepNumbers =
    typeof stepNumber === "number" && typeof stepsTotal === "number";
  const statusLabel = status.replace(/_/g, " ");
  const statusText = `${statusLabel.charAt(0).toUpperCase()}${statusLabel.slice(1)}`;

  // Status color mapping
  const getStatusColor = (status: string): string => {
    switch (status) {
      case "queued":
        return "bg-gray-200";
      case "in_progress":
        return "bg-blue-500";
      case "complete":
        return "bg-green-500";
      case "failed":
        return "bg-red-500";
      case "cancelled":
        return "bg-gray-400";
      default:
        return "bg-gray-200";
    }
  };

  const getStatusTextColor = (status: string): string => {
    switch (status) {
      case "queued":
        return "text-gray-600";
      case "in_progress":
        return "text-blue-600";
      case "complete":
        return "text-green-600";
      case "failed":
        return "text-red-600";
      case "cancelled":
        return "text-gray-500";
      default:
        return "text-gray-600";
    }
  };

  // Format job type for display
  const formatJobType = (jobType: string | undefined): string => {
    if (!jobType) {
      return "Unknown";
    }
    return jobType
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  // Check if this is a completed perspective analysis job that can be rerun
  const canRerun =
    status === "complete" &&
    jobType === "perspective_analysis" &&
    Boolean(onRerunWithMoreCompute);

  return (
    <div
      role="button"
      aria-label={`${title} job node`}
      className={`
        job-node bg-white rounded-lg shadow-md border-2 cursor-pointer
        min-w-[280px] max-w-[400px]
        transition-shadow hover:shadow-lg
        ${isSelected ? "ring-2 ring-blue-500 ring-offset-2" : "border-gray-300"}
      `}
      onClick={(e) => onSelect?.(e)}
      onDoubleClick={onDoubleClick}
      data-node-id={id}
      data-node-type="job"
    >
      {/* Header with job type and status */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 bg-gray-50 rounded-t-lg">
        <div className="flex items-center gap-2">
          {/* Status indicator dot */}
          <div
            className={`w-3 h-3 rounded-full ${getStatusColor(status)}`}
            title={status}
          />
          <span className="text-sm font-medium text-gray-700">
            {formatJobType(jobType)}
          </span>
        </div>
        {/* Connection status indicator */}
        {progressData && (
          <div
            className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-400" : "bg-gray-300"}`}
            title={isConnected ? "Live" : "Offline"}
          />
        )}
      </div>

      {/* Body with progress info */}
      <div className="px-3 py-3 space-y-3">
        {/* Title */}
        <h3 className="text-sm font-semibold text-gray-800 line-clamp-2">
          {title}
        </h3>

        {/* Status text */}
        <p className={`text-xs font-medium ${getStatusTextColor(status)}`}>
          {statusText}
        </p>

        {/* Progress bar */}
        <div className="space-y-1">
          <div className="flex justify-between items-center text-xs text-gray-600">
            <span>Progress</span>
            <span className="font-medium">{Math.round(safeProgressPercent)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full ${getStatusColor(status)} transition-all duration-300 ease-out`}
              style={{ width: `${safeProgressPercent}%` }}
            />
          </div>
        </div>

        {/* Step counter */}
        {hasStepNumbers && (
          <p className="text-xs text-gray-500">
            Step {stepNumber} of {stepsTotal}
          </p>
        )}

        {/* Current step description */}
        {currentStep && (
          <p className="text-xs text-gray-600 line-clamp-2">
            {currentStep}
          </p>
        )}

        {/* Result preview */}
        {resultPreview && (
          <div className="space-y-1">
            <div className="text-[10px] uppercase tracking-[0.2em] text-gray-400">
              Result
            </div>
            <p className="text-xs text-gray-700 line-clamp-3">
              {resultPreview}
            </p>
          </div>
        )}

        {/* Job ID (for reference) */}
        <p className="text-xs text-gray-400 font-mono">
          ID: {getJobId(displayData).slice(0, 8)}...
        </p>

        {/* Rerun with more compute button (FR-012: Multi-Judge Compute) */}
        {canRerun && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRerunWithMoreCompute?.();
            }}
            className="w-full mt-2 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-md hover:bg-indigo-100 transition-colors"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                d="M6 1V11M1 6H11"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
            Rerun with more compute
          </button>
        )}

        {onRouteResults && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRouteResults();
            }}
            className="w-full mt-2 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-md hover:bg-amber-100 transition-colors"
          >
            Route results
          </button>
        )}
      </div>
    </div>
  );
}
