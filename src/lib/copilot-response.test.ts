import { describe, expect, it } from "vitest";

import {
  buildCopilotRequestBody,
  COPILOT_NOTIFICATION_URL_PLACEHOLDER,
  extractCopilotConversationId,
  extractCopilotText,
  parseCopilotResponse,
} from "./copilot-response";

describe("copilot response text extraction", () => {
  it("prefers lastResponse", () => {
    expect(
      extractCopilotText({
        lastResponse: "最後の応答",
        responses: ["ひとつめ", "ふたつめ"],
      }),
    ).toBe("最後の応答");
  });

  it("joins responses when lastResponse is missing", () => {
    expect(extractCopilotText({ responses: ["ひとつめ", "ふたつめ"] })).toBe(
      "ひとつめ\n\nふたつめ",
    );
  });

  it("skips empty entries in responses", () => {
    expect(extractCopilotText({ responses: ["", "  ", "本文"] })).toBe("本文");
  });

  it("falls back through text, message and response", () => {
    expect(extractCopilotText({ text: "text値" })).toBe("text値");
    expect(extractCopilotText({ message: "message値" })).toBe("message値");
    expect(extractCopilotText({ response: "response値" })).toBe("response値");
  });

  it("unwraps a data-wrapped payload", () => {
    expect(extractCopilotText({ data: { lastResponse: "包まれた応答" } })).toBe(
      "包まれた応答",
    );
  });

  it("returns an empty string for unusable payloads", () => {
    expect(extractCopilotText(undefined)).toBe("");
    expect(extractCopilotText(null)).toBe("");
    expect(extractCopilotText("文字列")).toBe("");
    expect(extractCopilotText({ responses: [] })).toBe("");
  });
});

describe("copilot conversation id extraction", () => {
  it("accepts both camelCase and PascalCase", () => {
    expect(extractCopilotConversationId({ conversationId: "abc" })).toBe("abc");
    expect(extractCopilotConversationId({ ConversationId: "def" })).toBe("def");
  });

  it("looks inside a nested body", () => {
    expect(
      extractCopilotConversationId({ body: { conversationId: "ghi" } }),
    ).toBe("ghi");
    expect(
      extractCopilotConversationId({ data: { body: { ConversationId: "jkl" } } }),
    ).toBe("jkl");
  });

  it("returns undefined when absent or blank", () => {
    expect(extractCopilotConversationId({})).toBe(undefined);
    expect(extractCopilotConversationId({ conversationId: "   " })).toBe(
      undefined,
    );
    expect(extractCopilotConversationId(undefined)).toBe(undefined);
  });
});

describe("copilot request body", () => {
  it("never includes the agent name (it is a path parameter)", () => {
    const body = buildCopilotRequestBody({ message: "こんにちは" });

    expect(body).toEqual({
      message: "こんにちは",
      notificationUrl: COPILOT_NOTIFICATION_URL_PLACEHOLDER,
      locale: "ja-JP",
    });
    expect(body).not.toHaveProperty("agentName");
    expect(body).not.toHaveProperty("Copilot");
  });
});

describe("parseCopilotResponse", () => {
  it("returns both text and conversation id", () => {
    expect(
      parseCopilotResponse({
        data: { lastResponse: "応答", conversationId: "conv-1" },
      }),
    ).toEqual({ text: "応答", conversationId: "conv-1" });
  });
});
