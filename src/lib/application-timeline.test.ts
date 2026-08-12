import { describe, expect, it } from "vitest";

import {
  buildApplicationTimeline,
  summarizeApplicationTimeline,
  type BuildApplicationTimelineInput,
} from "./application-timeline";
import {
  ApplicationStage,
  MessageKind,
  ParticipantRole,
} from "@/types/decisionflow";

const emptyInput: BuildApplicationTimelineInput = {
  application: { ds_applicationid: "app-1" },
  messages: [],
  participants: [],
  resources: [],
  decisions: [],
  decisionOptions: [],
};

function build(
  overrides: Partial<BuildApplicationTimelineInput>,
): ReturnType<typeof buildApplicationTimeline> {
  return buildApplicationTimeline({
    ...emptyInput,
    ...overrides,
    application: { ...emptyInput.application, ...overrides.application },
  });
}

describe("buildApplicationTimeline", () => {
  it("orders every source in one chronological sequence", () => {
    const events = build({
      application: {
        ds_applicationid: "app-1",
        createdon: "2026-05-01T00:00:00Z",
        ds_submittedat: "2026-05-02T00:00:00Z",
        ds_aidecisionupdatedat: "2026-05-03T00:00:00Z",
      },
      messages: [
        {
          ds_messageid: "msg-1",
          createdon: "2026-05-05T00:00:00Z",
          ds_kind: MessageKind.Question,
          ds_body: "追加の資料はありますか",
        },
      ],
      participants: [
        {
          ds_participantid: "par-1",
          ds_addedat: "2026-05-04T00:00:00Z",
          ds_role: ParticipantRole.Contributor,
        },
      ],
      resources: [
        {
          ds_applicationresourceid: "res-1",
          ds_name: "見積書",
          createdon: "2026-05-06T00:00:00Z",
        },
      ],
      decisions: [
        {
          ds_decisionid: "dec-1",
          ds_decidedat: "2026-05-07T00:00:00Z",
          _ds_decisionoptionid_value: "opt-1",
        },
      ],
      decisionOptions: [{ ds_decisionoptionid: "OPT-1", ds_name: "承認" }],
    });

    expect(events.map((event) => event.type)).toEqual([
      "created",
      "submitted",
      "ai-decision",
      "participant",
      "message",
      "resource",
      "decision",
    ]);
    expect(events.map((event) => event.title)).toEqual([
      "申請を作成",
      "提出",
      "AI判断を生成",
      "関係者を追加",
      "質問",
      "関連資料を追加",
      "判断: 承認",
    ]);
  });

  it("falls back to a plain label for a role the app does not model", () => {
    // 実データに `CoDecider`(100000002) の行がある。`ParticipantRole` には無い値なので
    // ラベル解決に失敗するが、出来事そのものは経緯から落とさない。
    const events = build({
      participants: [
        {
          ds_participantid: "par-1",
          ds_addedat: "2026-05-01T13:07:47Z",
          ds_role: 100000002 as never,
        },
      ],
    });

    expect(events.map((event) => event.title)).toEqual(["関係者を追加"]);
  });

  it("drops rows whose timestamp is missing or unparseable", () => {
    const events = build({
      application: {
        ds_applicationid: "app-1",
        createdon: "2026-05-01T00:00:00Z",
        ds_submittedat: null,
        ds_aidecisionupdatedat: "こわれた日付",
      },
      messages: [
        { ds_messageid: "msg-none", ds_body: "日時なし" },
        { ds_messageid: "msg-bad", createdon: "  ", ds_body: "空白" },
      ],
      decisions: [{ ds_decisionid: "dec-none", ds_rationale: "日時なし" }],
    });

    expect(events.map((event) => event.id)).toEqual(["created:app-1"]);
  });

  it("keeps source order when two events share a timestamp", () => {
    const events = build({
      messages: [
        { ds_messageid: "first", createdon: "2026-05-05T00:00:00Z" },
        { ds_messageid: "second", createdon: "2026-05-05T00:00:00Z" },
      ],
    });

    expect(events.map((event) => event.id)).toEqual([
      "message:first",
      "message:second",
    ]);
  });

  it("marks the submission as a re-submission when a decision predates it", () => {
    const events = build({
      application: {
        ds_applicationid: "app-1",
        ds_submittedat: "2026-08-09T08:45:00Z",
      },
      decisions: [
        { ds_decisionid: "dec-1", ds_decidedat: "2026-05-20T00:15:53Z" },
      ],
    });

    const submitted = events.find((event) => event.type === "submitted");
    expect(submitted?.detail).toBe(
      "差し戻し後の再提出。過去の提出日時は記録されていない",
    );
    expect(events.map((event) => event.type)).toEqual([
      "decision",
      "submitted",
    ]);
  });

  it("leaves a first-time submission without the re-submission note", () => {
    const events = build({
      application: {
        ds_applicationid: "app-1",
        ds_submittedat: "2026-05-01T00:00:00Z",
      },
      decisions: [
        { ds_decisionid: "dec-1", ds_decidedat: "2026-05-07T00:00:00Z" },
      ],
    });

    expect(
      events.find((event) => event.type === "submitted")?.detail,
    ).toBeUndefined();
  });

  it("matches decision options regardless of guid casing", () => {
    const events = build({
      decisions: [
        {
          ds_decisionid: "dec-1",
          ds_decidedat: "2026-05-07T00:00:00Z",
          _ds_decisionoptionid_value: "AB12CD34-0000-0000-0000-000000000000",
        },
      ],
      decisionOptions: [
        {
          ds_decisionoptionid: "ab12cd34-0000-0000-0000-000000000000",
          ds_name: "差し戻し",
        },
      ],
    });

    expect(events[0].title).toBe("判断: 差し戻し");
  });

  it("falls back to a plain label when the decision option is unknown", () => {
    const events = build({
      decisions: [
        {
          ds_decisionid: "dec-1",
          ds_decidedat: "2026-05-07T00:00:00Z",
          _ds_decisionoptionid_value: "missing",
        },
      ],
    });

    expect(events[0].title).toBe("判断");
  });

  it("carries the actor of each event without resolving the name", () => {
    const events = build({
      decisions: [
        {
          ds_decisionid: "dec-1",
          ds_decidedat: "2026-05-07T00:00:00Z",
          _ds_deciderid_value: "user-decider",
        },
      ],
      messages: [
        {
          ds_messageid: "msg-1",
          createdon: "2026-05-05T00:00:00Z",
          _createdby_value: "user-author",
        },
      ],
    });

    expect(events.map((event) => event.actorUserId)).toEqual([
      "user-author",
      "user-decider",
    ]);
  });

  it("truncates long detail text", () => {
    const events = build({
      messages: [
        {
          ds_messageid: "msg-1",
          createdon: "2026-05-05T00:00:00Z",
          ds_body: "あ".repeat(200),
        },
      ],
    });

    expect(events[0].detail).toBe(`${"あ".repeat(120)}…`);
  });
});

describe("summarizeApplicationTimeline", () => {
  const events = build({
    application: {
      ds_applicationid: "app-1",
      createdon: "2026-08-01T00:00:00Z",
      ds_submittedat: "2026-08-02T00:00:00Z",
    },
  });

  it("reports the elapsed whole days since the newest event", () => {
    expect(
      summarizeApplicationTimeline({
        events,
        stage: ApplicationStage.Submitted,
        now: new Date("2026-08-05T12:00:00Z"),
      }),
    ).toEqual({
      lastEventAt: "2026-08-02T00:00:00Z",
      daysSinceLastEvent: 3,
      isStalled: true,
    });
  });

  it("does not call a submitted application stalled before the threshold", () => {
    expect(
      summarizeApplicationTimeline({
        events,
        stage: ApplicationStage.Submitted,
        now: new Date("2026-08-04T23:00:00Z"),
      }).isStalled,
    ).toBe(false);
  });

  it("never calls a draft or decided application stalled", () => {
    const now = new Date("2026-09-01T00:00:00Z");

    expect(
      summarizeApplicationTimeline({
        events,
        stage: ApplicationStage.Draft,
        now,
      }).isStalled,
    ).toBe(false);
    expect(
      summarizeApplicationTimeline({
        events,
        stage: ApplicationStage.Decided,
        now,
      }).isStalled,
    ).toBe(false);
  });

  it("returns nulls when there is no event to measure from", () => {
    expect(
      summarizeApplicationTimeline({
        events: [],
        stage: ApplicationStage.Submitted,
        now: new Date("2026-08-05T00:00:00Z"),
      }),
    ).toEqual({
      lastEventAt: null,
      daysSinceLastEvent: null,
      isStalled: false,
    });
  });

  it("clamps a future timestamp to zero days instead of going negative", () => {
    expect(
      summarizeApplicationTimeline({
        events,
        stage: ApplicationStage.Submitted,
        now: new Date("2026-07-01T00:00:00Z"),
      }),
    ).toMatchObject({ daysSinceLastEvent: 0, isStalled: false });
  });
});
