import { describe, expect, it } from "vitest";

import {
  appendTemplateToBody,
  canInsertTemplate,
  getApplicationTemplate,
} from "./application-template";

const categories = [
  { ds_categoryid: "cat-1", ds_template: "1. 目的\n2. 影響範囲" },
  { ds_categoryid: "cat-2", ds_template: "   " },
  { ds_categoryid: "cat-3" },
];

describe("getApplicationTemplate", () => {
  it("returns the template of the selected category", () => {
    expect(getApplicationTemplate(categories, "cat-1")).toBe(
      "1. 目的\n2. 影響範囲",
    );
  });

  it("matches the category regardless of guid casing", () => {
    expect(getApplicationTemplate(categories, "CAT-1")).toBe(
      "1. 目的\n2. 影響範囲",
    );
  });

  it.each([
    ["a blank template", "cat-2"],
    ["a category without a template", "cat-3"],
    ["an unknown category", "cat-9"],
    ["no category", null],
  ])("returns null for %s", (_label, categoryId) => {
    expect(getApplicationTemplate(categories, categoryId)).toBeNull();
  });
});

describe("appendTemplateToBody", () => {
  it("fills an empty body with the template", () => {
    expect(appendTemplateToBody("", "1. 目的")).toBe("1. 目的");
    expect(appendTemplateToBody("   \n ", "1. 目的")).toBe("1. 目的");
  });

  it("keeps what the applicant already wrote and appends below", () => {
    // 置き換えにすると、少し書いてからテンプレートが欲しくなった入力が消える。
    expect(appendTemplateToBody("先に書いた内容", "1. 目的")).toBe(
      "先に書いた内容\n\n1. 目的",
    );
  });

  it("does not pile up trailing blank lines", () => {
    expect(appendTemplateToBody("先に書いた内容\n\n\n", "1. 目的")).toBe(
      "先に書いた内容\n\n1. 目的",
    );
  });

  it("does not duplicate the template when pressed twice", () => {
    const once = appendTemplateToBody("", "1. 目的");

    expect(appendTemplateToBody(once, "1. 目的")).toBe(once);
  });

  it("leaves the body untouched when there is no template", () => {
    expect(appendTemplateToBody("先に書いた内容", null)).toBe("先に書いた内容");
  });
});

describe("canInsertTemplate", () => {
  it("allows inserting when the body does not have the template yet", () => {
    expect(canInsertTemplate("", "1. 目的")).toBe(true);
    expect(canInsertTemplate("先に書いた内容", "1. 目的")).toBe(true);
  });

  it.each([
    ["there is no template", "本文", null],
    ["the template is already in the body", "1. 目的\n続き", "1. 目的"],
  ])("refuses when %s", (_label, body, template) => {
    expect(canInsertTemplate(body, template)).toBe(false);
  });
});
