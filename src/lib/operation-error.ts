function getErrorText(
  error: unknown,
  seen = new Set<object>(),
  depth = 0,
): string {
  if (typeof error === "string") return error;
  if (error instanceof Error) {
    return `${error.name} ${error.message}`;
  }
  if (!error || typeof error !== "object" || depth > 2 || seen.has(error)) {
    return "";
  }

  seen.add(error);
  const record = error as Record<string, unknown>;
  return [
    record.status,
    record.statusCode,
    record.code,
    record.name,
    record.message,
    record.error && getErrorText(record.error, seen, depth + 1),
  ]
    .filter((value) => value !== undefined && value !== null)
    .map(String)
    .join(" ");
}

export function getOperationErrorMessage(
  error: unknown,
  fallback: string,
): string {
  const text = getErrorText(error).toLowerCase();

  if (/\b401\b|unauthenticated|unauthorized|認証/.test(text)) {
    return `${fallback} サインイン状態を確認して、もう一度お試しください。`;
  }
  if (/\b403\b|forbidden|access denied|privilege|permission|権限/.test(text)) {
    return `${fallback} この操作を行う権限がありません。`;
  }
  if (/\b404\b|not found|does not exist|見つかりません/.test(text)) {
    return `${fallback} 対象が見つかりません。画面を更新してください。`;
  }
  if (/\b409\b|\b412\b|conflict|precondition|concurr|etag|競合/.test(text)) {
    return `${fallback} 他の変更が反映されています。画面を更新してから再試行してください。`;
  }
  if (
    /network|failed to fetch|fetch failed|timeout|timed out|offline|通信|接続/.test(
      text,
    )
  ) {
    return `${fallback} 通信状態を確認して、もう一度お試しください。`;
  }
  return `${fallback} 時間をおいてもう一度お試しください。`;
}
