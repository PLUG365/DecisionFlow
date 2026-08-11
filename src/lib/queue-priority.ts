import type { Application } from "@/types/decisionflow";

export type QueueDueStatus = "overdue" | "today" | "upcoming" | "none";

function calendarDateKey(value: string | null | undefined): number | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d(?:\.\d+)?)?(?:Z|[+-](?:0\d|1[0-4]):[0-5]\d)?)?$/.exec(
    value,
  );
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
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
