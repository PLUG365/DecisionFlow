import { DAY_IN_MS } from "./calendar-date";
import { normalizeGuid } from "./decisionflow-utils";

/**
 * 判断理由の下書き。**Dataverse には保存しない**（列追加も権限変更もしない）。
 * ブラウザのローカル保存だけで、画面遷移で書きかけが消える問題を塞ぐ。
 *
 * **判断選択肢は保存しない。** 古い選択が復元されたまま「判断を確定」を押されると、
 * 読み直さずに不可逆な判断が記録されうる。打ち直しが高くつくのは本文の方で、
 * 選択はクリック1回なので、危ない方を保存対象から外している。
 */
export type DecisionDraft = {
  text: string;
  savedAt: string;
};

/**
 * これより古い下書きは復元しない。数か月前の書きかけが「今の考え」として
 * 復元され、そのまま判断記録になるのを防ぐ。
 */
export const DECISION_DRAFT_TTL_DAYS = 30;



/**
 * 利用者ごとに分ける。ブラウザのプロファイルを共有している場合に、
 * 他人の書きかけを復元しないため。
 */
export function decisionDraftKey(
  systemUserId: string | null | undefined,
  applicationId: string | null | undefined,
): string | null {
  const user = normalizeGuid(systemUserId);
  const application = normalizeGuid(applicationId);
  if (!user || !application) return null;
  return `decisionflow:decision-draft:${user}:${application}`;
}

/** 空白だけの下書きは保存しない（`null` を返す＝保存済みの下書きを消す合図） */
export function serializeDecisionDraft(
  text: string,
  now: Date,
): string | null {
  if (!text.trim()) return null;
  return JSON.stringify({ text, savedAt: now.toISOString() });
}

export function parseDecisionDraft(
  raw: string | null | undefined,
  now: Date,
): DecisionDraft | null {
  if (!raw) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }

  if (!parsed || typeof parsed !== "object") return null;
  const record = parsed as Record<string, unknown>;
  const { text, savedAt } = record;
  if (typeof text !== "string" || !text.trim()) return null;
  if (typeof savedAt !== "string") return null;

  const savedAtMs = Date.parse(savedAt);
  if (Number.isNaN(savedAtMs)) return null;
  if (now.getTime() - savedAtMs > DECISION_DRAFT_TTL_DAYS * DAY_IN_MS) {
    return null;
  }

  return { text, savedAt };
}
