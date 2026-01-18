export type NodeContext = {
  id: string;
  title: string;
  node_type: string;
  content?: string;
  metadata?: Record<string, unknown>;
};

export type SelectionScope = {
  selected_nodes: string[];
  selected_edges: string[];
  node_context?: NodeContext[];
  primary_node_id?: string;
};

export type ContextPreviewNode = {
  id: string;
  title: string;
  node_type: string;
  score: number;
  reasons: string[];
  is_primary: boolean;
  similarity?: number | null;
  recency?: number | null;
  reason_scores?: Record<string, number> | null;
  content?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type ContextPreviewTurn = {
  id: number;
  sequence_number: number;
  summary: string;
  actor: string;
  turn_type: string;
  timestamp: string;
  score: number;
  reasons: string[];
  similarity?: number | null;
  recency?: number | null;
  reason_scores?: Record<string, number> | null;
};

export type ContextPreviewAttachment = {
  id: string;
  filename: string;
  attachment_type: string;
  mime_type: string;
  size_bytes: number;
  text_content?: string | null;
  transcription?: string | null;
  description?: string | null;
  status?: string | null;
};

export type ContextPreview = {
  input_text: string;
  prompt: string;
  nodes: ContextPreviewNode[];
  turns: ContextPreviewTurn[];
  attachments: ContextPreviewAttachment[];
  selection?: SelectionScope | null;
  explicit_node_refs: string[];
  explicit_turn_refs: number[];
};
