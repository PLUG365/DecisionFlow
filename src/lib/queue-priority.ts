import type { Application } from "@/types/decisionflow";
import { calendarDateKey, currentCalendarDateKey } from "./calendar-date";

export type QueueDueStatus = "overdue" | "today" | "upcoming" | "none";
export type QueueCategoryFilter = "all" | "unassigned" | string;
export type QueueSortMode = "due" | "oldest";

export function getQueueDueStatus(
  dueDate: string | null | undefined,
  now: Date,
): QueueDueStatus {
  const dueDateKey = calendarDateKey(dueDate);
  if (dueDateKey === null) return "none";

  const today = currentCalendarDateKey(now);
  if (dueDateKey < today) return "overdue";
  if (dueDateKey === today) return "today";
  return "upcoming";
}

export function sortQueueApplicationsByDueDate(
  applications: Application[],
): Application[] {
  return applications
    .map((application, index) => ({
      application,
      index,
      dueDateKey: calendarDateKey(application.ds_duedate) ?? Infinity,
    }))
    .sort(
      (left, right) =>
        left.dueDateKey - right.dueDateKey || left.index - right.index,
    )
    .map(({ application }) => application);
}

export function sortQueueApplications(
  applications: Application[],
  mode: QueueSortMode,
): Application[] {
  if (mode === "due") {
    return sortQueueApplicationsByDueDate(applications);
  }

  return applications
    .map((application, index) => {
      const activityDate =
        application.modifiedon ??
        application.ds_submittedat ??
        application.createdon;
      const timestamp = activityDate ? Date.parse(activityDate) : NaN;
      return {
        application,
        index,
        timestamp: Number.isFinite(timestamp) ? timestamp : Infinity,
      };
    })
    .sort(
      (left, right) =>
        left.timestamp - right.timestamp || left.index - right.index,
    )
    .map(({ application }) => application);
}

function comparableId(value: string | null | undefined): string {
  return value?.replace(/^\{|\}$/g, "").toLowerCase() ?? "";
}

export function filterQueueApplicationsByCategory(
  applications: Application[],
  categoryFilter: QueueCategoryFilter,
): Application[] {
  if (categoryFilter === "all") return applications;
  if (categoryFilter === "unassigned") {
    return applications.filter(
      (application) => !application._ds_categoryid_value,
    );
  }

  const categoryId = comparableId(categoryFilter);
  return applications.filter(
    (application) =>
      comparableId(application._ds_categoryid_value) === categoryId,
  );
}
