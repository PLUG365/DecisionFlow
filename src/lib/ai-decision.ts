export type AiSimilarCase = {
  title: string;
  decision?: string;
  reason?: string;
};

export type ParsedAiDecisionBasis = {
  risks: string[];
  similarCases: AiSimilarCase[];
  rawText: string | null;
};

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function toSimilarCases(value: unknown): AiSimilarCase[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter(
      (item): item is Record<string, unknown> =>
        Boolean(item) && typeof item === "object",
    )
    .map((item) => ({
      title: String(item.title ?? ""),
      decision: item.decision ? String(item.decision) : undefined,
      reason: item.reason ? String(item.reason) : undefined,
    }))
    .filter((item) => item.title.trim());
}

export function parseAiDecisionBasis(
  basis: string | null | undefined,
): ParsedAiDecisionBasis {
  const trimmed = basis?.trim();
  if (!trimmed) {
    return { risks: [], similarCases: [], rawText: null };
  }

  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    return {
      risks: toStringArray(parsed.risks),
      similarCases: toSimilarCases(parsed.similarCases),
      rawText: null,
    };
  } catch {
    return { risks: [], similarCases: [], rawText: trimmed };
  }
}

export function formatAiDecisionUpdatedAt(
  value: string | null | undefined,
): string {
  if (!value) return "未更新";
  return new Date(value).toLocaleString("ja-JP");
}
