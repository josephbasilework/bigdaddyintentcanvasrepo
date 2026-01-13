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
}

type DisplayData = JobData | JobProgressData;

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

/**
 * JobNode component displays a job's status and progress on the canvas.
 *
 * Shows:
 * - Job type and status
 * - Progress bar with percentage
 * - Current step description
 * - Step counter (e.g., "Step 3 of 5")
 */
export function JobNode({
  id,
  title,
  jobData,
  isSelected,
  onSelect,
  onDoubleClick,
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

        {/* Job ID (for reference) */}
        <p className="text-xs text-gray-400 font-mono">
          ID: {getJobId(displayData).slice(0, 8)}...
        </p>
      </div>
    </div>
  );
}
