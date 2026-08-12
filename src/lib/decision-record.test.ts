import { describe, expect, it } from "vitest";

import {
  buildDecisionRecord,
  isDecisionRecordFinal,
  type BuildDecisionRecordInput,
} from "./decision-record";
import { ApplicationStage } from "@/types/decisionflow";

const base: BuildDecisionRecordInput = {
  application: { ds_name: "新システム導入" },
  decisions: [],
  decisionOptions: [],
};

function build(
  overrides: Partial<BuildDecisionRecordInput>,
): ReturnType<typeof buildDecisionRecord> {
  return buildDecisionRecord({
    ...base,
    ...overrides,
    application: { ...base.application, ...overrides.application },
  });
}

describe("buildDecisionRecord", () => {
  it("carries the application fields the record needs", () => {
    const record = build({
      application: {
        ds_name: "新システム導入",
        ds_body: "  予算を確保したい  ",
        ds_stage: ApplicationStage.Decided,
        ds_duedate: "2026-08-20",
        ds_submittedat: "2026-08-09T08:45:00Z",
        _ds_categoryid_value: "CAT-1",
        _ds_deciderid_value: "USER-1",
      },
    });

    expect(record).toMatchObject({
      title: "新システム導入",
      body: "予算を確保したい",
      stageLabel: "判断済み",
      categoryId: "cat-1",
      deciderUserId: "user-1",
      dueDate: "2026-08-20",
      submittedAt: "2026-08-09T08:45:00Z",
    });
  });

  it.each([
    ["空文字", ""],
    ["空白だけ", "   "],
    ["未設定", undefined],
  ])("does not invent a value when the body is %s", (_label, body) => {
    // 記録として残る紙が、実データより多くを主張しないこと。
    expect(build({ application: { ds_name: "x", ds_body: body } }).body).toBeNull();
  });

  it("takes the newest decision and resolves its option name", () => {
    const record = build({
      decisions: [
        {
          ds_decidedat: "2026-08-10T20:31:55Z",
          ds_rationale: "条件を満たしている",
          ds_aisuggestionatdecision: "差し戻し",
          _ds_deciderid_value: "USER-9",
          _ds_decisionoptionid_value: "OPT-1",
        },
        {
          ds_decidedat: "2026-05-20T00:15:53Z",
          ds_rationale: "古い判断",
          _ds_decisionoptionid_value: "opt-2",
        },
      ],
      decisionOptions: [
        { ds_decisionoptionid: "opt-1", ds_name: "承認" },
        { ds_decisionoptionid: "opt-2", ds_name: "差し戻し" },
      ],
    });

    expect(record.decision).toEqual({
      optionName: "承認",
      rationale: "条件を満たしている",
      decidedAt: "2026-08-10T20:31:55Z",
      deciderUserId: "user-9",
      aiSuggestionAtDecision: "差し戻し",
    });
    expect(record.isUndecided).toBe(false);
  });

  it("reports an unknown option name as null instead of guessing", () => {
    const record = build({
      decisions: [
        { ds_decidedat: "2026-08-10T20:31:55Z", _ds_decisionoptionid_value: "gone" },
      ],
      decisionOptions: [],
    });

    expect(record.decision?.optionName).toBeNull();
  });

  it("marks an application with no decision as undecided", () => {
    const record = build({ application: { ds_name: "x" } });

    expect(record.decision).toBeNull();
    expect(record.isUndecided).toBe(true);
  });

  it("keeps the AI snapshot empty when none was recorded", () => {
    const record = build({
      decisions: [{ ds_decidedat: "2026-08-10T20:31:55Z" }],
    });

    expect(record.decision?.aiSuggestionAtDecision).toBeNull();
  });
});

describe("isDecisionRecordFinal", () => {
  it("treats a decided application with a decision as final", () => {
    const record = build({
      application: { ds_name: "x", ds_stage: ApplicationStage.Decided },
      decisions: [{ ds_decidedat: "2026-08-10T20:31:55Z" }],
    });

    expect(isDecisionRecordFinal(record)).toBe(true);
  });

  it("does not call a returned application final even though a decision exists", () => {
    // 差し戻し中はステージが Draft へ戻る。最新判断は残るが「確定した判断」ではない。
    const record = build({
      application: { ds_name: "x", ds_stage: ApplicationStage.Draft },
      decisions: [{ ds_decidedat: "2026-08-10T20:31:55Z" }],
    });

    expect(isDecisionRecordFinal(record)).toBe(false);
  });

  it("does not call an undecided application final", () => {
    const record = build({
      application: { ds_name: "x", ds_stage: ApplicationStage.Decided },
    });

    expect(isDecisionRecordFinal(record)).toBe(false);
  });
});
