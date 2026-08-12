import { calendarDateKey, currentCalendarDateKey } from "@/lib/calendar-date";
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
    const dueDate = calendarDateKey(application.ds_duedate);
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
