"use client";

import { useState, useRef, useEffect, useCallback, CSSProperties } from "react";

export interface AudioRecording {
  blob?: Blob;
  url: string;
  duration: number;
  createdAt: Date;
}

export interface AudioMarker {
  id: string;
  time: number;
  label?: string;
}

export type RecordingStatus = "idle" | "recording" | "paused" | "completed" | "error";

interface AudioCaptureProps {
  onRecordingComplete?: (recording: AudioRecording) => void;
  onRecordingStart?: () => void;
  onRecordingDeleted?: () => void;
  existingRecording?: AudioRecording | null;
  markers?: AudioMarker[];
  onAddMarker?: (marker: AudioMarker) => void;
  onDeleteMarker?: (markerId: string) => void;
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
  onRecordingDeleted,
  existingRecording = null,
  markers = [],
  onAddMarker,
  onDeleteMarker,
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
  const [playbackTime, setPlaybackTime] = useState(0);
  const [waveform, setWaveform] = useState<number[] | null>(null);
  const [isWaveformLoading, setIsWaveformLoading] = useState(false);

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

  // Sync existing recordings to local state
  useEffect(() => {
    if (status === "recording") return;
    if (existingRecording) {
      setRecording(existingRecording);
      setDuration(existingRecording.duration);
      setStatus("completed");
      setError(null);
      return;
    }
    if (!recording?.blob && status !== "error") {
      setRecording(null);
      setDuration(0);
      setStatus("idle");
    }
  }, [existingRecording, recording?.blob, status]);

  // Format duration as MM:SS
  const formatDuration = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  };

  const formatTimestamp = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, "0")}:${remainingSeconds
      .toString()
      .padStart(2, "0")}`;
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
      if (recording.blob || recording.url.startsWith("blob:")) {
        URL.revokeObjectURL(recording.url);
      }
    }
    setRecording(null);
    setDuration(0);
    setStatus("idle");
    setError(null);
    if (onRecordingDeleted) {
      onRecordingDeleted();
    }
  }, [onRecordingDeleted, recording]);

  const handleAddMarker = useCallback(() => {
    if (!audioRef.current || !onAddMarker) return;
    const time = audioRef.current.currentTime;
    const id = typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const marker: AudioMarker = {
      id,
      time,
      label: `Marker ${markers.length + 1}`,
    };
    onAddMarker(marker);
  }, [markers.length, onAddMarker]);

  const handleSeekMarker = useCallback((marker: AudioMarker) => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = marker.time;
  }, []);

  const handleDeleteMarker = useCallback((markerId: string) => {
    if (!onDeleteMarker) return;
    onDeleteMarker(markerId);
  }, [onDeleteMarker]);

  useEffect(() => {
    if (!recording) {
      setWaveform(null);
      return;
    }

    const AudioContextImpl =
      typeof window !== "undefined"
        ? (window.AudioContext || (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext)
        : undefined;
    if (!AudioContextImpl) {
      setWaveform(null);
      return;
    }

    let isCancelled = false;

    const buildWaveform = async () => {
      setIsWaveformLoading(true);
      try {
        const arrayBuffer = recording.blob
          ? await recording.blob.arrayBuffer()
          : await fetch(recording.url).then((response) => response.arrayBuffer());

        if (isCancelled) return;

        const audioContext = new AudioContextImpl();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer.slice(0));
        const channelData = audioBuffer.getChannelData(0);

        const samples = 64;
        const blockSize = Math.floor(channelData.length / samples);
        const peaks = Array.from({ length: samples }, (_, index) => {
          const start = index * blockSize;
          let max = 0;
          for (let i = 0; i < blockSize; i += 1) {
            const value = Math.abs(channelData[start + i] || 0);
            if (value > max) max = value;
          }
          return max;
        });

        if (!isCancelled) {
          setWaveform(peaks);
        }
        await audioContext.close();
      } catch {
        if (!isCancelled) {
          setWaveform(null);
        }
      } finally {
        if (!isCancelled) {
          setIsWaveformLoading(false);
        }
      }
    };

    void buildWaveform();

    return () => {
      isCancelled = true;
    };
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
          onTimeUpdate={() => {
            if (audioRef.current) {
              setPlaybackTime(audioRef.current.currentTime);
            }
          }}
          onLoadedMetadata={() => {
            if (audioRef.current && Number.isFinite(audioRef.current.duration)) {
              setDuration(Math.round(audioRef.current.duration * 1000));
            }
          }}
          style={{
            width: "100%",
            height: "32px",
          }}
          aria-label="Audio playback"
        />
      )}

      {recording && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div
            style={{
              position: "relative",
              height: "48px",
              display: "flex",
              alignItems: "flex-end",
              gap: "2px",
              padding: "6px 4px",
              backgroundColor: "rgba(15, 23, 42, 0.6)",
              borderRadius: "6px",
              border: "1px solid rgba(148, 163, 184, 0.2)",
              overflow: "hidden",
            }}
            aria-label="Audio waveform"
          >
            {waveform && waveform.length > 0 ? (
              waveform.map((value, index) => {
                const progressRatio = duration > 0
                  ? playbackTime / (duration / 1000)
                  : 0;
                const isPlayed = index / waveform.length <= progressRatio;
                return (
                  <div
                    key={`wave-${index}`}
                    style={{
                      width: "3px",
                      height: `${Math.max(4, value * 40)}px`,
                      backgroundColor: isPlayed ? "#38bdf8" : "rgba(148, 163, 184, 0.6)",
                      borderRadius: "2px",
                      transition: "background-color 0.2s ease",
                    }}
                  />
                );
              })
            ) : (
              <div
                style={{
                  fontSize: "11px",
                  color: "#94a3b8",
                }}
              >
                {isWaveformLoading ? "Loading waveform..." : "Waveform unavailable"}
              </div>
            )}

            {markers.map((marker) => {
              const left = duration > 0
                ? `${Math.min(100, (marker.time / (duration / 1000)) * 100)}%`
                : "0%";
              return (
                <div
                  key={marker.id}
                  style={{
                    position: "absolute",
                    left,
                    bottom: 0,
                    top: 0,
                    width: "2px",
                    backgroundColor: "#f97316",
                  }}
                />
              );
            })}
          </div>

          {markers.length > 0 && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "6px",
              }}
            >
              {markers.map((marker) => (
                <div
                  key={`marker-${marker.id}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: "12px",
                    color: "#e2e8f0",
                  }}
                >
                  <button
                    type="button"
                    onClick={() => handleSeekMarker(marker)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#38bdf8",
                      cursor: "pointer",
                      padding: 0,
                    }}
                  >
                    {marker.label ?? "Marker"} · {formatTimestamp(marker.time)}
                  </button>
                  {onDeleteMarker && (
                    <button
                      type="button"
                      onClick={() => handleDeleteMarker(marker.id)}
                      aria-label={`Delete marker ${marker.label ?? formatTimestamp(marker.time)}`}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#f87171",
                        cursor: "pointer",
                        fontSize: "11px",
                      }}
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
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
            {onAddMarker && (
              <button
                type="button"
                onClick={handleAddMarker}
                style={{
                  padding: "8px 16px",
                  backgroundColor: "#0ea5e9",
                  border: "none",
                  borderRadius: "4px",
                  color: "#fff",
                  cursor: "pointer",
                  fontSize: "13px",
                }}
                aria-label="Add marker at current time"
              >
                Add marker
              </button>
            )}
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
