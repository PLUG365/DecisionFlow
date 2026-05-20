export const FIXED_DECISION_OPTION_NAMES = [
  "承認",
  "却下",
  "差し戻し",
] as const;

export type FixedDecisionOptionName =
  (typeof FIXED_DECISION_OPTION_NAMES)[number];

export function isFixedDecisionOptionName(
  value: string,
): value is FixedDecisionOptionName {
  return FIXED_DECISION_OPTION_NAMES.includes(value as FixedDecisionOptionName);
}
