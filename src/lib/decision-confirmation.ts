export const DRAFT_STAGE = 100000000;
export const SUBMITTED_STAGE = 100000001;
export const DECIDED_STAGE = 100000004;

export const RECONCILIATION_POLL_INTERVAL_MS = 500;
export const RECONCILIATION_POLL_TIMEOUT_MS = 3000;

export function getDecisionNextApplicationStage(
  decisionOptionLabel: string,
): number {
  return decisionOptionLabel === "差し戻し" ? DRAFT_STAGE : DECIDED_STAGE;
}
