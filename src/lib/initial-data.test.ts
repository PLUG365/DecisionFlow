import { describe, expect, it } from "vitest";

import {
  DEFAULT_CATEGORIES,
  DEFAULT_DECISION_OPTIONS,
  getMissingInitialRows,
} from "./initial-data";

describe("initial data", () => {
  it("defines the default categories used by setup_dataverse.py", () => {
    expect(DEFAULT_CATEGORIES.map((category) => category.ds_name)).toEqual([
      "顧客案件",
      "部内案件",
      "課内案件",
      "他部署案件",
      "事務処理",
    ]);
  });

  it("defines default regulation text for every startup category", () => {
    expect(DEFAULT_CATEGORIES).toHaveLength(5);
    for (const category of DEFAULT_CATEGORIES) {
      expect(category.ds_regulationtext?.trim()).toBeTruthy();
      expect(category.ds_regulationtext).toContain("確認");
    }
  });

  it("defines the fixed decision options as startup seed data", () => {
    expect(DEFAULT_DECISION_OPTIONS).toEqual([
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
    ]);
  });

  it("returns only rows missing by name", () => {
    const missing = getMissingInitialRows(
      [
        { ds_name: "承認", ds_description: "申請内容を承認する" },
        {
          ds_name: "差し戻し",
          ds_description: "追加情報や修正を求めて差し戻す",
        },
      ],
      DEFAULT_DECISION_OPTIONS,
    );

    expect(missing.map((row) => row.ds_name)).toEqual(["却下"]);
  });
});
