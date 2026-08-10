/**
 * アプリの現在地をエージェントへ渡すための文脈生成。
 *
 * この文脈ブロックは**アプリから開いたときだけ**付く。Teams などで
 * エージェントを単独利用する場合は付かないため、エージェント側は
 * 文脈が無くても成立する作りである必要がある（追加情報として扱う）。
 */

export type CopilotScreenContext = {
  screenLabel: string;
  applicationId?: string;
};

const SCREEN_LABELS: Record<string, string> = {
  dashboard: "ダッシュボード",
  applications: "申請リスト",
  queue: "判断キュー",
  mentions: "メンション",
  resources: "関連資料",
  masters: "マスタ管理",
};

const UNKNOWN_SCREEN_LABEL = "DecisionFlow";

export function getCopilotScreenContext(
  pathname: string | null | undefined,
): CopilotScreenContext {
  const segments = (pathname ?? "")
    .split("/")
    .map((segment) => segment.trim())
    .filter(Boolean);

  const [first, second] = segments;
  if (!first) return { screenLabel: UNKNOWN_SCREEN_LABEL };

  if (first === "applications" && second) {
    return { screenLabel: "申請詳細", applicationId: second };
  }

  return { screenLabel: SCREEN_LABELS[first] ?? UNKNOWN_SCREEN_LABEL };
}

/**
 * このパネルは Adaptive Card を描画できない。
 *
 * `ExecuteCopilotAsyncV2` の応答契約はテキスト（`message`）だけで、添付や activity を
 * 運ばない。パネル側にもカードのレンダラは無い。そのため判断確定トピックがここで
 * 起動すると、`issue_decision_card` が `ds_decisioncard` を発行して Teams で出した
 * カードを Superseded にしたうえで、カードが表示できずに行き止まる。
 *
 * エージェントへ制約を伝えて、パネルでは判断確定トピックへ入らせない。
 * **これはモデルの従い方に依存する暫定策**であり、確実に塞ぐならトピック側で
 * `System.Activity.ChannelId` を見るのが本筋（docs/AGENT_WRITE_BOUNDARY.md）。
 */
const PANEL_CAPABILITY_NOTE =
  "この画面は Adaptive Card を表示できません。カードを出す操作（判断の確定）はここでは実行せず、判断タブへ案内してください。";

export function buildCopilotMessageWithContext(
  message: string,
  context: CopilotScreenContext,
): string {
  const trimmed = message.trim();
  const parts = [`画面: ${context.screenLabel}`];
  if (context.applicationId) {
    parts.push(`申請ID: ${context.applicationId}`);
  }

  return [
    `[DecisionFlow アプリの文脈] ${parts.join(" / ")}`,
    `[この画面の制約] ${PANEL_CAPABILITY_NOTE}`,
    "（上の2行はアプリが自動付与した参考情報です。ユーザーの発言は次の行から）",
    trimmed,
  ].join("\n");
}
