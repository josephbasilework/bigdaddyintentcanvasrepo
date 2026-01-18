"use client";

const TURN_SEQUENCE_PREFIX = "intentui_turn_sequence_v1";

const getStorageKey = (sessionId: string): string =>
  `${TURN_SEQUENCE_PREFIX}:${sessionId}`;

const coerceSequenceNumber = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

export const getLastSyncedTurnSequence = (sessionId: string): number | null => {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const stored = localStorage.getItem(getStorageKey(sessionId));
    if (!stored) {
      return null;
    }
    return coerceSequenceNumber(stored);
  } catch {
    return null;
  }
};

export const setLastSyncedTurnSequence = (
  sessionId: string,
  sequenceNumber: number
): void => {
  if (typeof window === "undefined") {
    return;
  }
  const normalized = coerceSequenceNumber(sequenceNumber);
  if (normalized === null) {
    return;
  }
  try {
    localStorage.setItem(getStorageKey(sessionId), String(normalized));
  } catch {
    // ignore
  }
};

export const clearLastSyncedTurnSequence = (sessionId: string): void => {
  if (typeof window === "undefined") {
    return;
  }
  try {
    localStorage.removeItem(getStorageKey(sessionId));
  } catch {
    // ignore
  }
};
