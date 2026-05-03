import { describe, expect, it } from "vitest";

import { formatAiDecisionUpdatedAt, parseAiDecisionBasis } from "./ai-decision";

describe("parseAiDecisionBasis", () => {
  it("extracts risks and similar cases from JSON basis", () => {
    const result = parseAiDecisionBasis(
      JSON.stringify({
        risks: ["契約条件の追加確認が必要", "期限が短い"],
        similarCases: [
          {
            title: "顧客案件: 見積条件の例外承認",
            decision: "承認",
            reason: "収益影響と顧客関係のバランスが近い",
          },
        ],
      }),
    );

    expect(result.risks).toEqual(["契約条件の追加確認が必要", "期限が短い"]);
    expect(result.similarCases).toEqual([
      {
        title: "顧客案件: 見積条件の例外承認",
        decision: "承認",
        reason: "収益影響と顧客関係のバランスが近い",
      },
    ]);
    expect(result.rawText).toBeNull();
  });

  it("falls back to raw text when basis is not JSON", () => {
    const result = parseAiDecisionBasis("類似案件は見つかりませんでした。");

    expect(result.risks).toEqual([]);
    expect(result.similarCases).toEqual([]);
    expect(result.rawText).toBe("類似案件は見つかりませんでした。");
  });
});

describe("formatAiDecisionUpdatedAt", () => {
  it("shows not updated for empty value", () => {
    expect(formatAiDecisionUpdatedAt(null)).toBe("未更新");
    expect(formatAiDecisionUpdatedAt(undefined)).toBe("未更新");
  });

  it("formats timestamp in Japanese locale", () => {
    expect(formatAiDecisionUpdatedAt("2026-05-03T01:23:00Z")).toContain("2026");
  });
});
