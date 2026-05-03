import { useMemo, useState } from "react";
import { ExternalLink, Plus, Trash2 } from "lucide-react";

import { FormModal, FormSection } from "@/components/form-modal";
import { ListTable, type TableColumn } from "@/components/list-table";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  useApplications,
  useCreateResource,
  useDeleteResource,
  useResources,
} from "@/hooks/use-decisionflow";
import { validateResourceInput } from "@/lib/decisionflow-utils";
import { type ApplicationResource } from "@/types/decisionflow";
import { toast } from "sonner";

type ResourceRow = ApplicationResource & Record<string, unknown>;

export default function ResourcesPage() {
  const { data: resources = [] } = useResources();
  const { data: applications = [] } = useApplications();
  const createResource = useCreateResource();
  const deleteResource = useDeleteResource();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [resourceToDelete, setResourceToDelete] =
    useState<ApplicationResource | null>(null);
  const [formApplicationId, setFormApplicationId] = useState("");
  const [formTitle, setFormTitle] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formUrl, setFormUrl] = useState("");
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

  const resetForm = () => {
    setFormApplicationId("");
    setFormTitle("");
    setFormDescription("");
    setFormUrl("");
  };

  const handleSave = () => {
    if (!formApplicationId) {
      toast.error("申請を選択してください");
      return;
    }
    const validation = validateResourceInput({
      title: formTitle,
      url: formUrl,
    });
    if (!validation.valid) {
      toast.error(Object.values(validation.fieldErrors)[0]);
      return;
    }

    createResource.mutate(
      {
        resource: {
          ds_name: formTitle.trim(),
          ds_description: formDescription.trim() || undefined,
          ds_url: formUrl.trim(),
          _ds_applicationid_value: formApplicationId,
        },
      },
      {
        onSuccess: () => {
          toast.success("関連資料リンクを追加しました");
          setIsFormOpen(false);
          resetForm();
        },
        onError: (error) =>
          toast.error(
            error instanceof Error
              ? error.message
              : "関連資料の追加に失敗しました",
          ),
      },
    );
  };

  const handleDelete = () => {
    if (!resourceToDelete) return;
    deleteResource.mutate(resourceToDelete.ds_applicationresourceid, {
      onSuccess: () => {
        toast.success("関連資料リンクを削除しました");
        setResourceToDelete(null);
      },
      onError: () => toast.error("関連資料リンクの削除に失敗しました"),
    });
  };

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
    {
      key: "actions",
      label: "操作",
      render: (item) => (
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
    },
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
        <Button onClick={() => setIsFormOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          資料を追加
        </Button>
      </div>
      <ListTable
        data={resources as ResourceRow[]}
        columns={columns}
        searchKeys={["ds_name", "ds_description"]}
      />

      <FormModal
        open={isFormOpen}
        onOpenChange={(open) => {
          setIsFormOpen(open);
          if (!open) resetForm();
        }}
        title="関連資料を追加"
        description="申請の根拠になるリンクを登録します。"
        onSave={handleSave}
        saveLabel="追加"
        isSaving={createResource.isPending}
      >
        <div className="space-y-6">
          <FormSection title="対象申請">
            <div className="space-y-2">
              <Label>申請 *</Label>
              <Combobox
                options={applicationOptions}
                value={formApplicationId}
                onValueChange={setFormApplicationId}
                placeholder="申請を選択"
                searchPlaceholder="申請を検索"
              />
            </div>
          </FormSection>

          <FormSection title="リンク情報">
            <div className="space-y-2">
              <Label htmlFor="resource-title">タイトル *</Label>
              <Input
                id="resource-title"
                value={formTitle}
                onChange={(event) => setFormTitle(event.target.value)}
                placeholder="例: 見積条件の根拠資料"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="resource-url">URL *</Label>
              <Input
                id="resource-url"
                value={formUrl}
                onChange={(event) => setFormUrl(event.target.value)}
                placeholder="https://..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="resource-description">説明</Label>
              <Textarea
                id="resource-description"
                value={formDescription}
                onChange={(event) => setFormDescription(event.target.value)}
                rows={4}
                placeholder="資料の位置づけや確認ポイント"
              />
            </div>
          </FormSection>
        </div>
      </FormModal>

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
