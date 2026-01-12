import { useEffect, useRef, useState, useCallback } from "react";
import { useCanvasStore, CanvasNode, CanvasEdge, CanvasDocument } from "../state/canvasStore";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Auto-save configuration options.
 */
export interface AutoSaveConfig {
  /** Debounce delay in milliseconds (default: 500ms) */
  debounceMs?: number;
  /** Maximum number of retry attempts for failed saves (default: 3) */
  maxRetries?: number;
  /** Initial delay for retry backoff in milliseconds (default: 1000ms) */
  retryDelayMs?: number;
  /** Enable/disable debug logging (default: false) */
  debug?: boolean;
}

/**
 * Save status for tracking auto-save state.
 */
export type SaveStatus = "idle" | "saving" | "saved" | "error";

/**
 * Result object returned by useAutoSave hook.
 */
export interface AutoSaveResult {
  /** Current save status */
  saveStatus: SaveStatus;
  /** Error message if save failed */
  saveError: string | null;
  /** Whether there are uncommitted changes */
  hasUnsavedChanges: boolean;
  /** Function to manually trigger a save */
  saveNow: () => Promise<void>;
}

/**
 * Custom hook for auto-saving canvas state with debouncing and retry logic.
 *
 * Features:
 * - Debounced saves to avoid excessive API calls
 * - Save status tracking (idle, saving, saved, error)
 * - Exponential backoff retry for failed saves
 * - Saves nodes, edges, and documents
 *
 * @param config - Configuration options for auto-save behavior
 * @returns AutoSaveResult object with save status and control functions
 *
 * @example
 * ```tsx
 * const { saveStatus, saveError, saveNow } = useAutoSave({
 *   debounceMs: 1000,
 *   maxRetries: 3,
 * });
 * ```
 */
export function useAutoSave(config: AutoSaveConfig = {}): AutoSaveResult {
  const {
    debounceMs = 500,
    maxRetries = 3,
    retryDelayMs = 1000,
    debug = false,
  } = config;

  const nodes = useCanvasStore((state) => state.nodes);
  const edges = useCanvasStore((state) => state.edges);
  const documents = useCanvasStore((state) => state.documents);

  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedRef = useRef<string>(JSON.stringify({ nodes: [], edges: [], documents: [] }));
  const isInitialLoadRef = useRef(true);

  const log = useCallback((...args: unknown[]) => {
    if (debug) {
      console.log("[useAutoSave]", ...args);
    }
  }, [debug]);

  /**
   * Performs the actual save operation with retry logic.
   */
  const performSave = useCallback(
    async (nodesToSave: CanvasNode[], edgesToSave: CanvasEdge[], documentsToSave: CanvasDocument[], retryCount = 0): Promise<boolean> => {
      try {
        log(`Saving attempt ${retryCount + 1}/${maxRetries}`);

        const response = await fetch(`${API_BASE_URL}/api/workspace`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            nodes: nodesToSave,
            edges: edgesToSave,
            documents: documentsToSave,
          }),
        });

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`Save failed with status ${response.status}: ${errorText}`);
        }

        log("Save successful");
        return true;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Unknown error";
        log(`Save failed: ${errorMessage}`);

        if (retryCount < maxRetries - 1) {
          const delay = retryDelayMs * Math.pow(2, retryCount);
          log(`Retrying in ${delay}ms...`);
          await new Promise((resolve) => setTimeout(resolve, delay));
          return performSave(nodesToSave, edgesToSave, documentsToSave, retryCount + 1);
        }

        throw error;
      }
    },
    [maxRetries, retryDelayMs, log]
  );

  /**
   * Manually trigger a save operation.
   */
  const saveNow = useCallback(async () => {
    // Clear any pending debounced save
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    // Skip saving if empty canvas and not previously saved
    const currentState = JSON.stringify({ nodes, edges, documents });
    if (nodes.length === 0 && edges.length === 0 && documents.length === 0 && lastSavedRef.current === "[]") {
      log("Skipping save: empty canvas");
      return;
    }

    setSaveStatus("saving");
    setSaveError(null);

    try {
      await performSave(nodes, edges, documents);
      lastSavedRef.current = currentState;
      setSaveStatus("saved");
      setHasUnsavedChanges(false);

      // Reset to "idle" after a brief "saved" indication
      setTimeout(() => {
        setSaveStatus("idle");
      }, 1500);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Failed to save";
      setSaveError(errorMessage);
      setSaveStatus("error");
      setHasUnsavedChanges(true);
    }
  }, [nodes, edges, documents, performSave, log]);

  /**
   * Debounced save effect that triggers on state changes.
   */
  useEffect(() => {
    // Skip on initial load (avoid saving immediately after loading)
    if (isInitialLoadRef.current) {
      isInitialLoadRef.current = false;
      lastSavedRef.current = JSON.stringify({ nodes, edges, documents });
      return;
    }

    // Skip if both arrays are empty (nothing to save)
    if (nodes.length === 0 && edges.length === 0 && documents.length === 0) {
      return;
    }

    // Check if state actually changed
    const currentState = JSON.stringify({ nodes, edges, documents });
    if (currentState === lastSavedRef.current) {
      return;
    }

    // Mark as having unsaved changes
    setHasUnsavedChanges(true);

    // Clear any pending timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    // Schedule debounced save
    timeoutRef.current = setTimeout(async () => {
      setSaveStatus("saving");
      setSaveError(null);

      try {
        await performSave(nodes, edges, documents);
        lastSavedRef.current = currentState;
        setSaveStatus("saved");
        setHasUnsavedChanges(false);

        // Reset to "idle" after a brief "saved" indication
        setTimeout(() => {
          setSaveStatus("idle");
        }, 1500);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Failed to save";
        setSaveError(errorMessage);
        setSaveStatus("error");
      }
    }, debounceMs);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [nodes, edges, documents, debounceMs, performSave]);

  return {
    saveStatus,
    saveError,
    hasUnsavedChanges,
    saveNow,
  };
}
