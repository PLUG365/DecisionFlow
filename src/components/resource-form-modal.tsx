import { useEffect, useState } from "react";
import { toast } from "sonner";

import { FormModal, FormSection } from "@/components/form-modal";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateResource } from "@/hooks/use-decisionflow";
import {
  appendGeneratedDescription,
  resolveDescribeOutcome,
  resolveDescribeRequest,
  validateResourceInput,
} from "@/lib/decisionflow-utils";
import { getOperationErrorMessage } from "@/lib/operation-error";
import { ApplicationResource_DescribeLinkService } from "@/generated/services/ApplicationResource_DescribeLinkService";

type ApplicationOption = { value: string; label: string };

type ResourceFormModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** 申請を選ばせるときの候補。`fixedApplicationId` があるときは使わない。 */
  applicationOptions?: ApplicationOption[];
  /**
   * 申請詳細から開くときに渡す。**選択済みで固定**になり、申請の選択欄は出ない。
   * 横断ページ（関連資料）からは渡さないので、従来どおり選択欄が出る。
   */
  fixedApplicationId?: string;
};

/**
 * 関連資料の追加モーダル。
 *
 * 横断ページと申請詳細の資料タブの**両方から使う**。同じフォームを2箇所に書くと、
 * 片方だけ直して食い違う（開発メモ（非公開） の「配線層の守り方」規則2）。
 *
 * **表示の可否はここでは判定しない。** 呼び出し側が
 * `canManageApplicationResources` で閉じる。判定を2箇所に置かないため。
 */
export function ResourceFormModal({
  open,
  onOpenChange,
  applicationOptions = [],
  fixedApplicationId,
}: ResourceFormModalProps) {
  const createResource = useCreateResource();
  const [applicationId, setApplicationId] = useState(fixedApplicationId ?? "");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [url, setUrl] = useState("");
  const [isDescribing, setIsDescribing] = useState(false);

  /**
   * URL 先を読んで説明文を生成し、**説明欄の末尾に足す**。
   *
   * 読むのは**呼び出した本人の資格**（フローの SharePoint 接続が invoker。
   * 2026-08-16 に実測）。本人が読めないファイルは読めない。
   *
   * **上書きしない。** `説明 *` は必須項目なので、生成結果で利用者の文章を潰すと
   * 書き直しを強いることになる（開発メモ（非公開） の決定）。
   */
  const handleDescribe = async () => {
    // **判断は全部純関数に置いている。** ここに残すのは
    // 「呼ぶ」「トーストを出す」「状態を更新する」だけにして、
    // 分岐がテストの外に出ないようにする。
    const request = resolveDescribeRequest(url);
    if (request.kind === "error") {
      toast.error(request.message);
      return;
    }

    setIsDescribing(true);
    try {
      const result = await ApplicationResource_DescribeLinkService.Run({
        text: request.text,
        text_1: request.text_1,
      });
      if (!result.success) {
        toast.error(getOperationErrorMessage(result.error, "読み取りに失敗しました"));
        return;
      }
      // **どう扱うかの判定は純関数に置いている**（`resolveDescribeOutcome`）。
      // 分岐が5通りあり、画面の中に散らすと「追記してはいけないときに追記する」
      // 退行がテストの外で起きる。
      const outcome = resolveDescribeOutcome(result.data);
      if (outcome.kind === "error") {
        toast.error(outcome.message);
        return;
      }
      setDescription((current) =>
        appendGeneratedDescription(current, outcome.description),
      );
      toast.success("説明を追記しました");
    } catch (error) {
      toast.error(getOperationErrorMessage(error, "読み取りに失敗しました"));
    } finally {
      setIsDescribing(false);
    }
  };

  // 申請詳細では `id` だけ変わって再マウントされないことがあるので、
  // 固定の申請が変わったら追従させる。
  useEffect(() => {
    if (fixedApplicationId) setApplicationId(fixedApplicationId);
  }, [fixedApplicationId]);

  const resetForm = () => {
    setApplicationId(fixedApplicationId ?? "");
    setTitle("");
    setDescription("");
    setUrl("");
  };

  const handleSave = () => {
    const targetApplicationId = fixedApplicationId ?? applicationId;
    if (!targetApplicationId) {
      toast.error("申請を選択してください");
      return;
    }
    const validation = validateResourceInput({ title, url, description });
    if (!validation.valid) {
      toast.error(Object.values(validation.fieldErrors)[0]);
      return;
    }

    createResource.mutate(
      {
        resource: {
          ds_name: title.trim(),
          ds_description: description.trim() || undefined,
          ds_url: url.trim(),
          _ds_applicationid_value: targetApplicationId,
        },
      },
      {
        onSuccess: () => {
          toast.success("関連資料リンクを追加しました");
          onOpenChange(false);
          resetForm();
        },
        onError: (error) =>
          toast.error(
            getOperationErrorMessage(error, "関連資料の追加に失敗しました。"),
          ),
      },
    );
  };

  return (
    <FormModal
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) resetForm();
      }}
      title="関連資料を追加"
      description="申請の根拠になるリンクを登録します。"
      onSave={handleSave}
      saveLabel="追加"
      isSaving={createResource.isPending}
    >
      <div className="space-y-6">
        {!fixedApplicationId && (
          <FormSection title="対象申請">
            <div className="space-y-2">
              <Label>申請 *</Label>
              <Combobox
                options={applicationOptions}
                value={applicationId}
                onValueChange={setApplicationId}
                placeholder="申請を選択"
                searchPlaceholder="申請を検索"
              />
            </div>
          </FormSection>
        )}

        <FormSection title="リンク情報">
          <div className="space-y-2">
            <Label htmlFor="resource-title">タイトル *</Label>
            <Input
              id="resource-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="例: 見積条件の根拠資料"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="resource-url">URL *</Label>
            <div className="flex gap-2">
              <Input
                id="resource-url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="https://..."
              />
              <Button
                type="button"
                variant="outline"
                onClick={handleDescribe}
                disabled={isDescribing || !url.trim()}
              >
                {isDescribing ? "読み取り中..." : "説明を生成"}
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="resource-description">説明 *</Label>
            <Textarea
              id="resource-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={4}
              placeholder="資料の位置づけ・確認ポイント・判断に必要な要点（AI 判断に活用されます）"
            />
          </div>
        </FormSection>
      </div>
    </FormModal>
  );
}
