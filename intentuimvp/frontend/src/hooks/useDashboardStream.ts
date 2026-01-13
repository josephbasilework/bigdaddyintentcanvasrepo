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
  },
  recentChanges: [],
  isSubscribed: false,
  lastUpdateTime: null,
  activeSubscriptions: [],
};

export function useDashboardStream(
  dashboardNodeId: number | null,
  canvasId: number | null,
  enabled = true
) {
  const [stats, setStats] = useState<DashboardStreamStats>(initialStats);
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
      setStats((prev) => ({ ...prev, isSubscribed: false }));
    };
  }, [dashboardNodeId, canvasId, enabled, handleUpdate, handleSubscribed]);

  useEffect(() => {
    if (!enabled) {
      // Reset stats when stream is disabled
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setStats(initialStats);
    }
  }, [enabled]);

  return {
    stats,
    isConnected: stats.isSubscribed,
    lastUpdate: stats.lastUpdateTime,
    recentChanges: stats.recentChanges,
    _handleUpdate: handleUpdate,
    _handleSubscribed: handleSubscribed,
  };
}
