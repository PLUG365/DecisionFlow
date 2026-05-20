export type InitialDataRow = {
  ds_name: string;
  ds_description?: string;
  ds_template?: string;
  ds_sortorder?: number;
};

export const DEFAULT_CATEGORIES = [
  {
    ds_name: "顧客案件",
    ds_description: "顧客に関わる見積、契約、提案、例外対応など",
    ds_template: "背景 / 顧客影響 / 判断してほしいこと / 期限 / 関連資料",
    ds_sortorder: 1,
  },
  {
    ds_name: "部内案件",
    ds_description: "部内で判断が必要な施策や運用変更",
    ds_template: "目的 / 対象範囲 / 選択肢 / 推奨案 / 懸念点",
    ds_sortorder: 2,
  },
  {
    ds_name: "課内案件",
    ds_description: "課内の業務改善や進め方の判断",
    ds_template: "現状 / 課題 / 提案 / 必要な判断 / 希望期限",
    ds_sortorder: 3,
  },
  {
    ds_name: "他部署案件",
    ds_description: "他部署との調整や合意が必要な案件",
    ds_template: "関係部署 / 依頼事項 / 影響範囲 / 期限 / 未解決事項",
    ds_sortorder: 4,
  },
  {
    ds_name: "事務処理",
    ds_description: "定型的な承認・確認が必要な事務処理",
    ds_template: "処理内容 / 根拠 / 期限 / 添付資料",
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
