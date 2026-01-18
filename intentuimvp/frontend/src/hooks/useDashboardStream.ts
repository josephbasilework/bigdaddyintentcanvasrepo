"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { getAGUIClient } from "../agui/client";
import type {
  DashboardSubscriptionTarget,
  DashboardChangeType,
  DashboardUpdatePayload,
  DashboardSubscribedPayload,
} from "../agui/protocol";

export type { DashboardUpdatePayload, DashboardSubscribedPayload };

export interface DashboardStreamStats {
  entityCounts: Record<DashboardSubscriptionTarget, number>;
  recentChanges: DashboardChange[];
  isSubscribed: boolean;
  lastUpdateTime: Date | null;
  activeSubscriptions: DashboardSubscribedPayload["subscriptions"];
}

export type ExternalStreamStatus = "idle" | "connecting" | "connected" | "error";

export interface ExternalStreamState {
  data: unknown;
  status: ExternalStreamStatus;
  error: string | null;
  lastUpdated: Date | null;
}

export interface DashboardChange {
  target: DashboardSubscriptionTarget;
  sourceId: string | null;
  changeType: DashboardChangeType;
  timestamp: Date;
  data: Record<string, unknown>;
}

const MAX_RECENT_CHANGES = 50;

const initialStats: DashboardStreamStats = {
  entityCounts: {
    workspace_state: 0,
    node: 0,
    edge: 0,
    job: 0,
    artifact: 0,
    tool_output: 0,
    external_state: 0,
  },
  recentChanges: [],
  isSubscribed: false,
  lastUpdateTime: null,
  activeSubscriptions: [],
};

const initialExternalState: ExternalStreamState = {
  data: null,
  status: "idle",
  error: null,
  lastUpdated: null,
};

export function useDashboardStream(
  dashboardNodeId: number | null,
  canvasId: number | null,
  enabled = true
) {
  const [stats, setStats] = useState<DashboardStreamStats>(initialStats);
  const [externalState, setExternalState] =
    useState<ExternalStreamState>(initialExternalState);
  const cleanupRef = useRef<(() => void) | null>(null);

  const handleUpdate = useCallback((payload: DashboardUpdatePayload) => {
    setStats((prev) => {
      const newChange: DashboardChange = {
        target: payload.subscription_target as DashboardSubscriptionTarget,
        sourceId: payload.source_id,
        changeType: payload.change_type,
        timestamp: new Date(payload.timestamp),
        data: payload.data,
      };

      const newEntityCounts = { ...prev.entityCounts };
      const target = payload.subscription_target as DashboardSubscriptionTarget;

      if (payload.change_type === "created") {
        newEntityCounts[target] = (newEntityCounts[target] || 0) + 1;
      } else if (payload.change_type === "deleted") {
        newEntityCounts[target] = Math.max(0, (newEntityCounts[target] || 0) - 1);
      }

      const recentChanges = [newChange, ...prev.recentChanges].slice(
        0,
        MAX_RECENT_CHANGES
      );

      return {
        ...prev,
        entityCounts: newEntityCounts,
        recentChanges,
        lastUpdateTime: new Date(),
      };
    });

    if (payload.subscription_target === "external_state") {
      const updateData = payload.data ?? {};
      const statusCandidate =
        typeof updateData.status === "string" ? updateData.status : null;
      const errorCandidate =
        typeof updateData.error === "string"
          ? updateData.error
          : typeof updateData.message === "string"
            ? updateData.message
            : null;
      const hasPayload = Object.prototype.hasOwnProperty.call(updateData, "payload");
      const isStatusOnly =
        !hasPayload &&
        (statusCandidate !== null || errorCandidate !== null) &&
        Object.keys(updateData).every((key) =>
          ["status", "error", "observed_at"].includes(key)
        );
      const payloadValue = hasPayload ? updateData.payload : isStatusOnly ? null : updateData;
      const normalizedStatus: ExternalStreamStatus =
        statusCandidate === "connecting" ||
        statusCandidate === "connected" ||
        statusCandidate === "error"
          ? (statusCandidate as ExternalStreamStatus)
          : "connected";
      const timestamp = new Date(payload.timestamp);
      setExternalState((prev) => ({
        data: payloadValue ?? prev.data,
        status: normalizedStatus,
        error:
          normalizedStatus === "error"
            ? errorCandidate ?? prev.error ?? "External source error"
            : null,
        lastUpdated:
          payloadValue !== null || normalizedStatus === "connected"
            ? timestamp
            : prev.lastUpdated,
      }));
    }
  }, []);

  const handleSubscribed = useCallback((payload: DashboardSubscribedPayload) => {
    setStats((prev) => ({
      ...prev,
      isSubscribed: true,
      activeSubscriptions: payload.subscriptions,
    }));
  }, []);

  useEffect(() => {
    if (!enabled || dashboardNodeId === null || canvasId === null) {
      return;
    }

    const client = getAGUIClient();
    if (!client) {
      return;
    }

    const unsubUpdate = client.onDashboardUpdate(dashboardNodeId, handleUpdate);
    const unsubSubscribed = client.onDashboardSubscribed(
      dashboardNodeId,
      handleSubscribed
    );
    client.subscribeToDashboard(dashboardNodeId, canvasId);

    cleanupRef.current = () => {
      unsubUpdate();
      unsubSubscribed();
      client.unsubscribeFromDashboard(dashboardNodeId);
    };

    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
      setStats(initialStats);
      setExternalState(initialExternalState);
    };
  }, [dashboardNodeId, canvasId, enabled, handleUpdate, handleSubscribed]);

  return {
    stats,
    isConnected: stats.isSubscribed,
    lastUpdate: stats.lastUpdateTime,
    recentChanges: stats.recentChanges,
    externalState,
    _handleUpdate: handleUpdate,
    _handleSubscribed: handleSubscribed,
  };
}
