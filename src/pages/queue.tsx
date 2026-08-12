import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
} from "@/types/decisionflow";
import {
  buildLatestDecisionOptionNameLookup,
  type DeciderQueueColumnKey,
} from "@/lib/decisionflow-utils";
import {
  getQueueDueStatus,
  type QueueSortMode,
} from "@/lib/queue-priority";
import {
  buildDeciderQueueColumns,
  toQueueContextParams,
} from "@/lib/queue-sequence";

const columns: {
  key: DeciderQueueColumnKey;
  label: string;
  color: string;
  emptyMessage: string;
}[] = [
  {
    key: "submitted",
    label: stageMeta[ApplicationStage.Submitted].label,
    color: "border-t-sky-500",
    emptyMessage: "判断待ちの申請はありません。",
  },
  {
    key: "returned",
    label: "差し戻し中",
    color: "border-t-amber-500",
    emptyMessage: "差し戻し中の申請はありません。",
  },
  {
    key: "decided",
    label: stageMeta[ApplicationStage.Decided].label,
    color: "border-t-emerald-500",
    emptyMessage: "判断済みの申請はまだありません。",
  },
];

function QueueColumn({
  label,
  count,
  color,
  emptyMessage,
  children,
}: {
  label: string;
  count: number;
  color: string;
  emptyMessage: string;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`flex min-h-[240px] min-w-0 flex-col rounded-lg border-t-4 bg-muted/30 ${color}`}
    >
      <div className="flex items-center justify-between px-3 py-3">
        <h3 className="text-sm font-semibold">{label}</h3>
        <Badge variant="secondary">{count}</Badge>
      </div>
      <div className="min-w-0 flex-1 space-y-2 overflow-y-auto overflow-x-hidden px-2 pb-2">
        {count === 0 ? (
          <p className="px-2 py-8 text-center text-xs text-muted-foreground">
            {emptyMessage}
          </p>
        ) : (
          children
        )}
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
  const dueStatus = getQueueDueStatus(application.ds_duedate, new Date());

  return (
    <Card
      className="min-w-0 cursor-pointer overflow-hidden hover:shadow-md"
      onClick={onClick}
    >
      <CardContent className="min-w-0 space-y-2 p-3">
        <p className="truncate text-sm font-medium">{application.ds_name}</p>
        <div className="flex min-w-0 flex-wrap gap-1">
          {dueStatus === "overdue" && (
            <Badge variant="destructive" className="text-[10px]">
              期限超過
            </Badge>
          )}
          {dueStatus === "today" && (
            <Badge variant="secondary" className="text-[10px]">
              期限当日
            </Badge>
          )}
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
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [sortMode, setSortMode] = useState<QueueSortMode>("due");
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
  const getLatestDecisionOptionName = useMemo(
    () => buildLatestDecisionOptionNameLookup(decisions, decisionOptions),
    [decisions, decisionOptions],
  );
  const categoryOptions = useMemo(
    () =>
      [...categories].sort(
        (left, right) =>
          (left.ds_sortorder ?? 0) - (right.ds_sortorder ?? 0) ||
          left.ds_name.localeCompare(right.ds_name, "ja"),
      ),
    [categories],
  );
  // 申請詳細の「前/次」が同じ並びを見るため、列構成は共有の純関数に寄せている。
  const grouped = useMemo(
    () =>
      buildDeciderQueueColumns({
        applications,
        currentSystemUserId: systemUserId,
        categoryFilter,
        sortMode,
        getLatestDecisionOptionName,
      }),
    [
      applications,
      systemUserId,
      categoryFilter,
      sortMode,
      getLatestDecisionOptionName,
    ],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">判断キュー</h2>
          <p className="text-sm text-muted-foreground">
            自分が判断者に設定されている申請を、ステージ別・希望期限の近い順に確認します。
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          <Select value={sortMode} onValueChange={(value) => setSortMode(value as QueueSortMode)}>
            <SelectTrigger className="w-full sm:w-[180px]" aria-label="並び順">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="due">期限が近い順</SelectItem>
              <SelectItem value="oldest">更新が古い順</SelectItem>
            </SelectContent>
          </Select>
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-full sm:w-[240px]" aria-label="カテゴリで絞り込む">
              <SelectValue placeholder="カテゴリで絞り込む" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">すべてのカテゴリ</SelectItem>
              <SelectItem value="unassigned">未分類</SelectItem>
              {categoryOptions.map((category) => (
                <SelectItem
                  key={category.ds_categoryid}
                  value={category.ds_categoryid}
                >
                  {category.ds_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid min-h-0 grid-cols-1 gap-4 md:grid-cols-3">
        {columns.map((column) => {
          const items = grouped.get(column.key) ?? [];
          return (
            <QueueColumn
              key={column.key}
              label={column.label}
              color={column.color}
              count={items.length}
              emptyMessage={column.emptyMessage}
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
                  decisionOptionName={getLatestDecisionOptionName(
                    application.ds_applicationid,
                  )}
                  onClick={() =>
                    navigate(
                      `/applications/${application.ds_applicationid}?` +
                        new URLSearchParams(
                          toQueueContextParams({
                            column: column.key,
                            sortMode,
                            categoryFilter,
                          }),
                        ).toString(),
                    )
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
