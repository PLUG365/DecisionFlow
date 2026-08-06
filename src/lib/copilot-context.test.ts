import { describe, expect, it } from "vitest";

import {
  buildCopilotMessageWithContext,
  getCopilotScreenContext,
} from "./copilot-context";

describe("copilot screen context", () => {
  it("maps known screens to Japanese labels", () => {
    expect(getCopilotScreenContext("/dashboard")).toEqual({
      screenLabel: "ダッシュボード",
    });
    expect(getCopilotScreenContext("/queue")).toEqual({
      screenLabel: "判断キュー",
    });
    expect(getCopilotScreenContext("/masters")).toEqual({
      screenLabel: "マスタ管理",
    });
  });

  it("extracts the application id on the detail screen", () => {
    expect(getCopilotScreenContext("/applications/abc-123")).toEqual({
      screenLabel: "申請詳細",
      applicationId: "abc-123",
    });
  });

  it("treats the application list as a list, not a detail", () => {
    expect(getCopilotScreenContext("/applications")).toEqual({
      screenLabel: "申請リスト",
    });
    expect(getCopilotScreenContext("/applications/")).toEqual({
      screenLabel: "申請リスト",
    });
  });

  it("falls back for unknown or empty paths", () => {
    expect(getCopilotScreenContext("/")).toEqual({
      screenLabel: "DecisionFlow",
    });
    expect(getCopilotScreenContext("")).toEqual({
      screenLabel: "DecisionFlow",
    });
    expect(getCopilotScreenContext(undefined)).toEqual({
      screenLabel: "DecisionFlow",
    });
    expect(getCopilotScreenContext("/unknown-screen")).toEqual({
      screenLabel: "DecisionFlow",
    });
  });
});

describe("copilot message with context", () => {
  it("prefixes the screen and keeps the user text last", () => {
    const built = buildCopilotMessageWithContext("判断待ちを見せて", {
      screenLabel: "判断キュー",
    });

    expect(built).toContain("画面: 判断キュー");
    expect(built.endsWith("判断待ちを見せて")).toBe(true);
    expect(built).not.toContain("申請ID");
  });

  it("includes the application id when on a detail screen", () => {
    const built = buildCopilotMessageWithContext("この申請どう思う？", {
      screenLabel: "申請詳細",
      applicationId: "abc-123",
    });

    expect(built).toContain("画面: 申請詳細");
    expect(built).toContain("申請ID: abc-123");
    expect(built.endsWith("この申請どう思う？")).toBe(true);
  });

  it("trims the user message", () => {
    const built = buildCopilotMessageWithContext("  余白あり  ", {
      screenLabel: "ダッシュボード",
    });

    expect(built.endsWith("余白あり")).toBe(true);
  });
});
