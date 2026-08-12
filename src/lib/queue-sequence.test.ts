import { describe, expect, it } from "vitest";

import {
  buildDeciderQueueColumns,
  getQueueNavigation,
  parseQueueContext,
  toQueueContextParams,
} from "./queue-sequence";
import { ApplicationStage, type Application } from "@/types/decisionflow";

const DECIDER = "11111111-1111-1111-1111-111111111111";
const OTHER = "22222222-2222-2222-2222-222222222222";

function application(
  id: string,
  overrides: Partial<Application> = {},
): Application {
  return {
    ds_applicationid: id,
    ds_name: id,
    ds_stage: ApplicationStage.Submitted,
    _ds_deciderid_value: DECIDER,
    ...overrides,
  };
}

const noDecisions = () => undefined;

function build(
  applications: Application[],
  overrides: Partial<Parameters<typeof buildDeciderQueueColumns>[0]> = {},
) {
  return buildDeciderQueueColumns({
    applications,
    currentSystemUserId: DECIDER,
    categoryFilter: "all",
    sortMode: "due",
    getLatestDecisionOptionName: noDecisions,
    ...overrides,
  });
}

describe("buildDeciderQueueColumns", () => {
  it("keeps only the applications the current user decides", () => {
    const columns = build([
      application("mine"),
      application("theirs", { _ds_deciderid_value: OTHER }),
    ]);

    expect(
      columns.get("submitted")?.map((item) => item.ds_applicationid),
    ).toEqual(["mine"]);
  });

  it("sorts each column by the chosen mode", () => {
    const columns = build([
      application("later", { ds_duedate: "2026-08-20" }),
      application("earlier", { ds_duedate: "2026-08-12" }),
    ]);

    expect(
      columns.get("submitted")?.map((item) => item.ds_applicationid),
    ).toEqual(["earlier", "later"]);
  });

  it("routes a returned application to its own column", () => {
    const columns = build(
      [application("returned", { ds_stage: ApplicationStage.Draft })],
      { getLatestDecisionOptionName: () => "差し戻し" },
    );

    expect(
      columns.get("returned")?.map((item) => item.ds_applicationid),
    ).toEqual(["returned"]);
    expect(columns.get("submitted")).toEqual([]);
  });

  it("applies the category filter before grouping", () => {
    const columns = build(
      [
        application("keep", { _ds_categoryid_value: "cat-1" }),
        application("drop", { _ds_categoryid_value: "cat-2" }),
      ],
      { categoryFilter: "cat-1" },
    );

    expect(
      columns.get("submitted")?.map((item) => item.ds_applicationid),
    ).toEqual(["keep"]);
  });

  it("always returns every column, even when empty", () => {
    const columns = build([]);

    expect([...columns.keys()]).toEqual(["submitted", "returned", "decided"]);
    expect([...columns.values()].every((items) => items.length === 0)).toBe(true);
  });
});

describe("getQueueNavigation", () => {
  const column = [application("a"), application("b"), application("c")];

  it.each([
    ["a", { previousId: null, nextId: "b", position: 1 }],
    ["b", { previousId: "a", nextId: "c", position: 2 }],
    ["c", { previousId: "b", nextId: null, position: 3 }],
  ])("gives the neighbours of %s", (id, expected) => {
    expect(getQueueNavigation(column, id)).toEqual({ ...expected, total: 3 });
  });

  it("matches the current application regardless of guid casing", () => {
    expect(getQueueNavigation(column, "B").position).toBe(2);
  });

  it("offers no movement when the application is not in the column", () => {
    // 判断を確定した直後は列が変わる。見ていない並びの中を進ませない。
    expect(getQueueNavigation(column, "gone")).toEqual({
      previousId: null,
      nextId: null,
      position: null,
      total: 3,
    });
  });

  it("offers no movement without a current application", () => {
    expect(getQueueNavigation(column, undefined).position).toBeNull();
  });
});

describe("queue context round trip", () => {
  it("survives a trip through the URL", () => {
    const context = {
      column: "submitted" as const,
      sortMode: "oldest" as const,
      categoryFilter: "cat-1",
    };
    const params = new URLSearchParams(toQueueContextParams(context));

    expect(parseQueueContext(params)).toEqual(context);
  });

  it.each([
    ["nothing", ""],
    ["a partial context", "qcol=submitted"],
    ["an unknown column", "qcol=nope&qsort=due&qcat=all"],
    ["an unknown sort mode", "qcol=submitted&qsort=nope&qcat=all"],
  ])("refuses %s", (_label, query) => {
    expect(parseQueueContext(new URLSearchParams(query))).toBeNull();
  });
});
