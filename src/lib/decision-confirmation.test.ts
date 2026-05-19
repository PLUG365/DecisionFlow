import { describe, expect, it } from "vitest";

describe("decision confirmation helpers", () => {
  it("derives the next stage from the selected decision option label", async () => {
    const helpers = await import("./decision-confirmation");

    expect(helpers.getDecisionNextApplicationStage("承認")).toBe(100000004);
    expect(helpers.getDecisionNextApplicationStage("却下")).toBe(100000004);
    expect(helpers.getDecisionNextApplicationStage("差し戻し")).toBe(100000000);
  });

  it("exposes reconciliation polling constants for the Code Apps optimistic UI", async () => {
    const helpers = await import("./decision-confirmation");

    expect(helpers.RECONCILIATION_POLL_INTERVAL_MS).toBe(500);
    expect(helpers.RECONCILIATION_POLL_TIMEOUT_MS).toBe(3000);
  });
});
