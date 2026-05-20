import { describe, expect, it } from "vitest";
import {
  FIXED_DECISION_OPTION_NAMES,
  isFixedDecisionOptionName,
} from "./decision-options";

describe("fixed decision options", () => {
  it("keeps the workflow and chat contract decision labels fixed", () => {
    expect(FIXED_DECISION_OPTION_NAMES).toEqual(["承認", "却下", "差し戻し"]);
  });

  it("rejects labels outside the fixed contract", () => {
    expect(isFixedDecisionOptionName("承認")).toBe(true);
    expect(isFixedDecisionOptionName("条件付き承認")).toBe(false);
  });
});
