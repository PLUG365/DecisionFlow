import { useMemo, useState } from "react";
import { ExternalLink, Plus, Trash2 } from "lucide-react";

import { ListTable, type TableColumn } from "@/components/list-table";
import { ResourceFormModal } from "@/components/resource-form-modal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import {
  useApplications,
  useDeleteResource,
  useIsAdmin,
  useIsApplicant,
  useResources,
} from "@/hooks/use-decisionflow";
import { canManageApplicationResources } from "@/lib/decisionflow-utils";
import { getOperationErrorMessage } from "@/lib/operation-error";
import { type ApplicationResource } from "@/types/decisionflow";
import { toast } from "sonner";

type ResourceRow = ApplicationResource & Record<string, unknown>;

export default function ResourcesPage() {
  const { data: resources = [] } = useResources();
  const { data: applications = [] } = useApplications();
  const { data: isAdmin, isLoading: isAdminLoading } = useIsAdmin();
  const { data: isApplicant, isLoading: isApplicantLoading } = useIsApplicant();
  const deleteResource = useDeleteResource();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [resourceToDelete, setResourceToDelete] =
    useState<ApplicationResource | null>(null);
  const applicationMap = useMemo(
    () =>
      new Map(
        applications.map((item) => [item.ds_applicationid, item.ds_name]),
      ),
    [applications],
  );
  const applicationOptions = applications.map((application) => ({
    value: application.ds_applicationid,
    label: application.ds_name,
  }));

  const handleDelete = () => {
    if (!resourceToDelete) return;
    deleteResource.mutate(resourceToDelete.ds_applicationresourceid, {
      onSuccess: () => {
        toast.success("関連資料リンクを削除しました");
        setResourceToDelete(null);
      },
      onError: (error) =>
        toast.error(
          getOperationErrorMessage(
            error,
            "関連資料リンクの削除に失敗しました。",
          ),
        ),
    });
  };

  if (isAdminLoading || isApplicantLoading) return <div />;
  const canManageResources = canManageApplicationResources({
    isAdmin,
    isApplicant,
  });

  const columns: TableColumn<ResourceRow>[] = [
    { key: "ds_name", label: "タイトル", sortable: true },
    {
      key: "_ds_applicationid_value",
      label: "申請",
      render: (item) =>
        item._ds_applicationid_value
          ? (applicationMap.get(item._ds_applicationid_value as string) ?? "")
          : "",
    },
    {
      key: "ds_url",
      label: "リンク",
      render: (item) =>
        item.ds_url ? (
          <Button variant="outline" size="sm" asChild>
            <a href={item.ds_url as string} target="_blank" rel="noreferrer">
              <ExternalLink className="mr-2 h-4 w-4" />
              開く
            </a>
          </Button>
        ) : null,
    },
    // 削除も作成と同じ権限で閉じる。`ds_Decider` は Delete も持っていないので、
    // 出したままだと確認ダイアログまで進んで 403 になる。
    ...(canManageResources
      ? [
          {
            key: "actions",
            label: "操作",
            render: (item: ResourceRow) => (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={(event) => {
                  event.stopPropagation();
                  setResourceToDelete(item);
                }}
                aria-label="関連資料リンクを削除"
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            ),
          } satisfies TableColumn<ResourceRow>,
        ]
      : []),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">関連資料</h2>
          <p className="text-sm text-muted-foreground">
            申請に紐づくリンク資料を横断確認します。
          </p>
        </div>
        {canManageResources && (
          <Button onClick={() => setIsFormOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            資料を追加
          </Button>
        )}
      </div>
      <ListTable
        data={resources as ResourceRow[]}
        columns={columns}
        searchKeys={["ds_name", "ds_description"]}
      />

      <ResourceFormModal
        open={isFormOpen}
        onOpenChange={setIsFormOpen}
        applicationOptions={applicationOptions}
      />

      <ConfirmDialog
        open={Boolean(resourceToDelete)}
        onOpenChange={(open) => {
          if (!open) setResourceToDelete(null);
        }}
        title="関連資料リンクを削除しますか？"
        description={
          resourceToDelete
            ? `「${resourceToDelete.ds_name}」を削除します。この操作は取り消せません。`
            : "関連資料リンクを削除します。"
        }
        confirmLabel="削除"
        variant="destructive"
        onConfirm={handleDelete}
      />
    </div>
  );
}
