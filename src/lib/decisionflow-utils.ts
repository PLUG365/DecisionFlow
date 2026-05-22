import {
  ApplicationStage,
  type Category,
  type ApplicationStageValue,
} from "@/types/decisionflow";

export const EMPTY_CATEGORY_REGULATION_MESSAGE =
  "このカテゴリにはレギュレーションが未設定です。";

export const CATEGORY_REGULATION_MAX_LENGTH = 50000;

export type ResourceInput = {
  title?: string | null;
  url?: string | null;
  description?: string | null;
};

export type ApplicationInput = {
  name?: string | null;
  body?: string | null;
  stage?: number | null;
  deciderId?: string | null;
  categoryId?: string | null;
  categoriesAvailable?: boolean;
};

export const applicantSelectableStageValues: ApplicationStageValue[] = [
  ApplicationStage.Draft,
  ApplicationStage.Submitted,
];

export function isApplicantSelectableStage(
  stage: number | null | undefined,
): stage is ApplicationStageValue {
  return applicantSelectableStageValues.includes(
    stage as ApplicationStageValue,
  );
}

export function normalizeApplicationStage(
  stage: number | null | undefined,
): ApplicationStageValue {
  if (stage === ApplicationStage.Draft || stage === ApplicationStage.Decided) {
    return stage;
  }
  return ApplicationStage.Submitted;
}

export type ValidationResult = {
  valid: boolean;
  fieldErrors: Record<string, string>;
};

export type OperationWaitState = {
  visible: boolean;
  title: string;
  description: string;
};

export type AiResultDialogMode = "draft" | "submit";

export type AiResultDialogConfig = {
  title: string;
  primaryLabel: string;
  showFinalSubmit: boolean;
  showKeepDraft: boolean;
};

export type ParticipantInput = {
  userId?: string | null;
  role?: number | null;
};

export type MentionInput = {
  targetUserId?: string | null;
};

export function shouldShowMasterManagementNavigation(): boolean {
  return true;
}

export function canEditMasterData(input: {
  isAdmin?: boolean | null;
  isDecider?: boolean | null;
}): boolean {
  return Boolean(input.isAdmin || input.isDecider);
}

export function validateResourceInput(input: ResourceInput): ValidationResult {
  const fieldErrors: Record<string, string> = {};

  if (!input.title?.trim()) {
    fieldErrors.title = "タイトルが必須です";
  }

  if (!input.url?.trim()) {
    fieldErrors.url = "リンク資料では URL が必須です";
  }

  if (!input.description?.trim()) {
    fieldErrors.description = "説明が必須です（AI 判断に活用されます）";
  }

  return {
    valid: Object.keys(fieldErrors).length === 0,
    fieldErrors,
  };
}

export function validateApplicationInput(
  input: ApplicationInput,
): ValidationResult {
  const fieldErrors: Record<string, string> = {};

  if (!input.name?.trim()) {
    fieldErrors.name = "タイトルは必須です";
  }

  if (!input.body?.trim()) {
    fieldErrors.body = "申請本文は必須です";
  }

  if (
    normalizeApplicationStage(input.stage) === ApplicationStage.Submitted &&
    !input.deciderId?.trim()
  ) {
    fieldErrors.deciderId = "提出時は判断者を選択してください";
  }

  if (
    normalizeApplicationStage(input.stage) === ApplicationStage.Submitted &&
    input.categoriesAvailable === true &&
    !input.categoryId?.trim()
  ) {
    fieldErrors.categoryId = "提出時はカテゴリを選択してください";
  }

  return {
    valid: Object.keys(fieldErrors).length === 0,
    fieldErrors,
  };
}

export function shouldRequireCategoryForSubmission(
  categories: Pick<Category, "ds_categoryid">[],
): boolean {
  return categories.length > 0;
}

export function getSelectedCategoryRegulationText(
  categories: Pick<
    Category,
    "ds_categoryid" | "ds_name" | "ds_regulationtext"
  >[],
  categoryId: string | null | undefined,
): string | null {
  const selectedCategoryId = normalizeGuid(categoryId);
  if (!selectedCategoryId) return null;

  const category = categories.find(
    (item) => normalizeGuid(item.ds_categoryid) === selectedCategoryId,
  );
  if (!category) return null;

  const regulationText = category.ds_regulationtext?.trim();
  return regulationText || EMPTY_CATEGORY_REGULATION_MESSAGE;
}

export function getSelectedCategoryRegulationInfo(
  categories: Pick<
    Category,
    "ds_categoryid" | "ds_name" | "ds_regulationtext"
  >[],
  categoryId: string | null | undefined,
): { categoryName: string; regulationText: string } | null {
  const selectedCategoryId = normalizeGuid(categoryId);
  if (!selectedCategoryId) return null;

  const category = categories.find(
    (item) => normalizeGuid(item.ds_categoryid) === selectedCategoryId,
  );
  if (!category) return null;

  return {
    categoryName: category.ds_name,
    regulationText:
      category.ds_regulationtext?.trim() || EMPTY_CATEGORY_REGULATION_MESSAGE,
  };
}

export function getAiCheckWaitState(isPending: boolean): OperationWaitState {
  return {
    visible: isPending,
    title: "AI判断を生成しています ✨",
    description:
      "申請内容とカテゴリ別レギュレーションを確認しています。このままお待ちください ☕",
  };
}

export function canRefreshAiDecisionFromDecisionTab(
  stage: number | null | undefined,
  isPending: boolean,
): boolean {
  return (
    !isPending && normalizeApplicationStage(stage) !== ApplicationStage.Decided
  );
}

export function getAiResultDialogConfig(
  mode: AiResultDialogMode,
): AiResultDialogConfig {
  if (mode === "submit") {
    return {
      title: "AI判断結果を確認しましたか？ 🔎",
      primaryLabel: "本提出",
      showFinalSubmit: true,
      showKeepDraft: true,
    };
  }
  return {
    title: "AI事前確認が完了しました ✨",
    primaryLabel: "閉じる",
    showFinalSubmit: false,
    showKeepDraft: false,
  };
}

export function getApplicationDecisionDetailPath(
  applicationId: string | null | undefined,
): string | null {
  const normalizedApplicationId = applicationId?.trim();
  if (!normalizedApplicationId) return null;
  return `/applications/${normalizedApplicationId}?tab=decision`;
}

export function validateCategoryRegulationInput(
  regulationText: string | null | undefined,
): ValidationResult {
  const fieldErrors: Record<string, string> = {};
  if ((regulationText ?? "").length > CATEGORY_REGULATION_MAX_LENGTH) {
    fieldErrors.regulationText = `レギュレーションは${CATEGORY_REGULATION_MAX_LENGTH}文字以内で入力してください`;
  }
  return {
    valid: Object.keys(fieldErrors).length === 0,
    fieldErrors,
  };
}

export function normalizeGuid(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  return trimmed ? trimmed.toLowerCase() : null;
}

export function filterRowsForCurrentUser<T extends Record<string, unknown>>(
  rows: T[],
  currentSystemUserId: string | null | undefined,
  lookupKey: keyof T,
): T[] {
  const normalizedCurrentUserId = normalizeGuid(currentSystemUserId);
  if (!normalizedCurrentUserId) return [];

  return rows.filter((row) => {
    const lookupValue = row[lookupKey];
    return (
      typeof lookupValue === "string" &&
      normalizeGuid(lookupValue) === normalizedCurrentUserId
    );
  });
}

export function getDeciderQueueApplications<
  T extends { _ds_deciderid_value?: string | null },
>(rows: T[], currentSystemUserId: string | null | undefined): T[] {
  return filterRowsForCurrentUser(
    rows as (T & Record<string, unknown>)[],
    currentSystemUserId,
    "_ds_deciderid_value",
  );
}

export function canEditApplication({
  application,
  currentSystemUserId,
}: {
  application: {
    _createdby_value?: string | null;
    ds_stage?: number | null;
  };
  currentSystemUserId: string | null | undefined;
}): boolean {
  const createdBy = normalizeGuid(application._createdby_value);
  const currentUser = normalizeGuid(currentSystemUserId);
  const stage = normalizeApplicationStage(application.ds_stage);
  return Boolean(
    createdBy &&
    currentUser &&
    createdBy === currentUser &&
    stage === ApplicationStage.Draft,
  );
}

export function canReturnApplicationToDraft({
  application,
  currentSystemUserId,
}: {
  application: {
    _createdby_value?: string | null;
    ds_stage?: number | null;
  };
  currentSystemUserId: string | null | undefined;
}): boolean {
  const createdBy = normalizeGuid(application._createdby_value);
  const currentUser = normalizeGuid(currentSystemUserId);
  const stage = normalizeApplicationStage(application.ds_stage);
  return Boolean(
    createdBy &&
    currentUser &&
    createdBy === currentUser &&
    stage === ApplicationStage.Submitted,
  );
}

export function canDecideApplication({
  application,
  currentSystemUserId,
}: {
  application: {
    _ds_deciderid_value?: string | null;
    ds_stage?: number | null;
  };
  currentSystemUserId: string | null | undefined;
}): boolean {
  const decider = normalizeGuid(application._ds_deciderid_value);
  const currentUser = normalizeGuid(currentSystemUserId);
  const stage = normalizeApplicationStage(application.ds_stage);
  return Boolean(
    decider &&
    currentUser &&
    decider === currentUser &&
    stage === ApplicationStage.Submitted,
  );
}

export function validateParticipantInput(
  input: ParticipantInput,
): ValidationResult {
  const fieldErrors: Record<string, string> = {};

  if (!input.userId?.trim()) {
    fieldErrors.userId = "ユーザーを選択してください";
  }

  if (input.role == null) {
    fieldErrors.role = "役割を選択してください";
  }

  return {
    valid: Object.keys(fieldErrors).length === 0,
    fieldErrors,
  };
}

export function validateMentionInput(input: MentionInput): ValidationResult {
  const fieldErrors: Record<string, string> = {};

  if (!input.targetUserId?.trim()) {
    fieldErrors.targetUserId = "メンション先を選択してください";
  }

  return {
    valid: Object.keys(fieldErrors).length === 0,
    fieldErrors,
  };
}

export function getDecisionNextApplicationStage(
  decisionOptionName: string | null | undefined,
): ApplicationStageValue {
  return decisionOptionName?.trim() === "差し戻し"
    ? ApplicationStage.Draft
    : ApplicationStage.Decided;
}

export function getParticipantDeleteWaitState(
  isProcessing: boolean,
): OperationWaitState {
  if (!isProcessing) {
    return {
      visible: false,
      title: "",
      description: "",
    };
  }

  return {
    visible: true,
    title: "権限を除外しています",
    description: "Power Automate の処理が完了するまでお待ちください。",
  };
}

export function isIgnorableParticipantRevokeFailure(
  message: string | null | undefined,
): boolean {
  const normalized = message?.toLowerCase() ?? "";
  return (
    normalized.includes("has insufficient privileges") &&
    normalized.includes("principalid:")
  );
}
