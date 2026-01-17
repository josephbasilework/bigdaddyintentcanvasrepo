export type TurnResponse = {
  id: number;
  sessionId: string;
  sequenceNumber: number;
  timestamp: string;
  actor: string;
  type: string;
  summary: string;
  payload: Record<string, unknown>;
  relatedNodeId: number | null;
  relatedEdgeId: number | null;
};

export type TurnListResponse = {
  turns: TurnResponse[];
  count: number;
};
