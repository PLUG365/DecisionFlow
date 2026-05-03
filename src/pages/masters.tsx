import {
  InlineEditTable,
  type EditableColumn,
} from "@/components/inline-edit-table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useCategories,
  useCreateCategory,
  useCreateDecisionOption,
  useDecisionOptions,
  useUpdateCategory,
  useUpdateDecisionOption,
} from "@/hooks/use-decisionflow";
import { toast } from "sonner";

type MasterRow = Record<string, unknown> & { id: string };

export default function MastersPage() {
  const { data: categories = [] } = useCategories();
  const { data: decisionOptions = [] } = useDecisionOptions();
  const createCategory = useCreateCategory();
  const updateCategory = useUpdateCategory();
  const createDecisionOption = useCreateDecisionOption();
  const updateDecisionOption = useUpdateDecisionOption();

  const categoryRows: MasterRow[] = categories.map((item) => ({
    id: item.ds_categoryid,
    name: item.ds_name,
    description: item.ds_description,
    template: item.ds_template,
    sortOrder: item.ds_sortorder,
  }));
  const decisionRows: MasterRow[] = decisionOptions.map((item) => ({
    id: item.ds_decisionoptionid,
    name: item.ds_name,
    description: item.ds_description,
    sortOrder: item.ds_sortorder,
  }));

  const categoryColumns: EditableColumn<MasterRow>[] = [
    { key: "name", label: "名前", editable: true, type: "text" },
    { key: "description", label: "説明", editable: true, type: "textarea" },
    {
      key: "template",
      label: "推奨フォーマット",
      editable: true,
      type: "textarea",
    },
    { key: "sortOrder", label: "並び順", editable: true, type: "number" },
  ];
  const optionColumns: EditableColumn<MasterRow>[] = [
    { key: "name", label: "名前", editable: true, type: "text" },
    { key: "description", label: "説明", editable: true, type: "textarea" },
    { key: "sortOrder", label: "並び順", editable: true, type: "number" },
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
    updateCategory.mutate(
      {
        id: String(id),
        ds_name: name,
        ds_description: String(row.description ?? "") || undefined,
        ds_template: String(row.template ?? "") || undefined,
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
    createCategory.mutate(
      {
        ds_name: name,
        ds_description: String(row.description ?? "") || undefined,
        ds_template: String(row.template ?? "") || undefined,
        ds_sortorder: Number(row.sortOrder ?? 0),
      },
      {
        onSuccess: () => toast.success("カテゴリを追加しました"),
        onError: () => toast.error("カテゴリの追加に失敗しました"),
      },
    );
  };

  const handleSaveDecisionOption = (
    id: string | number,
    row: Partial<MasterRow>,
  ) => {
    const name = requireName(row.name);
    if (!name) return;
    updateDecisionOption.mutate(
      {
        id: String(id),
        ds_name: name,
        ds_description: String(row.description ?? "") || undefined,
        ds_sortorder: Number(row.sortOrder ?? 0),
      },
      {
        onSuccess: () => toast.success("判断選択肢を保存しました"),
        onError: () => toast.error("判断選択肢の保存に失敗しました"),
      },
    );
  };

  const handleAddDecisionOption = (row: Omit<MasterRow, "id">) => {
    const name = requireName(row.name);
    if (!name) return;
    createDecisionOption.mutate(
      {
        ds_name: name,
        ds_description: String(row.description ?? "") || undefined,
        ds_sortorder: Number(row.sortOrder ?? 0),
      },
      {
        onSuccess: () => toast.success("判断選択肢を追加しました"),
        onError: () => toast.error("判断選択肢の追加に失敗しました"),
      },
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">マスタ管理</h2>
        <p className="text-sm text-muted-foreground">
          カテゴリと判断選択肢を保守します。
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
            onSave={handleSaveCategory}
            onAdd={handleAddCategory}
            addButtonLabel="カテゴリを追加"
          />
        </TabsContent>
        <TabsContent value="decisions">
          <InlineEditTable
            data={decisionRows}
            columns={optionColumns}
            title="判断選択肢"
            onSave={handleSaveDecisionOption}
            onAdd={handleAddDecisionOption}
            addButtonLabel="判断選択肢を追加"
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
