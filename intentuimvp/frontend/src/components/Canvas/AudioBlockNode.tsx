"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AudioCapture, type AudioMarker, type AudioRecording } from "./AudioCapture";
import { useCanvasStore, type CanvasNode } from "../../state/canvasStore";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AudioMetadata = {
  blockId?: number;
  uri?: string;
  duration?: number;
  status?: string;
  transcription?: string | null;
  errorMessage?: string | null;
  markers?: AudioMarker[];
  jobId?: string;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const getNumber = (value: unknown): number | undefined => {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
};

const getString = (value: unknown): string | undefined =>
  typeof value === "string" ? value : undefined;

const toMarker = (value: unknown): AudioMarker | null => {
  if (!isRecord(value)) return null;
  const id = getString(value.id);
  const time = getNumber(value.time);
  if (!id || time === undefined) return null;
  const label = getString(value.label);
  return { id, time, label };
};

export const toMarkers = (value: unknown): AudioMarker[] => {
  if (!Array.isArray(value)) return [];
  return value.map(toMarker).filter((marker): marker is AudioMarker => marker !== null);
};

const formatDurationSeconds = (seconds: number): string => {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
};

const buildAudioContent = (audio: AudioMetadata): string | undefined => {
  if (audio.transcription && audio.transcription.trim().length > 0) {
    return audio.transcription;
  }
  if (audio.duration !== undefined) {
    return `Audio recording (${formatDurationSeconds(audio.duration)})`;
  }
  if (audio.blockId || audio.uri) {
    return "Audio recording";
  }
  return undefined;
};

const isRemoteUri = (uri?: string): boolean =>
  Boolean(uri && /^(https?:)?\/\//.test(uri));

const toAudioMetadata = (metadata?: Record<string, unknown>): AudioMetadata => {
  if (!metadata) return {};
  const audioValue = metadata.audio;
  const audio = isRecord(audioValue) ? audioValue : {};
  const blockId = getNumber(audio.blockId ?? audio.audioBlockId ?? audio.id);
  const uri = getString(audio.uri ?? audio.audioUri ?? audio.url);
  const duration = getNumber(audio.duration);
  const status = getString(audio.status);
  const transcription = getString(audio.transcription) ?? undefined;
  const errorMessage = getString(audio.errorMessage ?? audio.error);
  const jobId = getString(audio.jobId ?? audio.job_id);
  const markers = toMarkers(audio.markers);
  return {
    blockId,
    uri,
    duration,
    status,
    transcription,
    errorMessage,
    markers,
    jobId,
  };
};

const blobToBase64 = (blob: Blob): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
        return;
      }
      reject(new Error("Failed to read audio data"));
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read audio data"));
    reader.readAsDataURL(blob);
  });

type AudioBlockNodeProps = {
  node: CanvasNode;
};

export function AudioBlockNode({ node }: AudioBlockNodeProps) {
  const updateNode = useCanvasStore((state) => state.updateNode);
  const canvasId = useCanvasStore((state) => state.canvasId);
  const [error, setError] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);

  const audioMeta = useMemo(() => toAudioMetadata(node.metadata), [node.metadata]);

  const updateAudioMetadata = useCallback(
    (updates: Partial<AudioMetadata>) => {
      const latestNode = useCanvasStore.getState().nodes.find((n) => n.id === node.id);
      const currentMetadata = (latestNode?.metadata ?? node.metadata ?? {}) as Record<
        string,
        unknown
      >;
      const currentAudio = isRecord(currentMetadata.audio) ? currentMetadata.audio : {};
      const nextAudio = { ...currentAudio, ...updates };
      const nextMetadata = { ...currentMetadata, audio: nextAudio };
      updateNode(node.id, {
        metadata: nextMetadata,
        content: buildAudioContent(toAudioMetadata(nextMetadata)),
      });
    },
    [node.id, node.metadata, updateNode]
  );

  const audioSource = useMemo(() => {
    if (audioMeta.blockId) {
      if (isRemoteUri(audioMeta.uri)) {
        return audioMeta.uri;
      }
      return `${API_BASE_URL}/api/audio/blocks/${audioMeta.blockId}/content`;
    }
    if (audioMeta.uri) return audioMeta.uri;
    return null;
  }, [audioMeta.blockId, audioMeta.uri]);

  const existingRecording = useMemo<AudioRecording | null>(() => {
    if (!audioSource) return null;
    return {
      url: audioSource,
      duration: Math.max(0, Math.round((audioMeta.duration ?? 0) * 1000)),
      createdAt: new Date(),
    };
  }, [audioMeta.duration, audioSource]);

  const refreshAudioBlock = useCallback(async () => {
    if (!audioMeta.blockId) return;
    setIsRefreshing(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/audio/blocks/${audioMeta.blockId}`);
      if (!response.ok) {
        throw new Error(`Failed to refresh audio block (${response.status})`);
      }
      const data = (await response.json()) as {
        id: number;
        audioUri: string;
        duration: number | null;
        status: string;
        transcription?: string | null;
        errorMessage?: string | null;
      };
      updateAudioMetadata({
        blockId: data.id,
        uri: data.audioUri,
        duration: data.duration ?? undefined,
        status: data.status,
        transcription: data.transcription ?? undefined,
        errorMessage: data.errorMessage ?? undefined,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to refresh audio block";
      setError(message);
    } finally {
      setIsRefreshing(false);
    }
  }, [audioMeta.blockId, updateAudioMetadata]);

  useEffect(() => {
    if (!audioMeta.blockId) return;
    void refreshAudioBlock();
  }, [audioMeta.blockId, refreshAudioBlock]);

  useEffect(() => {
    if (audioMeta.status !== "transcribing" || !audioMeta.blockId) return;
    const timer = window.setTimeout(() => {
      void refreshAudioBlock();
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [audioMeta.blockId, audioMeta.status, refreshAudioBlock]);

  const handleRecordingComplete = useCallback(
    async (recording: AudioRecording) => {
      if (!canvasId) {
        setError("Canvas not ready. Please reload and try again.");
        return;
      }
      if (!recording.blob) {
        setError("Recording data missing.");
        return;
      }

      setIsUploading(true);
      setError(null);
      try {
        if (audioMeta.blockId) {
          await fetch(`${API_BASE_URL}/api/audio/blocks/${audioMeta.blockId}`, {
            method: "DELETE",
          });
        }

        const audioData = await blobToBase64(recording.blob);
        const response = await fetch(`${API_BASE_URL}/api/audio/blocks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            canvas_id: canvasId,
            audio_data: audioData,
            duration: recording.duration / 1000,
          }),
        });
        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Upload failed (${response.status}): ${errorText}`);
        }
        const data = (await response.json()) as {
          id: number;
          audioUri: string;
          duration: number | null;
          status: string;
          transcription?: string | null;
        };
        updateAudioMetadata({
          blockId: data.id,
          uri: data.audioUri,
          duration: data.duration ?? undefined,
          status: data.status,
          transcription: data.transcription ?? undefined,
          markers: [],
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Audio upload failed";
        setError(message);
      } finally {
        setIsUploading(false);
      }
    },
    [audioMeta.blockId, canvasId, updateAudioMetadata]
  );

  const handleRecordingDeleted = useCallback(async () => {
    if (audioMeta.blockId) {
      try {
        await fetch(`${API_BASE_URL}/api/audio/blocks/${audioMeta.blockId}`, {
          method: "DELETE",
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to delete audio block";
        setError(message);
      }
    }
    updateAudioMetadata({
      blockId: undefined,
      uri: undefined,
      duration: undefined,
      status: undefined,
      transcription: undefined,
      errorMessage: undefined,
      markers: [],
      jobId: undefined,
    });
  }, [audioMeta.blockId, updateAudioMetadata]);

  const handleAddMarker = useCallback(
    (marker: AudioMarker) => {
      const nextMarkers = [...(audioMeta.markers ?? []), marker];
      updateAudioMetadata({ markers: nextMarkers });
    },
    [audioMeta.markers, updateAudioMetadata]
  );

  const handleDeleteMarker = useCallback(
    (markerId: string) => {
      const nextMarkers = (audioMeta.markers ?? []).filter((marker) => marker.id !== markerId);
      updateAudioMetadata({ markers: nextMarkers });
    },
    [audioMeta.markers, updateAudioMetadata]
  );

  const handleTranscribe = useCallback(async () => {
    if (!audioMeta.blockId) return;
    setIsTranscribing(true);
    setError(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/audio/blocks/${audioMeta.blockId}/transcribe`,
        { method: "POST" }
      );
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Transcription request failed (${response.status}): ${errorText}`);
      }
      const data = (await response.json()) as { job_id?: string };
      updateAudioMetadata({
        status: "transcribing",
        jobId: data.job_id,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to start transcription";
      setError(message);
    } finally {
      setIsTranscribing(false);
    }
  }, [audioMeta.blockId, updateAudioMetadata]);

  const audioStatus = audioMeta.status ?? "ready";
  const canTranscribe = Boolean(audioMeta.blockId) && audioStatus !== "transcribing";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <AudioCapture
        onRecordingComplete={handleRecordingComplete}
        onRecordingDeleted={handleRecordingDeleted}
        existingRecording={existingRecording}
        markers={audioMeta.markers ?? []}
        onAddMarker={handleAddMarker}
        onDeleteMarker={handleDeleteMarker}
        disabled={isUploading}
        style={{
          minWidth: "280px",
        }}
        aria-label={`Audio capture for ${node.title}`}
      />

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: "6px",
          fontSize: "12px",
          color: "#94a3b8",
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
          <span>Status: {audioStatus}</span>
          {audioMeta.duration !== undefined && (
            <span>Duration: {formatDurationSeconds(audioMeta.duration)}</span>
          )}
          {audioMeta.jobId && <span>Job: {audioMeta.jobId}</span>}
        </div>

        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {canTranscribe && (
            <button
              type="button"
              onClick={handleTranscribe}
              disabled={isTranscribing || !audioMeta.blockId}
              style={{
                padding: "6px 12px",
                backgroundColor: "#f59e0b",
                border: "none",
                borderRadius: "4px",
                color: "#1f2937",
                fontSize: "12px",
                cursor: isTranscribing ? "not-allowed" : "pointer",
                opacity: isTranscribing ? 0.7 : 1,
              }}
            >
              {isTranscribing ? "Transcribing..." : "Transcribe"}
            </button>
          )}
          <button
            type="button"
            onClick={refreshAudioBlock}
            disabled={isRefreshing || !audioMeta.blockId}
            style={{
              padding: "6px 12px",
              backgroundColor: "rgba(15, 23, 42, 0.8)",
              border: "1px solid rgba(148, 163, 184, 0.4)",
              borderRadius: "4px",
              color: "#e2e8f0",
              fontSize: "12px",
              cursor: isRefreshing ? "not-allowed" : "pointer",
              opacity: isRefreshing ? 0.7 : 1,
            }}
          >
            {isRefreshing ? "Refreshing..." : "Refresh"}
          </button>
        </div>

        {audioMeta.transcription && (
          <div
            style={{
              marginTop: "6px",
              padding: "8px",
              borderRadius: "6px",
              border: "1px solid rgba(148, 163, 184, 0.2)",
              backgroundColor: "rgba(15, 23, 42, 0.6)",
              color: "#e2e8f0",
              whiteSpace: "pre-wrap",
              lineHeight: "1.4",
            }}
            aria-label="Audio transcription"
          >
            {audioMeta.transcription}
          </div>
        )}

        {audioMeta.errorMessage && (
          <div style={{ color: "#f87171" }}>{audioMeta.errorMessage}</div>
        )}
        {error && <div style={{ color: "#f87171" }}>{error}</div>}
      </div>
    </div>
  );
}
