import { describe, expect, it } from "vitest";

import {
  parseSharePointLink,
  applicantSelectableStageValues,
  buildLatestDecisionOptionNameLookup,
  canDecideApplication,
  canReassignApplication,
  canEditMasterData,
  canRefreshAiDecisionFromDecisionTab,
  canEditApplication,
  canReturnApplicationToDraft,
  DEFAULT_APPLICATION_BODY_PLACEHOLDER,
  getAiCheckWaitState,
  getAiResultDialogConfig,
  getApplicationBodyPlaceholder,
  getApplicationDecisionDetailPath,
  getDecisionNextApplicationStage,
  getDeciderQueueApplications,
  getDeciderQueueColumnKey,
  getDecisionReflectionWaitState,
  getParticipantDeleteWaitState,
  isDecisionReflectedOnApplication,
  resolveDecisionReflectionPhase,
  getSelectedCategoryRegulationInfo,
  getSelectedCategoryRegulationText,
  isApplicationReturnedForRevision,
  isIgnorableParticipantRevokeFailure,
  appendGeneratedDescription,
  encodeSharingUrl,
  resolveDescribeOutcome,
  resolveDescribeRequest,
  buildApplicationListRow,
  canManageApplicationResources,
  filterApplicationsByScope,
  filterRowsForCurrentUser,
  isApplicantSelectableStage,
  shouldShowMasterManagementNavigation,
  shouldRequireCategoryForSubmission,
  validateCategoryRegulationInput,
  validateApplicationInput,
  validateMentionInput,
  validateParticipantInput,
  validateResourceInput,
} from "./decisionflow-utils";
import { ApplicationStage } from "@/types/decisionflow";

describe("master management access", () => {
  it("shows master management navigation to every user", () => {
    expect(shouldShowMasterManagementNavigation()).toBe(true);
  });

  it("allows only admin or decider to edit master data", () => {
    expect(canEditMasterData({ isAdmin: true, isDecider: false })).toBe(true);
    expect(canEditMasterData({ isAdmin: false, isDecider: true })).toBe(true);
    expect(canEditMasterData({ isAdmin: false, isDecider: false })).toBe(false);
  });
});

describe("filterApplicationsByScope", () => {
  const rows = [
    { id: "1", _createdby_value: "USER-A" },
    { id: "2", _createdby_value: "USER-B" },
    { id: "3", _createdby_value: undefined },
  ];

  it("returns every row that reached the client when scope is all", () => {
    // 読めない申請はそもそも来ないので、ここで絞るのは画面の都合でしかない。
    expect(filterApplicationsByScope(rows, "all", "user-a")).toEqual(rows);
  });

  it("keeps only rows created by the current user when scope is mine", () => {
    expect(filterApplicationsByScope(rows, "mine", "user-a")).toEqual([rows[0]]);
  });

  it("still returns everything for scope all when the user is unresolved", () => {
    // 本人が引けないときに「全体」まで空にすると、何も見えない画面になる。
    expect(filterApplicationsByScope(rows, "all", null)).toEqual(rows);
    expect(filterApplicationsByScope(rows, "mine", null)).toEqual([]);
  });
});

describe("buildApplicationListRow", () => {
  const userName = (id: string | null | undefined) =>
    id === "DECIDER" ? "Archie Grady" : id === "APPLICANT" ? "Diego" : "";

  it("puts display names on the row so search and sort see text, not GUIDs", () => {
    const row = buildApplicationListRow(
      {
        _ds_deciderid_value: "DECIDER",
        _createdby_value: "APPLICANT",
        ds_submittedat: "2026-08-16T00:00:00Z",
        createdon: "2026-08-01T00:00:00Z",
      },
      userName,
    );

    expect(row.deciderName).toBe("Archie Grady");
    expect(row.applicantName).toBe("Diego");
  });

  it("labels an unassigned decider instead of leaving it blank", () => {
    const row = buildApplicationListRow({ _ds_deciderid_value: null }, userName);
    expect(row.deciderName).toBe("未割当");
  });

  it("falls back to createdon when the application is not submitted yet", () => {
    expect(
      buildApplicationListRow(
        { ds_submittedat: null, createdon: "2026-08-01T00:00:00Z" },
        userName,
      ).appliedAt,
    ).toBe("2026-08-01T00:00:00Z");
    expect(
      buildApplicationListRow(
        { ds_submittedat: "2026-08-16T00:00:00Z", createdon: "2026-08-01T00:00:00Z" },
        userName,
      ).appliedAt,
    ).toBe("2026-08-16T00:00:00Z");
  });
});

describe("canManageApplicationResources", () => {
  it("allows applicants and admins, who hold Create on ds_applicationresource", () => {
    expect(
      canManageApplicationResources({ isAdmin: false, isApplicant: true }),
    ).toBe(true);
    expect(
      canManageApplicationResources({ isAdmin: true, isApplicant: false }),
    ).toBe(true);
  });

  it("denies a decider-only user, who has Read and AppendTo but no Create", () => {
    expect(
      canManageApplicationResources({ isAdmin: false, isApplicant: false }),
    ).toBe(false);
  });

  it("allows a user holding both decider and applicant roles", () => {
    // 「判断者ではない」で代用すると、この利用者の導線まで消える。
    expect(canManageApplicationResources({ isApplicant: true })).toBe(true);
  });

  it("denies when the role flags are still unresolved", () => {
    expect(canManageApplicationResources({})).toBe(false);
    expect(
      canManageApplicationResources({ isAdmin: null, isApplicant: undefined }),
    ).toBe(false);
  });
});

describe("validateResourceInput", () => {
  it("requires URL when resource type is Link", () => {
    const result = validateResourceInput({
      title: "見積条件の根拠",
      url: "",
      description: "根拠となる見積条件の詳細",
    });

    expect(result.valid).toBe(false);
    expect(result.fieldErrors.url).toBe("リンク資料では URL が必須です");
  });

  it("requires description", () => {
    const result = validateResourceInput({
      title: "SharePoint 資料",
      url: "https://example.com/resource",
      description: "",
    });

    expect(result.valid).toBe(false);
    expect(result.fieldErrors.description).toBe(
      "説明が必須です（AI 判断に活用されます）",
    );
  });

  it("accepts valid link resource input", () => {
    const result = validateResourceInput({
      title: "SharePoint 資料",
      url: "https://example.com/resource",
      description: "見積条件の根拠資料。承認条件の範囲と例外理由を記載。",
    });

    expect(result.valid).toBe(true);
    expect(result.fieldErrors).toEqual({});
  });
});

describe("filterRowsForCurrentUser", () => {
  it("returns empty rows when current system user is unresolved", () => {
    const rows = [
      { id: "1", _ds_targetuserid_value: "USER-A" },
      { id: "2", _ds_targetuserid_value: "USER-B" },
    ];

    expect(
      filterRowsForCurrentUser(rows, null, "_ds_targetuserid_value"),
    ).toEqual([]);
  });

  it("matches GUID values case-insensitively", () => {
    const rows = [
      { id: "1", _ds_targetuserid_value: "ABC-123" },
      { id: "2", _ds_targetuserid_value: "DEF-456" },
    ];

    expect(
      filterRowsForCurrentUser(rows, "abc-123", "_ds_targetuserid_value"),
    ).toEqual([rows[0]]);
  });
});

describe("getDeciderQueueApplications", () => {
  it("returns only applications assigned to the current decider", () => {
    const rows = [
      { id: "1", _ds_deciderid_value: "USER-A" },
      { id: "2", _ds_deciderid_value: "USER-B" },
      { id: "3", _ds_deciderid_value: undefined },
    ];

    expect(getDeciderQueueApplications(rows, "user-a")).toEqual([rows[0]]);
  });

  it("returns empty rows when current decider is unresolved", () => {
    const rows = [{ id: "1", _ds_deciderid_value: "USER-A" }];

    expect(getDeciderQueueApplications(rows, null)).toEqual([]);
  });
});

describe("canEditApplication", () => {
  it("allows the creator to edit a draft application", () => {
    expect(
      canEditApplication({
        application: {
          _createdby_value: "USER-A",
          ds_stage: 100000000,
        },
        currentSystemUserId: "user-a",
      }),
    ).toBe(true);
  });

  it("prevents non-creators from editing an application", () => {
    expect(
      canEditApplication({
        application: {
          _createdby_value: "USER-A",
          ds_stage: 100000000,
        },
        currentSystemUserId: "USER-B",
      }),
    ).toBe(false);
  });

  it("prevents editing when current user is unresolved", () => {
    expect(
      canEditApplication({
        application: {
          _createdby_value: undefined,
          ds_stage: 100000000,
        },
        currentSystemUserId: null,
      }),
    ).toBe(false);
  });

  it("prevents editing decided applications", () => {
    expect(
      canEditApplication({
        application: {
          _createdby_value: "USER-A",
          ds_stage: 100000004,
        },
        currentSystemUserId: "user-a",
      }),
    ).toBe(false);
  });

  it("prevents editing submitted applications", () => {
    expect(
      canEditApplication({
        application: {
          _createdby_value: "USER-A",
          ds_stage: 100000001,
        },
        currentSystemUserId: "user-a",
      }),
    ).toBe(false);
  });
});

describe("canReassignApplication", () => {
  const submitted = {
    ds_stage: ApplicationStage.Submitted,
    _ds_deciderid_value: "USER-A",
  };

  it("allows the current decider or an admin for submitted applications", () => {
    expect(
      canReassignApplication({
        application: submitted,
        currentSystemUserId: "user-a",
        isAdmin: false,
      }),
    ).toBe(true);
    expect(
      canReassignApplication({
        application: submitted,
        currentSystemUserId: "user-b",
        isAdmin: true,
      }),
    ).toBe(true);
  });

  it("rejects other users and non-submitted applications", () => {
    expect(
      canReassignApplication({
        application: submitted,
        currentSystemUserId: "user-b",
        isAdmin: false,
      }),
    ).toBe(false);
    expect(
      canReassignApplication({
        application: { ...submitted, ds_stage: ApplicationStage.Decided },
        currentSystemUserId: "user-a",
        isAdmin: true,
      }),
    ).toBe(false);
  });
});

describe("canReturnApplicationToDraft", () => {
  it("allows the creator to return a submitted application to draft", () => {
    expect(
      canReturnApplicationToDraft({
        application: {
          _createdby_value: "USER-A",
          ds_stage: 100000001,
        },
        currentSystemUserId: "user-a",
      }),
    ).toBe(true);
  });

  it("prevents returning draft or decided applications to draft", () => {
    expect(
      canReturnApplicationToDraft({
        application: {
          _createdby_value: "USER-A",
          ds_stage: 100000000,
        },
        currentSystemUserId: "user-a",
      }),
    ).toBe(false);

    expect(
      canReturnApplicationToDraft({
        application: {
          _createdby_value: "USER-A",
          ds_stage: 100000004,
        },
        currentSystemUserId: "user-a",
      }),
    ).toBe(false);
  });

  it("prevents non-creators from returning submitted applications to draft", () => {
    expect(
      canReturnApplicationToDraft({
        application: {
          _createdby_value: "USER-A",
          ds_stage: 100000001,
        },
        currentSystemUserId: "USER-B",
      }),
    ).toBe(false);
  });
});

describe("canDecideApplication", () => {
  it("allows the assigned decider to decide a submitted application", () => {
    expect(
      canDecideApplication({
        application: {
          _ds_deciderid_value: "USER-A",
          ds_stage: 100000001,
        },
        currentSystemUserId: "user-a",
      }),
    ).toBe(true);
  });

  it("prevents non-deciders from deciding a submitted application", () => {
    expect(
      canDecideApplication({
        application: {
          _ds_deciderid_value: "USER-A",
          ds_stage: 100000001,
        },
        currentSystemUserId: "USER-B",
      }),
    ).toBe(false);
  });

  it("prevents the assigned decider from deciding draft or decided applications", () => {
    expect(
      canDecideApplication({
        application: {
          _ds_deciderid_value: "USER-A",
          ds_stage: 100000000,
        },
        currentSystemUserId: "user-a",
      }),
    ).toBe(false);

    expect(
      canDecideApplication({
        application: {
          _ds_deciderid_value: "USER-A",
          ds_stage: 100000004,
        },
        currentSystemUserId: "user-a",
      }),
    ).toBe(false);
  });

  it("prevents deciding when current user is unresolved", () => {
    expect(
      canDecideApplication({
        application: {
          _ds_deciderid_value: "USER-A",
          ds_stage: 100000001,
        },
        currentSystemUserId: null,
      }),
    ).toBe(false);
  });
});

describe("applicant stage rules", () => {
  it("allows applicants to choose only draft or submitted", () => {
    expect(applicantSelectableStageValues).toEqual([100000000, 100000001]);
    expect(isApplicantSelectableStage(100000000)).toBe(true);
    expect(isApplicantSelectableStage(100000001)).toBe(true);
    expect(isApplicantSelectableStage(100000004)).toBe(false);
  });
});

describe("validateApplicationInput", () => {
  it("requires a decider when submitting an application", () => {
    const result = validateApplicationInput({
      name: "判断依頼",
      body: "本文",
      stage: 100000001,
      deciderId: "",
    });

    expect(result.valid).toBe(false);
    expect(result.fieldErrors.deciderId).toBe(
      "提出時は判断者を選択してください",
    );
  });

  it("allows draft applications without a decider", () => {
    const result = validateApplicationInput({
      name: "判断依頼",
      body: "本文",
      stage: 100000000,
      deciderId: "",
    });

    expect(result.valid).toBe(true);
    expect(result.fieldErrors).toEqual({});
  });

  it("requires a category for final submission when category master rows exist", () => {
    const result = validateApplicationInput({
      name: "判断依頼",
      body: "本文",
      stage: 100000001,
      deciderId: "decider-1",
      categoryId: "",
      categoriesAvailable: true,
    });

    expect(result.valid).toBe(false);
    expect(result.fieldErrors.categoryId).toBe(
      "提出時はカテゴリを選択してください",
    );
  });

  it("allows final submission without a category when no category master rows exist", () => {
    const result = validateApplicationInput({
      name: "判断依頼",
      body: "本文",
      stage: 100000001,
      deciderId: "decider-1",
      categoryId: "",
      categoriesAvailable: false,
    });

    expect(result.valid).toBe(true);
    expect(result.fieldErrors).toEqual({});
  });
});

describe("returned-for-revision detection", () => {
  it("treats a draft whose latest decision is 差し戻し as returned", () => {
    expect(
      isApplicationReturnedForRevision(ApplicationStage.Draft, "差し戻し"),
    ).toBe(true);
  });

  it("does not treat a draft that was never decided as returned", () => {
    expect(
      isApplicationReturnedForRevision(ApplicationStage.Draft, undefined),
    ).toBe(false);
    expect(isApplicationReturnedForRevision(ApplicationStage.Draft, "")).toBe(
      false,
    );
    expect(isApplicationReturnedForRevision(ApplicationStage.Draft, "  ")).toBe(
      false,
    );
  });

  it("does not treat a draft whose latest decision is not 差し戻し as returned", () => {
    expect(
      isApplicationReturnedForRevision(ApplicationStage.Draft, "承認"),
    ).toBe(false);
    expect(
      isApplicationReturnedForRevision(ApplicationStage.Draft, "却下"),
    ).toBe(false);
  });

  it("does not treat submitted or decided applications as returned", () => {
    expect(
      isApplicationReturnedForRevision(ApplicationStage.Submitted, "差し戻し"),
    ).toBe(false);
    expect(
      isApplicationReturnedForRevision(ApplicationStage.Decided, "差し戻し"),
    ).toBe(false);
  });
});

describe("latest decision option lookup", () => {
  const decisionOptions = [
    { ds_decisionoptionid: "option-approve", ds_name: "承認" },
    { ds_decisionoptionid: "option-return", ds_name: "差し戻し" },
  ];

  it("returns the first decision listed for each application", () => {
    const lookup = buildLatestDecisionOptionNameLookup(
      [
        {
          _ds_applicationid_value: "app-1",
          _ds_decisionoptionid_value: "option-return",
        },
        {
          _ds_applicationid_value: "app-1",
          _ds_decisionoptionid_value: "option-approve",
        },
      ],
      decisionOptions,
    );

    expect(lookup("app-1")).toBe("差し戻し");
  });

  it("matches application ids case-insensitively via normalizeGuid", () => {
    const lookup = buildLatestDecisionOptionNameLookup(
      [
        {
          _ds_applicationid_value: "APP-1",
          _ds_decisionoptionid_value: "option-approve",
        },
      ],
      decisionOptions,
    );

    expect(lookup("app-1")).toBe("承認");
  });

  it("returns undefined for applications without a decision", () => {
    const lookup = buildLatestDecisionOptionNameLookup([], decisionOptions);

    expect(lookup("app-1")).toBe(undefined);
    expect(lookup(undefined)).toBe(undefined);
  });
});

describe("decider queue column assignment", () => {
  it("puts submitted applications in the submitted column", () => {
    expect(
      getDeciderQueueColumnKey(ApplicationStage.Submitted, undefined),
    ).toBe("submitted");
  });

  it("puts decided applications in the decided column", () => {
    expect(getDeciderQueueColumnKey(ApplicationStage.Decided, "承認")).toBe(
      "decided",
    );
    expect(getDeciderQueueColumnKey(ApplicationStage.Decided, "差し戻し")).toBe(
      "decided",
    );
  });

  it("keeps returned applications visible instead of dropping them", () => {
    expect(getDeciderQueueColumnKey(ApplicationStage.Draft, "差し戻し")).toBe(
      "returned",
    );
  });

  it("excludes drafts that were never decided", () => {
    expect(getDeciderQueueColumnKey(ApplicationStage.Draft, undefined)).toBe(
      null,
    );
    expect(getDeciderQueueColumnKey(ApplicationStage.Draft, "")).toBe(null);
  });
});

describe("category regulation helpers", () => {
  const categories = [
    {
      ds_categoryid: "category-1",
      ds_name: "顧客案件",
      ds_regulationtext: "契約条件と収益影響を確認する。",
    },
  ];

  it("requires category only when category master rows exist", () => {
    expect(shouldRequireCategoryForSubmission(categories)).toBe(true);
    expect(shouldRequireCategoryForSubmission([])).toBe(false);
  });

  it("returns selected regulation text for applicant read-only display", () => {
    expect(getSelectedCategoryRegulationText(categories, "category-1")).toBe(
      "契約条件と収益影響を確認する。",
    );
  });

  it("returns selected regulation dialog information without changing form layout", () => {
    expect(getSelectedCategoryRegulationInfo(categories, "CATEGORY-1")).toEqual(
      {
        categoryName: "顧客案件",
        regulationText: "契約条件と収益影響を確認する。",
      },
    );
  });

  it("uses the selected category recommended format as the body placeholder", () => {
    const withTemplate = [
      {
        ds_categoryid: "category-1",
        ds_template: "背景 / 顧客影響 / 判断してほしいこと / 期限 / 関連資料",
      },
    ];

    expect(getApplicationBodyPlaceholder(withTemplate, "CATEGORY-1")).toBe(
      "背景 / 顧客影響 / 判断してほしいこと / 期限 / 関連資料",
    );
  });

  it("falls back to the default body placeholder when no category is selected", () => {
    expect(getApplicationBodyPlaceholder(categories, "")).toBe(
      DEFAULT_APPLICATION_BODY_PLACEHOLDER,
    );
    expect(getApplicationBodyPlaceholder(categories, null)).toBe(
      DEFAULT_APPLICATION_BODY_PLACEHOLDER,
    );
  });

  it("falls back to the default body placeholder when the category has no recommended format", () => {
    expect(
      getApplicationBodyPlaceholder(
        [{ ds_categoryid: "category-1", ds_template: "   " }],
        "category-1",
      ),
    ).toBe(DEFAULT_APPLICATION_BODY_PLACEHOLDER);

    expect(
      getApplicationBodyPlaceholder(
        [{ ds_categoryid: "category-1" }],
        "category-1",
      ),
    ).toBe(DEFAULT_APPLICATION_BODY_PLACEHOLDER);
  });

  it("falls back to the default body placeholder when the category is not found", () => {
    expect(getApplicationBodyPlaceholder(categories, "missing-category")).toBe(
      DEFAULT_APPLICATION_BODY_PLACEHOLDER,
    );
  });

  it("returns missing regulation copy for empty selected category regulation", () => {
    expect(
      getSelectedCategoryRegulationText(
        [
          {
            ds_categoryid: "category-1",
            ds_name: "顧客案件",
            ds_regulationtext: "",
          },
        ],
        "category-1",
      ),
    ).toBe("このカテゴリにはレギュレーションが未設定です。");
  });

  it("validates long regulation text with the Dataverse Memo limit", () => {
    expect(validateCategoryRegulationInput("a".repeat(50000)).valid).toBe(true);
    const result = validateCategoryRegulationInput("a".repeat(50001));
    expect(result.valid).toBe(false);
    expect(result.fieldErrors.regulationText).toContain("50000文字以内");
  });
});

describe("AI check feedback helpers", () => {
  it("allows decision-tab AI refresh before an application is decided", () => {
    expect(canRefreshAiDecisionFromDecisionTab(100000000, false)).toBe(true);
    expect(canRefreshAiDecisionFromDecisionTab(100000001, false)).toBe(true);
  });

  it("blocks decision-tab AI refresh only after decided or while pending", () => {
    expect(canRefreshAiDecisionFromDecisionTab(100000004, false)).toBe(false);
    expect(canRefreshAiDecisionFromDecisionTab(100000001, true)).toBe(false);
  });

  it("shows a blocking wait message while AI judgment is running", () => {
    expect(getAiCheckWaitState(true)).toEqual({
      visible: true,
      title: "AI判断を生成しています ✨",
      description:
        "申請内容とカテゴリ別レギュレーションを確認しています。このままお待ちください ☕",
    });
    expect(getAiCheckWaitState(false).visible).toBe(false);
  });

  it("uses a read-only AI result dialog for draft pre-check", () => {
    expect(getAiResultDialogConfig("draft")).toEqual({
      title: "AI事前確認が完了しました ✨",
      primaryLabel: "閉じる",
      showFinalSubmit: false,
      showKeepDraft: false,
    });
  });

  it("uses final submit actions for submit-time AI result dialog", () => {
    expect(getAiResultDialogConfig("submit")).toEqual({
      title: "AI判断結果を確認しましたか？ 🔎",
      primaryLabel: "本提出",
      showFinalSubmit: true,
      showKeepDraft: true,
    });
  });

  it("builds a decision-tab detail link for AI result details", () => {
    expect(getApplicationDecisionDetailPath("application-1")).toBe(
      "/applications/application-1?tab=decision",
    );
    expect(getApplicationDecisionDetailPath(null)).toBeNull();
  });
});

describe("validateParticipantInput", () => {
  it("requires a user and role", () => {
    const result = validateParticipantInput({ userId: "", role: undefined });

    expect(result.valid).toBe(false);
    expect(result.fieldErrors.userId).toBe("ユーザーを選択してください");
    expect(result.fieldErrors.role).toBe("役割を選択してください");
  });
});

describe("validateMentionInput", () => {
  it("requires a target user when creating a mention", () => {
    const result = validateMentionInput({ targetUserId: "" });

    expect(result.valid).toBe(false);
    expect(result.fieldErrors.targetUserId).toBe(
      "メンション先を選択してください",
    );
  });

  it("accepts a selected mention target", () => {
    const result = validateMentionInput({ targetUserId: "USER-A" });

    expect(result.valid).toBe(true);
    expect(result.fieldErrors).toEqual({});
  });
});

describe("getDecisionNextApplicationStage", () => {
  it("returns draft when the decision option is send back", () => {
    expect(getDecisionNextApplicationStage("差し戻し")).toBe(100000000);
  });

  it("returns decided for regular decision options", () => {
    expect(getDecisionNextApplicationStage("承認")).toBe(100000004);
    expect(getDecisionNextApplicationStage(undefined)).toBe(100000004);
  });
});

describe("getParticipantDeleteWaitState", () => {
  it("shows flow waiting copy while participant deletion is processing", () => {
    expect(getParticipantDeleteWaitState(true)).toEqual({
      visible: true,
      title: "権限を除外しています",
      description: "Power Automate の処理が完了するまでお待ちください。",
    });
  });

  it("hides waiting copy when participant deletion is idle", () => {
    expect(getParticipantDeleteWaitState(false)).toEqual({
      visible: false,
      title: "",
      description: "",
    });
  });
});

describe("isIgnorableParticipantRevokeFailure", () => {
  it("allows deletion to continue when revoke fails because the target support user lacks privileges", () => {
    expect(
      isIgnorableParticipantRevokeFailure(
        "The support user has insufficient privileges. OrgType :13 and PrincipalId: a8ddab2d-026b-f011-b4cc-6045bdeb657d",
      ),
    ).toBe(true);
  });

  it("keeps unrelated revoke failures blocking deletion", () => {
    expect(isIgnorableParticipantRevokeFailure("Access revoke failed.")).toBe(
      false,
    );
    expect(isIgnorableParticipantRevokeFailure(undefined)).toBe(false);
  });
});

describe("判断確定後のサーバ反映待ち", () => {
  it("反映は「ステージ一致」だけでは足りない。差し戻しは submittedat の消去まで見る", () => {
    // Decision_OnCreated は差し戻し時に2回書く（ステージ更新 → submittedat クリア）。
    // ステージだけを見ると、その2回の間で反映済みと誤判定し、submittedat が
    // 残ったまま画面を進めてしまう。
    expect(
      isDecisionReflectedOnApplication({
        stage: 100000000,
        submittedAt: "2026-08-15T00:44:32Z",
        expectedStage: 100000000,
      }),
    ).toBe(false);
    expect(
      isDecisionReflectedOnApplication({
        stage: 100000000,
        submittedAt: null,
        expectedStage: 100000000,
      }),
    ).toBe(true);
  });

  it("承認・却下は submittedat を消さないので、ステージ一致だけで反映とみなす", () => {
    expect(
      isDecisionReflectedOnApplication({
        stage: 100000004,
        submittedAt: "2026-08-15T00:44:32Z",
        expectedStage: 100000004,
      }),
    ).toBe(true);
    expect(
      isDecisionReflectedOnApplication({
        stage: 100000001,
        submittedAt: "2026-08-15T00:44:32Z",
        expectedStage: 100000004,
      }),
    ).toBe(false);
  });

  it("待機中は「記録済み・反映待ち」と伝える。失敗とは言わない", () => {
    const waiting = getDecisionReflectionWaitState(true);
    expect(waiting.visible).toBe(true);
    expect(waiting.title).toContain("反映");
    expect(`${waiting.title}${waiting.description}`).not.toContain("失敗");
    expect(getDecisionReflectionWaitState(false).visible).toBe(false);
  });

  it("待ち切れなくても失敗ではない。記録済みであることを保ったまま打ち切る", () => {
    expect(
      resolveDecisionReflectionPhase({
        elapsedMs: 0,
        reflected: false,
        timeoutMs: 30000,
      }),
    ).toBe("waiting");
    expect(
      resolveDecisionReflectionPhase({
        elapsedMs: 5000,
        reflected: true,
        timeoutMs: 30000,
      }),
    ).toBe("reflected");
    expect(
      resolveDecisionReflectionPhase({
        elapsedMs: 30000,
        reflected: false,
        timeoutMs: 30000,
      }),
    ).toBe("timeout");
  });

  it("打ち切り時刻ちょうどでも、反映を検知できていれば反映を優先する", () => {
    expect(
      resolveDecisionReflectionPhase({
        elapsedMs: 999999,
        reflected: true,
        timeoutMs: 30000,
      }),
    ).toBe("reflected");
  });
});

describe("parseSharePointLink", () => {
  it("個人用 OneDrive のパス形式をサイトとパスに割る", () => {
    expect(
      parseSharePointLink(
        "https://contoso-my.sharepoint.com/personal/admin_contoso_com/Documents/plan.pptx",
      ),
    ).toEqual({
      kind: "path",
      siteUrl:
        "https://contoso-my.sharepoint.com/personal/admin_contoso_com",
      filePath: "/Documents/plan.pptx",
    });
  });

  it("日本語ファイル名がパーセント符号化された実物の URL を解ける", () => {
    // ブラウザからコピーすると日本語は必ずこの形になる。**実測に使った実物。**
    // 符号化されたまま SharePoint へ渡すと、二重符号化でファイルが見つからない。
    expect(
      parseSharePointLink(
        "https://contoso-my.sharepoint.com/personal/taro_contoso_com/Documents/%E3%83%AC%E3%83%9D%E3%83%BC%E3%83%88%E5%85%B1%E6%9C%89%E3%81%AB%E3%81%A4%E3%81%84%E3%81%A6_skill.pptx",
      ),
    ).toEqual({
      kind: "path",
      siteUrl:
        "https://contoso-my.sharepoint.com/personal/taro_contoso_com",
      filePath: "/Documents/レポート共有について_skill.pptx",
    });
  });

  it("チームサイトのパス形式で、サイトの区切りを /sites/<name> にする", () => {
    expect(
      parseSharePointLink(
        "https://contoso.sharepoint.com/sites/Sales/Shared%20Documents/q3.docx",
      ),
    ).toEqual({
      kind: "path",
      siteUrl: "https://contoso.sharepoint.com/sites/Sales",
      filePath: "/Shared Documents/q3.docx",
    });
  });

  it("共有リンクをパス形式と混同せず、サイトと元 URL を持たせる", () => {
    // ここを path として扱うと、トークンをパスとして読みに行き、
    // 権限エラーと区別できない失敗になる。**利用者が貼るのはほぼこの形。**
    expect(
      parseSharePointLink(
        "https://contoso-my.sharepoint.com/:p:/g/personal/admin_contoso_com/IQCLYXUHAUcfTYaxzoGHQC0d?e=bibmNR",
      ),
    ).toEqual({
      kind: "sharing-link",
      siteUrl:
        "https://contoso-my.sharepoint.com/personal/admin_contoso_com",
      // **クエリまで含めて元のまま。** `?e=…` はトークンの一部で、削ると別のリンクになる。
      sharingUrl:
        "https://contoso-my.sharepoint.com/:p:/g/personal/admin_contoso_com/IQCLYXUHAUcfTYaxzoGHQC0d?e=bibmNR",
    });
  });

  it("チームサイトの共有リンクからもサイトを取り出す", () => {
    expect(
      parseSharePointLink(
        "https://contoso.sharepoint.com/:w:/s/Sales/EYt1234abcd?e=xyz",
      ),
    ).toEqual({
      kind: "sharing-link",
      siteUrl: "https://contoso.sharepoint.com/sites/Sales",
      sharingUrl: "https://contoso.sharepoint.com/:w:/s/Sales/EYt1234abcd?e=xyz",
    });
  });

  it("sourcedoc 形式のようなパスを持たない URL を弾く", () => {
    expect(
      parseSharePointLink(
        "https://contoso.sharepoint.com/sites/Sales/_layouts/15/Doc.aspx?sourcedoc=%7Bguid%7D",
      ),
    ).toEqual({ kind: "unsupported" });
  });

  it("サイトだけでファイルを指していない URL を弾く", () => {
    expect(
      parseSharePointLink("https://contoso.sharepoint.com/sites/Sales"),
    ).toEqual({ kind: "unsupported" });
  });

  it("SharePoint 以外や壊れた URL を種別で区別する", () => {
    expect(parseSharePointLink("https://example.com/a/b.docx")).toEqual({
      kind: "not-sharepoint",
    });
    expect(parseSharePointLink("not a url")).toEqual({ kind: "not-sharepoint" });
    expect(parseSharePointLink("")).toEqual({ kind: "not-sharepoint" });
    // http は SharePoint Online では成立しない。
    expect(
      parseSharePointLink("http://contoso.sharepoint.com/sites/S/a.docx"),
    ).toEqual({ kind: "not-sharepoint" });
  });
});

describe("appendGeneratedDescription", () => {
  it("利用者が書いた説明を上書きせず末尾に足す", () => {
    expect(appendGeneratedDescription("手で書いた要点", "生成された説明")).toBe(
      "手で書いた要点\n\n生成された説明",
    );
  });

  it("説明が空なら生成結果だけを置く（先頭に空行を作らない）", () => {
    expect(appendGeneratedDescription("", "生成された説明")).toBe(
      "生成された説明",
    );
    expect(appendGeneratedDescription(null, "生成された説明")).toBe(
      "生成された説明",
    );
    expect(appendGeneratedDescription("   \n ", "生成された説明")).toBe(
      "生成された説明",
    );
  });

  it("生成結果が空なら既存の説明を変えない", () => {
    expect(appendGeneratedDescription("手で書いた要点", "")).toBe(
      "手で書いた要点",
    );
    expect(appendGeneratedDescription("手で書いた要点", "  ")).toBe(
      "手で書いた要点",
    );
    expect(appendGeneratedDescription("手で書いた要点", undefined)).toBe(
      "手で書いた要点",
    );
  });

  it("同じ生成結果を2回押しても重ねない", () => {
    const once = appendGeneratedDescription("手で書いた要点", "生成された説明");
    expect(appendGeneratedDescription(once, "生成された説明")).toBe(once);
  });

  it("末尾の空白は落とすが、途中の改行は保つ", () => {
    expect(appendGeneratedDescription("一行目\n二行目  \n", "生成")).toBe(
      "一行目\n二行目\n\n生成",
    );
  });
});

describe("resolveDescribeOutcome", () => {
  const ok = {
    actingAs: "i:0#.f|membership|taro@contoso.com",
    description: "Power BI のレポート共有パターンをまとめた勉強会資料です。",
    reason: "",
  };

  it("身元と説明が揃っていれば追記する", () => {
    expect(resolveDescribeOutcome(ok)).toEqual({
      kind: "append",
      description: ok.description,
    });
  });

  it("身元が取れないときは権限の問題として伝える", () => {
    // フローは呼び出した本人の資格で動くので、身元が空 = 本人が読めない。
    for (const actingAs of ["", "   ", null, undefined]) {
      expect(resolveDescribeOutcome({ ...ok, actingAs })).toEqual({
        kind: "error",
        message: "このファイルを読む権限がありません",
      });
    }
  });

  it("reason ごとに違う文言を返す（直す場所が違うため）", () => {
    const cases: Array<[string, string]> = [
      ["unreadable", "ファイルが見つかりませんでした。URL を確認してください"],
      ["too-large", "ファイルが大きすぎます（25 MB まで）"],
      ["content-unreadable", "ファイルの中身を読み取れませんでした"],
      ["extract-failed", "資料からテキストを取り出せませんでした"],
      ["generation-failed", "説明を生成できませんでした"],
    ];
    for (const [reason, message] of cases) {
      expect(resolveDescribeOutcome({ ...ok, reason })).toEqual({
        kind: "error",
        message,
      });
    }
  });

  it("reason が立っていたら、説明文が入っていても追記しない", () => {
    // 抽出に失敗すると説明文プロンプトは「読み取れませんでした」を返す。
    // **それを説明欄に足してはいけない。**
    expect(
      resolveDescribeOutcome({
        ...ok,
        reason: "extract-failed",
        description: "この資料の内容を読み取れませんでした。",
      }),
    ).toEqual({
      kind: "error",
      message: "資料からテキストを取り出せませんでした",
    });
  });

  it("説明が空なら追記しない", () => {
    for (const description of ["", "   ", null, undefined]) {
      expect(resolveDescribeOutcome({ ...ok, description })).toEqual({
        kind: "error",
        message: "説明を生成できませんでした",
      });
    }
  });

  it("応答そのものが無いときも落ちない", () => {
    expect(resolveDescribeOutcome(undefined).kind).toBe("error");
    expect(resolveDescribeOutcome(null).kind).toBe("error");
  });

  it("知らない reason は握り潰さず、説明があれば追記する", () => {
    // フロー側に値が増えたとき、画面が黙って止まるより追記して見せるほうがよい。
    expect(resolveDescribeOutcome({ ...ok, reason: "something-new" })).toEqual({
      kind: "append",
      description: ok.description,
    });
  });
});

describe("encodeSharingUrl", () => {
  // Learn の手順: base64 → 末尾の `=` を落とす → `/`→`_`、`+`→`-` → `u!` を前置。
  const decode = (token: string) => {
    const body = token.replace(/^u!/, "").replace(/_/g, "/").replace(/-/g, "+");
    const padded = body + "=".repeat((4 - (body.length % 4)) % 4);
    return new TextDecoder().decode(
      Uint8Array.from(atob(padded), (c) => c.charCodeAt(0)),
    );
  };

  it("元の URL に復元できる（往復する）", () => {
    const url =
      "https://contoso-my.sharepoint.com/:p:/g/personal/taro_contoso_com/IQCLYXUHAUcfTYaxzoGHQC0d?e=bibmNR";
    const token = encodeSharingUrl(url);
    expect(token.startsWith("u!")).toBe(true);
    expect(decode(token)).toBe(url);
  });

  it("base64url にする（`=` を残さず、`/` と `+` を使わない）", () => {
    // ここを素の base64 のままにすると、URL の一部として渡したときに壊れる。
    const token = encodeSharingUrl(
      "https://contoso.sharepoint.com/:w:/s/Sales/E??>>??abc+/def?e=1",
    );
    expect(token).not.toMatch(/[=/+]/);
  });

  it("日本語を含む URL でも壊れない", () => {
    // btoa は Latin-1 しか受けないので、UTF-8 のバイト列にしてから符号化している。
    const url = "https://contoso.sharepoint.com/:p:/g/personal/u/共有資料?e=1";
    expect(decode(encodeSharingUrl(url))).toBe(url);
  });

  it("Learn の例と同じ結果になる", () => {
    // 記事に載っている C# の例と突き合わせる。**手順を自分で言い換えていないか**の確認。
    const url =
      "https://onedrive.live.com/redir?resid=1231244193912!12&authKey=1201919!12921!1";
    expect(encodeSharingUrl(url)).toBe(
      "u!aHR0cHM6Ly9vbmVkcml2ZS5saXZlLmNvbS9yZWRpcj9yZXNpZD0xMjMxMjQ0MTkzOTEyITEyJmF1dGhLZXk9MTIwMTkxOSExMjkyMSEx",
    );
  });
});

describe("resolveDescribeRequest", () => {
  it("パス形式はサイトとパスに割って渡す", () => {
    expect(
      resolveDescribeRequest(
        "https://contoso-my.sharepoint.com/personal/taro_contoso_com/Documents/plan.pptx",
      ),
    ).toEqual({
      kind: "run",
      text: "https://contoso-my.sharepoint.com/personal/taro_contoso_com",
      text_1: "/Documents/plan.pptx",
    });
  });

  it("共有リンクは u! トークンにして渡す（パスを渡さない）", () => {
    // **ここを取り違えると、共有リンクにパスを送る。** 症状は
    // 「読み取れませんでした」だけで、権限エラーと見分けが付かない。
    const request = resolveDescribeRequest(
      "https://contoso-my.sharepoint.com/:p:/g/personal/taro_contoso_com/IQCabc?e=x",
    );
    expect(request.kind).toBe("run");
    if (request.kind !== "run") return;
    expect(request.text).toBe(
      "https://contoso-my.sharepoint.com/personal/taro_contoso_com",
    );
    expect(request.text_1.startsWith("u!")).toBe(true);
    expect(request.text_1).not.toContain("/");
  });

  it("SharePoint 以外は呼ばずに断る", () => {
    for (const url of ["https://example.com/a.docx", "not a url", "", null]) {
      expect(resolveDescribeRequest(url)).toEqual({
        kind: "error",
        message: "SharePoint / OneDrive の URL を入れてください",
      });
    }
  });

  it("ファイルを特定できない URL は呼ばずに断る", () => {
    // 呼んでも必ず失敗するので、往復させずにその場で伝える。
    expect(
      resolveDescribeRequest(
        "https://contoso.sharepoint.com/sites/S/_layouts/15/Doc.aspx?sourcedoc=%7BGUID%7D",
      ),
    ).toEqual({
      kind: "error",
      message: "この URL からはファイルを特定できませんでした",
    });
  });
});
