import {
  ApplicationStage,
  type Category,
  type ApplicationStageValue,
} from "@/types/decisionflow";

export const EMPTY_CATEGORY_REGULATION_MESSAGE =
  "このカテゴリにはレギュレーションが未設定です。";

export const CATEGORY_REGULATION_MAX_LENGTH = 50000;

export const DEFAULT_APPLICATION_BODY_PLACEHOLDER =
  "背景、判断してほしいこと、選択肢、懸念点を記入";

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

/**
 * 関連資料を作成・削除できるか。
 *
 * `ds_applicationresource` の Create / Delete を持つのは `ds_Applicant` と `ds_Admin` だけ。
 * **`ds_Decider` は Read と AppendTo しか無い**（2026-08-16 に MinoDev2 の
 * `roleprivileges` で実測）。判断者に導線を出すと、フォームを全部埋めさせたうえで
 * 保存時に 403 になる。
 *
 * **「判断者ではない」で代用してはならない。** 判断者と申請者を両方持つ利用者は
 * 作成できるので、その人の導線まで消えてしまう。
 */
export function canManageApplicationResources(input: {
  isAdmin?: boolean | null;
  isApplicant?: boolean | null;
}): boolean {
  return Boolean(input.isAdmin || input.isApplicant);
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

/**
 * 生成した説明文を、利用者が書いた説明の**末尾に付け足す**（G13 第2段）。
 *
 * **上書きしない。** `説明 *` は必須項目で、`validateResourceInput` が空を弾く。
 * 利用者が既に書いた文章を生成結果で潰すと、書き直しを強いることになる。
 * 追記なら非破壊なので、生成を試してから消す・直すが利用者側でできる
 * （`docs/UX_ROADMAP.md`「決定: 生成した説明は末尾に付け足す」）。
 *
 * 同じ文章を2回押しで重ねない。**押したのに何も起きないように見える**より、
 * 重複が積まれるほうが直しにくい。
 */
export function appendGeneratedDescription(
  current: string | null | undefined,
  generated: string | null | undefined,
): string {
  const addition = generated?.trim() ?? "";
  const existing = current?.trimEnd() ?? "";
  if (!addition) return existing;
  if (!existing) return addition;
  if (existing.endsWith(addition)) return existing;
  return `${existing}\n\n${addition}`;
}

/**
 * フローが返す `reason` を利用者向けの文言にする。
 *
 * **フローの生の値を画面へ出さない。** `too-large` をそのまま見せても、
 * 何をすればいいのか分からない。上限のような具体値も文言側に持たせる。
 */
const DESCRIBE_FAILURE_MESSAGES: Record<string, string> = {
  unreadable: "ファイルが見つかりませんでした。URL を確認してください",
  "too-large": "ファイルが大きすぎます（25 MB まで）",
  // ファイルは見つかったが中身を取れなかった。抽出・生成の失敗と分けているのは、
  // **直す場所が違う**から（読み取り / 抽出プロンプト / 説明文プロンプト）。
  "content-unreadable": "ファイルの中身を読み取れませんでした",
  "extract-failed": "資料からテキストを取り出せませんでした",
  "generation-failed": "説明を生成できませんでした",
  // 共有リンクは**本人の資格で解決する**。本人がまだ開いていないリンクは
  // 解決できず、それが正しい挙動（フローが権限を与える装置になってはいけない）。
  // **「失敗」ではなく「まだ開けない」と伝える**のが肝で、そうしないと
  // 次に触る人が「直すために引き換えを足す」方向へ動く。
  "sharing-link-unresolved":
    "この共有リンクをまだ開けません。一度ブラウザで開いてから試してください",
  "sharing-link-unsupported": "この共有リンクにはまだ対応していません",
};

export type DescribeResult = {
  actingAs?: string | null;
  description?: string | null;
  reason?: string | null;
};

export type DescribeOutcome =
  | { kind: "error"; message: string }
  | { kind: "append"; description: string };

/**
 * 説明生成フローの応答を、画面がやることに翻訳する。
 *
 * **判定をコンポーネントに置かない。** ここが「いつ追記してよいか」の唯一の門で、
 * 分岐が5通りある。画面の中に散らすと、追記してはいけないときに追記する退行が
 * テストの外で起きる。
 */
export function resolveDescribeOutcome(
  data: DescribeResult | null | undefined,
): DescribeOutcome {
  // 身元が取れないのは、そのサイトを読む権限が無いとき。フローは呼び出した本人の
  // 資格で動くので（2026-08-16 実測）、**本人が読めないものは読めない**。
  if (!data?.actingAs?.trim()) {
    return { kind: "error", message: "このファイルを読む権限がありません" };
  }

  const failure = DESCRIBE_FAILURE_MESSAGES[data.reason?.trim() ?? ""];
  if (failure) return { kind: "error", message: failure };

  const description = data.description?.trim() ?? "";
  if (!description) {
    return { kind: "error", message: "説明を生成できませんでした" };
  }

  return { kind: "append", description };
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

export function getApplicationBodyPlaceholder(
  categories: Pick<Category, "ds_categoryid" | "ds_template">[],
  categoryId: string | null | undefined,
): string {
  const selectedCategoryId = normalizeGuid(categoryId);
  if (!selectedCategoryId) return DEFAULT_APPLICATION_BODY_PLACEHOLDER;

  const category = categories.find(
    (item) => normalizeGuid(item.ds_categoryid) === selectedCategoryId,
  );
  const template = category?.ds_template?.trim();
  return template || DEFAULT_APPLICATION_BODY_PLACEHOLDER;
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

export const APPLICATION_LIST_SCOPES = ["mine", "all"] as const;
export type ApplicationListScope = (typeof APPLICATION_LIST_SCOPES)[number];

/**
 * 申請リストの表示範囲。
 *
 * **`all` は「全部見せる」ではなく「取得できたものを全部見せる」。**
 * 本当の境界は Dataverse のロールで、読めない申請はそもそもクライアントへ来ない
 * （2026-08-16 に MinoDev2 で実測。申請者には自分の分と共有された分だけが届く）。
 * ここでの絞り込みは**画面の都合**であって、安全のためのものではない。
 */
export function filterApplicationsByScope<
  T extends { _createdby_value?: string | null },
>(
  applications: T[],
  scope: ApplicationListScope,
  currentSystemUserId: string | null | undefined,
): T[] {
  if (scope === "all") return applications;
  return filterRowsForCurrentUser(
    applications as (T & Record<string, unknown>)[],
    currentSystemUserId,
    "_createdby_value",
  );
}

/**
 * 検索とソートのために、行へ**表示名の文字列**を持たせる。
 *
 * `ListTable` の検索もソートも `item[key]` の生の値を見るので、
 * 判断者や申請者を lookup の GUID のまま置くと**GUID を検索することになる**。
 */
export function buildApplicationListRow<
  T extends {
    _ds_deciderid_value?: string | null;
    _createdby_value?: string | null;
    ds_submittedat?: string | null;
    createdon?: string | null;
  },
>(application: T, userName: (id: string | null | undefined) => string) {
  return {
    ...application,
    deciderName: userName(application._ds_deciderid_value) || "未割当",
    applicantName: userName(application._createdby_value),
    // 提出済みなら提出日時、まだなら作成日時。並べ替えの基準を1つにする。
    appliedAt: application.ds_submittedat ?? application.createdon ?? "",
  };
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

export function canReassignApplication({
  application,
  currentSystemUserId,
  isAdmin,
}: {
  application: {
    ds_stage?: ApplicationStageValue | null;
    _ds_deciderid_value?: string | null;
  };
  currentSystemUserId?: string | null;
  isAdmin: boolean;
}) {
  if (application.ds_stage !== ApplicationStage.Submitted) return false;
  if (isAdmin) return true;
  return (
    normalizeGuid(application._ds_deciderid_value) !== null &&
    normalizeGuid(application._ds_deciderid_value) ===
      normalizeGuid(currentSystemUserId)
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

export const RETURNED_APPLICATION_BADGE = {
  label: "差し戻し",
  className: "border-amber-300 bg-amber-50 text-amber-700",
} as const;

/**
 * 差し戻された申請は `ds_stage` が Draft へ戻るため、一度も提出していない下書きと
 * 見分けがつかなくなる。直近の判断が「差し戻し」かどうかで区別する。
 */
export function isApplicationReturnedForRevision(
  stage: number | null | undefined,
  latestDecisionOptionName: string | null | undefined,
): boolean {
  if (normalizeApplicationStage(stage) !== ApplicationStage.Draft) return false;
  if (!latestDecisionOptionName?.trim()) return false;
  return (
    getDecisionNextApplicationStage(latestDecisionOptionName) ===
    ApplicationStage.Draft
  );
}

/**
 * 申請IDから「直近の判断結果の名前」を引く関数を作る。
 * `decisions` は新しい順に並んでいる前提（各申請で最初に現れたものを採用する）。
 */
export function buildLatestDecisionOptionNameLookup(
  decisions: {
    _ds_applicationid_value?: string | null;
    _ds_decisionoptionid_value?: string | null;
  }[],
  decisionOptions: { ds_decisionoptionid: string; ds_name: string }[],
): (applicationId: string | null | undefined) => string | undefined {
  const optionNameById = new Map(
    decisionOptions.map((option) => [
      option.ds_decisionoptionid,
      option.ds_name,
    ]),
  );
  const latestOptionIdByApplication = new Map<string, string>();

  decisions.forEach((decision) => {
    const applicationId = normalizeGuid(decision._ds_applicationid_value);
    if (applicationId && !latestOptionIdByApplication.has(applicationId)) {
      latestOptionIdByApplication.set(
        applicationId,
        decision._ds_decisionoptionid_value ?? "",
      );
    }
  });

  return (applicationId) =>
    optionNameById.get(
      latestOptionIdByApplication.get(normalizeGuid(applicationId) ?? "") ?? "",
    );
}

export type DeciderQueueColumnKey = "submitted" | "returned" | "decided";

/**
 * 判断キューの列振り分け。差し戻された申請は Draft へ戻るため、以前は列が無く
 * 黙って捨てられていた。未提出の下書きは判断者の担当ではないので null を返して
 * 明示的に除外する。
 */
export function getDeciderQueueColumnKey(
  stage: number | null | undefined,
  latestDecisionOptionName: string | null | undefined,
): DeciderQueueColumnKey | null {
  const normalizedStage = normalizeApplicationStage(stage);
  if (normalizedStage === ApplicationStage.Submitted) return "submitted";
  if (normalizedStage === ApplicationStage.Decided) return "decided";
  return isApplicationReturnedForRevision(stage, latestDecisionOptionName)
    ? "returned"
    : null;
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

/**
 * 判断確定後のサーバ反映待ち。
 *
 * **ステージ更新はクライアントではなく `Decision_OnCreated` が行う。**
 * 判断者は `ds_application` を更新できない（`ds_Decider` は Read のみ）ため、
 * クライアントから更新しようとすると 403 になり、成功ハンドラに到達しない。
 * 2026-08-15 に MinoDev2 の実利用者で踏んだ（「C5 第3段は実機で動いていなかった」節）。
 *
 * その代わり反映は**非同期**になる（実測 約4秒）。画面は反映を検知するまで
 * 待機し、**検知できるまで確定済みの表示に切り替えない**。
 */
export const DECISION_REFLECTION_POLL_MS = 1500;

/**
 * 打ち切りまでの時間。実測4秒に対して余裕を大きく取る。
 * ここを短くすると、フローが少し遅れただけで「反映が確認できていない」を出してしまう。
 */
export const DECISION_REFLECTION_TIMEOUT_MS = 30000;

/**
 * 反映済みか。
 *
 * **ステージの一致だけでは足りない。** `Decision_OnCreated` は差し戻しのとき
 * `Update_application_stage` → `Clear_submitted_at_if_returned_to_draft` の
 * **2回に分けて書く**ので、ステージだけを見ると2回の間で反映済みと誤判定し、
 * `ds_submittedat` が残ったまま画面を進めてしまう。
 */
export function isDecisionReflectedOnApplication({
  stage,
  submittedAt,
  expectedStage,
}: {
  stage: number | null | undefined;
  submittedAt: string | null | undefined;
  expectedStage: number;
}): boolean {
  if (normalizeApplicationStage(stage) !== expectedStage) return false;
  // 差し戻しは submittedat の消去まで終わって初めて反映済み。
  if (expectedStage === ApplicationStage.Draft) return !submittedAt;
  return true;
}

export type DecisionReflectionPhase = "waiting" | "reflected" | "timeout";

/**
 * **反映を検知できていれば、経過時間に関わらず反映を優先する。**
 * 打ち切りは「まだ確認できていない」を意味するだけで、判断の成否とは無関係。
 */
export function resolveDecisionReflectionPhase({
  elapsedMs,
  reflected,
  timeoutMs,
}: {
  elapsedMs: number;
  reflected: boolean;
  timeoutMs: number;
}): DecisionReflectionPhase {
  if (reflected) return "reflected";
  return elapsedMs >= timeoutMs ? "timeout" : "waiting";
}

/**
 * **「失敗」と言わない。** 判断は既に記録されており、待っているのは反映だけである。
 */
export function getDecisionReflectionWaitState(
  isWaiting: boolean,
): OperationWaitState {
  if (!isWaiting) return { visible: false, title: "", description: "" };
  return {
    visible: true,
    title: "判断を反映しています",
    description:
      "判断は記録されました。申請の状態に反映されるまでお待ちください。",
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

/**
 * SharePoint / OneDrive の URL を、コネクタが要求する「サイト URL」と
 * 「サイト内のファイルパス」へ分解した結果。
 *
 * `sharing-link` を独立した種別にしているのは、**利用者が実際に貼るのが
 * ほとんどこの形**だから。`:p:/g/personal/.../IQC...` の末尾は暗号化された
 * トークンで、パスを含まない。パス形式と同じ扱いにすると「壊れたパス」として
 * 読みに行き、権限エラーと区別できない失敗になる。
 */
export type SharePointLink =
  | { kind: "path"; siteUrl: string; filePath: string }
  | { kind: "sharing-link"; siteUrl: string; sharingUrl: string }
  | { kind: "unsupported" }
  | { kind: "not-sharepoint" };

/** 共有リンクの種別プレフィックス（`:p:` = PowerPoint、`:w:` = Word など）。 */
const SHARING_LINK_PREFIX = /^:[a-z]:$/;

/**
 * 共有 URL を Graph の `shares` が受け取る形（`u!…`）へ符号化する。
 *
 * 手順は Learn の [Accessing shared DriveItems] のとおり:
 * base64 にして、末尾の `=` を落とし、`/` を `_`、`+` を `-` に置き換え、`u!` を前置。
 *
 * **元の URL をそのまま渡さない。** クエリ（`?e=…`）まで含めて1つのトークンなので、
 * 削ったり正規化したりすると別のリンクになる。
 *
 * 日本語などの非 ASCII を含む URL でも壊れないよう、**UTF-8 のバイト列にしてから**
 * base64 にする（`btoa` は Latin-1 しか受け付けない）。
 */
export function encodeSharingUrl(sharingUrl: string): string {
  const utf8 = new TextEncoder().encode(sharingUrl);
  let binary = "";
  for (const byte of utf8) binary += String.fromCharCode(byte);
  const base64 = btoa(binary);
  return `u!${base64.replace(/=+$/, "").replace(/\//g, "_").replace(/\+/g, "-")}`;
}

export function parseSharePointLink(
  rawUrl: string | null | undefined,
): SharePointLink {
  const trimmed = rawUrl?.trim() ?? "";
  if (!trimmed) return { kind: "not-sharepoint" };

  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    return { kind: "not-sharepoint" };
  }

  if (parsed.protocol !== "https:") return { kind: "not-sharepoint" };
  const host = parsed.hostname.toLowerCase();
  if (!host.endsWith(".sharepoint.com")) return { kind: "not-sharepoint" };

  const segments = parsed.pathname
    .split("/")
    .filter(Boolean)
    .map((segment) => decodeURIComponent(segment));
  if (segments.length === 0) return { kind: "unsupported" };

  if (SHARING_LINK_PREFIX.test(segments[0])) {
    // **サイトを取り出すのは、コネクタが「どのサイトへ REST を投げるか」を
    // 要求するから**（トークン自体はテナント内で解決される）。
    //
    // 2つ目のセグメントが範囲を表す記号で、**その後ろの読み方が記号ごとに違う**。
    //
    //   `/:p:/g/personal/<user>/<token>` … `g` の後ろは実パス（`personal/<user>`）
    //   `/:w:/s/<siteName>/<token>`      … `s` の後ろは**サイト名だけ**（`sites/` は入らない）
    //   `/:x:/t/<teamName>/<token>`      … `t` も同様
    //
    // `s` を `g` と同じ「実パス」と読むとサイトが取れない。**テストで捕まえた。**
    const scope = (segments[1] ?? "").toLowerCase();
    const rest = segments.slice(2);
    let siteSegments: string[] = [];
    if (scope === "g") {
      siteSegments = ["personal", "sites", "teams"].includes(
        (rest[0] ?? "").toLowerCase(),
      )
        ? rest.slice(0, 2)
        : [];
    } else if (scope === "s" && rest[0]) {
      siteSegments = ["sites", rest[0]];
    } else if (scope === "t" && rest[0]) {
      siteSegments = ["teams", rest[0]];
    }

    return {
      kind: "sharing-link",
      // 記号が読めなければサイトを付けず、テナントのルートへ投げる。
      // Diego がルートサイトに到達できることは第1段で実測済み。
      siteUrl: [parsed.origin, ...siteSegments].join("/"),
      // **クエリまで含めて元のまま渡す。** `?e=…` はトークンの一部。
      sharingUrl: trimmed,
    };
  }

  // `_layouts/15/Doc.aspx?sourcedoc={GUID}` 形式もパスを持たない。
  if (segments.some((segment) => segment.toLowerCase() === "_layouts")) {
    return { kind: "unsupported" };
  }

  // サイトの区切りは `/personal/<user>`、`/sites/<name>`、`/teams/<name>`。
  // どれでもなければテナントのルートサイト。
  const scoped = ["personal", "sites", "teams"].includes(
    segments[0].toLowerCase(),
  );
  const siteSegments = scoped ? segments.slice(0, 2) : [];
  const pathSegments = scoped ? segments.slice(2) : segments;

  if (scoped && segments.length < 2) return { kind: "unsupported" };
  if (pathSegments.length === 0) return { kind: "unsupported" };

  return {
    kind: "path",
    siteUrl: [parsed.origin, ...siteSegments].join("/"),
    filePath: `/${pathSegments.join("/")}`,
  };
}
