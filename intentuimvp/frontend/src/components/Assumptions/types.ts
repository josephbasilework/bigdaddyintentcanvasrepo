/** Types for assumptions extracted by agents. */

export interface Assumption {
  /** Unique identifier for this assumption */
  id: string;
  /** The assumption text extracted by the agent */
  text: string;
  /** Confidence score (0-1) for this assumption */
  confidence: number;
  /** The category/type of assumption (e.g., "context", "intent", "parameter") */
  category: "context" | "intent" | "parameter" | "other";
  /** Whether user has accepted, rejected, or not yet decided */
  status: "pending" | "accepted" | "rejected";
  /** Optional explanation of why this assumption was made */
  explanation?: string;
}

export interface AssumptionsPanelProps {
  /** Array of assumptions to display */
  assumptions: Assumption[];
  /** Callback when user accepts an assumption */
  onAccept: (id: string) => void;
  /** Callback when user rejects an assumption */
  onReject: (id: string) => void;
  /** Callback when user confirms all assumptions and proceeds */
  onConfirm: () => void;
  /** Optional callback to dismiss the panel */
  onDismiss?: () => void;
}
