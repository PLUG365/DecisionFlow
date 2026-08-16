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
  parseSharePointLink,
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
 * 片方だけ直して食い違う（`docs/UX_ROADMAP.md` の「配線層の守り方」規則2）。
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
   * URL 先を読んで説明文を生成する（第1段）。
   *
   * **第1段では説明文を書かない。** いま確かめたいのは
   * 「このフローが**誰の資格で**外部を読むか」で、それが決まらないと
   * 機能そのものが成立しない（`docs/UX_ROADMAP.md` の境界表）。
   * フローが返す `actingAs` を出して、呼び出した本人かどうかを見る。
   */
  const handleDescribe = async () => {
    const link = parseSharePointLink(url);
    if (link.kind === "not-sharepoint") {
      toast.error("SharePoint / OneDrive の URL を入れてください");
      return;
    }
    if (link.kind === "sharing-link") {
      toast.error(
        "共有リンクはまだ読めません。ファイルを開いた状態のアドレスを貼ってください",
      );
      return;
    }
    if (link.kind === "unsupported") {
      toast.error("この URL からはファイルを特定できませんでした");
      return;
    }

    setIsDescribing(true);
    try {
      const result = await ApplicationResource_DescribeLinkService.Run({
        text: link.siteUrl,
        text_1: link.filePath,
      });
      if (!result.success) {
        toast.error(getOperationErrorMessage(result.error, "読み取りに失敗しました"));
        return;
      }
      const actingAs = result.data?.actingAs?.trim() || "(不明)";
      const status = result.data?.status ?? "(不明)";
      toast.info(`実行者: ${actingAs} / 読み取り: ${status}`, {
        duration: 15000,
      });
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
