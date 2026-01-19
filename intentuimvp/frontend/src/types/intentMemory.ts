export type IntentMemoryStats = {
  total: number;
  accepted: number;
  rejected: number;
  last_used_at?: string | null;
};

export type IntentMemoryEntry = {
  entry_id: string;
  scope: "user" | "workspace" | "session";
  kind: "explicit" | "implicit" | "confirmation";
  usage: "classification" | "routing" | "auto_confirm" | "note_suggestion";
  trigger: string;
  trigger_type: string;
  response?: unknown;
  confidence: number;
  enabled: boolean;
  workspace_id?: string | null;
  session_id?: string | null;
  created_at: string;
  updated_at: string;
  stats: IntentMemoryStats;
  description?: string | null;
};

export type IntentMemorySettings = {
  enabled: boolean;
  auto_classify_enabled: boolean;
  auto_confirm_enabled: boolean;
  suggestions_enabled: boolean;
  auto_classify_threshold: number;
  auto_confirm_threshold: number;
  auto_confirm_min_samples: number;
  auto_confirm_similarity_threshold: number;
  note_suggestion_threshold: number;
};
