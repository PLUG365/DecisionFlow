import { describe, expect, it } from "vitest";
import {
  buildApplicationDetailParams,
  buildQueueSiblingPath,
  getQueueShortcutDirection,
  isEditableElement,
  parseApplicationDetailTab,
  toApplicationDetailTab,
} from "./application-detail-url";
import type { QueueContext } from "./queue-sequence";

const queueContext: QueueContext = {
  column: "submitted",
  sortMode: "due",
  categoryFilter: "all",
};

describe("parseApplicationDetailTab", () => {
  it("既知のタブをそのまま返す", () => {
    expect(parseApplicationDetailTab(new URLSearchParams("tab=decision"))).toBe(
      "decision",
    );
  });

  it("未知の値と欠落は概要へ落とす", () => {
    expect(parseApplicationDetailTab(new URLSearchParams("tab=unknown"))).toBe(
      "summary",
    );
    expect(parseApplicationDetailTab(new URLSearchParams(""))).toBe("summary");
  });
});

describe("toApplicationDetailTab", () => {
  it("既知のタブ名だけ通す", () => {
    expect(toApplicationDetailTab("people")).toBe("people");
    expect(toApplicationDetailTab("nope")).toBe("summary");
    expect(toApplicationDetailTab(null)).toBe("summary");
    expect(toApplicationDetailTab(undefined)).toBe("summary");
  });
});

describe("buildApplicationDetailParams", () => {
  it("既定タブでは tab を書かない", () => {
    expect(
      buildApplicationDetailParams({ tab: "summary", queueContext: null }),
    ).toEqual({});
  });

  it("既定タブ以外は tab を書く", () => {
    expect(
      buildApplicationDetailParams({ tab: "decision", queueContext: null }),
    ).toEqual({ tab: "decision" });
  });

  /**
   * これが C5 第1段の不具合そのもの。判断タブへ移った瞬間に判断キュー文脈が
   * 消え、「判断キュー N / 総数」と前後移動が画面から無くなっていた。
   */
  it("タブを変えても判断キュー文脈を落とさない", () => {
    expect(
      buildApplicationDetailParams({ tab: "decision", queueContext }),
    ).toEqual({
      tab: "decision",
      qcol: "submitted",
      qsort: "due",
      qcat: "all",
    });
  });

  it("概要へ戻っても判断キュー文脈は残る", () => {
    expect(
      buildApplicationDetailParams({ tab: "summary", queueContext }),
    ).toEqual({ qcol: "submitted", qsort: "due", qcat: "all" });
  });
});

describe("buildQueueSiblingPath", () => {
  /** 「判断パネルを開いたまま次へ送る」= 移動先でも判断タブのままであること。 */
  it("移動先でも今見ているタブを保つ", () => {
    const path = buildQueueSiblingPath({
      applicationId: "abc-123",
      tab: "decision",
      queueContext,
    });
    const params = new URLSearchParams(path.split("?")[1]);
    expect(path.startsWith("/applications/abc-123?")).toBe(true);
    expect(params.get("tab")).toBe("decision");
    expect(params.get("qcol")).toBe("submitted");
  });

  it("概要のままなら tab は付けず、キュー文脈だけ持ち回る", () => {
    const path = buildQueueSiblingPath({
      applicationId: "abc-123",
      tab: "summary",
      queueContext,
    });
    expect(path).toBe("/applications/abc-123?qcol=submitted&qsort=due&qcat=all");
  });
});

describe("getQueueShortcutDirection", () => {
  it("[ と ] を前後に割り当てる", () => {
    expect(getQueueShortcutDirection({ key: "[" })).toBe("previous");
    expect(getQueueShortcutDirection({ key: "]" })).toBe("next");
  });

  it("割り当てのないキーは無視する", () => {
    expect(getQueueShortcutDirection({ key: "a" })).toBeNull();
    expect(getQueueShortcutDirection({ key: "ArrowRight" })).toBeNull();
  });

  /** 判断理由を書いている最中に画面が飛ばないこと。 */
  it("入力欄に焦点があるときは発火しない", () => {
    expect(
      getQueueShortcutDirection({ key: "]", isEditableTarget: true }),
    ).toBeNull();
  });

  it("IME 変換中は発火しない", () => {
    expect(
      getQueueShortcutDirection({ key: "]", isComposing: true }),
    ).toBeNull();
  });

  /**
   * 申請詳細は `id` が変わっても再マウントされず、モーダルの開閉状態と入力値が
   * 次の申請へ持ち越される。ボタンはオーバーレイに隠れるがキーは届いてしまう。
   */
  it("モーダルが開いている間は発火しない", () => {
    expect(
      getQueueShortcutDirection({ key: "]", isDialogOpen: true }),
    ).toBeNull();
    expect(
      getQueueShortcutDirection({ key: "[", isDialogOpen: true }),
    ).toBeNull();
  });

  it("修飾キー付きは見送る", () => {
    expect(getQueueShortcutDirection({ key: "]", ctrlKey: true })).toBeNull();
    expect(getQueueShortcutDirection({ key: "]", metaKey: true })).toBeNull();
    expect(getQueueShortcutDirection({ key: "]", altKey: true })).toBeNull();
    expect(getQueueShortcutDirection({ key: "]", shiftKey: true })).toBeNull();
  });
});

describe("isEditableElement", () => {
  it("入力系のタグを編集中とみなす", () => {
    expect(isEditableElement({ tagName: "INPUT" })).toBe(true);
    expect(isEditableElement({ tagName: "textarea" })).toBe(true);
    expect(isEditableElement({ tagName: "SELECT" })).toBe(true);
  });

  it("contenteditable も編集中とみなす", () => {
    expect(isEditableElement({ tagName: "DIV", isContentEditable: true })).toBe(
      true,
    );
  });

  it("それ以外は編集中ではない", () => {
    expect(isEditableElement({ tagName: "BUTTON" })).toBe(false);
    expect(isEditableElement(null)).toBe(false);
    expect(isEditableElement(undefined)).toBe(false);
  });
});
