"use client";

import { useState, useRef, useEffect, useCallback, CSSProperties } from "react";

export interface AudioRecording {
  blob: Blob;
  url: string;
  duration: number;
  createdAt: Date;
}

export type RecordingStatus = "idle" | "recording" | "paused" | "completed" | "error";

interface AudioCaptureProps {
  onRecordingComplete?: (recording: AudioRecording) => void;
  onRecordingStart?: () => void;
  existingRecording?: AudioRecording | null;
  disabled?: boolean;
  style?: CSSProperties;
  className?: string;
  "aria-label"?: string;
}

/**
 * AudioCapture component for recording and playing audio within the canvas.
 *
 * Features:
 * - Record audio from microphone using MediaRecorder API
 * - Play back recordings with HTML5 Audio
 * - Visual duration display
 * - Status indicators for recording state
 */
export function AudioCapture({
  onRecordingComplete,
  onRecordingStart,
  existingRecording = null,
  disabled = false,
  style,
  className = "",
  "aria-label": ariaLabel = "Audio capture and playback",
}: AudioCaptureProps) {
  // Initialize status based on whether there's an existing recording
  const initialStatus = existingRecording ? "completed" : "idle";
  const initialDuration = existingRecording?.duration ?? 0;

  const [status, setStatus] = useState<RecordingStatus>(initialStatus);
  const [duration, setDuration] = useState(initialDuration);
  const [recording, setRecording] = useState<AudioRecording | null>(existingRecording);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  // Format duration as MM:SS
  const formatDuration = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  };

  // Start recording
  const startRecording = useCallback(async () => {
    if (disabled) return;

    setError(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const audioUrl = URL.createObjectURL(audioBlob);
        const audioRecording: AudioRecording = {
          blob: audioBlob,
          url: audioUrl,
          duration,
          createdAt: new Date(),
        };

        setRecording(audioRecording);
        setStatus("completed");

        // Stop all tracks to release microphone
        stream.getTracks().forEach((track) => track.stop());

        if (onRecordingComplete) {
          onRecordingComplete(audioRecording);
        }
      };

      mediaRecorder.start();
      setStatus("recording");
      setDuration(0);
      startTimeRef.current = Date.now();

      // Start duration timer
      timerRef.current = window.setInterval(() => {
        if (startTimeRef.current) {
          setDuration(Date.now() - startTimeRef.current);
        }
      }, 100);

      if (onRecordingStart) {
        onRecordingStart();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to access microphone";
      setError(message);
      setStatus("error");
      console.error("Error starting recording:", err);
    }
  }, [disabled, duration, onRecordingComplete, onRecordingStart]);

  // Stop recording
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && status === "recording") {
      mediaRecorderRef.current.stop();

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [status]);

  // Delete recording
  const deleteRecording = useCallback(() => {
    if (recording) {
      URL.revokeObjectURL(recording.url);
    }
    setRecording(null);
    setDuration(0);
    setStatus("idle");
    setError(null);
  }, [recording]);

  // Get status indicator color
  const getStatusColor = (): string => {
    switch (status) {
      case "recording":
        return "#ef4444";
      case "completed":
        return "#10b981";
      case "error":
        return "#f59e0b";
      default:
        return "#6b7280";
    }
  };

  // Get status text
  const getStatusText = (): string => {
    switch (status) {
      case "recording":
        return "● Recording";
      case "completed":
        return "✓ Recorded";
      case "error":
        return "⚠ Error";
      default:
        return "Ready";
    }
  };

  const baseStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    width: "100%",
    boxSizing: "border-box",
    ...style,
  };

  return (
    <div style={baseStyle} className={`audio-capture ${className}`} aria-label={ariaLabel}>
      {/* Status indicator */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: "12px",
          color: getStatusColor(),
        }}
      >
        <span>{getStatusText()}</span>
        <span style={{ fontFamily: "monospace" }}>
          {formatDuration(duration)}
        </span>
      </div>

      {/* Error message */}
      {error && (
        <div
          style={{
            padding: "8px",
            backgroundColor: "rgba(239, 68, 68, 0.1)",
            border: "1px solid #ef4444",
            borderRadius: "4px",
            fontSize: "12px",
            color: "#ef4444",
          }}
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Audio player (when recording exists) */}
      {recording && (
        <audio
          ref={audioRef}
          src={recording.url}
          controls
          style={{
            width: "100%",
            height: "32px",
          }}
          aria-label="Audio playback"
        />
      )}

      {/* Control buttons */}
      <div
        style={{
          display: "flex",
          gap: "8px",
          flexWrap: "wrap",
        }}
      >
        {status === "idle" && (
          <button
            type="button"
            onClick={startRecording}
            disabled={disabled}
            style={{
              padding: "8px 16px",
              backgroundColor: "#ef4444",
              border: "none",
              borderRadius: "4px",
              color: "#fff",
              cursor: disabled ? "not-allowed" : "pointer",
              fontSize: "13px",
              opacity: disabled ? 0.5 : 1,
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            aria-label="Start recording"
          >
            <span>●</span> Record
          </button>
        )}

        {status === "recording" && (
          <button
            type="button"
            onClick={stopRecording}
            style={{
              padding: "8px 16px",
              backgroundColor: "#10b981",
              border: "none",
              borderRadius: "4px",
              color: "#fff",
              cursor: "pointer",
              fontSize: "13px",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            aria-label="Stop recording"
          >
            <span>■</span> Stop
          </button>
        )}

        {status === "completed" && (
          <>
            <button
              type="button"
              onClick={startRecording}
              disabled={disabled}
              style={{
                padding: "8px 16px",
                backgroundColor: "#3b82f6",
                border: "none",
                borderRadius: "4px",
                color: "#fff",
                cursor: disabled ? "not-allowed" : "pointer",
                fontSize: "13px",
                opacity: disabled ? 0.5 : 1,
              }}
              aria-label="Record new audio"
            >
              Re-record
            </button>
            <button
              type="button"
              onClick={deleteRecording}
              style={{
                padding: "8px 16px",
                backgroundColor: "#6b7280",
                border: "none",
                borderRadius: "4px",
                color: "#fff",
                cursor: "pointer",
                fontSize: "13px",
              }}
              aria-label="Delete recording"
            >
              Delete
            </button>
          </>
        )}

        {(status === "error" || status === "completed") && (
          <button
            type="button"
            onClick={() => {
              setStatus("idle");
              setError(null);
            }}
            style={{
              padding: "8px 16px",
              backgroundColor: "#6b7280",
              border: "none",
              borderRadius: "4px",
              color: "#fff",
              cursor: "pointer",
              fontSize: "13px",
            }}
            aria-label="Reset"
          >
            Reset
          </button>
        )}
      </div>
    </div>
  );
}
