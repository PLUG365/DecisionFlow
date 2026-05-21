export type InitialDataRow = {
  ds_name: string;
  ds_description?: string;
  ds_template?: string;
  ds_regulationtext?: string;
  ds_sortorder?: number;
};

export const DEFAULT_CATEGORIES = [
  {
    ds_name: "顧客案件",
    ds_description: "顧客に関わる見積、契約、提案、例外対応など",
    ds_template: "背景 / 顧客影響 / 判断してほしいこと / 期限 / 関連資料",
    ds_regulationtext:
      "顧客影響、契約条件、収益影響、例外条件の妥当性を確認する。重要顧客対応の場合は、短期的な採算だけでなく継続取引への影響とリスク低減策も確認する。",
    ds_sortorder: 1,
  },
  {
    ds_name: "部内案件",
    ds_description: "部内で判断が必要な施策や運用変更",
    ds_template: "目的 / 対象範囲 / 選択肢 / 推奨案 / 懸念点",
    ds_regulationtext:
      "目的、対象範囲、必要工数、既存業務への影響、代替案を確認する。部内メンバーの負荷や運用定着の見込みが説明されているか確認する。",
    ds_sortorder: 2,
  },
  {
    ds_name: "課内案件",
    ds_description: "課内の業務改善や進め方の判断",
    ds_template: "現状 / 課題 / 提案 / 必要な判断 / 希望期限",
    ds_regulationtext:
      "現状課題、期待効果、実施範囲、担当、期限を確認する。課内で完結できる判断か、上位者や他部署の合意が必要かも確認する。",
    ds_sortorder: 3,
  },
  {
    ds_name: "他部署案件",
    ds_description: "他部署との調整や合意が必要な案件",
    ds_template: "関係部署 / 依頼事項 / 影響範囲 / 期限 / 未解決事項",
    ds_regulationtext:
      "関係部署、依頼事項、影響範囲、合意状況、未解決事項を確認する。相手部署の責任範囲、期限、コミュニケーション計画が明確か確認する。",
    ds_sortorder: 4,
  },
  {
    ds_name: "事務処理",
    ds_description: "定型的な承認・確認が必要な事務処理",
    ds_template: "処理内容 / 根拠 / 期限 / 添付資料",
    ds_regulationtext:
      "処理内容、根拠資料、期限、必要な添付資料、承認条件を確認する。定型処理から外れる例外や不備がある場合は、差し戻しまたは追加確認の必要性を確認する。",
    ds_sortorder: 5,
  },
] as const satisfies readonly InitialDataRow[];

export const DEFAULT_DECISION_OPTIONS = [
  {
    ds_name: "承認",
    ds_description: "申請内容を承認する",
    ds_sortorder: 1,
  },
  {
    ds_name: "却下",
    ds_description: "申請内容を却下する",
    ds_sortorder: 2,
  },
  {
    ds_name: "差し戻し",
    ds_description: "追加情報や修正を求めて差し戻す",
    ds_sortorder: 3,
  },
] as const satisfies readonly InitialDataRow[];

export function getMissingInitialRows<TExisting extends { ds_name?: string }>(
  existingRows: readonly TExisting[],
  requiredRows: readonly InitialDataRow[],
) {
  const existingNames = new Set(
    existingRows
      .map((row) => row.ds_name?.trim())
      .filter((name): name is string => Boolean(name)),
  );
  return requiredRows.filter((row) => !existingNames.has(row.ds_name));
}
