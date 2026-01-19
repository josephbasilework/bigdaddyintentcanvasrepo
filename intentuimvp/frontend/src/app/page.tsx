"use client";

import { Canvas, CanvasWorkspace } from "@/components/Canvas";
import {
  FloatingInput,
  type VoiceRecordingPayload,
} from "@/components/ContextInput/FloatingInput";
import { ChatViewPanel } from "@/components/ChatView";
import { EventsViewPanel } from "@/components/EventsView";
import { HooksPanel } from "@/components/Hooks";
import { NotificationToasts, NotificationsPanel } from "@/components/Notifications";
import { WheelViewPanel } from "@/components/WheelView";
import { MCPInstallPanel } from "@/components/MCP";
import { IntentMemoryPanel } from "@/components/IntentMemory";
import { AssumptionsPanel } from "@/components/Assumptions";
import {
  canExecuteProposal,
  deriveProposalStage,
  getAssumptionCounts,
} from "@/components/Assumptions/stateMachine";
import { OfflineQueuePanel } from "@/components/OfflineQueue/OfflineQueuePanel";
import { ContextPreviewPanel } from "@/components/ContextPreview";
import type {
  Assumption,
  AssumptionSet,
  IntentWorkflowRound,
} from "@/components/Assumptions";
import {
  useCanvasStore,
  type CanvasEdgeRelationType,
  type CanvasNode,
  type JobData,
} from "@/state/canvasStore";
import { useConversationStore } from "@/state/conversationStore";
import { useViewFiltersStore } from "@/state/viewFiltersStore";
import { useNotificationsStore } from "@/state/notificationsStore";
import { useEffect, useState, useCallback, useMemo } from "react";
import { useChatTurns } from "@/hooks/useChatTurns";
import { useTurns } from "@/hooks/useTurns";
import { useContextPreview } from "@/hooks/useContextPreview";
import { useOfflineQueueReplay } from "@/hooks/useOfflineQueueReplay";
import { useWebSocketEnhanced, type WebSocketMessage } from "@/hooks/useWebSocketEnhanced";
import { createAGUIClient } from "@/agui/client";
import type { NodeContext, SelectionScope } from "@/types/contextPreview";
import {
  type AttachmentItem,
  type AttachmentListResponse,
  normalizeAttachment,
} from "@/lib/attachments";
import {
  createOfflineQueueId,
  shouldQueueOfflineRequest,
  type OfflineRequestData,
  useOfflineQueueStore,
} from "@/state/offlineQueueStore";
import { setLastSyncedTurnSequence } from "@/utils/turnSequence";
import { buildNodeContextFromNode, resolveNodeTypeId } from "@/nodeTypes";
import { normalizeEdgeRelationType } from "@/components/Canvas/edgeRelations";
import {
  buildHierarchyIndex,
  getDescendantIds,
  isContainerNode,
} from "@/utils/canvasHierarchy";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Derive WebSocket URL from API base URL
const getWebSocketUrl = (): string => {
  const url = new URL(API_BASE_URL);
  const protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${url.host}/ws`;
};
const WS_URL = getWebSocketUrl();

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

type CommandSubmissionLog = {
  id: string;
  text: string;
  attachments: AttachmentItem[];
};

type WorkflowRound = IntentWorkflowRound & {
  selection: SelectionScope;
};

const getSelectionIds = (
  selectedNodeIds: string[],
  selectedNodeId: string | null
): string[] => {
  if (selectedNodeIds.length > 0) {
    return selectedNodeIds;
  }
  return selectedNodeId ? [selectedNodeId] : [];
};

const getSelectionScopeItems = (
  selectionIds: string[],
  nodes: CanvasNode[]
): Array<{ id: string; label: string; hasContent?: boolean }> => {
  if (selectionIds.length === 0) {
    return [];
  }
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  return selectionIds.map((id) => {
    const node = nodeById.get(id);
    return {
      id,
      label: node?.title ?? "Unknown node",
      hasContent: Boolean(node?.content),
    };
  });
};

/**
 * Build node context array from selected nodes.
 * Includes node content for contextual conversation with agent.
 */
const buildNodeContext = (
  selectionIds: string[],
  nodes: CanvasNode[]
): NodeContext[] => {
  if (selectionIds.length === 0) {
    return [];
  }
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const hierarchyIndex = buildHierarchyIndex(nodes);
  const expandedIds: string[] = [];
  const seen = new Set<string>();
  const pushId = (id: string) => {
    if (seen.has(id)) return;
    seen.add(id);
    expandedIds.push(id);
  };

  selectionIds.forEach((id) => {
    pushId(id);
    const node = nodeById.get(id);
    if (node && isContainerNode(node)) {
      getDescendantIds(id, hierarchyIndex).forEach((childId) => pushId(childId));
    }
  });

  return expandedIds
    .map((id) => {
      const node = nodeById.get(id);
      if (!node) return null;
      return buildNodeContextFromNode(node);
    })
    .filter((ctx): ctx is NodeContext => ctx !== null);
};

type AssumptionResponse = {
  id: string;
  text: string;
  confidence: number;
  category: string;
  explanation?: string | null;
  status?: "pending" | "accepted" | "rejected" | null;
};

type ProposalResponse = {
  action: string;
  confidence: number;
  alternatives: Array<{
    name: string;
    confidence: number;
    description: string;
  }>;
  assumptions: AssumptionResponse[];
};

type AssumptionSetResponse = {
  intent: string;
  intent_description?: string | null;
  confidence: number;
  alternatives: Array<{
    name: string;
    confidence: number;
    description: string;
  }>;
  assumptions: AssumptionResponse[];
  reasoning: string;
  should_auto_execute: boolean;
  session_id?: string | null;
  clarifying_questions?: string[] | null;
  proposal?: ProposalResponse | null;
};

type AssumptionResolutionPayload = {
  assumption_id: string;
  action: "accept" | "reject" | "edit";
  edited_text?: string | null;
  original_text?: string | null;
  category?: string | null;
};

type AssumptionResolutionBatch = {
  session_id?: string | null;
  resolutions: AssumptionResolutionPayload[];
};

const normalizeCategory = (category: string): Assumption["category"] => {
  switch (category) {
    case "context":
    case "intent":
    case "parameter":
    case "other":
      return category;
    default:
      return "other";
  }
};

const normalizeStatus = (
  status?: string | null
): Assumption["status"] => {
  switch (status) {
    case "accepted":
    case "rejected":
    case "pending":
      return status;
    default:
      return "pending";
  }
};

const mapAssumptionResponse = (assumption: AssumptionResponse): Assumption => ({
  id: assumption.id,
  originalText: assumption.text,
  text: assumption.text,
  confidence: assumption.confidence,
  category: normalizeCategory(assumption.category),
  status: normalizeStatus(assumption.status),
  explanation: assumption.explanation ?? undefined,
});

const createRoundId = (): string => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `round-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const buildClarifyingQuestions = (
  assumptionData: AssumptionSetResponse
): string[] => {
  const proposalAssumptions =
    assumptionData.proposal?.assumptions ?? assumptionData.assumptions;
  const proposalAlternatives =
    assumptionData.proposal?.alternatives ?? assumptionData.alternatives;
  if (
    assumptionData.clarifying_questions &&
    assumptionData.clarifying_questions.length > 0
  ) {
    return assumptionData.clarifying_questions;
  }
  if (proposalAssumptions.length > 0 || assumptionData.should_auto_execute) {
    return [];
  }
  if (proposalAlternatives.length > 0) {
    return ["Which of these intents best matches your goal?"];
  }
  return ["Can you clarify what you want to accomplish?"];
};

const createWorkflowRound = (
  assumptionData: AssumptionSetResponse,
  commandText: string,
  attachments: AttachmentItem[],
  selection: SelectionScope,
  options: { force?: boolean } = {}
): WorkflowRound | null => {
  const proposal = assumptionData.proposal ?? null;
  const proposalAction = proposal?.action ?? assumptionData.intent;
  const proposalConfidence = proposal?.confidence ?? assumptionData.confidence;
  const proposalAlternatives = proposal?.alternatives ?? assumptionData.alternatives ?? [];
  const proposalAssumptions = proposal?.assumptions ?? assumptionData.assumptions ?? [];
  const mappedAssumptions = proposalAssumptions.map(mapAssumptionResponse);
  const clarifyingQuestions = buildClarifyingQuestions(assumptionData);
  const shouldCreate =
    options.force || mappedAssumptions.length > 0 || clarifyingQuestions.length > 0;

  if (!shouldCreate) {
    return null;
  }

  const assumptionSet: AssumptionSet = {
    intent: proposalAction,
    action: proposalAction,
    intentDescription: assumptionData.intent_description ?? undefined,
    confidence: proposalConfidence,
    reasoning: assumptionData.reasoning,
    alternatives: proposalAlternatives,
    sessionId: assumptionData.session_id ?? undefined,
  };

  return {
    id: assumptionData.session_id ?? createRoundId(),
    createdAt: new Date().toISOString(),
    commandText,
    attachments,
    selection,
    assumptions: mappedAssumptions,
    assumptionSet,
    clarifyingQuestions,
    status: "reviewing",
  };
};

const buildRevisionPrompt = (round: WorkflowRound, note?: string): string => {
  const lines: string[] = [
    "Please revise the proposal and assumptions based on the feedback below.",
    "",
    `Original request: ${round.commandText}`,
  ];

  if (round.assumptionSet?.intent) {
    lines.push(
      `Current proposal: ${round.assumptionSet.action ?? round.assumptionSet.intent}`
    );
  }
  if (round.assumptionSet?.intentDescription) {
    lines.push(`Proposal details: ${round.assumptionSet.intentDescription}`);
  }

  if (round.assumptions.length > 0) {
    lines.push("", "Assumption feedback:");
    for (const assumption of round.assumptions) {
      const normalizedText = assumption.text.trim();
      const normalizedOriginal = assumption.originalText.trim();
      if (
        assumption.status === "accepted" &&
        normalizedText !== normalizedOriginal
      ) {
        lines.push(`- edited: \"${normalizedOriginal}\" -> \"${normalizedText}\"`);
        continue;
      }
      lines.push(`- ${assumption.status}: ${normalizedText}`);
    }
  }

  if (note) {
    lines.push("", `User clarification: ${note}`);
  }

  lines.push("", "Return an updated proposal with any remaining assumptions.");
  return lines.join("\n");
};

const buildAssumptionResolutions = (
  assumptions: Assumption[]
): AssumptionResolutionPayload[] =>
  assumptions
    .filter((assumption) => assumption.status !== "pending")
    .map((assumption) => {
      const normalizedText = assumption.text.trim();
      const normalizedOriginal = assumption.originalText.trim();
      const isEdited = normalizedText !== normalizedOriginal;
      const base = {
        assumption_id: assumption.id,
        original_text: assumption.originalText,
        category: assumption.category,
      };

      if (assumption.status === "rejected") {
        return { ...base, action: "reject" };
      }

      if (isEdited) {
        return {
          ...base,
          action: "edit",
          edited_text: normalizedText,
        };
      }

      return { ...base, action: "accept" };
    });

const persistAssumptionResolutions = async (
  payload: AssumptionResolutionBatch
): Promise<void> => {
  if (payload.resolutions.length === 0) {
    return;
  }

  const response = await fetch(`${API_BASE_URL}/api/context/assumptions/batch-resolve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(
      `Assumption resolution error: ${response.status} ${response.statusText}`
    );
  }
};

const completeAssumptionSession = async (
  sessionId?: string | null
): Promise<void> => {
  if (!sessionId) {
    return;
  }

  const response = await fetch(
    `${API_BASE_URL}/api/context/sessions/${sessionId}/complete`,
    {
      method: "POST",
    }
  );

  if (!response.ok) {
    throw new Error(
      `Assumption session completion error: ${response.status} ${response.statusText}`
    );
  }
};

export default function Home() {
  const [commands, setCommands] = useState<CommandSubmissionLog[]>([]);
  const [workflowRounds, setWorkflowRounds] = useState<WorkflowRound[]>([]);
  const [activeRoundId, setActiveRoundId] = useState<string | null>(null);
  const [routingError, setRoutingError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState("Ready for commands.");
  const [attachments, setAttachments] = useState<AttachmentItem[]>([]);
  const [draftCommand, setDraftCommand] = useState("");
  const [activeView, setActiveView] = useState<
    | "chat"
    | "wheel"
    | "events"
    | "mcp"
    | "context"
    | "hooks"
    | "memory"
    | "notifications"
    | null
  >(null);
  const canvasId = useCanvasStore((state) => state.canvasId);
  const nodes = useCanvasStore((state) => state.nodes);
  const edges = useCanvasStore((state) => state.edges);
  const addNode = useCanvasStore((state) => state.addNode);
  const addEdge = useCanvasStore((state) => state.addEdge);
  const removeNode = useCanvasStore((state) => state.removeNode);
  const updateEdge = useCanvasStore((state) => state.updateEdge);
  const removeEdge = useCanvasStore((state) => state.removeEdge);
  const updateNodePosition = useCanvasStore((state) => state.updateNodePosition);
  const updateNode = useCanvasStore((state) => state.updateNode);
  const selectNode = useCanvasStore((state) => state.selectNode);
  const clearSelection = useCanvasStore((state) => state.clearSelection);
  const selectedNodeId = useCanvasStore((state) => state.selectedNodeId);
  const selectedNodeIds = useCanvasStore((state) => state.selectedNodeIds);
  const conversationScope = useConversationStore((state) => state.scope);
  const setNodeScope = useConversationStore((state) => state.setNodeScope);
  const setGlobalScope = useConversationStore((state) => state.setGlobalScope);
  const enqueueNotificationToast = useNotificationsStore(
    (state) => state.enqueueToastFromPayload
  );
  const selectionIds = useMemo(
    () => getSelectionIds(selectedNodeIds, selectedNodeId),
    [selectedNodeIds, selectedNodeId]
  );
  const selectionItems = useMemo(
    () => getSelectionScopeItems(selectionIds, nodes),
    [selectionIds, nodes]
  );
  const nodeContext = useMemo(
    () => buildNodeContext(selectionIds, nodes),
    [selectionIds, nodes]
  );
  const selectionScope = useMemo<SelectionScope>(
    () => ({
      selected_nodes: selectionIds,
      selected_edges: [],
      node_context: nodeContext.length > 0 ? nodeContext : undefined,
      primary_node_id: selectedNodeId ?? undefined,
    }),
    [selectionIds, nodeContext, selectedNodeId]
  );
  const previewAttachmentIds = useMemo(
    () => attachments.filter((item) => item.status === "ready").map((item) => item.id),
    [attachments]
  );

  // Sync conversation scope with primary selected node
  useEffect(() => {
    if (selectedNodeId) {
      const node = nodes.find((n) => n.id === selectedNodeId);
      if (node) {
        setNodeScope(node.id, node.title, Boolean(node.content));
      }
    } else {
      setGlobalScope();
    }
  }, [selectedNodeId, nodes, setNodeScope, setGlobalScope]);

  // Handler to clear node context (also clears selection)
  const handleClearContext = useCallback(() => {
    clearSelection();
    setGlobalScope();
  }, [clearSelection, setGlobalScope]);

  const currentRound = useMemo(() => {
    if (!activeRoundId) {
      return null;
    }
    return workflowRounds.find((round) => round.id === activeRoundId) ?? null;
  }, [activeRoundId, workflowRounds]);

  const previousRounds = useMemo(() => {
    if (!activeRoundId) {
      return workflowRounds;
    }
    return workflowRounds.filter((round) => round.id !== activeRoundId);
  }, [activeRoundId, workflowRounds]);

  // Handle WebSocket messages for real-time node updates from backend
  const handleWebSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      const asRecord = (value: unknown): Record<string, unknown> =>
        value && typeof value === "object" ? (value as Record<string, unknown>) : {};
      const isRecord = (value: unknown): value is Record<string, unknown> =>
        Boolean(value && typeof value === "object" && !Array.isArray(value));

      const asId = (value: unknown): string | null => {
        if (typeof value === "string") {
          const trimmed = value.trim();
          return trimmed.length > 0 ? trimmed : null;
        }
        if (typeof value === "number" && Number.isFinite(value)) {
          return String(value);
        }
        return null;
      };

      const asNumber = (value: unknown): number | null => {
        if (typeof value === "number" && Number.isFinite(value)) {
          return value;
        }
        if (typeof value === "string") {
          const parsed = Number(value);
          return Number.isFinite(parsed) ? parsed : null;
        }
        return null;
      };

      const resolvePosition = (value: Record<string, unknown>) => {
        const position = asRecord(value.position);
        return {
          x: asNumber(value.x ?? position.x),
          y: asNumber(value.y ?? position.y),
          z: asNumber(value.z ?? position.z),
        };
      };

      const formatJobTypeLabel = (value: string) =>
        value
          .replace(/_/g, " ")
          .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
          .replace(/\s+/g, " ")
          .trim()
          .replace(/\b\w/g, (char) => char.toUpperCase());

      const getJobDescriptor = (payload: Record<string, unknown>): string | null => {
        const data = asRecord(payload.data);
        const candidate =
          data.query ??
          data.topic ??
          data.goal ??
          data.source_job_id ??
          data.sourceJobId;
        return typeof candidate === "string" && candidate.trim().length > 0
          ? candidate.trim()
          : null;
      };

      const findJobNode = (jobId: string): CanvasNode | undefined =>
        nodes.find((node) => {
          if (node.type !== "job") return false;
          if (node.jobData?.jobId === jobId) return true;
          const metadataJobId =
            typeof node.metadata?.jobId === "string"
              ? node.metadata.jobId
              : typeof node.metadata?.job_id === "string"
                ? node.metadata.job_id
                : null;
          return metadataJobId === jobId;
        });

      const resolveJobNodePosition = (): { x: number; y: number; z: number } => {
        const anchor =
          selectedNodeId !== null
            ? nodes.find((node) => node.id === selectedNodeId)
            : null;
        if (anchor) {
          return { x: anchor.x + 340, y: anchor.y, z: anchor.z };
        }
        const jobCount = nodes.filter((node) => node.type === "job").length;
        return { x: 120, y: 80 + jobCount * 200, z: 0 };
      };

      if (message.type === "notification") {
        if (isRecord(message.payload)) {
          enqueueNotificationToast(message.payload);
        }
        return;
      }

      if (message.type === "job.progress" && message.payload) {
        const payload = asRecord(message.payload);
        const jobId = asId(payload.job_id ?? payload.jobId);
        if (!jobId) {
          console.warn("DEBUG: job.progress missing job_id:", payload);
          return;
        }
        const jobType =
          (payload.job_type as string | undefined) ??
          (payload.jobType as string | undefined) ??
          "unknown";
        const status =
          (payload.status as string | undefined) ??
          "queued";
        const progressRaw =
          asNumber(payload.progress_percent ?? payload.progressPercent) ?? 0;
        const progressPercent = Math.min(100, Math.max(0, progressRaw));
        const currentStep =
          typeof payload.current_step === "string"
            ? payload.current_step
            : typeof payload.currentStep === "string"
              ? payload.currentStep
              : undefined;
        const stepNumber = asNumber(payload.step_number ?? payload.stepNumber) ?? undefined;
        const stepsTotal = asNumber(payload.steps_total ?? payload.stepsTotal) ?? undefined;
        const data = isRecord(payload.data) ? payload.data : undefined;

        const jobData: JobData = {
          jobId,
          jobType,
          status,
          progressPercent,
          ...(currentStep ? { currentStep } : {}),
          ...(stepNumber !== undefined ? { stepNumber } : {}),
          ...(stepsTotal !== undefined ? { stepsTotal } : {}),
          ...(data ? { data } : {}),
        };

        const existingNode = findJobNode(jobId);
        if (existingNode) {
          updateNode(
            existingNode.id,
            { jobData },
            { source: "remote", log: false, recordHistory: false }
          );
          return;
        }

        const descriptor = getJobDescriptor(payload);
        const titleBase = formatJobTypeLabel(jobType);
        const title = descriptor ? `${titleBase}: ${descriptor}` : `${titleBase} job`;
        const position = resolveJobNodePosition();
        addNode(
          {
            id: `job-${jobId}`,
            type: "job",
            x: position.x,
            y: position.y,
            z: position.z,
            title,
            jobData,
            metadata: {
              jobId,
              jobType,
            },
          },
          { source: "remote", log: false }
        );
        return;
      }

      if (message.type === "node.created" && message.payload) {
        const payload = asRecord(message.payload);
        const nodePayload = asRecord(payload.node ?? payload);
        const position = resolvePosition(nodePayload);
        const nodeId = asId(nodePayload.id ?? payload.id);
        if (!nodeId) {
          console.warn("DEBUG: node.created missing id:", nodePayload);
          return;
        }
        const title =
          (nodePayload.title as string | undefined) ??
          (nodePayload.label as string | undefined) ??
          (nodePayload.content as string | undefined) ??
          "Untitled";
        const nodeType =
          (nodePayload.type as string | undefined) ??
          (payload.type as string | undefined) ??
          "text";
        const resolvedType = resolveNodeTypeId(nodeType);
        const metadata =
          (nodePayload.metadata as Record<string, unknown> | undefined) ??
          (nodePayload.node_metadata as Record<string, unknown> | undefined) ??
          (nodePayload.nodeMetadata as Record<string, unknown> | undefined);
        const content =
          (nodePayload.content as string | undefined) ??
          (metadata?.content as string | undefined);
        console.log("DEBUG: Received node.created from backend:", nodePayload);
        // Check if node already exists (to avoid duplicates from local creation)
        const existingNode = nodes.find((n) => n.id === nodeId);
        if (!existingNode) {
          addNode(
            {
              id: nodeId,
              type: resolvedType,
              x: position.x ?? 0,
              y: position.y ?? 0,
              z: position.z ?? 0,
              title,
              content,
              metadata,
            },
            { source: "remote" }
          );
          console.log("DEBUG: Added backend-created node:", nodeId);
          if (!selectedNodeId && selectedNodeIds.length === 0) {
            selectNode(nodeId);
          }
        } else {
          console.log("DEBUG: Node already exists, skipping:", nodeId);
        }
      }
      if (message.type === "node.updated" && message.payload) {
        const payload = asRecord(message.payload);
        const nodePayload = asRecord(payload.node ?? payload);
        const payloadUpdates = asRecord(payload.updates);
        let nodeId = asId(nodePayload.id ?? payload.id);
        let targetNode = nodeId ? nodes.find((node) => node.id === nodeId) : null;
        const previous = asRecord(payload.previous);
        const previousX = asNumber(previous.x);
        const previousY = asNumber(previous.y);
        const previousZ = asNumber(previous.z);
        if (!targetNode && previousX !== null && previousY !== null) {
          targetNode = nodes.find((node) =>
            node.x === previousX &&
            node.y === previousY &&
            (previousZ === null || node.z === previousZ)
          );
          if (targetNode && !nodeId) {
            nodeId = targetNode.id;
          }
        }
        if (!targetNode || !nodeId) {
          console.warn("DEBUG: node.updated for missing node:", nodeId ?? "unknown");
          return;
        }
        const position = resolvePosition({ ...nodePayload, ...payloadUpdates });
        if (position.x !== null && position.y !== null) {
          updateNodePosition(
            nodeId,
            position.x,
            position.y,
            position.z ?? undefined,
            { source: "remote" }
          );
        }
        const updates: Partial<CanvasNode> = {};
        const nextType =
          (nodePayload.type as string | undefined) ??
          (payloadUpdates.type as string | undefined) ??
          (payload.type as string | undefined);
        if (nextType !== undefined) {
          updates.type = resolveNodeTypeId(nextType, targetNode.type);
        }
        const nextTitle =
          (nodePayload.title as string | undefined) ??
          (nodePayload.label as string | undefined) ??
          (payloadUpdates.label as string | undefined) ??
          (payloadUpdates.content as string | undefined) ??
          (payload.title as string | undefined);
        if (nextTitle !== undefined) updates.title = nextTitle;
        const nextContent =
          (nodePayload.content as string | undefined) ??
          (payloadUpdates.content as string | undefined) ??
          (payload.content as string | undefined);
        if (nextContent !== undefined) updates.content = nextContent;
        const nextMetadata =
          (nodePayload.metadata as Record<string, unknown> | undefined) ??
          (payloadUpdates.metadata as Record<string, unknown> | undefined) ??
          (payload.metadata as Record<string, unknown> | undefined);
        if (nextMetadata !== undefined) updates.metadata = nextMetadata;
        if (Object.keys(updates).length > 0) {
          updateNode(nodeId, updates, { source: "remote" });
        }
      }
      if (message.type === "node.deleted" && message.payload) {
        const payload = asRecord(message.payload);
        const nodePayload = asRecord(payload.node ?? payload);
        const nodeId = asId(nodePayload.id ?? payload.id);
        if (!nodeId) {
          console.warn("DEBUG: node.deleted missing id:", nodePayload);
          return;
        }
        removeNode(nodeId, { source: "remote" });
      }
      if (message.type === "edge.created" && message.payload) {
        const payload = asRecord(message.payload);
        const edgePayload = asRecord(payload.edge ?? payload);
        const edgeId = asId(edgePayload.id ?? payload.id);
        if (!edgeId) {
          console.warn("DEBUG: edge.created missing id:", edgePayload);
          return;
        }
        if (edges.some((edge) => edge.id === edgeId)) {
          return;
        }
        const sourceId =
          edgePayload.fromNodeId ??
          edgePayload.from_node_id ??
          edgePayload.sourceNodeId ??
          payload.fromNodeId ??
          payload.from_node_id ??
          payload.sourceNodeId;
        const targetId =
          edgePayload.toNodeId ??
          edgePayload.to_node_id ??
          edgePayload.targetNodeId ??
          payload.toNodeId ??
          payload.to_node_id ??
          payload.targetNodeId;
        if (!sourceId || !targetId) {
          console.warn("DEBUG: edge.created missing node IDs:", edgePayload);
          return;
        }
        const relationType =
          edgePayload.relationType ??
          edgePayload.relation_type ??
          payload.relationType ??
          payload.relation_type;
        const normalizedRelation = normalizeEdgeRelationType(
          relationType as CanvasEdgeRelationType | string | null | undefined
        );
        addEdge(
          {
            id: edgeId,
            sourceNodeId: String(sourceId),
            targetNodeId: String(targetId),
            relationType: normalizedRelation ?? undefined,
            label: (edgePayload.label as string | undefined) ?? (payload.label as string | undefined),
          },
          { source: "remote" }
        );
      }
      if (message.type === "edge.updated" && message.payload) {
        const payload = asRecord(message.payload);
        const edgePayload = asRecord(payload.edge ?? payload);
        const edgeId = asId(edgePayload.id ?? payload.id);
        if (!edgeId) {
          console.warn("DEBUG: edge.updated missing id:", edgePayload);
          return;
        }
        const relationType =
          edgePayload.relationType ??
          edgePayload.relation_type ??
          payload.relationType ??
          payload.relation_type;
        const normalizedRelation = normalizeEdgeRelationType(
          relationType as CanvasEdgeRelationType | string | null | undefined
        );
        const label =
          (edgePayload.label as string | undefined) ?? (payload.label as string | undefined);
        const updates: { relationType?: CanvasEdgeRelationType; label?: string } = {};
        if (normalizedRelation) {
          updates.relationType = normalizedRelation;
        }
        if (label !== undefined) {
          updates.label = label;
        }
        if (Object.keys(updates).length > 0) {
          updateEdge(edgeId, updates, { source: "remote" });
        }
      }
      if (message.type === "edge.deleted" && message.payload) {
        const payload = asRecord(message.payload);
        const edgePayload = asRecord(payload.edge ?? payload);
        const edgeId = asId(edgePayload.id ?? payload.id);
        if (!edgeId) {
          console.warn("DEBUG: edge.deleted missing id:", edgePayload);
          return;
        }
        removeEdge(edgeId, { source: "remote" });
      }
    },
    [
      nodes,
      edges,
      addNode,
      addEdge,
      removeNode,
      updateEdge,
      removeEdge,
      updateNodePosition,
      updateNode,
      selectNode,
      selectedNodeId,
      selectedNodeIds,
      enqueueNotificationToast,
    ]
  );

  // Connect to WebSocket for real-time updates
  const {
    sessionId: wsSessionId,
    connectionState: wsConnectionState,
  } = useWebSocketEnhanced({
    url: WS_URL,
    onMessage: handleWebSocketMessage,
  });

  const queuedEvents = useOfflineQueueStore((state) => state.queue);
  const updateQueuedEvent = useOfflineQueueStore((state) => state.updateQueuedEvent);
  const deleteQueuedEvent = useOfflineQueueStore((state) => state.deleteQueuedEvent);
  const isFlushingQueue = useOfflineQueueStore((state) => state.isFlushingQueue);
  const lastFlushedEventCount = useOfflineQueueStore(
    (state) => state.lastFlushedEventCount
  );

  useEffect(() => {
    useOfflineQueueStore.getState().setConnectionState(wsConnectionState);
  }, [wsConnectionState]);

  useEffect(() => {
    useOfflineQueueStore.getState().setSessionId(wsSessionId ?? null);
  }, [wsSessionId]);

  useOfflineQueueReplay({
    sessionId: wsSessionId ?? null,
    connectionState: wsConnectionState,
  });

  const aguiGatewayUrl = useMemo(() => {
    if (!WS_URL) {
      return "";
    }
    return wsSessionId
      ? `${WS_URL}?session_id=${encodeURIComponent(wsSessionId)}`
      : WS_URL;
  }, [wsSessionId]);

  const aguiClient = useMemo(() => {
    if (!aguiGatewayUrl) {
      return null;
    }
    return createAGUIClient({ gatewayUrl: aguiGatewayUrl });
  }, [aguiGatewayUrl]);

  useEffect(() => {
    if (!aguiClient) {
      return undefined;
    }
    aguiClient.connect();
    return () => {
      aguiClient.disconnect();
    };
  }, [aguiClient]);

  const chatSessionIds = useMemo(() => {
    const ids = new Set<string>();
    if (wsSessionId) {
      ids.add(wsSessionId);
    }
    for (const round of workflowRounds) {
      const sessionId = round.assumptionSet?.sessionId;
      if (sessionId) {
        ids.add(sessionId);
      }
    }
    return Array.from(ids);
  }, [wsSessionId, workflowRounds]);

  const isChatOpen = activeView === "chat";
  const isWheelOpen = activeView === "wheel";
  const isEventsOpen = activeView === "events";
  const isMcpOpen = activeView === "mcp";
  const isContextOpen = activeView === "context";
  const isHooksOpen = activeView === "hooks";
  const isMemoryOpen = activeView === "memory";
  const isNotificationsOpen = activeView === "notifications";

  const wheelFilters = useViewFiltersStore((state) => state.wheel);
  const eventsFilters = useViewFiltersStore((state) => state.events);
  const parsedEventNodeId = useMemo(() => {
    const trimmed = eventsFilters.nodeFilter.trim();
    if (!trimmed) {
      return null;
    }
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }, [eventsFilters.nodeFilter]);
  const wheelTurnFilters = useMemo(
    () => ({
      actorGroups: wheelFilters.actorFilters,
      categories:
        wheelFilters.typeFilter === "all" ? [] : [wheelFilters.typeFilter],
    }),
    [wheelFilters.actorFilters, wheelFilters.typeFilter]
  );
  const eventsTurnFilters = useMemo(
    () => ({
      actorGroups: eventsFilters.actorFilters,
      eventTypes: eventsFilters.typeFilters,
      relatedNodeId: parsedEventNodeId,
    }),
    [eventsFilters.actorFilters, eventsFilters.typeFilters, parsedEventNodeId]
  );

  const {
    turns: chatTurns,
    isLoading: isChatLoading,
    error: chatError,
  } = useChatTurns({
    sessionIds: chatSessionIds,
    enabled: isChatOpen,
  });

  const {
    turns: wheelTurns,
    isLoading: isWheelLoading,
    error: wheelError,
  } = useTurns({
    sessionIds: chatSessionIds,
    enabled: isWheelOpen,
    filters: wheelTurnFilters,
  });

  const {
    turns: eventsTurns,
    isLoading: isEventsLoading,
    error: eventsError,
  } = useTurns({
    sessionIds: chatSessionIds,
    enabled: isEventsOpen,
    filters: eventsTurnFilters,
  });

  const {
    preview: contextPreview,
    isLoading: isContextLoading,
    error: contextError,
    refresh: refreshContextPreview,
  } = useContextPreview({
    enabled: isContextOpen,
    text: draftCommand,
    attachments: previewAttachmentIds,
    selection: selectionScope,
    sessionId: wsSessionId,
  });

  useEffect(() => {
    if (routingError) {
      setStatusMessage(`Routing error: ${routingError}`);
      return;
    }
    if (currentRound) {
      const stage = deriveProposalStage(currentRound);
      if (stage === "clarifying") {
        setStatusMessage("Clarification needed.");
        return;
      }
      if (stage === "needs_resolution") {
        const { pending } = getAssumptionCounts(currentRound.assumptions);
        setStatusMessage(`${pending} assumptions need review.`);
        return;
      }
      if (stage === "needs_revision") {
        setStatusMessage("Proposal needs revision.");
        return;
      }
      if (stage === "ready") {
        setStatusMessage("Review the proposal.");
        return;
      }
    }
    if (commands.length > 0) {
      setStatusMessage("Command queued.");
      return;
    }
    setStatusMessage("Ready for commands.");
  }, [commands.length, currentRound, routingError]);

  useEffect(() => {
    if (!activeRoundId) {
      return;
    }
    if (!workflowRounds.some((round) => round.id === activeRoundId)) {
      setActiveRoundId(null);
    }
  }, [activeRoundId, workflowRounds]);

  const buildSourceKey = (file: File) =>
    `${file.name}-${file.size}-${file.lastModified}`;

  const revokePreviewUrl = (url?: string) => {
    if (url && url.startsWith("blob:")) {
      URL.revokeObjectURL(url);
    }
  };

  const uploadAttachments = async (files: File[]): Promise<AttachmentItem[]> => {
    const formData = new FormData();
    for (const file of files) {
      formData.append("files", file);
    }
    if (wsSessionId) {
      formData.append("session_id", wsSessionId);
    }
    const primaryNodeId = selectionScope.primary_node_id;
    if (primaryNodeId && /^\d+$/.test(primaryNodeId)) {
      formData.append("node_id", primaryNodeId);
    }

    const response = await fetch(`${API_BASE_URL}/api/attachments`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Attachment upload failed: ${response.status} ${response.statusText}`);
    }

    const data: AttachmentListResponse = await response.json();
    return data.attachments.map((attachment) =>
      normalizeAttachment(attachment, API_BASE_URL)
    );
  };

  const handleFilesDrop = async (files: File[]) => {
    if (files.length === 0) return;
    const existingKeys = new Set(attachments.map((item) => item.sourceKey));
    const uniqueFiles = files.filter(
      (file) => !existingKeys.has(buildSourceKey(file))
    );
    if (uniqueFiles.length === 0) return;

    const pending = uniqueFiles.map<AttachmentItem>((file) => ({
      id: `pending-${crypto.randomUUID()}`,
      name: file.name,
      mimeType: file.type || "application/octet-stream",
      sizeBytes: file.size,
      attachmentType: "upload",
      status: "processing",
      previewUrl: URL.createObjectURL(file),
      sourceKey: buildSourceKey(file),
    }));

    setAttachments((prev) => [...prev, ...pending]);
    setStatusMessage("Uploading attachments...");

    try {
      const uploaded = await uploadAttachments(uniqueFiles);
      const pendingKeys = new Set(pending.map((item) => item.sourceKey));
      pending.forEach((item) => revokePreviewUrl(item.previewUrl));
      setAttachments((prev) => [
        ...prev.filter((item) => !pendingKeys.has(item.sourceKey)),
        ...uploaded,
      ]);
      setStatusMessage("Attachments ready.");
    } catch (error) {
      const pendingKeys = new Set(pending.map((item) => item.sourceKey));
      setAttachments((prev) =>
        prev.map((item) => {
          if (!pendingKeys.has(item.sourceKey)) {
            return item;
          }
          return {
            ...item,
            status: "error",
            errorMessage:
              error instanceof Error ? error.message : "Attachment upload failed",
          };
        })
      );
      setRoutingError(error instanceof Error ? error.message : "Attachment upload failed");
    }
  };

  const handleRemoveAttachment = async (id: string) => {
    const removed = attachments.find((item) => item.id === id);
    if (removed) {
      revokePreviewUrl(removed.previewUrl);
    }
    setAttachments((prev) => prev.filter((item) => item.id !== id));
    if (removed && !removed.id.startsWith("pending-")) {
      try {
        await fetch(`${API_BASE_URL}/api/attachments/${removed.id}`, {
          method: "DELETE",
        });
      } catch (error) {
        console.warn("Failed to delete attachment:", error);
      }
    }
  };

  const updateRound = useCallback(
    (roundId: string, updater: (round: WorkflowRound) => WorkflowRound) => {
      setWorkflowRounds((prev) =>
        prev.map((round) => (round.id === roundId ? updater(round) : round))
      );
    },
    []
  );

  const extractSequenceNumber = (payload: unknown): number | null => {
    if (!payload || typeof payload !== "object") {
      return null;
    }
    const candidate = payload as { sequenceNumber?: unknown; sequence_number?: unknown };
    if (typeof candidate.sequenceNumber === "number") {
      return candidate.sequenceNumber;
    }
    if (typeof candidate.sequence_number === "number") {
      return candidate.sequence_number;
    }
    return null;
  };

  const queueCommand = async (
    value: string,
    attachmentsForSubmission: string[],
    attachmentsSnapshot: AttachmentItem[],
    selection: SelectionScope
  ) => {
    const clientRequestId = createOfflineQueueId();
    const sessionId = wsSessionId ?? undefined;
    const body = {
      command: value,
      attachments: attachmentsForSubmission,
      selection,
      session_id: sessionId,
      client_request_id: clientRequestId,
    };
    const request: OfflineRequestData = {
      url: `${API_BASE_URL}/api/commands`,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      kind: "command",
      sessionId: sessionId ?? "",
    };

    const offlineState = useOfflineQueueStore.getState();
    const isNavigatorOnline =
      typeof navigator === "undefined" ? true : navigator.onLine;
    const shouldQueue = !isNavigatorOnline || shouldQueueOfflineRequest(offlineState);

    const commitQueuedCommand = (id: string) => {
      setCommands((prev) => [
        ...prev,
        { id, text: value, attachments: attachmentsSnapshot },
      ]);
      setAttachments([]);
    };

    if (sessionId && shouldQueue) {
      offlineState.enqueue(request, { id: clientRequestId });
      commitQueuedCommand(clientRequestId);
      return;
    }

    let response: Response;
    try {
      response = await fetch(request.url, {
        method: request.method,
        headers: request.headers,
        body: JSON.stringify(body),
      });
    } catch (error) {
      if (sessionId) {
        useOfflineQueueStore.getState().enqueue(request, { id: clientRequestId });
        commitQueuedCommand(clientRequestId);
        return;
      }
      throw error;
    }

    if (!response.ok) {
      if (response.status >= 500 && sessionId) {
        useOfflineQueueStore.getState().enqueue(request, { id: clientRequestId });
        commitQueuedCommand(clientRequestId);
        return;
      }
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    const data: {
      correlation_id: string;
      status: string;
      sequenceNumber?: number;
      sequence_number?: number;
    } = await response.json();
    setCommands((prev) => [
      ...prev,
      { id: data.correlation_id, text: value, attachments: attachmentsSnapshot },
    ]);
    setAttachments([]);
    const sequenceNumber = extractSequenceNumber(data);
    if (sessionId && sequenceNumber !== null) {
      setLastSyncedTurnSequence(sessionId, sequenceNumber);
    }
    // Node creation is now handled by the backend via WebSocket broadcast
    // The handleWebSocketMessage callback will add the node when it receives "node.created"
  };

  const resolveVoiceNodePosition = useCallback(() => {
    const lastNode = nodes[nodes.length - 1];
    if (lastNode) {
      return {
        x: lastNode.x + 40,
        y: lastNode.y + 40,
        z: lastNode.z ?? 0,
      };
    }
    return { x: 60, y: 60, z: 0 };
  }, [nodes]);

  const handleVoiceRecordingComplete = useCallback(
    async (payload: VoiceRecordingPayload) => {
      if (!canvasId) {
        setRoutingError("Canvas not ready. Please reload and try again.");
        return;
      }
      setRoutingError(null);
      setStatusMessage("Saving voice note...");
      try {
        const audioData = await blobToBase64(payload.blob);
        const audioResponse = await fetch(`${API_BASE_URL}/api/audio/blocks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            canvas_id: canvasId,
            audio_data: audioData,
            duration: payload.durationMs / 1000,
          }),
        });
        if (!audioResponse.ok) {
          const errorText = await audioResponse.text();
          throw new Error(`Audio upload failed (${audioResponse.status}): ${errorText}`);
        }
        const audioBlock = (await audioResponse.json()) as {
          id: number;
          audioUri: string;
          duration: number | null;
          status: string;
          transcription?: string | null;
        };
        const transcript = payload.transcript.trim();
        const labelBase = transcript ? `Voice: ${transcript}` : "Voice note";
        const label =
          labelBase.length > 48
            ? `${labelBase.slice(0, 45).trimEnd()}...`
            : labelBase;
        const position = resolveVoiceNodePosition();
        const metadata = {
          audio: {
            blockId: audioBlock.id,
            uri: audioBlock.audioUri,
            duration: audioBlock.duration ?? payload.durationMs / 1000,
            status: audioBlock.status,
            transcription: transcript || audioBlock.transcription,
          },
        };

        const nodeResponse = await fetch(`${API_BASE_URL}/api/nodes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            canvas_id: canvasId,
            label,
            type: "audio",
            content: transcript || null,
            position,
            metadata,
          }),
        });
        if (!nodeResponse.ok) {
          const errorText = await nodeResponse.text();
          throw new Error(`Node creation failed (${nodeResponse.status}): ${errorText}`);
        }
        const nodePayload = (await nodeResponse.json()) as {
          id: number | string;
          type: string;
          label?: string;
          content?: string | null;
          position?: { x?: number; y?: number; z?: number };
          metadata?: Record<string, unknown>;
        };
        const nodeId = String(nodePayload.id);
        const resolvedType = resolveNodeTypeId(nodePayload.type, "audio");
        addNode(
          {
            id: nodeId,
            type: resolvedType,
            x: nodePayload.position?.x ?? position.x,
            y: nodePayload.position?.y ?? position.y,
            z: nodePayload.position?.z ?? position.z,
            title: nodePayload.label ?? label,
            content: nodePayload.content ?? transcript,
            metadata: nodePayload.metadata ?? metadata,
          },
          { source: "remote" }
        );
        selectNode(nodeId);
      } catch (error) {
        console.error("Voice recording save failed:", error);
        const message =
          error instanceof Error ? error.message : "Failed to save voice note.";
        setRoutingError(message);
      } finally {
        setStatusMessage("Ready for commands.");
      }
    },
    [addNode, canvasId, resolveVoiceNodePosition, selectNode]
  );

  const handleCommandSubmit = async (value: string) => {
    setRoutingError(null);
    const normalizedValue = value.trim().toLowerCase();
    if (normalizedValue === "close all panels") {
      setActiveView(null);
      setStatusMessage("Panels closed.");
      return;
    }
    const hasUploadsPending = attachments.some((item) =>
      ["pending", "processing"].includes(item.status)
    );
    if (hasUploadsPending) {
      setRoutingError("Attachments are still uploading. Please wait.");
      return;
    }
    const hasUploadErrors = attachments.some((item) => item.status === "error");
    if (hasUploadErrors) {
      setRoutingError("Remove failed attachments before submitting.");
      return;
    }

    const attachmentsSnapshot = attachments.filter((item) => item.status === "ready");
    const attachmentsForSubmission = attachmentsSnapshot.map((item) => item.id);
    const selection = selectionScope;

    // Clear selection immediately after capturing it for the command
    // This allows new nodes (created via WebSocket) to be auto-selected
    clearSelection();

    try {
      const assumptionResponse = await fetch(`${API_BASE_URL}/api/context/assumptions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: value,
          attachments: attachmentsForSubmission,
        }),
      });

      if (!assumptionResponse.ok) {
        throw new Error(
          `Assumptions API error: ${assumptionResponse.status} ${assumptionResponse.statusText}`
        );
      }

      const assumptionData: AssumptionSetResponse = await assumptionResponse.json();
      const nextRound = createWorkflowRound(
        assumptionData,
        value,
        attachmentsSnapshot,
        selection
      );

      if (nextRound) {
        setWorkflowRounds((prev) => [...prev, nextRound]);
        setActiveRoundId(nextRound.id);
        setAttachments([]);
        return;
      }
    } catch (error) {
      console.error("Assumptions check failed:", error);
    }

    try {
      await queueCommand(value, attachmentsForSubmission, attachmentsSnapshot, selection);
    } catch (error) {
      console.error("Routing failed:", error);
      setRoutingError(error instanceof Error ? error.message : "Unknown error");
    }
  };

  const handleAcceptAssumption = (id: string) => {
    if (!activeRoundId || currentRound?.status !== "reviewing") {
      return;
    }
    updateRound(activeRoundId, (round) => ({
      ...round,
      assumptions: round.assumptions.map((assumption) =>
        assumption.id === id
          ? { ...assumption, status: "accepted" as const }
          : assumption
      ),
    }));
  };

  const handleRejectAssumption = (id: string) => {
    if (!activeRoundId || currentRound?.status !== "reviewing") {
      return;
    }
    updateRound(activeRoundId, (round) => ({
      ...round,
      assumptions: round.assumptions.map((assumption) =>
        assumption.id === id
          ? { ...assumption, status: "rejected" as const }
          : assumption
      ),
    }));
  };

  const handleEditAssumption = (id: string, text: string) => {
    if (!activeRoundId || currentRound?.status !== "reviewing") {
      return;
    }
    updateRound(activeRoundId, (round) => ({
      ...round,
      assumptions: round.assumptions.map((assumption) =>
        assumption.id === id
          ? { ...assumption, text, status: "accepted" as const }
          : assumption
      ),
    }));
  };

  const handleConfirmAssumptions = async () => {
    if (!currentRound || currentRound.status !== "reviewing") {
      return;
    }
    if (!canExecuteProposal(currentRound)) {
      return;
    }
    const roundId = currentRound.id;
    const resolutions = buildAssumptionResolutions(currentRound.assumptions);

    try {
      await persistAssumptionResolutions({
        session_id: currentRound.assumptionSet?.sessionId ?? undefined,
        resolutions,
      });
    } catch (error) {
      console.error("Failed to store assumption resolutions:", error);
    }

    try {
      await completeAssumptionSession(currentRound.assumptionSet?.sessionId ?? undefined);
    } catch (error) {
      console.error("Failed to mark assumption session complete:", error);
    }

    updateRound(roundId, (round) => ({ ...round, status: "resolved" }));

    try {
      const attachmentsSnapshot = currentRound.attachments;
      const attachmentsForSubmission = attachmentsSnapshot.map((item) => item.id);
      await queueCommand(
        currentRound.commandText,
        attachmentsForSubmission,
        attachmentsSnapshot,
        currentRound.selection
      );
      updateRound(roundId, (round) => ({ ...round, status: "executed" }));
    } catch (error) {
      console.error("Routing failed:", error);
      setRoutingError(error instanceof Error ? error.message : "Unknown error");
    }
  };

  const requestFollowupRound = async (note?: string) => {
    if (!currentRound || currentRound.status !== "reviewing") {
      return;
    }
    setRoutingError(null);
    const resolutions = buildAssumptionResolutions(currentRound.assumptions);
    if (resolutions.length > 0) {
      try {
        await persistAssumptionResolutions({
          session_id: currentRound.assumptionSet?.sessionId ?? undefined,
          resolutions,
        });
      } catch (error) {
        console.error("Failed to store assumption revisions:", error);
      }
    }
    try {
      const attachmentIds = currentRound.attachments.map((attachment) => attachment.id);
      const response = await fetch(`${API_BASE_URL}/api/context/assumptions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text: buildRevisionPrompt(currentRound, note),
          attachments: attachmentIds,
        }),
      });

      if (!response.ok) {
        throw new Error(
          `Assumptions API error: ${response.status} ${response.statusText}`
        );
      }

      const assumptionData: AssumptionSetResponse = await response.json();
      const nextRound = createWorkflowRound(
        assumptionData,
        currentRound.commandText,
        currentRound.attachments,
        currentRound.selection,
        { force: true }
      );

      if (!nextRound) {
        return;
      }

      setWorkflowRounds((prev) =>
        prev
          .map((round) =>
            round.id === currentRound.id
              ? {
                  ...round,
                  status: "superseded" as const,
                  clarificationResponse: note ?? round.clarificationResponse,
                }
              : round
          )
          .concat(nextRound)
      );
      setActiveRoundId(nextRound.id);
    } catch (error) {
      console.error("Assumptions follow-up failed:", error);
      setRoutingError(error instanceof Error ? error.message : "Unknown error");
    }
  };

  const handleRequestRevision = () => {
    void requestFollowupRound();
  };

  const handleClarificationSubmit = (note: string) => {
    void requestFollowupRound(note);
  };

  const handleDismissAssumptions = () => {
    if (!activeRoundId) {
      return;
    }
    updateRound(activeRoundId, (round) => ({ ...round, status: "dismissed" }));
    setActiveRoundId(null);
  };

  const handleViewToggle = (
    view:
      | "chat"
      | "wheel"
      | "events"
      | "mcp"
      | "context"
      | "hooks"
      | "memory"
      | "notifications"
  ) => {
    setActiveView((prev) => (prev === view ? null : view));
  };

  const chatPanel = isChatOpen ? (
    <ChatViewPanel
      id="chat-view-panel"
      turns={chatTurns}
      isLoading={isChatLoading}
      error={chatError}
    />
  ) : null;

  const eventsPanel = isEventsOpen ? (
    <EventsViewPanel
      id="events-view-panel"
      turns={eventsTurns}
      isLoading={isEventsLoading}
      error={eventsError}
    />
  ) : null;

  const mcpPanel = isMcpOpen ? <MCPInstallPanel id="mcp-install-panel" /> : null;

  const contextPanel = isContextOpen ? (
    <ContextPreviewPanel
      id="context-preview-panel"
      preview={contextPreview}
      isLoading={isContextLoading}
      error={contextError}
      onRefresh={refreshContextPreview}
    />
  ) : null;

  const hooksPanel = isHooksOpen ? (
    <HooksPanel id="hooks-panel" />
  ) : null;

  const notificationsPanel = isNotificationsOpen ? (
    <NotificationsPanel id="notifications-panel" />
  ) : null;

  const memoryPanel = isMemoryOpen ? (
    <IntentMemoryPanel id="intent-memory-panel" />
  ) : null;

  const wheelPanel = isWheelOpen ? (
    <WheelViewPanel
      id="wheel-view-panel"
      turns={wheelTurns}
      isLoading={isWheelLoading}
      error={wheelError}
    />
  ) : null;

  const visiblePreviousRounds = previousRounds.filter(
    (round) => round.status !== "dismissed"
  );

  const workflowPanel =
    currentRound || visiblePreviousRounds.length > 0 ? (
      <AssumptionsPanel
        key={currentRound?.id ?? "intent-workflow"}
        id="intent-workflow-panel"
        currentRound={currentRound}
        previousRounds={visiblePreviousRounds}
        onAccept={handleAcceptAssumption}
        onReject={handleRejectAssumption}
        onEdit={handleEditAssumption}
        onConfirm={handleConfirmAssumptions}
        onDismiss={handleDismissAssumptions}
        onRequestRevision={handleRequestRevision}
        onClarificationSubmit={handleClarificationSubmit}
      />
    ) : null;

  const viewPanel = isChatOpen
    ? chatPanel
    : isMcpOpen
      ? mcpPanel
      : isContextOpen
        ? contextPanel
        : isMemoryOpen
          ? memoryPanel
        : isWheelOpen
          ? wheelPanel
          : isEventsOpen
          ? eventsPanel
          : isHooksOpen
            ? hooksPanel
            : isNotificationsOpen
              ? notificationsPanel
            : null;

  const panelContent =
    workflowPanel || viewPanel ? (
      <>
        {workflowPanel}
        {viewPanel}
      </>
    ) : null;

  return (
    <>
      <Canvas>
        <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
          {statusMessage}
        </div>
        <CanvasWorkspace />
        {commands.length > 0 && (
          <div style={{ position: "absolute", top: "20px", left: "20px", color: "#fff" }}>
            <h3>Commands:</h3>
            <ul>
              {commands.map((cmd) => (
                <li key={cmd.id}>
                  <div>{cmd.text}</div>
                  <div style={{ fontSize: "12px", color: "#cbd5f5" }}>
                    ID: {cmd.id}
                  </div>
                  {cmd.attachments.length > 0 && (
                    <div style={{ fontSize: "12px", color: "#94a3b8" }}>
                      Attachments: {cmd.attachments.map((item) => item.name).join(", ")}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
        {routingError && (
          <div
            style={{
              position: "absolute",
              bottom: "100px",
              left: "50%",
              transform: "translateX(-50%)",
              padding: "1rem",
              backgroundColor: "#7f1d1d",
              border: "1px solid #ef4444",
              borderRadius: "0.5rem",
              color: "#fecaca",
            }}
            role="alert"
            aria-live="assertive"
          >
            Error: {routingError}
          </div>
        )}
      </Canvas>
      <NotificationToasts />
      <OfflineQueuePanel
        connectionState={wsConnectionState}
        queuedEvents={queuedEvents}
        onUpdateEvent={updateQueuedEvent}
        onDeleteEvent={deleteQueuedEvent}
        isFlushingQueue={isFlushingQueue}
        lastFlushedEventCount={lastFlushedEventCount}
      />
      <FloatingInput
        onSubmit={handleCommandSubmit}
        onFilesDrop={handleFilesDrop}
        onValueChange={setDraftCommand}
        attachments={attachments}
        selection={selectionItems}
        onRemoveAttachment={handleRemoveAttachment}
        onClearSelection={clearSelection}
        placeholder="Type a command..."
        panelContent={panelContent}
        conversationScope={conversationScope}
        onClearContext={handleClearContext}
        onVoiceRecordingComplete={handleVoiceRecordingComplete}
        panelToggles={[
          {
            label: "Chat",
            isOpen: isChatOpen,
            onToggle: () => handleViewToggle("chat"),
            ariaControls: "chat-view-panel",
          },
          {
            label: "MCP",
            isOpen: isMcpOpen,
            onToggle: () => handleViewToggle("mcp"),
            ariaControls: "mcp-install-panel",
          },
          {
            label: "Context",
            isOpen: isContextOpen,
            onToggle: () => handleViewToggle("context"),
            ariaControls: "context-preview-panel",
          },
          {
            label: "Memory",
            isOpen: isMemoryOpen,
            onToggle: () => handleViewToggle("memory"),
            ariaControls: "intent-memory-panel",
          },
          {
            label: "Wheel",
            isOpen: isWheelOpen,
            onToggle: () => handleViewToggle("wheel"),
            ariaControls: "wheel-view-panel",
          },
          {
            label: "Events",
            isOpen: isEventsOpen,
            onToggle: () => handleViewToggle("events"),
            ariaControls: "events-view-panel",
          },
          {
            label: "Notifications",
            isOpen: isNotificationsOpen,
            onToggle: () => handleViewToggle("notifications"),
            ariaControls: "notifications-panel",
          },
          {
            label: "Hooks",
            isOpen: isHooksOpen,
            onToggle: () => handleViewToggle("hooks"),
            ariaControls: "hooks-panel",
          },
        ]}
      />
    </>
  );
}
