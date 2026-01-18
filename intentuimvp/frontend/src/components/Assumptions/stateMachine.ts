import type { Assumption, IntentWorkflowRound } from "./types";

export type ProposalStage =
  | "idle"
  | "clarifying"
  | "needs_resolution"
  | "needs_revision"
  | "ready"
  | "resolved"
  | "executed"
  | "dismissed"
  | "superseded";

export const getAssumptionCounts = (
  assumptions: Assumption[]
): { pending: number; accepted: number; rejected: number } => {
  return assumptions.reduce(
    (counts, assumption) => {
      if (assumption.status === "pending") {
        counts.pending += 1;
      } else if (assumption.status === "accepted") {
        counts.accepted += 1;
      } else {
        counts.rejected += 1;
      }
      return counts;
    },
    { pending: 0, accepted: 0, rejected: 0 }
  );
};

export const deriveProposalStage = (
  round: IntentWorkflowRound | null
): ProposalStage => {
  if (!round) {
    return "idle";
  }
  if (round.status === "executed") {
    return "executed";
  }
  if (round.status === "dismissed") {
    return "dismissed";
  }
  if (round.status === "superseded") {
    return "superseded";
  }
  if (round.status === "resolved") {
    return "resolved";
  }
  if ((round.clarifyingQuestions?.length ?? 0) > 0) {
    return "clarifying";
  }
  const counts = getAssumptionCounts(round.assumptions);
  if (counts.pending > 0) {
    return "needs_resolution";
  }
  if (counts.rejected > 0) {
    return "needs_revision";
  }
  return "ready";
};

export const canExecuteProposal = (round: IntentWorkflowRound | null): boolean =>
  deriveProposalStage(round) === "ready";
