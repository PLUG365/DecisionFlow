import { useMemo, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowRight } from "lucide-react";

import { ListTable, type TableColumn } from "@/components/list-table";
import { LoadingSkeletonGrid } from "@/components/loading-skeleton";
import { StageBadge } from "@/components/stage-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  useApplications,
  useCategories,
  useCurrentSystemUser,
  useDecisionOptions,
  useDecisions,
  useSystemUsers,
} from "@/hooks/use-decisionflow";
import {
  stageMeta,
  type Application,
  type ApplicationStageValue,
} from "@/types/decisionflow";
import {
  groupDashboardActionApplications,
  type DashboardActionScope,
} from "@/lib/dashboard-actions";
import {
  buildLatestDecisionOptionNameLookup,
  normalizeApplicationStage,
} from "@/lib/decisionflow-utils";

type ApplicationRow = Application & Record<string, unknown>;

const chartColors = ["#2563eb", "#d97706", "#ea580c", "#059669", "#71717a"];
const chartTooltipContentStyle = {
  backgroundColor: "rgba(24, 24, 27, 0.9)",
  border: "1px solid rgba(255, 255, 255, 0.18)",
  borderRadius: "8px",
  boxShadow: "0 12px 32px rgba(0, 0, 0, 0.22)",
  color: "rgba(255, 255, 255, 0.96)",
  backdropFilter: "blur(8px)",
} satisfies CSSProperties;
const chartTooltipTextStyle = {
  color: "rgba(255, 255, 255, 0.96)",
} satisfies CSSProperties;

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data: applications = [], isLoading } = useApplications();
  const { data: categories = [] } = useCategories();
  const { data: decisions = [] } = useDecisions();
  const { data: decisionOptions = [] } = useDecisionOptions();
  const { data: users = [] } = useSystemUsers();
  const [actionScope, setActionScope] =
    useState<DashboardActionScope>("mine");
  const {
    systemUserId,
    isLoading: isCurrentUserLoading,
    isError: isCurrentUserError,
  } = useCurrentSystemUser();

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

  const stageCounts = useMemo(() => {
    const counts = new Map<ApplicationStageValue, number>();
    applications.forEach((application) => {
      const stage = normalizeApplicationStage(application.ds_stage);
      counts.set(stage, (counts.get(stage) ?? 0) + 1);
    });
    return counts;
  }, [applications]);

  const actionGroups = useMemo(
    () =>
      groupDashboardActionApplications({
        applications,
        scope: actionScope,
        currentSystemUserId: systemUserId,
        now: new Date(),
      }),
    [applications, actionScope, systemUserId],
  );

  const isMineIdentityPending =
    actionScope === "mine" && isCurrentUserLoading;
  const isMineIdentityUnavailable =
    actionScope === "mine" &&
    !isCurrentUserLoading &&
    (isCurrentUserError || !systemUserId);

  const categoryChartData = useMemo(() => {
    const counts = new Map<string, number>();
    applications.forEach((application) => {
      const name = application._ds_categoryid_value
        ? (categoryMap.get(application._ds_categoryid_value) ?? "未分類")
        : "未分類";
      counts.set(name, (counts.get(name) ?? 0) + 1);
    });
    return Array.from(counts.entries()).map(([name, count]) => ({
      name,
      count,
    }));
  }, [applications, categoryMap]);

  const deciderChartData = useMemo(() => {
    const counts = new Map<string, number>();
    applications.forEach((application) => {
      const name = application._ds_deciderid_value
        ? (userMap.get(application._ds_deciderid_value) ?? "未割当")
        : "未割当";
      counts.set(name, (counts.get(name) ?? 0) + 1);
    });
    return Array.from(counts.entries()).map(([name, count]) => ({
      name,
      count,
    }));
  }, [applications, userMap]);

  const stageChartData = Array.from(stageCounts.entries()).map(
    ([stage, count]) => ({
      name: stageMeta[stage].shortLabel,
      value: count,
    }),
  );

  const columns: TableColumn<ApplicationRow>[] = [
    { key: "ds_name", label: "タイトル", sortable: true },
    {
      key: "ds_stage",
      label: "ステージ",
      render: (item) => (
        <StageBadge
          stage={item.ds_stage}
          latestDecisionOptionName={getLatestDecisionOptionName(
            item.ds_applicationid,
          )}
        />
      ),
    },
    {
      key: "_ds_categoryid_value",
      label: "カテゴリ",
      render: (item) => {
        const value = item._ds_categoryid_value as string | undefined;
        return value ? (categoryMap.get(value) ?? "") : "";
      },
    },
    {
      key: "_ds_deciderid_value",
      label: "判断者",
      render: (item) => {
        const value = item._ds_deciderid_value as string | undefined;
        return value ? (userMap.get(value) ?? "") : "未割当";
      },
    },
  ];

  if (isLoading) {
    return <LoadingSkeletonGrid columns={4} count={8} variant="compact" />;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">
            ダッシュボード
          </h2>
          <p className="text-sm text-muted-foreground">
            判断待ち、期限超過、カテゴリ別傾向をまとめて確認します。
          </p>
        </div>
        <Button onClick={() => navigate("/applications")}>
          申請リストへ
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">ステージ分布</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={stageChartData}
                  dataKey="value"
                  innerRadius={55}
                  outerRadius={90}
                >
                  {stageChartData.map((entry, index) => (
                    <Cell
                      key={entry.name}
                      fill={chartColors[index % chartColors.length]}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={chartTooltipContentStyle}
                  labelStyle={chartTooltipTextStyle}
                  itemStyle={chartTooltipTextStyle}
                  formatter={(value) => [`${value} 件`, "件数"]}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">カテゴリ別申請</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={categoryChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" interval={0} tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip
                  contentStyle={chartTooltipContentStyle}
                  labelStyle={chartTooltipTextStyle}
                  itemStyle={chartTooltipTextStyle}
                />
                <Bar
                  dataKey="count"
                  name="件数"
                  fill="#2563eb"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">判断者別負荷</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={deciderChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" interval={0} tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} />
                <Tooltip
                  contentStyle={chartTooltipContentStyle}
                  labelStyle={chartTooltipTextStyle}
                  itemStyle={chartTooltipTextStyle}
                />
                <Bar
                  dataKey="count"
                  name="件数"
                  fill="#059669"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <section className="space-y-3" aria-labelledby="dashboard-actions-heading">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3 id="dashboard-actions-heading" className="text-lg font-semibold">
              対応が必要な申請
            </h3>
            <p className="text-sm text-muted-foreground">
              希望期限を過ぎ、提出・修正または判断が必要な申請です。
            </p>
          </div>
          <div
            className="inline-flex w-fit rounded-md border p-1"
            role="group"
            aria-label="申請の表示範囲"
          >
            <Button
              type="button"
              size="sm"
              variant={actionScope === "mine" ? "default" : "ghost"}
              aria-pressed={actionScope === "mine"}
              onClick={() => setActionScope("mine")}
            >
              自分
            </Button>
            <Button
              type="button"
              size="sm"
              variant={actionScope === "all" ? "default" : "ghost"}
              aria-pressed={actionScope === "all"}
              onClick={() => setActionScope("all")}
            >
              全体
            </Button>
          </div>
        </div>

        {isMineIdentityPending ? (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              本人情報を確認しています。
            </CardContent>
          </Card>
        ) : isMineIdentityUnavailable ? (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              本人情報を取得できませんでした。「全体」に切り替えると、閲覧可能な申請を確認できます。
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
            <ListTable
              data={actionGroups.submitOrRevise as ApplicationRow[]}
              columns={columns}
              title="提出・修正が必要"
              description={
                actionScope === "mine"
                  ? "自分が作成した、希望期限超過の下書き・差し戻し申請"
                  : "希望期限超過の下書き・差し戻し申請"
              }
              searchKeys={["ds_name"]}
              itemsPerPage={5}
              emptyMessage={
                actionScope === "mine"
                  ? "自分が提出・修正する期限超過申請はありません"
                  : "提出・修正が必要な期限超過申請はありません"
              }
              onRowClick={(row) =>
                navigate(`/applications/${row.ds_applicationid}`)
              }
            />
            <ListTable
              data={actionGroups.decide as ApplicationRow[]}
              columns={columns}
              title="判断が必要"
              description={
                actionScope === "mine"
                  ? "自分が判断者の、希望期限超過の提出済み申請"
                  : "希望期限超過の提出済み申請"
              }
              searchKeys={["ds_name"]}
              itemsPerPage={5}
              emptyMessage={
                actionScope === "mine"
                  ? "自分が判断する期限超過申請はありません"
                  : "判断が必要な期限超過申請はありません"
              }
              onRowClick={(row) =>
                navigate(`/applications/${row.ds_applicationid}`)
              }
            />
          </div>
        )}
      </section>
    </div>
  );
}
