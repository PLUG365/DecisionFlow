import {
  InlineEditTable,
  type EditableColumn,
} from "@/components/inline-edit-table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useCategories,
  useCreateCategory,
  useDecisionOptions,
  useDeleteCategory,
  useIsAdmin,
  useIsDecider,
  useUpdateCategory,
} from "@/hooks/use-decisionflow";
import {
  canEditMasterData,
  validateCategoryRegulationInput,
} from "@/lib/decisionflow-utils";
import { isFixedDecisionOptionName } from "@/lib/decision-options";
import { toast } from "sonner";

type MasterRow = Record<string, unknown> & { id: string };

export default function MastersPage() {
  const { data: isAdmin, isLoading: isAdminLoading } = useIsAdmin();
  const { data: isDecider, isLoading: isDeciderLoading } = useIsDecider();
  const { data: categories = [] } = useCategories();
  const { data: decisionOptions = [] } = useDecisionOptions();
  const createCategory = useCreateCategory();
  const updateCategory = useUpdateCategory();
  const deleteCategory = useDeleteCategory();

  if (isAdminLoading || isDeciderLoading) return <div />;
  const canEditMasters = canEditMasterData({ isAdmin, isDecider });

  const categoryRows: MasterRow[] = categories.map((item) => ({
    id: item.ds_categoryid,
    name: item.ds_name,
    description: item.ds_description,
    template: item.ds_template,
    regulationText: item.ds_regulationtext,
    sortOrder: item.ds_sortorder,
  }));
  const decisionRows: MasterRow[] = decisionOptions.map((item) => ({
    id: item.ds_decisionoptionid,
    name: item.ds_name,
    description: item.ds_description,
    sortOrder: item.ds_sortorder,
  }));

  const categoryColumns: EditableColumn<MasterRow>[] = [
    { key: "name", label: "名前", editable: canEditMasters, type: "text" },
    {
      key: "description",
      label: "説明",
      editable: canEditMasters,
      type: "textarea",
    },
    {
      key: "template",
      label: "推奨フォーマット",
      editable: canEditMasters,
      type: "textarea",
    },
    {
      key: "regulationText",
      label: "レギュレーション",
      editable: canEditMasters,
      type: "textarea",
      render: (value) =>
        String(value ?? "").trim() ||
        "このカテゴリにはレギュレーションが未設定です。",
    },
    {
      key: "sortOrder",
      label: "並び順",
      editable: canEditMasters,
      type: "number",
    },
  ];
  const optionColumns: EditableColumn<MasterRow>[] = [
    {
      key: "name",
      label: "名前",
      editable: false,
      type: "text",
      render: (value) => {
        const label = String(value ?? "");
        return isFixedDecisionOptionName(label) ? label : `${label}（非標準）`;
      },
    },
    { key: "description", label: "説明", editable: false, type: "textarea" },
    { key: "sortOrder", label: "並び順", editable: false, type: "number" },
  ];

  const requireName = (value: unknown) => {
    const name = String(value ?? "").trim();
    if (!name) {
      toast.error("名前は必須です");
      return null;
    }
    return name;
  };

  const handleSaveCategory = (id: string | number, row: Partial<MasterRow>) => {
    const name = requireName(row.name);
    if (!name) return;
    const regulationValidation = validateCategoryRegulationInput(
      String(row.regulationText ?? ""),
    );
    if (!regulationValidation.valid) {
      toast.error(Object.values(regulationValidation.fieldErrors)[0]);
      return;
    }
    updateCategory.mutate(
      {
        id: String(id),
        ds_name: name,
        ds_description: String(row.description ?? "") || undefined,
        ds_template: String(row.template ?? "") || undefined,
        ds_regulationtext: String(row.regulationText ?? "") || undefined,
        ds_sortorder: Number(row.sortOrder ?? 0),
      },
      {
        onSuccess: () => toast.success("カテゴリを保存しました"),
        onError: () => toast.error("カテゴリの保存に失敗しました"),
      },
    );
  };

  const handleAddCategory = (row: Omit<MasterRow, "id">) => {
    const name = requireName(row.name);
    if (!name) return;
    const regulationValidation = validateCategoryRegulationInput(
      String(row.regulationText ?? ""),
    );
    if (!regulationValidation.valid) {
      toast.error(Object.values(regulationValidation.fieldErrors)[0]);
      return;
    }
    createCategory.mutate(
      {
        ds_name: name,
        ds_description: String(row.description ?? "") || undefined,
        ds_template: String(row.template ?? "") || undefined,
        ds_regulationtext: String(row.regulationText ?? "") || undefined,
        ds_sortorder: Number(row.sortOrder ?? 0),
      },
      {
        onSuccess: () => toast.success("カテゴリを追加しました"),
        onError: () => toast.error("カテゴリの追加に失敗しました"),
      },
    );
  };

  const handleDeleteCategory = (id: string | number) => {
    deleteCategory.mutate(String(id), {
      onSuccess: () => toast.success("カテゴリを削除しました"),
      onError: () =>
        toast.error(
          "カテゴリの削除に失敗しました。既存の申請で参照されている可能性があります。",
        ),
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">マスタ管理</h2>
        <p className="text-sm text-muted-foreground">
          {canEditMasters
            ? "カテゴリを保守します。判断選択肢はフローとチャットで利用する固定値として参照のみ表示します。"
            : "カテゴリとレギュレーションを参照できます。編集は判断者または管理者ロールで有効になります。"}
        </p>
      </div>
      <Tabs defaultValue="categories">
        <TabsList>
          <TabsTrigger value="categories">カテゴリ</TabsTrigger>
          <TabsTrigger value="decisions">判断選択肢</TabsTrigger>
        </TabsList>
        <TabsContent value="categories">
          <InlineEditTable
            data={categoryRows}
            columns={categoryColumns}
            title="カテゴリ"
            description={
              canEditMasters
                ? "カテゴリ別レギュレーションは申請者の提出前確認と判断者向けAI判断に利用します。"
                : "現在のロールでは参照専用です。"
            }
            onSave={canEditMasters ? handleSaveCategory : undefined}
            onAdd={canEditMasters ? handleAddCategory : undefined}
            onDelete={canEditMasters ? handleDeleteCategory : undefined}
            addButtonLabel="カテゴリを追加"
          />
        </TabsContent>
        <TabsContent value="decisions">
          <InlineEditTable
            data={decisionRows}
            columns={optionColumns}
            title="判断選択肢"
            description="承認 / 却下 / 差し戻しは固定のシステムマスタです。名称や件数を変更すると、Power Automate フローや Copilot Studio の判断確定処理と整合しなくなります。"
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
