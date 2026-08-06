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
    "（この行はアプリが自動付与した参考情報です。ユーザーの発言は次の行から）",
    trimmed,
  ].join("\n");
}
