/**
 * Copilot Studio コネクタ (`ExecuteCopilotAsyncV2`) のレスポンス解析。
 *
 * このコネクタは型上 `IOperationResult<void>` を返すが、実際には本文が入っている。
 * さらに SDK のバージョンによって `data` でラップされる場合とされない場合があり、
 * `conversationId` はキャメルケース／パスカルケースが混在する。
 * 解析ロジックをここに閉じ込めてテスト可能にする。
 */

export type ParsedCopilotResponse = {
  text: string;
  conversationId?: string;
};

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : undefined;
}

function asNonEmptyString(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const trimmed = value.trim();
  return trimmed ? trimmed : undefined;
}

/** `data` でラップされる場合とされない場合の両方に対応する。 */
function unwrap(result: unknown): Record<string, unknown> | undefined {
  const root = asRecord(result);
  if (!root) return undefined;
  return asRecord(root.data) ?? root;
}

export function extractCopilotConversationId(
  result: unknown,
): string | undefined {
  const data = unwrap(result);
  if (!data) return undefined;

  const nested = asRecord(data.body);
  return (
    asNonEmptyString(data.conversationId) ??
    asNonEmptyString(data.ConversationId) ??
    asNonEmptyString(nested?.conversationId) ??
    asNonEmptyString(nested?.ConversationId)
  );
}

export function extractCopilotText(result: unknown): string {
  const data = unwrap(result);
  if (!data) return "";

  const lastResponse = asNonEmptyString(data.lastResponse);
  if (lastResponse) return lastResponse;

  if (Array.isArray(data.responses)) {
    const joined = data.responses
      .map((item) => asNonEmptyString(item))
      .filter((item): item is string => Boolean(item))
      .join("\n\n");
    if (joined) return joined;
  }

  return (
    asNonEmptyString(data.text) ??
    asNonEmptyString(data.message) ??
    asNonEmptyString(data.response) ??
    ""
  );
}

export function parseCopilotResponse(result: unknown): ParsedCopilotResponse {
  return {
    text: extractCopilotText(result),
    conversationId: extractCopilotConversationId(result),
  };
}

/**
 * `ExecuteCopilotAsyncV2` の body。
 * エージェント名は `Copilot` パスパラメータで渡すため **body に含めてはいけない**。
 * 含めると `{"success":false,"error":{}}` が返る。
 * `notificationUrl` はスキーマ上必須で、プレースホルダで構わない。
 */
export const COPILOT_NOTIFICATION_URL_PLACEHOLDER =
  "https://notificationurlplaceholder";

export function buildCopilotRequestBody(input: {
  message: string;
  locale?: string;
}): Record<string, unknown> {
  return {
    message: input.message,
    notificationUrl: COPILOT_NOTIFICATION_URL_PLACEHOLDER,
    locale: input.locale ?? "ja-JP",
  };
}
