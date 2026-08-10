import { normalizeGuid } from "@/lib/decisionflow-utils";
import {
  ApplicationStage,
  type Application,
} from "@/types/decisionflow";

export type DashboardActionScope = "mine" | "all";

export type DashboardActionGroups = {
  submitOrRevise: Application[];
  decide: Application[];
};

export type DashboardActionInput = {
  applications: Application[];
  scope: DashboardActionScope;
  currentSystemUserId: string | null | undefined;
  now: Date;
};

function calendarDateKey(value: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d+)?)?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)?)?$/.exec(
    value,
  );
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(year, month - 1, day);
  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null;
  }

  return year * 10000 + month * 100 + day;
}

function currentCalendarDateKey(now: Date): number {
  return (
    now.getFullYear() * 10000 +
    (now.getMonth() + 1) * 100 +
    now.getDate()
  );
}

function comparableGuid(value: string | null | undefined): string | null {
  return normalizeGuid(value)?.replace(/^\{|\}$/g, "") ?? null;
}

export function groupDashboardActionApplications({
  applications,
  scope,
  currentSystemUserId,
  now,
}: DashboardActionInput): DashboardActionGroups {
  const groups: DashboardActionGroups = { submitOrRevise: [], decide: [] };
  const currentUserId = comparableGuid(currentSystemUserId);
  if (scope === "mine" && !currentUserId) return groups;

  const today = currentCalendarDateKey(now);
  applications.forEach((application) => {
    const dueDate = application.ds_duedate
      ? calendarDateKey(application.ds_duedate)
      : null;
    if (dueDate === null || dueDate >= today) return;

    if (application.ds_stage === ApplicationStage.Draft) {
      if (
        scope === "all" ||
        comparableGuid(application._createdby_value) === currentUserId
      ) {
        groups.submitOrRevise.push(application);
      }
      return;
    }

    if (
      application.ds_stage === ApplicationStage.Submitted &&
      (scope === "all" ||
        comparableGuid(application._ds_deciderid_value) === currentUserId)
    ) {
      groups.decide.push(application);
    }
  });

  return groups;
}
