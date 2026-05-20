import { describe, expect, it } from "vitest";

import {
  applicantSelectableStageValues,
  canDecideApplication,
  canEditApplication,
  canReturnApplicationToDraft,
  getDecisionNextApplicationStage,
  getDeciderQueueApplications,
  getParticipantDeleteWaitState,
  isIgnorableParticipantRevokeFailure,
  filterRowsForCurrentUser,
  isApplicantSelectableStage,
  validateApplicationInput,
  validateMentionInput,
  validateParticipantInput,
  validateResourceInput,
} from "./decisionflow-utils";

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
