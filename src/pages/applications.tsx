import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";

import { FormColumns, FormModal, FormSection } from "@/components/form-modal";
import { ListTable, type TableColumn } from "@/components/list-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  useApplications,
  useCategories,
  useCreateApplication,
  useCurrentSystemUser,
  useDeleteApplication,
  useDecisionOptions,
  useDecisions,
  useGenerateAiDecision,
  useSystemUsers,
  useUpdateApplication,
} from "@/hooks/use-decisionflow";
import {
  applicantSelectableStageValues,
  canEditApplication,
  canReturnApplicationToDraft,
  filterRowsForCurrentUser,
  normalizeApplicationStage,
  normalizeGuid,
} from "@/lib/decisionflow-utils";
import {
  ApplicationStage,
  stageMeta,
  type Application,
  type ApplicationStageValue,
} from "@/types/decisionflow";
import { toast } from "sonner";

type ApplicationRow = Application & Record<string, unknown>;

export default function ApplicationsPage() {
  const navigate = useNavigate();
  const { data: applications = [] } = useApplications();
  const { data: categories = [] } = useCategories();
  const { data: decisions = [] } = useDecisions();
  const { data: decisionOptions = [] } = useDecisionOptions();
  const { data: users = [] } = useSystemUsers();
  const { systemUserId } = useCurrentSystemUser();
  const createApplication = useCreateApplication();
  const updateApplication = useUpdateApplication();
  const deleteApplication = useDeleteApplication();
  const generateAiDecision = useGenerateAiDecision();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingApplication, setEditingApplication] =
    useState<Application | null>(null);
  const [applicationToDelete, setApplicationToDelete] =
    useState<Application | null>(null);
  const [formName, setFormName] = useState("");
  const [formBody, setFormBody] = useState("");
  const [formCategoryId, setFormCategoryId] = useState("");
  const [formDeciderId, setFormDeciderId] = useState("");
  const [formDueDate, setFormDueDate] = useState("");
  const [formStage, setFormStage] = useState<ApplicationStageValue>(
    ApplicationStage.Draft,
  );

  const categoryMap = useMemo(() => {
    const map = new Map<string, string>();
    categories.forEach((category) =>
      map.set(category.ds_categoryid, category.ds_name),
    );
    return map;
  }, [categories]);

  const userMap = useMemo(() => {
    const map = new Map<string, string>();
    users.forEach((user) => {
      map.set(
        user.systemuserid,
        user.fullname || user.internalemailaddress || "",
      );
    });
    return map;
  }, [users]);

  const myApplications = useMemo(
    () =>
      filterRowsForCurrentUser(applications, systemUserId, "_createdby_value"),
    [applications, systemUserId],
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

  const columns: TableColumn<ApplicationRow>[] = [
    { key: "ds_name", label: "タイトル", sortable: true },
    {
      key: "ds_stage",
      label: "ステージ",
      render: (item) => {
        const stage = normalizeApplicationStage(item.ds_stage);
        return (
          <Badge variant="outline" className={stageMeta[stage].className}>
            {stageMeta[stage].label}
          </Badge>
        );
      },
    },
    {
      key: "decisionResult",
      label: "判断結果",
      render: (item) => {
        const decisionOptionId = latestDecisionByApplication.get(
          normalizeGuid(item.ds_applicationid) ?? "",
        );
        const decisionOptionName = decisionOptionId
          ? decisionOptionMap.get(decisionOptionId)
          : undefined;
        return decisionOptionName ? (
          <Badge variant="outline">{decisionOptionName}</Badge>
        ) : (
          <span className="text-muted-foreground">未判断</span>
        );
      },
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
    {
      key: "ds_duedate",
      label: "希望期限",
      render: (item) =>
        item.ds_duedate
          ? new Date(item.ds_duedate).toLocaleDateString("ja-JP")
          : "",
    },
    {
      key: "actions",
      label: "操作",
      render: (item) => {
        const canEdit = canEditApplication({
          application: item,
          currentSystemUserId: systemUserId,
        });
        const canReturnToDraft = canReturnApplicationToDraft({
          application: item,
          currentSystemUserId: systemUserId,
        });

        if (canReturnToDraft) {
          return (
            <Button
              variant="outline"
              size="sm"
              onClick={(event) => {
                event.stopPropagation();
                handleReturnToDraft(item);
              }}
              disabled={updateApplication.isPending}
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              下書きに戻す
            </Button>
          );
        }

        if (!canEdit) return null;

        return (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={(event) => {
                event.stopPropagation();
                openEdit(item);
              }}
              aria-label="申請を編集"
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={(event) => {
                event.stopPropagation();
                setApplicationToDelete(item);
              }}
              aria-label="申請を削除"
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        );
      },
    },
  ];

  const filterStageOptions = Object.values(ApplicationStage).map((stage) => ({
    value: String(stage),
    label: stageMeta[stage].label,
  }));
  const applicantStageOptions = applicantSelectableStageValues.map((stage) => ({
    value: String(stage),
    label: stageMeta[stage].label,
  }));
  const categoryOptions = categories.map((category) => ({
    value: category.ds_categoryid,
    label: category.ds_name,
  }));
  const userOptions = users
    .filter((user) => Boolean(user.azureactivedirectoryobjectid?.trim()))
    .map((user) => ({
      value: user.systemuserid,
      label: user.fullname || user.internalemailaddress || "名前なし",
    }));

  const resetForm = () => {
    setEditingApplication(null);
    setFormName("");
    setFormBody("");
    setFormCategoryId("");
    setFormDeciderId("");
    setFormDueDate("");
    setFormStage(ApplicationStage.Draft);
  };

  const openCreate = () => {
    resetForm();
    setIsFormOpen(true);
  };

  const openEdit = (application: Application) => {
    setEditingApplication(application);
    setFormName(application.ds_name ?? "");
    setFormBody(application.ds_body ?? "");
    setFormCategoryId(application._ds_categoryid_value ?? "");
    setFormDeciderId(application._ds_deciderid_value ?? "");
    setFormDueDate(application.ds_duedate?.slice(0, 10) ?? "");
    setFormStage(
      applicantSelectableStageValues.includes(
        normalizeApplicationStage(application.ds_stage),
      )
        ? normalizeApplicationStage(application.ds_stage)
        : ApplicationStage.Submitted,
    );
    setIsFormOpen(true);
  };

  const handleSave = () => {
    if (
      editingApplication &&
      !canEditApplication({
        application: editingApplication,
        currentSystemUserId: systemUserId,
      })
    ) {
      toast.error("提出済みの申請は、下書きに戻すまで編集できません");
      return;
    }

    if (!formName.trim()) {
      toast.error("タイトルは必須です");
      return;
    }
    if (!formBody.trim()) {
      toast.error("申請本文は必須です");
      return;
    }

    const payload = {
      ds_name: formName.trim(),
      ds_body: formBody.trim(),
      ds_stage: formStage,
      ds_duedate: formDueDate || undefined,
      ds_submittedat:
        formStage === ApplicationStage.Submitted
          ? (editingApplication?.ds_submittedat ?? new Date().toISOString())
          : null,
      _ds_categoryid_value: formCategoryId || undefined,
      _ds_deciderid_value: formDeciderId || undefined,
    };

    if (editingApplication) {
      updateApplication.mutate(
        { id: editingApplication.ds_applicationid, ...payload },
        {
          onSuccess: () => {
            toast.success("申請を更新しました");
            if (formStage === ApplicationStage.Submitted) {
              generateAiDecision.mutate(editingApplication.ds_applicationid, {
                onSuccess: () => toast.success("AI判断を更新しました"),
                onError: () => toast.error("AI判断の更新に失敗しました"),
              });
            }
            setIsFormOpen(false);
            resetForm();
          },
          onError: () => toast.error("申請の更新に失敗しました"),
        },
      );
      return;
    }

    createApplication.mutate(payload, {
      onSuccess: (createdApplication) => {
        toast.success("申請を作成しました");
        if (formStage === ApplicationStage.Submitted) {
          generateAiDecision.mutate(createdApplication.ds_applicationid, {
            onSuccess: () => toast.success("AI判断を更新しました"),
            onError: () => toast.error("AI判断の更新に失敗しました"),
          });
        }
        setIsFormOpen(false);
        resetForm();
      },
      onError: () => toast.error("申請の作成に失敗しました"),
    });
  };

  const handleReturnToDraft = (application: Application) => {
    if (
      !canReturnApplicationToDraft({
        application,
        currentSystemUserId: systemUserId,
      })
    ) {
      toast.error("この申請は下書きに戻せません");
      return;
    }
    updateApplication.mutate(
      {
        id: application.ds_applicationid,
        ds_stage: ApplicationStage.Draft,
        ds_submittedat: null,
      },
      {
        onSuccess: () => toast.success("申請を下書きに戻しました"),
        onError: () => toast.error("下書きへの戻しに失敗しました"),
      },
    );
  };

  const handleDelete = () => {
    if (!applicationToDelete) return;
    deleteApplication.mutate(applicationToDelete.ds_applicationid, {
      onSuccess: () => {
        toast.success("申請を削除しました");
        setApplicationToDelete(null);
      },
      onError: () => toast.error("申請の削除に失敗しました"),
    });
  };

  const isSaving = createApplication.isPending || updateApplication.isPending;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">申請リスト</h2>
          <p className="text-sm text-muted-foreground">
            自分が起票した申請の作成、確認、関連資料の追加をここから始めます。
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />
          申請を作成
        </Button>
      </div>

      <ListTable
        data={myApplications as ApplicationRow[]}
        columns={columns}
        title="申請一覧"
        searchable
        searchKeys={["ds_name", "ds_body"]}
        filters={[
          {
            key: "ds_stage",
            label: "ステージ",
            options: filterStageOptions,
          },
        ]}
        emptyMessage="起票した申請はまだありません"
        onRowClick={(row) => navigate(`/applications/${row.ds_applicationid}`)}
      />

      <FormModal
        open={isFormOpen}
        onOpenChange={(open) => {
          setIsFormOpen(open);
          if (!open) resetForm();
        }}
        title={editingApplication ? "申請を編集" : "申請を作成"}
        description="判断者が読みやすい形で、背景・判断してほしいこと・期限をまとめます。"
        onSave={handleSave}
        saveLabel={editingApplication ? "更新" : "作成"}
        isSaving={isSaving}
      >
        <div className="space-y-6">
          <FormSection title="基本情報">
            <div className="space-y-2">
              <Label htmlFor="application-title">タイトル *</Label>
              <Input
                id="application-title"
                value={formName}
                onChange={(event) => setFormName(event.target.value)}
                placeholder="例: 顧客向け提案条件の承認依頼"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="application-body">申請本文 *</Label>
              <Textarea
                id="application-body"
                value={formBody}
                onChange={(event) => setFormBody(event.target.value)}
                rows={7}
                placeholder="背景、判断してほしいこと、選択肢、懸念点を記入"
              />
            </div>
          </FormSection>

          <FormSection title="分類と担当">
            <FormColumns columns={2}>
              <div className="space-y-2">
                <Label>カテゴリ</Label>
                <Combobox
                  options={categoryOptions}
                  value={formCategoryId}
                  onValueChange={setFormCategoryId}
                  placeholder="カテゴリを選択"
                  searchPlaceholder="カテゴリを検索"
                />
              </div>
              <div className="space-y-2">
                <Label>判断者</Label>
                <Combobox
                  options={userOptions}
                  value={formDeciderId}
                  onValueChange={setFormDeciderId}
                  placeholder="判断者を選択"
                  searchPlaceholder="ユーザーを検索"
                />
              </div>
            </FormColumns>
            <FormColumns columns={2}>
              <div className="space-y-2">
                <Label htmlFor="application-due-date">希望期限</Label>
                <Input
                  id="application-due-date"
                  type="date"
                  value={formDueDate}
                  onChange={(event) => setFormDueDate(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>ステージ</Label>
                <div className="grid grid-cols-2 gap-2">
                  {applicantStageOptions.map((stage) => (
                    <label
                      key={stage.value}
                      className="flex min-h-10 cursor-pointer items-center gap-2 rounded-md border px-3 text-sm hover:bg-muted/50"
                    >
                      <input
                        type="radio"
                        name="application-stage"
                        value={stage.value}
                        checked={formStage === Number(stage.value)}
                        onChange={() =>
                          setFormStage(
                            Number(stage.value) as ApplicationStageValue,
                          )
                        }
                        className="h-4 w-4 accent-primary"
                      />
                      <span>{stage.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            </FormColumns>
          </FormSection>
        </div>
      </FormModal>

      <ConfirmDialog
        open={Boolean(applicationToDelete)}
        onOpenChange={(open) => {
          if (!open) setApplicationToDelete(null);
        }}
        title="申請を削除しますか？"
        description={
          applicationToDelete
            ? `「${applicationToDelete.ds_name}」を削除します。この操作は取り消せません。`
            : "申請を削除します。"
        }
        confirmLabel="削除"
        variant="destructive"
        onConfirm={handleDelete}
      />
    </div>
  );
}
