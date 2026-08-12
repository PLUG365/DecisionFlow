import { toQueueContextParams, type QueueContext } from "./queue-sequence";

/**
 * 申請詳細のクエリ文字列の**唯一の持ち主**。
 *
 * ここを1本にしたのは、C5 第1段の前後移動が「判断タブを押した瞬間に消える」不具合を
 * 出したためである。原因はタブ切替が `setSearchParams({ tab })` でクエリを**丸ごと
 * 置き換え**、判断キューの文脈（`qcol` / `qsort` / `qcat`）を落としていたこと。
 * 書き手が2箇所あってどちらも全体を書いていた、という形の壊れ方だった。
 *
 * **タブと判断キュー文脈は同じクエリ文字列に同居する。** 片方だけを書く経路を
 * 作らないため、URL を組み立てるのは `buildApplicationDetailParams` だけにする。
 */
export const APPLICATION_DETAIL_TABS = [
  "summary",
  "timeline",
  "thread",
  "resources",
  "people",
  "decision",
] as const;

export type ApplicationDetailTab = (typeof APPLICATION_DETAIL_TABS)[number];

export const DEFAULT_APPLICATION_DETAIL_TAB: ApplicationDetailTab = "summary";

/** 未知の値・欠落は概要へ落とす（URL を手で書き換えられても壊れないため）。 */
export function toApplicationDetailTab(
  value: string | null | undefined,
): ApplicationDetailTab {
  return APPLICATION_DETAIL_TABS.includes(value as ApplicationDetailTab)
    ? (value as ApplicationDetailTab)
    : DEFAULT_APPLICATION_DETAIL_TAB;
}

export function parseApplicationDetailTab(
  params: URLSearchParams,
): ApplicationDetailTab {
  return toApplicationDetailTab(params.get("tab"));
}

/**
 * 既定タブ（概要）では `tab` を書かない。URL を短く保つ既存の挙動を維持する。
 * 判断キュー文脈は**あれば必ず持ち回る**。
 */
export function buildApplicationDetailParams({
  tab,
  queueContext,
}: {
  tab: ApplicationDetailTab;
  queueContext: QueueContext | null;
}): Record<string, string> {
  return {
    ...(tab === DEFAULT_APPLICATION_DETAIL_TAB ? {} : { tab }),
    ...(queueContext ? toQueueContextParams(queueContext) : {}),
  };
}

/**
 * 判断キューの隣の申請へ移るときの URL。**今見ているタブを保つ**のが要点で、
 * これが「判断パネルを開いたまま次へ送る」体験そのものになる。
 * 保たないと、次の申請ごとに判断タブを押し直すことになる。
 */
export function buildQueueSiblingPath({
  applicationId,
  tab,
  queueContext,
}: {
  applicationId: string;
  tab: ApplicationDetailTab;
  queueContext: QueueContext;
}): string {
  const params = new URLSearchParams(
    buildApplicationDetailParams({ tab, queueContext }),
  ).toString();
  return `/applications/${applicationId}${params ? `?${params}` : ""}`;
}

export type QueueShortcutDirection = "previous" | "next";

/**
 * キーボードでの前後移動を「発火してよいか」まで含めて判定する。
 *
 * **入力中は絶対に発火させない。** 判断理由を書いている最中に画面が切り替わると、
 * 書きかけが視界から消える（C4 の下書き保存はローカルにあるが、消えたように見える）。
 * IME 変換中（`isComposing`）も同様に外す。日本語入力では確定前のキーが届く。
 *
 * **重なりものが開いている間も発火させない。** 対象はモーダルと**選択リスト**の両方。
 *
 * - モーダル: 申請詳細はルートが同じまま `id` だけ変わるため、コンポーネントが
 *   再マウントされず**開閉状態と入力値が次の申請へ持ち越される**。ボタンは
 *   オーバーレイに隠れて押せないが、キーボードはそこを素通りする
 * - 選択リスト: Radix の `Select` を開くと**焦点は `div[role="option"]` に載る**。
 *   入力欄ではないので編集中の判定に引っかからない。実測で
 *   `listbox: 1 / dialog: 0 / activeRole: option` を確認しており、
 *   **判断選択肢を選んでいる最中に次の申請へ飛ぶ**経路が実在した（2026-08-12）
 *
 * 修飾キー付きは全部見送る。ブラウザや OS の割り当てを奪わないため。
 */
export function getQueueShortcutDirection(source: {
  key: string;
  altKey?: boolean;
  ctrlKey?: boolean;
  metaKey?: boolean;
  shiftKey?: boolean;
  isComposing?: boolean;
  isEditableTarget?: boolean;
  isOverlayOpen?: boolean;
}): QueueShortcutDirection | null {
  if (source.altKey || source.ctrlKey || source.metaKey || source.shiftKey) {
    return null;
  }
  if (source.isComposing) return null;
  if (source.isEditableTarget) return null;
  if (source.isOverlayOpen) return null;

  if (source.key === "[") return "previous";
  if (source.key === "]") return "next";
  return null;
}

/**
 * 画面に重なっているものが開いているか。個々の state を数え上げずに一括で見る。
 *
 * **どれも閉じるとDOMから消えることを実測で確認済み**（2026-08-12・公開版）。
 * 閉じても残る作りだと、このセレクタが一致し続けてショートカットが永久に死ぬ。
 * `forceMount` を使うときはここを見直すこと。
 */
export const OPEN_OVERLAY_SELECTOR =
  '[role="dialog"],[role="alertdialog"],[role="listbox"]';

/** 入力欄・テキストエリア・リッチテキストのどれかに焦点があるか。 */
export function isEditableElement(element: unknown): boolean {
  if (!element || typeof element !== "object") return false;
  const candidate = element as {
    tagName?: unknown;
    isContentEditable?: unknown;
  };
  if (candidate.isContentEditable === true) return true;
  const tagName =
    typeof candidate.tagName === "string" ? candidate.tagName.toUpperCase() : "";
  return tagName === "INPUT" || tagName === "TEXTAREA" || tagName === "SELECT";
}
