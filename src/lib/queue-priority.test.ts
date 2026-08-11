import { describe, expect, it } from "vitest";

import {
  getQueueDueStatus,
  sortQueueApplicationsByDueDate,
} from "./queue-priority";
import type { Application } from "@/types/decisionflow";

const application = (
  id: string,
  dueDate?: string,
): Application => ({
  ds_applicationid: id,
  ds_name: id,
  ds_duedate: dueDate,
});

describe("queue priority", () => {
  it("sorts by earliest valid due date and puts missing dates last", () => {
    const rows = [
      application("missing"),
      application("later", "2026-08-20"),
      application("earlier", "2026-08-12"),
      application("invalid", "not-a-date"),
    ];

    expect(
      sortQueueApplicationsByDueDate(rows).map(
        (row) => row.ds_applicationid,
      ),
    ).toEqual(["earlier", "later", "missing", "invalid"]);
  });

  it("keeps source order when due dates are equal", () => {
    const rows = [
      application("first", "2026-08-12"),
      application("second", "2026-08-12"),
    ];

    expect(
      sortQueueApplicationsByDueDate(rows).map(
        (row) => row.ds_applicationid,
      ),
    ).toEqual(["first", "second"]);
  });

  it.each([
    ["2026-08-10", "overdue"],
    ["2026-08-11", "today"],
    ["2026-08-12", "upcoming"],
    [undefined, "none"],
    ["not-a-date", "none"],
    ["2026-08-10not-a-date", "none"],
  ] as const)("classifies %s as %s", (dueDate, expected) => {
    expect(getQueueDueStatus(dueDate, new Date(2026, 7, 11, 12))).toBe(
      expected,
    );
  });
});
