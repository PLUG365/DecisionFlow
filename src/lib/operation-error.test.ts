import { describe, expect, it } from "vitest";

import { getOperationErrorMessage } from "./operation-error";

describe("getOperationErrorMessage", () => {
  it.each([
    [new Error("401 Unauthorized"), "サインイン状態を確認"],
    [{ status: 403, message: "Forbidden" }, "権限がありません"],
    [{ error: { code: 404, message: "Not Found" } }, "対象が見つかりません"],
    [new Error("412 precondition failed"), "他の変更が反映されています"],
    [new Error("Failed to fetch"), "通信状態を確認"],
  ])("maps a known failure without exposing raw details", (error, expected) => {
    const message = getOperationErrorMessage(error, "保存に失敗しました。");

    expect(message).toContain(expected);
    expect(message).not.toContain("Forbidden");
    expect(message).not.toContain("precondition");
    expect(message).not.toContain("Failed to fetch");
  });

  it("uses safe generic guidance for an unknown error", () => {
    const message = getOperationErrorMessage(
      new Error("secret backend detail"),
      "保存に失敗しました。",
    );

    expect(message).toBe(
      "保存に失敗しました。 時間をおいてもう一度お試しください。",
    );
    expect(message).not.toContain("secret backend detail");
  });

  it("handles a cyclic SDK error safely", () => {
    const error: Record<string, unknown> = { status: 403 };
    error.error = error;

    expect(
      getOperationErrorMessage(error, "保存に失敗しました。"),
    ).toContain("権限がありません");
  });
});
