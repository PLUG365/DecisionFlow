import type { Application } from "@/types/decisionflow";
import {
  getDeciderQueueApplications,
  getDeciderQueueColumnKey,
  normalizeGuid,
  type DeciderQueueColumnKey,
} from "./decisionflow-utils";
import {
  filterQueueApplicationsByCategory,
  sortQueueApplications,
  type QueueCategoryFilter,
  type QueueSortMode,
} from "./queue-priority";

export const DECIDER_QUEUE_COLUMN_KEYS: DeciderQueueColumnKey[] = [
  "submitted",
  "returned",
  "decided",
];

export type BuildDeciderQueueColumnsInput = {
  applications: Application[];
  currentSystemUserId: string | null | undefined;
  categoryFilter: QueueCategoryFilter;
  sortMode: QueueSortMode;
  /** `buildLatestDecisionOptionNameLookup` の戻り値 */
  getLatestDecisionOptionName: (
    applicationId: string | null | undefined,
  ) => string | undefined;
};

/**
 * 判断キューの列構成。**判断キュー画面と申請詳細の「前/次」が同じ並びを見るため**に
 * 純関数へ出してある。片方だけが並べ替えると、利用者が見ていた順と違う順で
 * 次の申請へ送られる。
 */
export function buildDeciderQueueColumns({
  applications,
  currentSystemUserId,
  categoryFilter,
  sortMode,
  getLatestDecisionOptionName,
}: BuildDeciderQueueColumnsInput): Map<DeciderQueueColumnKey, Application[]> {
  const columns = new Map<DeciderQueueColumnKey, Application[]>();
  DECIDER_QUEUE_COLUMN_KEYS.forEach((key) => columns.set(key, []));

  const filtered = filterQueueApplicationsByCategory(
    applications,
    categoryFilter,
  );

  getDeciderQueueApplications(filtered, currentSystemUserId).forEach(
    (application) => {
      const columnKey = getDeciderQueueColumnKey(
        application.ds_stage,
        getLatestDecisionOptionName(application.ds_applicationid),
      );
      if (columnKey) columns.get(columnKey)?.push(application);
    },
  );

  DECIDER_QUEUE_COLUMN_KEYS.forEach((key) => {
    columns.set(key, sortQueueApplications(columns.get(key) ?? [], sortMode));
  });

  return columns;
}

export type QueueNavigation = {
  previousId: string | null;
  nextId: string | null;
  /** 1始まり。列に無ければ `null` */
  position: number | null;
  total: number;
};

/**
 * 「戻る → 探す → 開く」のループを消すための前後移動。
 *
 * **現在の申請が列に無いときは移動先を出さない。** 判断を確定した直後は列が変わるので、
 * そこで前後を出すと、利用者が見ていない並びの中を進ませることになる。
 */
export function getQueueNavigation(
  columnApplications: Application[],
  currentApplicationId: string | null | undefined,
): QueueNavigation {
  const currentId = normalizeGuid(currentApplicationId);
  const total = columnApplications.length;
  if (!currentId) return { previousId: null, nextId: null, position: null, total };

  const index = columnApplications.findIndex(
    (application) => normalizeGuid(application.ds_applicationid) === currentId,
  );
  if (index < 0) {
    return { previousId: null, nextId: null, position: null, total };
  }

  return {
    previousId:
      index > 0 ? columnApplications[index - 1].ds_applicationid : null,
    nextId:
      index < total - 1 ? columnApplications[index + 1].ds_applicationid : null,
    position: index + 1,
    total,
  };
}

export type PostDecisionTarget = {
  applicationId: string;
  title: string;
};

/**
 * 判断を確定した直後に出す「次の申請へ」の行き先。
 *
 * **確定した瞬間に、その申請は提出済み列から出る。** すると `getQueueNavigation` は
 * `position: null` を返し、前後移動が画面から消える（列が変わった並びを黙って
 * 進ませない、という第1段の判断は正しい）。ただしその結果、**判断者がいちばん多く通る
 * 遷移で「戻る → 探す → 開く」が生き残っていた**。
 *
 * そこで**確定前に捕まえておいた行き先**を使う。並びを取り直さないので、利用者が
 * 見ていた順のまま次へ進める。自動では飛ばさず、押せる導線として出すだけにする。
 *
 * 列の最後だった場合は `null`（次が無いのに出すと空振りする）。
 */
export function buildPostDecisionTarget({
  capturedNextId,
  applications,
}: {
  capturedNextId: string | null | undefined;
  applications: Application[];
}): PostDecisionTarget | null {
  const nextId = normalizeGuid(capturedNextId);
  if (!nextId) return null;

  const next = applications.find(
    (application) => normalizeGuid(application.ds_applicationid) === nextId,
  );
  /**
   * 一覧に無い ID なら出さない。**これは防御であって、現在の呼び出し側では起きない。**
   * `capturedNextId` は同じ `applications` から組んだ列の `nextId` なので必ず見つかる。
   * 別の経路から ID を渡すようになったときに効く（守っている、と読み違えないこと）。
   */
  if (!next) return null;

  return {
    applicationId: next.ds_applicationid,
    title: next.ds_name,
  };
}

/**
 * 判断キューから開いたときだけ前後移動を出すための文脈。URL に載せて持ち回る。
 * 申請リストや横断検索から開いた申請には出さない（利用者が並びを選んでいないため）。
 */
export type QueueContext = {
  column: DeciderQueueColumnKey;
  sortMode: QueueSortMode;
  categoryFilter: QueueCategoryFilter;
};

const SORT_MODES: QueueSortMode[] = ["due", "oldest"];

export function toQueueContextParams(context: QueueContext): Record<string, string> {
  return {
    qcol: context.column,
    qsort: context.sortMode,
    qcat: context.categoryFilter,
  };
}

export function parseQueueContext(
  params: URLSearchParams,
): QueueContext | null {
  const column = params.get("qcol");
  const sortMode = params.get("qsort");
  const categoryFilter = params.get("qcat");
  if (!column || !sortMode || !categoryFilter) return null;
  if (!DECIDER_QUEUE_COLUMN_KEYS.includes(column as DeciderQueueColumnKey)) {
    return null;
  }
  if (!SORT_MODES.includes(sortMode as QueueSortMode)) return null;

  return {
    column: column as DeciderQueueColumnKey,
    sortMode: sortMode as QueueSortMode,
    categoryFilter,
  };
}
