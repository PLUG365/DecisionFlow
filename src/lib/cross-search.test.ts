import { describe, expect, it } from "vitest";

import { searchDecisionFlow } from "./cross-search";

const data = {
  applications: [
    {
      ds_applicationid: "app-1",
      ds_name: "SaaS導入",
      ds_body: "顧客情報の保管先を確認する",
    },
  ],
  messages: [
    {
      ds_messageid: "message-1",
      ds_name: "セキュリティ確認",
      ds_body: "SSOの追加費用を確認してください",
      _ds_applicationid_value: "app-1",
    },
  ],
  decisions: [
    {
      ds_decisionid: "decision-1",
      ds_name: "SaaS導入 - 判断",
      ds_rationale: "保管リージョンが未確認のため差し戻し",
      _ds_applicationid_value: "app-1",
    },
  ],
  resources: [
    {
      ds_applicationresourceid: "resource-1",
      ds_name: "製品仕様書",
      ds_description: "セキュリティ仕様",
      _ds_applicationid_value: "app-1",
    },
  ],
};

describe("searchDecisionFlow", () => {
  it("searches applications, messages, decisions, and resources", () => {
    expect(searchDecisionFlow({ ...data, query: "顧客情報" })[0].kind).toBe(
      "application",
    );
    expect(searchDecisionFlow({ ...data, query: "追加費用" })[0].kind).toBe(
      "message",
    );
    expect(searchDecisionFlow({ ...data, query: "リージョン 未確認" })[0].kind).toBe(
      "decision",
    );
    expect(searchDecisionFlow({ ...data, query: "製品仕様書" })[0].kind).toBe(
      "resource",
    );
  });

  it("normalizes full-width characters, case, and whitespace", () => {
    expect(
      searchDecisionFlow({ ...data, query: "  ｓａａｓ   導入 " })[0].id,
    ).toBe("application:app-1");
  });

  it("returns no results for empty or unrelated queries", () => {
    expect(searchDecisionFlow({ ...data, query: " " })).toEqual([]);
    expect(searchDecisionFlow({ ...data, query: "存在しない語" })).toEqual([]);
  });
});
