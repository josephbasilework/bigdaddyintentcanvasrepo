/** Types for assumptions extracted by agents. */

export type AssumptionCategory = "context" | "intent" | "parameter" | "other";
export type AssumptionStatus = "pending" | "accepted" | "rejected";

export interface Assumption {
  /** Unique identifier for this assumption */
  id: string;
  /** Original assumption text received from the agent */
  originalText: string;
  /** The assumption text extracted by the agent */
  text: string;
  /** Confidence score (0-1) for this assumption */
  confidence: number;
  /** The category/type of assumption (e.g., "context", "intent", "parameter") */
  category: AssumptionCategory;
  /** Whether user has accepted, rejected, or not yet decided */
  status: AssumptionStatus;
  /** Optional explanation of why this assumption was made */
  explanation?: string;
}

export interface IntentAlternative {
  /** Name of the alternative intent */
  name: string;
  /** Confidence score (0-1) for this alternative */
  confidence: number;
  /** Short description of the alternative */
  description: string;
}

export interface AssumptionSet {
  /** Primary intent inferred by the agent */
  intent: string;
  /** Optional description for the primary intent */
  intentDescription?: string;
  /** Confidence score (0-1) for the primary intent */
  confidence: number;
  /** Reasoning provided by the agent */
  reasoning?: string;
  /** Alternative intents if ambiguity exists */
  alternatives?: IntentAlternative[];
  /** Optional session ID for tracking resolutions */
  sessionId?: string;
}

export type WorkflowRoundStatus =
  | "reviewing"
  | "resolved"
  | "executed"
  | "dismissed"
  | "superseded";

export interface IntentWorkflowRound {
  id: string;
  createdAt: string;
  commandText: string;
  attachments: string[];
  assumptions: Assumption[];
  assumptionSet?: AssumptionSet;
  clarifyingQuestions?: string[];
  clarificationResponse?: string;
  status: WorkflowRoundStatus;
}

export interface AssumptionsPanelProps {
  id?: string;
  currentRound: IntentWorkflowRound | null;
  previousRounds?: IntentWorkflowRound[];
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onEdit: (id: string, text: string) => void;
  onConfirm: () => void;
  onDismiss?: () => void;
  onRequestRevision?: () => void;
  onClarificationSubmit?: (response: string) => void;
}
