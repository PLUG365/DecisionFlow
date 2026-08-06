import { Badge } from "@/components/ui/badge";
import {
  isApplicationReturnedForRevision,
  normalizeApplicationStage,
  RETURNED_APPLICATION_BADGE,
} from "@/lib/decisionflow-utils";
import { stageMeta } from "@/types/decisionflow";

/**
 * 申請のステージ表示。差し戻された申請は `ds_stage` が Draft へ戻るため、
 * 直近の判断結果を渡すと「下書き」ではなく「差し戻し」として表示する。
 */
export function StageBadge({
  stage,
  latestDecisionOptionName,
}: {
  stage?: number | null;
  latestDecisionOptionName?: string;
}) {
  const meta = isApplicationReturnedForRevision(stage, latestDecisionOptionName)
    ? RETURNED_APPLICATION_BADGE
    : stageMeta[normalizeApplicationStage(stage)];

  return (
    <Badge variant="outline" className={meta.className}>
      {meta.label}
    </Badge>
  );
}
