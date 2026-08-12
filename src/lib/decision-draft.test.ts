import { describe, expect, it } from "vitest";

import {
  DECISION_DRAFT_TTL_DAYS,
  decisionDraftKey,
  parseDecisionDraft,
  serializeDecisionDraft,
} from "./decision-draft";

const now = new Date("2026-08-12T09:00:00Z");

describe("decisionDraftKey", () => {
  it("separates drafts by user and application", () => {
    expect(decisionDraftKey("user-1", "app-1")).not.toBe(
      decisionDraftKey("user-2", "app-1"),
    );
    expect(decisionDraftKey("user-1", "app-1")).not.toBe(
      decisionDraftKey("user-1", "app-2"),
    );
  });

  it("treats guid casing as the same key", () => {
    expect(decisionDraftKey("USER-1", "APP-1")).toBe(
      decisionDraftKey("user-1", "app-1"),
    );
  });

  it.each([
    [null, "app-1"],
    ["user-1", null],
    ["  ", "app-1"],
  ])("refuses to build a key without both ids", (user, application) => {
    expect(decisionDraftKey(user, application)).toBeNull();
  });
});

describe("serializeDecisionDraft", () => {
  it("keeps the text as typed, including leading whitespace", () => {
    const raw = serializeDecisionDraft("  検討中の理由", now);

    expect(parseDecisionDraft(raw, now)).toEqual({
      text: "  検討中の理由",
      savedAt: "2026-08-12T09:00:00.000Z",
    });
  });

  it.each(["", "   ", "\n\t"])(
    "returns null for blank text so the stored draft is removed",
    (text) => {
      expect(serializeDecisionDraft(text, now)).toBeNull();
    },
  );
});

describe("parseDecisionDraft", () => {
  it("restores a draft saved just inside the retention window", () => {
    const raw = serializeDecisionDraft("まだ書きかけ", now);
    const almostExpired = new Date(
      now.getTime() + DECISION_DRAFT_TTL_DAYS * 24 * 60 * 60 * 1000,
    );

    expect(parseDecisionDraft(raw, almostExpired)?.text).toBe("まだ書きかけ");
  });

  it("drops a draft past the retention window", () => {
    // 数か月前の書きかけが「今の考え」として復元され、そのまま判断記録になるのを防ぐ。
    const raw = serializeDecisionDraft("古い考え", now);
    const expired = new Date(
      now.getTime() + (DECISION_DRAFT_TTL_DAYS + 1) * 24 * 60 * 60 * 1000,
    );

    expect(parseDecisionDraft(raw, expired)).toBeNull();
  });

  it.each([
    ["nothing stored", null],
    ["a non-JSON value", "not json"],
    ["a JSON primitive", '"just a string"'],
    ["a missing text field", '{"savedAt":"2026-08-12T09:00:00.000Z"}'],
    ["a blank text field", '{"text":"  ","savedAt":"2026-08-12T09:00:00.000Z"}'],
    ["a missing timestamp", '{"text":"理由"}'],
    ["an unparseable timestamp", '{"text":"理由","savedAt":"こわれた日付"}'],
  ])("returns null for %s", (_label, raw) => {
    expect(parseDecisionDraft(raw, now)).toBeNull();
  });
});
