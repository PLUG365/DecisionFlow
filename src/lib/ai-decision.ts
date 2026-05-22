export type AiSimilarCase = {
  title: string;
  decision?: string;
  reason?: string;
};

export type ParsedAiDecisionBasis = {
  risks: string[];
  similarCases: AiSimilarCase[];
  regulationContext?: {
    considered: boolean;
    audience?: string;
    message?: string;
  };
  rawText: string | null;
};

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") return item;
      if (Boolean(item) && typeof item === "object") {
        const record = item as Record<string, unknown>;
        if (typeof record.item === "string") return record.item;
      }
      return null;
    })
    .filter(
      (item): item is string =>
        typeof item === "string" && Boolean(item.trim()),
    );
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

function toRegulationContext(
  value: unknown,
): ParsedAiDecisionBasis["regulationContext"] {
  if (!value || typeof value !== "object") return undefined;
  const record = value as Record<string, unknown>;
  return {
    considered: record.considered === true || record.considered === "true",
    audience: typeof record.audience === "string" ? record.audience : undefined,
    message: typeof record.message === "string" ? record.message : undefined,
  };
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
      regulationContext: toRegulationContext(parsed.regulationContext),
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
