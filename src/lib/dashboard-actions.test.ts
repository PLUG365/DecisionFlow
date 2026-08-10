import { describe, expect, it } from "vitest";

import { groupDashboardActionApplications } from "./dashboard-actions";
import { ApplicationStage, type Application } from "@/types/decisionflow";

const NOW = new Date(2026, 7, 11, 12, 0, 0);

function application(
  id: string,
  overrides: Partial<Application> = {},
): Application {
  return {
    ds_applicationid: id,
    ds_name: id,
    ds_stage: ApplicationStage.Draft,
    ds_duedate: "2026-08-10",
    ...overrides,
  };
}

describe("groupDashboardActionApplications", () => {
  it("separates overdue Draft and Submitted rows", () => {
    const rows = [
      application("draft-overdue"),
      application("submitted-overdue", {
        ds_stage: ApplicationStage.Submitted,
      }),
    ];

    const result = groupDashboardActionApplications({
      applications: rows,
      scope: "all",
      currentSystemUserId: null,
      now: NOW,
    });

    expect(result.submitOrRevise.map((row) => row.ds_applicationid)).toEqual([
      "draft-overdue",
    ]);
    expect(result.decide.map((row) => row.ds_applicationid)).toEqual([
      "submitted-overdue",
    ]);
  });

  it("excludes rows that are not overdue actionable stages", () => {
    const rows = [
      application("due-today", { ds_duedate: "2026-08-11" }),
      application("due-future", { ds_duedate: "2026-08-12" }),
      application("decided", { ds_stage: ApplicationStage.Decided }),
      application("missing-due", { ds_duedate: undefined }),
      application("unknown-stage", { ds_stage: 999 as never }),
      application("invalid-due", { ds_duedate: "not-a-date" }),
    ];

    const result = groupDashboardActionApplications({
      applications: rows,
      scope: "all",
      currentSystemUserId: null,
      now: NOW,
    });

    expect(result).toEqual({ submitOrRevise: [], decide: [] });
  });

  it("uses creator ownership for Draft and decider ownership for Submitted", () => {
    const rows = [
      application("my-draft", { _createdby_value: "{USER-A}" }),
      application("other-draft", { _createdby_value: "USER-B" }),
      application("my-decision", {
        ds_stage: ApplicationStage.Submitted,
        _ds_deciderid_value: "USER-A",
      }),
      application("other-decision", {
        ds_stage: ApplicationStage.Submitted,
        _ds_deciderid_value: "USER-B",
      }),
    ];

    const result = groupDashboardActionApplications({
      applications: rows,
      scope: "mine",
      currentSystemUserId: "user-a",
      now: NOW,
    });

    expect(result.submitOrRevise.map((row) => row.ds_applicationid)).toEqual([
      "my-draft",
    ]);
    expect(result.decide.map((row) => row.ds_applicationid)).toEqual([
      "my-decision",
    ]);
  });

  it("returns no mine rows when the current user is unresolved", () => {
    const result = groupDashboardActionApplications({
      applications: [
        application("draft"),
        application("submitted", { ds_stage: ApplicationStage.Submitted }),
      ],
      scope: "mine",
      currentSystemUserId: null,
      now: NOW,
    });

    expect(result).toEqual({ submitOrRevise: [], decide: [] });
  });

  it("does not apply ownership filtering to the all scope", () => {
    const rows = [
      application("draft", { _createdby_value: "USER-B" }),
      application("submitted", {
        ds_stage: ApplicationStage.Submitted,
        _ds_deciderid_value: "USER-B",
      }),
    ];

    const result = groupDashboardActionApplications({
      applications: rows,
      scope: "all",
      currentSystemUserId: null,
      now: NOW,
    });

    expect(result.submitOrRevise).toEqual([rows[0]]);
    expect(result.decide).toEqual([rows[1]]);
  });
});
