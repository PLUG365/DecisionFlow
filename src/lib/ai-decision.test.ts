import { describe, expect, it } from "vitest";

import { formatAiDecisionUpdatedAt, parseAiDecisionBasis } from "./ai-decision";

describe("parseAiDecisionBasis", () => {
  it("extracts risks and similar cases from JSON basis", () => {
    const result = parseAiDecisionBasis(
      JSON.stringify({
        risks: ["契約条件の追加確認が必要", "期限が短い"],
        regulationContext: {
          considered: true,
          audience: "deciderReview",
          message: "カテゴリ別レギュレーションを考慮しました。",
        },
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
    expect(result.regulationContext).toEqual({
      considered: true,
      audience: "deciderReview",
      message: "カテゴリ別レギュレーションを考慮しました。",
    });
  });

  it("distinguishes applicant pre-check from decider review in regulation context", () => {
    const applicant = parseAiDecisionBasis(
      JSON.stringify({
        regulationContext: {
          considered: false,
          audience: "applicantPreSubmit",
        },
      }),
    );
    const decider = parseAiDecisionBasis(
      JSON.stringify({
        regulationContext: { considered: true, audience: "deciderReview" },
      }),
    );

    expect(applicant.regulationContext?.audience).toBe("applicantPreSubmit");
    expect(decider.regulationContext?.audience).toBe("deciderReview");
  });

  it("extracts object-shaped risks from AI Builder output", () => {
    const result = parseAiDecisionBasis(
      JSON.stringify({
        risks: [{ item: "予算額が未記載です。" }, "期限が近いです。"],
        similarCases: [],
      }),
    );

    expect(result.risks).toEqual(["予算額が未記載です。", "期限が近いです。"]);
  });

  it("extracts category and detail shaped risks from AI Builder output", () => {
    const result = parseAiDecisionBasis(
      JSON.stringify({
        risks: [
          {
            category: "情報不足リスク",
            detail: "判断に必要な情報が不足しています。",
          },
        ],
        similarCases: [],
      }),
    );

    expect(result.risks).toEqual([
      "情報不足リスク: 判断に必要な情報が不足しています。",
    ]);
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
