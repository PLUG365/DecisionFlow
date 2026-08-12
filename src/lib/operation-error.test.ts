import { describe, expect, it } from "vitest";

import {
  getOperationErrorMessage,
  isPermissionDeniedError,
} from "./operation-error";

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

describe("isPermissionDeniedError", () => {
  it.each([
    // G2 の実測で実際に返ってきた形（docs/UX_ROADMAP.md「G2 拒否系 実測」）
    [
      {
        status: 403,
        message:
          "Principal user is missing prvReadds_delegationhistory privilege",
      },
    ],
    [{ error: { code: "0x80040220", message: "Access denied" } }],
    [new Error("403 Forbidden")],
  ])("recognizes a Dataverse table-permission denial", (error) => {
    expect(isPermissionDeniedError(error)).toBe(true);
  });

  it.each([
    [new Error("401 Unauthorized")],
    [new Error("Failed to fetch")],
    [new Error("500 Internal Server Error")],
    [undefined],
  ])("does not treat a non-permission failure as denial", (error) => {
    expect(isPermissionDeniedError(error)).toBe(false);
  });

  it("handles a cyclic SDK error safely", () => {
    const error: Record<string, unknown> = { status: 403 };
    error.error = error;

    expect(
      getOperationErrorMessage(error, "保存に失敗しました。"),
    ).toContain("権限がありません");
  });
});
