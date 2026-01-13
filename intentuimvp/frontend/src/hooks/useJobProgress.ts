"use client";

import { useState, useEffect } from "react";
import { getAGUIClient } from "../agui/client";

/**
 * Job progress data from backend.
 */
export interface JobProgressData {
  job_id: string;
  job_type: string;
  status: string;
  progress_percent: number;
  current_step: string | null;
  step_number: number | null;
  steps_total: number | null;
  data: Record<string, unknown> | null;
  timestamp: string;
}

/**
 * Hook for streaming job progress via WebSocket.
 *
 * Subscribes to progress updates for a specific job and returns
 * the current job status and progress information.
 *
 * @param jobId - The job ID to stream progress for
 * @returns Job progress data and connection status
 */
export function useJobProgress(jobId: string | null) {
  const [jobData, setJobData] = useState<JobProgressData | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      // Reset state when jobId is null
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setJobData(null);
      setIsConnected(false);
      return;
    }

    const client = getAGUIClient();
    if (!client) {
      setError("AG-UI client not available");
      return;
    }

    setIsConnected(true);
    setError(null);

    // Listen for job progress notifications
    // The backend sends progress updates via WebSocket as notification messages
    // Note: Handler not yet registered - TODO: integrate with AGUIClient message handlers
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const _handleProgressUpdate = (message: { type: string; payload: Record<string, unknown> }) => {
      if (message.type === "notification" && message.payload) {
        const payload = message.payload as {
          title?: string;
          message?: string;
          job_id?: string;
          job_type?: string;
          status?: string;
          progress_percent?: number;
          current_step?: string;
          step_number?: number;
          steps_total?: number;
          data?: Record<string, unknown>;
          timestamp?: string;
        };

        // Check if this is a job progress update for our job
        if (payload.job_id === jobId) {
          setJobData({
            job_id: payload.job_id,
            job_type: payload.job_type || "unknown",
            status: payload.status || "unknown",
            progress_percent: payload.progress_percent ?? 0,
            current_step: payload.current_step ?? null,
            step_number: payload.step_number ?? null,
            steps_total: payload.steps_total ?? null,
            data: payload.data ?? null,
            timestamp: payload.timestamp || new Date().toISOString(),
          });
        }
      }
    };

    // Register with the client's message handlers
    // Note: This requires the AGUIClient to expose a way to register message handlers
    // For now, we'll fetch the initial job state via REST API

    // Fetch initial job state
    const fetchJobState = async () => {
      try {
        const response = await fetch(`/api/jobs/${jobId}`);
        if (response.ok) {
          const data = await response.json();
          setJobData({
            job_id: data.job_id,
            job_type: data.job_type,
            status: data.status,
            progress_percent: data.progress_percent ?? 0,
            current_step: data.current_step ?? null,
            step_number: null,
            steps_total: null,
            data: null,
            timestamp: data.updated_at || new Date().toISOString(),
          });
        }
      } catch (err) {
        console.error("Failed to fetch job state:", err);
      }
    };

    fetchJobState();

    // Poll for job updates every 2 seconds
    // In production, this would be replaced with WebSocket streaming
    const interval = setInterval(fetchJobState, 2000);

    return () => {
      clearInterval(interval);
    };
  }, [jobId]);

  return {
    jobData,
    isConnected,
    error,
  };
}
