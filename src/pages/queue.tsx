import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  useApplications,
  useCategories,
  useCurrentSystemUser,
  useDecisionOptions,
  useDecisions,
  useSystemUsers,
} from "@/hooks/use-decisionflow";
import {
  ApplicationStage,
  stageMeta,
  type Application,
  type ApplicationStageValue,
} from "@/types/decisionflow";
import {
  getDeciderQueueApplications,
  normalizeApplicationStage,
  normalizeGuid,
} from "@/lib/decisionflow-utils";

const columns: { stage: ApplicationStageValue; color: string }[] = [
  { stage: ApplicationStage.Submitted, color: "border-t-sky-500" },
  { stage: ApplicationStage.Decided, color: "border-t-emerald-500" },
];

function QueueColumn({
  stage,
  count,
  color,
  children,
}: {
  stage: ApplicationStageValue;
  count: number;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`flex min-h-[240px] min-w-0 flex-col rounded-lg border-t-4 bg-muted/30 ${color}`}
    >
      <div className="flex items-center justify-between px-3 py-3">
        <h3 className="text-sm font-semibold">{stageMeta[stage].label}</h3>
        <Badge variant="secondary">{count}</Badge>
      </div>
      <div className="min-w-0 flex-1 space-y-2 overflow-y-auto overflow-x-hidden px-2 pb-2">
        {children}
      </div>
    </div>
  );
}

function QueueCard({
  application,
  categoryName,
  deciderName,
  decisionOptionName,
  onClick,
}: {
  application: Application;
  categoryName: string;
  deciderName: string;
  decisionOptionName?: string;
  onClick: () => void;
}) {
  return (
    <Card
      className="min-w-0 cursor-pointer overflow-hidden hover:shadow-md"
      onClick={onClick}
    >
      <CardContent className="min-w-0 space-y-2 p-3">
        <p className="truncate text-sm font-medium">{application.ds_name}</p>
        <div className="flex min-w-0 flex-wrap gap-1">
          {categoryName && (
            <Badge variant="secondary" className="text-[10px]">
              {categoryName}
            </Badge>
          )}
          {deciderName && (
            <Badge variant="outline" className="text-[10px]">
              {deciderName}
            </Badge>
          )}
          {decisionOptionName && (
            <Badge variant="outline" className="text-[10px]">
              結果: {decisionOptionName}
            </Badge>
          )}
        </div>
        {application.ds_body && (
          <p className="line-clamp-2 text-xs text-muted-foreground">
            {application.ds_body}
          </p>
        )}
        <p className="text-[10px] text-muted-foreground">
          希望期限:{" "}
          {application.ds_duedate
            ? new Date(application.ds_duedate).toLocaleDateString("ja-JP")
            : "未設定"}
        </p>
      </CardContent>
    </Card>
  );
}

export default function QueuePage() {
  const navigate = useNavigate();
  const { data: applications = [] } = useApplications();
  const { data: categories = [] } = useCategories();
  const { data: decisions = [] } = useDecisions();
  const { data: decisionOptions = [] } = useDecisionOptions();
  const { data: users = [] } = useSystemUsers();
  const { systemUserId } = useCurrentSystemUser();

  const categoryMap = useMemo(
    () => new Map(categories.map((item) => [item.ds_categoryid, item.ds_name])),
    [categories],
  );
  const userMap = useMemo(
    () =>
      new Map(
        users.map((item) => [
          item.systemuserid,
          item.fullname || item.internalemailaddress || "",
        ]),
      ),
    [users],
  );
  const decisionOptionMap = useMemo(
    () =>
      new Map(
        decisionOptions.map((option) => [
          option.ds_decisionoptionid,
          option.ds_name,
        ]),
      ),
    [decisionOptions],
  );
  const latestDecisionByApplication = useMemo(() => {
    const map = new Map<string, string>();
    decisions.forEach((decision) => {
      const applicationId = normalizeGuid(decision._ds_applicationid_value);
      if (applicationId && !map.has(applicationId)) {
        map.set(applicationId, decision._ds_decisionoptionid_value ?? "");
      }
    });
    return map;
  }, [decisions]);

  const grouped = useMemo(() => {
    const map = new Map<ApplicationStageValue, Application[]>();
    columns.forEach((column) => map.set(column.stage, []));
    getDeciderQueueApplications(applications, systemUserId).forEach(
      (application) => {
        const stage = normalizeApplicationStage(application.ds_stage);
        map.get(stage)?.push(application);
      },
    );
    return map;
  }, [applications, systemUserId]);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">判断キュー</h2>
        <p className="text-sm text-muted-foreground">
          自分が判断者に設定されている申請をステージ別に確認します。
        </p>
      </div>
      <div className="grid min-h-0 grid-cols-1 gap-4 md:grid-cols-2">
        {columns.map((column) => {
          const items = grouped.get(column.stage) ?? [];
          return (
            <QueueColumn
              key={column.stage}
              stage={column.stage}
              color={column.color}
              count={items.length}
            >
              {items.map((application) => (
                <QueueCard
                  key={application.ds_applicationid}
                  application={application}
                  categoryName={
                    application._ds_categoryid_value
                      ? (categoryMap.get(application._ds_categoryid_value) ??
                        "")
                      : ""
                  }
                  deciderName={
                    application._ds_deciderid_value
                      ? (userMap.get(application._ds_deciderid_value) ?? "")
                      : ""
                  }
                  decisionOptionName={decisionOptionMap.get(
                    latestDecisionByApplication.get(
                      normalizeGuid(application.ds_applicationid) ?? "",
                    ) ?? "",
                  )}
                  onClick={() =>
                    navigate(`/applications/${application.ds_applicationid}`)
                  }
                />
              ))}
            </QueueColumn>
          );
        })}
      </div>
    </div>
  );
}
