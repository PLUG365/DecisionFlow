import {
  ApplicationStage,
  stageMeta,
  type Application,
  type Decision,
  type DecisionOption,
} from "@/types/decisionflow";
import { normalizeApplicationStage, normalizeGuid } from "./decisionflow-utils";

/**
 * 印刷・PDF 用の判断記録。証跡として残す1枚に何を載せるかを決める。
 *
 * **画面に出ていない事実を作らない。** 値が無いところは `null` を返し、表示側が
 * 「未設定」などの文言を決める。ここで既定値を埋めると、記録として残った紙が
 * 実際のデータより多くを主張してしまう。
 */
export type DecisionRecordDecision = {
  optionName: string | null;
  rationale: string | null;
  decidedAt: string | null;
  deciderUserId: string | null;
  /** 判断確定時点の AI 推奨のスナップショット。G1 で控えている値 */
  aiSuggestionAtDecision: string | null;
};

export type DecisionRecord = {
  title: string;
  body: string | null;
  stageLabel: string;
  categoryId: string | null;
  deciderUserId: string | null;
  dueDate: string | null;
  submittedAt: string | null;
  /** 判断が確定していなければ `null`。差し戻し中も最新の判断は載せる */
  decision: DecisionRecordDecision | null;
  /** 判断が1件も無い申請かどうか。表示側が「未判断」を出すために使う */
  isUndecided: boolean;
};

export type BuildDecisionRecordInput = {
  application: Pick<
    Application,
    | "ds_name"
    | "ds_body"
    | "ds_stage"
    | "ds_duedate"
    | "ds_submittedat"
    | "_ds_categoryid_value"
    | "_ds_deciderid_value"
  >;
  /** `ds_decidedat` の降順で渡す（`useDecisions` の並びをそのまま使える） */
  decisions: Pick<
    Decision,
    | "ds_rationale"
    | "ds_decidedat"
    | "ds_aisuggestionatdecision"
    | "_ds_deciderid_value"
    | "_ds_decisionoptionid_value"
  >[];
  decisionOptions: Pick<DecisionOption, "ds_decisionoptionid" | "ds_name">[];
};

function trimmedOrNull(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
}

export function buildDecisionRecord({
  application,
  decisions,
  decisionOptions,
}: BuildDecisionRecordInput): DecisionRecord {
  const stage = normalizeApplicationStage(application.ds_stage);
  const latest = decisions[0];

  const optionNameById = new Map(
    decisionOptions.map((option) => [
      normalizeGuid(option.ds_decisionoptionid) ?? "",
      option.ds_name,
    ]),
  );

  return {
    title: application.ds_name,
    body: trimmedOrNull(application.ds_body),
    stageLabel: stageMeta[stage].label,
    categoryId: normalizeGuid(application._ds_categoryid_value),
    deciderUserId: normalizeGuid(application._ds_deciderid_value),
    dueDate: trimmedOrNull(application.ds_duedate),
    submittedAt: trimmedOrNull(application.ds_submittedat),
    decision: latest
      ? {
          optionName:
            optionNameById.get(
              normalizeGuid(latest._ds_decisionoptionid_value) ?? "",
            ) ?? null,
          rationale: trimmedOrNull(latest.ds_rationale),
          decidedAt: trimmedOrNull(latest.ds_decidedat),
          deciderUserId: normalizeGuid(latest._ds_deciderid_value),
          aiSuggestionAtDecision: trimmedOrNull(
            latest.ds_aisuggestionatdecision,
          ),
        }
      : null,
    isUndecided: decisions.length === 0,
  };
}

/**
 * 記録の見出しに出す作成日時。**印刷した時刻**であって判断の時刻ではないので、
 * 表示側でもそう分かる文言にすること。
 */
export function formatDecisionRecordPrintedAt(now: Date): string {
  return now.toLocaleString("ja-JP");
}

/**
 * 差し戻し中の申請を「判断済み」と読ませない。ステージは Draft に戻っているのに
 * 最新判断は残っているため、記録上は「最新の判断」であって「確定した判断」ではない。
 */
export function isDecisionRecordFinal(record: DecisionRecord): boolean {
  return (
    record.decision !== null &&
    record.stageLabel === stageMeta[ApplicationStage.Decided].label
  );
}
