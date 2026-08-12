import {
  ApplicationStage,
  DelegationResult,
  MessageKind,
  participantRoleLabels,
  type Application,
  type ApplicationResource,
  type ApplicationStageValue,
  type Decision,
  type DecisionOption,
  type DelegationHistory,
  type Message,
  type MessageKindValue,
  type Participant,
  type ParticipantRoleValue,
} from "@/types/decisionflow";
import { normalizeApplicationStage, normalizeGuid } from "./decisionflow-utils";

export type TimelineEventType =
  | "created"
  | "submitted"
  | "ai-decision"
  | "participant"
  | "resource"
  | "message"
  | "decision"
  | "delegation";

export type TimelineEvent = {
  id: string;
  type: TimelineEventType;
  /** 元の値をそのまま持つ。表示側で toLocaleString する */
  at: string;
  timestamp: number;
  title: string;
  detail?: string;
  /** 表示側で氏名へ解決する。純関数側では ID のままにする */
  actorUserId?: string;
  /** 担当変更のときだけ入る。表示側で氏名へ解決する */
  delegation?: { previousUserId?: string; newUserId?: string };
};

const messageKindLabels: Record<MessageKindValue, string> = {
  [MessageKind.Comment]: "コメント",
  [MessageKind.Question]: "質問",
  [MessageKind.Answer]: "回答",
  [MessageKind.System]: "システム",
};

/**
 * **最後の活動から**何日で停滞とみなすか。
 *
 * 日数は `Application_StalledReminder` と同じ3日にそろえているが、**判定基準は別物**である。
 * フローは「希望期限超過 または `ds_submittedat` から3日」で判定し、意図的に最終活動時刻を見ない。
 * こちらは会話・資料・関係者・AI生成を含む最後の活動から数える。したがって
 * 「30日前に提出され、昨日コメントが付いた申請」はメールが飛ぶがバナーは出ない。
 * 判断キューの停滞順（`modifiedon` 基準）とも一致しない。
 */
export const TIMELINE_STALLED_THRESHOLD_DAYS = 3;

const DAY_IN_MS = 24 * 60 * 60 * 1000;

function parseTimestamp(value: string | null | undefined): number | null {
  const trimmed = value?.trim();
  if (!trimmed) return null;
  const parsed = Date.parse(trimmed);
  return Number.isNaN(parsed) ? null : parsed;
}

function truncate(value: string | null | undefined, max = 120): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  return trimmed.length > max ? `${trimmed.slice(0, max)}…` : trimmed;
}

export type BuildApplicationTimelineInput = {
  application: Pick<
    Application,
    | "ds_applicationid"
    | "createdon"
    | "ds_submittedat"
    | "ds_aidecisionupdatedat"
    | "ds_aidecisionoptiontext"
    | "_createdby_value"
  >;
  messages: Pick<
    Message,
    "ds_messageid" | "ds_body" | "ds_kind" | "createdon" | "_createdby_value"
  >[];
  participants: Pick<
    Participant,
    "ds_participantid" | "ds_role" | "ds_addedat" | "_ds_userid_value"
  >[];
  resources: Pick<
    ApplicationResource,
    "ds_applicationresourceid" | "ds_name" | "createdon" | "_createdby_value"
  >[];
  decisions: Pick<
    Decision,
    | "ds_decisionid"
    | "ds_rationale"
    | "ds_decidedat"
    | "_ds_deciderid_value"
    | "_ds_decisionoptionid_value"
  >[];
  decisionOptions: Pick<DecisionOption, "ds_decisionoptionid" | "ds_name">[];
  /**
   * 担当変更履歴。**権限が無い利用者には空で渡ってくる**（`ds_Applicant` は NO_ACCESS）。
   * 空であることと「履歴が無い」ことをここでは区別しない。区別は取得側の
   * `DelegationHistoryFetch` が持ち、表示側が扱う。
   */
  delegationHistories?: Pick<
    DelegationHistory,
    | "ds_delegationhistoryid"
    | "ds_detail"
    | "ds_result"
    | "ds_processedat"
    | "_ds_actorid_value"
    | "_ds_previousdeciderid_value"
    | "_ds_newdeciderid_value"
  >[];
};

/**
 * 申請1件の経緯を、既に取得済みのデータだけから組み立てる。新しい Dataverse query は増やさない。
 *
 * 日時が無い・壊れている行は**捨てる**。時系列に置けないものを推測で置くと、
 * 停滞判定がその推測に引きずられるため。
 */
export function buildApplicationTimeline({
  application,
  messages,
  participants,
  resources,
  decisions,
  decisionOptions,
  delegationHistories = [],
}: BuildApplicationTimelineInput): TimelineEvent[] {
  const optionNameById = new Map(
    decisionOptions.map((option) => [
      normalizeGuid(option.ds_decisionoptionid) ?? "",
      option.ds_name,
    ]),
  );

  const submittedAt = parseTimestamp(application.ds_submittedat);
  const decisionTimestamps = decisions
    .map((decision) => parseTimestamp(decision.ds_decidedat))
    .filter((value): value is number => value !== null);

  /**
   * `ds_submittedat` は再提出のたびに上書きされる単一列で、過去の提出時刻は残らない。
   * 判断が提出より前にあるなら差し戻し後の再提出である。
   */
  const isResubmitted =
    submittedAt !== null &&
    decisionTimestamps.some((decidedAt) => decidedAt < submittedAt);

  const events: TimelineEvent[] = [];

  const createdAt = parseTimestamp(application.createdon);
  if (createdAt !== null) {
    events.push({
      id: `created:${application.ds_applicationid}`,
      type: "created",
      at: application.createdon!,
      timestamp: createdAt,
      title: "申請を作成",
      actorUserId: application._createdby_value ?? undefined,
    });
  }

  if (submittedAt !== null) {
    events.push({
      id: `submitted:${application.ds_applicationid}`,
      type: "submitted",
      at: application.ds_submittedat!,
      timestamp: submittedAt,
      title: "提出",
      detail: isResubmitted
        ? "差し戻し後の再提出。過去の提出日時は記録されていない"
        : undefined,
      actorUserId: application._createdby_value ?? undefined,
    });
  }

  const aiUpdatedAt = parseTimestamp(application.ds_aidecisionupdatedat);
  if (aiUpdatedAt !== null) {
    events.push({
      id: `ai:${application.ds_applicationid}`,
      type: "ai-decision",
      at: application.ds_aidecisionupdatedat!,
      timestamp: aiUpdatedAt,
      title: "AI判断を生成",
      detail: truncate(application.ds_aidecisionoptiontext),
    });
  }

  participants.forEach((participant) => {
    const addedAt = parseTimestamp(participant.ds_addedat);
    if (addedAt === null) return;
    const roleLabel =
      participantRoleLabels[participant.ds_role as ParticipantRoleValue];
    events.push({
      id: `participant:${participant.ds_participantid}`,
      type: "participant",
      at: participant.ds_addedat!,
      timestamp: addedAt,
      title: roleLabel ? `${roleLabel}を追加` : "関係者を追加",
      actorUserId: participant._ds_userid_value ?? undefined,
    });
  });

  resources.forEach((resource) => {
    const createdOn = parseTimestamp(resource.createdon);
    if (createdOn === null) return;
    events.push({
      id: `resource:${resource.ds_applicationresourceid}`,
      type: "resource",
      at: resource.createdon!,
      timestamp: createdOn,
      title: "関連資料を追加",
      detail: truncate(resource.ds_name),
      actorUserId: resource._createdby_value ?? undefined,
    });
  });

  messages.forEach((message) => {
    const createdOn = parseTimestamp(message.createdon);
    if (createdOn === null) return;
    const kindLabel = messageKindLabels[message.ds_kind as MessageKindValue];
    events.push({
      id: `message:${message.ds_messageid}`,
      type: "message",
      at: message.createdon!,
      timestamp: createdOn,
      title: kindLabel ?? "コメント",
      detail: truncate(message.ds_body),
      actorUserId: message._createdby_value ?? undefined,
    });
  });

  decisions.forEach((decision) => {
    const decidedAt = parseTimestamp(decision.ds_decidedat);
    if (decidedAt === null) return;
    const optionName = optionNameById.get(
      normalizeGuid(decision._ds_decisionoptionid_value) ?? "",
    );
    events.push({
      id: `decision:${decision.ds_decisionid}`,
      type: "decision",
      at: decision.ds_decidedat!,
      timestamp: decidedAt,
      title: optionName ? `判断: ${optionName}` : "判断",
      detail: truncate(decision.ds_rationale),
      actorUserId: decision._ds_deciderid_value ?? undefined,
    });
  });

  delegationHistories.forEach((history) => {
    const processedAt = parseTimestamp(history.ds_processedat);
    if (processedAt === null) return;
    // 却下された試行も証跡として残す。G2 が書いた履歴を読める場所はここしかない。
    const succeeded = history.ds_result === DelegationResult.Succeeded;
    events.push({
      id: `delegation:${history.ds_delegationhistoryid}`,
      type: "delegation",
      at: history.ds_processedat!,
      timestamp: processedAt,
      title: succeeded ? "担当を変更" : "担当変更を却下",
      detail: truncate(history.ds_detail),
      actorUserId: history._ds_actorid_value ?? undefined,
      delegation: {
        previousUserId: history._ds_previousdeciderid_value ?? undefined,
        newUserId: history._ds_newdeciderid_value ?? undefined,
      },
    });
  });

  return events
    .map((event, index) => ({ event, index }))
    .sort(
      (left, right) =>
        left.event.timestamp - right.event.timestamp || left.index - right.index,
    )
    .map(({ event }) => event);
}

export type ApplicationTimelineSummary = {
  lastEventAt: string | null;
  daysSinceLastEvent: number | null;
  isStalled: boolean;
};

/**
 * 停滞は**提出済みの申請だけ**で意味を持つ。下書きは動かなくても正常で、
 * 判断済みは動きが止まって当たり前なので、どちらも停滞とは呼ばない。
 */
export function summarizeApplicationTimeline({
  events,
  stage,
  now,
}: {
  events: TimelineEvent[];
  stage: ApplicationStageValue | number | null | undefined;
  now: Date;
}): ApplicationTimelineSummary {
  const lastEvent = events.length > 0 ? events[events.length - 1] : null;
  if (!lastEvent) {
    return { lastEventAt: null, daysSinceLastEvent: null, isStalled: false };
  }

  const elapsedMs = now.getTime() - lastEvent.timestamp;
  const daysSinceLastEvent = Math.max(0, Math.floor(elapsedMs / DAY_IN_MS));

  return {
    lastEventAt: lastEvent.at,
    daysSinceLastEvent,
    isStalled:
      normalizeApplicationStage(stage) === ApplicationStage.Submitted &&
      daysSinceLastEvent >= TIMELINE_STALLED_THRESHOLD_DAYS,
  };
}
