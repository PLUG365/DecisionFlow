import type { Category } from "@/types/decisionflow";
import { normalizeGuid } from "./decisionflow-utils";

/**
 * カテゴリ別の申請テンプレート。
 *
 * B1 で入れたテンプレートは **placeholder（ゴースト文字）としてしか出ていなかった**ので、
 * 申請者は書式を見ながら自分で打ち直すしかなかった。本文へ入れられるようにする。
 */
export function getApplicationTemplate(
  categories: Pick<Category, "ds_categoryid" | "ds_template">[],
  categoryId: string | null | undefined,
): string | null {
  const selectedId = normalizeGuid(categoryId);
  if (!selectedId) return null;

  const category = categories.find(
    (item) => normalizeGuid(item.ds_categoryid) === selectedId,
  );
  const template = category?.ds_template?.trim();
  return template ? template : null;
}

/**
 * テンプレートを本文へ入れる。**書きかけを消さない。**
 *
 * 置き換えにすると、少し書いてからテンプレートが欲しくなった利用者の入力が消える。
 * 本文があるときは末尾へ足すだけにして、破壊的な経路を作らない。
 */
export function appendTemplateToBody(
  currentBody: string,
  template: string | null,
): string {
  if (!template) return currentBody;
  if (!currentBody.trim()) return template;
  // 続けて押しても増えない
  if (currentBody.includes(template)) return currentBody;
  return `${currentBody.replace(/\s+$/, "")}\n\n${template}`;
}

/**
 * 挿入ボタンを出してよいか。テンプレートが無いカテゴリでは押せる意味がない。
 * **既に本文へ入っている場合も出さない**（押しても何も起きないボタンを見せない）。
 */
export function canInsertTemplate(
  currentBody: string,
  template: string | null,
): boolean {
  if (!template) return false;
  return !currentBody.includes(template);
}
