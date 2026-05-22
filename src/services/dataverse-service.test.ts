import { beforeEach, describe, expect, it, vi } from "vitest";

const createDecisionRecord = vi.fn();
const createApplicationRecord = vi.fn();
const updateApplicationRecord = vi.fn();
const deleteApplicationRecord = vi.fn();
const getApplicationRecord = vi.fn();
const updateCategory = vi.fn();
const getApplications = vi.fn();
const getCategories = vi.fn();
const createCategory = vi.fn();
const deleteCategory = vi.fn();
const getDecisionOptions = vi.fn();
const createDecisionOption = vi.fn();
const getMessages = vi.fn();
const getMentions = vi.fn();
const getParticipants = vi.fn();
const getDecisions = vi.fn();
const getResources = vi.fn();
const getSystemUsers = vi.fn();
const runAiDecision = vi.fn();

vi.mock("@microsoft/power-apps/app", () => ({
  getContext: vi.fn(),
}));

vi.mock("@microsoft/power-apps/data", () => ({}));

vi.mock("@/generated/services/Ds_decisionsService", () => ({
  Ds_decisionsService: {
    create: createDecisionRecord,
    getAll: getDecisions,
  },
}));

vi.mock("@/generated/services/Ds_applicationsService", () => ({
  Ds_applicationsService: {
    create: createApplicationRecord,
    delete: deleteApplicationRecord,
    get: getApplicationRecord,
    getAll: getApplications,
    update: updateApplicationRecord,
  },
}));

vi.mock("@/generated/services/Ds_applicationresourcesService", () => ({
  Ds_applicationresourcesService: {
    getAll: getResources,
  },
}));

vi.mock("@/generated/services/Ds_categoriesService", () => ({
  Ds_categoriesService: {
    getAll: getCategories,
    create: createCategory,
    update: updateCategory,
    delete: deleteCategory,
  },
}));

vi.mock("@/generated/services/Ds_decisionoptionsService", () => ({
  Ds_decisionoptionsService: {
    getAll: getDecisionOptions,
    create: createDecisionOption,
  },
}));

vi.mock("@/generated/services/Ds_mentionsService", () => ({
  Ds_mentionsService: {
    getAll: getMentions,
  },
}));

vi.mock("@/generated/services/Ds_messagesService", () => ({
  Ds_messagesService: {
    getAll: getMessages,
  },
}));

vi.mock("@/generated/services/Ds_participantsService", () => ({
  Ds_participantsService: {
    getAll: getParticipants,
  },
}));

vi.mock("@/generated/services/SystemusersService", () => ({
  SystemusersService: {
    getAll: getSystemUsers,
  },
}));

vi.mock(
  "@/generated/services/Participant_PreDelete_RevokeAccessService",
  () => ({
    Participant_PreDelete_RevokeAccessService: {},
  }),
);

vi.mock("@/services/application-generate-ai-decision-service", () => ({
  Application_GenerateAiDecisionService: {
    Run: runAiDecision,
  },
}));

describe("DataverseService category regulation payloads", () => {
  beforeEach(() => {
    vi.resetModules();
    createCategory.mockReset();
    updateCategory.mockReset();
    createCategory.mockResolvedValue({
      success: true,
      data: { ds_categoryid: "category-1" },
    });
    updateCategory.mockResolvedValue({
      success: true,
      data: { ds_categoryid: "category-1" },
    });
  });

  it("sends regulation text when creating a category", async () => {
    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.createCategory({
      ds_name: "顧客案件",
      ds_regulationtext: "契約条件を確認する。",
    });

    expect(createCategory).toHaveBeenCalledWith(
      expect.objectContaining({ ds_regulationtext: "契約条件を確認する。" }),
    );
  });

  it("sends regulation text when updating a category", async () => {
    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.updateCategory({
      id: "category-1",
      ds_regulationtext: "最新の確認観点。",
    });

    expect(updateCategory).toHaveBeenCalledWith(
      "category-1",
      expect.objectContaining({ ds_regulationtext: "最新の確認観点。" }),
    );
  });
});

describe("DataverseService submit confirmation operations", () => {
  beforeEach(() => {
    vi.resetModules();
    createApplicationRecord.mockReset();
    updateApplicationRecord.mockReset();
    getApplicationRecord.mockReset();
    runAiDecision.mockReset();
    getSystemUsers.mockResolvedValue({ success: true, data: [] });
    createApplicationRecord.mockResolvedValue({
      success: true,
      data: { ds_applicationid: "application-1", ds_name: "申請" },
    });
    updateApplicationRecord.mockResolvedValue({
      success: true,
      data: { ds_applicationid: "application-1", ds_stage: 100000000 },
    });
    runAiDecision.mockResolvedValue({
      success: true,
      data: {
        ok: "true",
        applicationid: "application-1",
        message: "AI decision generated.",
      },
    });
    getApplicationRecord.mockResolvedValue({
      success: true,
      data: {
        ds_applicationid: "application-1",
        ds_aidecisioncomment: "AI結果",
      },
    });
  });

  it("saves a submitted attempt as Draft before running AI", async () => {
    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.saveDraftForAiCheck({
      id: "application-1",
      ds_name: "申請",
      ds_body: "本文",
      ds_stage: 100000001,
      ds_submittedat: "2026-05-22T00:00:00Z",
    });

    expect(updateApplicationRecord).toHaveBeenCalledWith(
      "application-1",
      expect.objectContaining({ ds_stage: 100000000, ds_submittedat: null }),
    );
  });

  it("runs AI against the saved draft application id", async () => {
    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.runAiPreCheck("application-1");

    expect(runAiDecision).toHaveBeenCalledWith({ text: "application-1" });
  });

  it("sets Submitted and submittedAt only when final submit is confirmed", async () => {
    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.confirmFinalSubmit("application-1");

    expect(updateApplicationRecord).toHaveBeenCalledWith(
      "application-1",
      expect.objectContaining({ ds_stage: 100000001 }),
    );
    expect(updateApplicationRecord.mock.calls[0][1].ds_submittedat).toEqual(
      expect.any(String),
    );
  });

  it("keeps Draft and clears submittedAt when applicant keeps draft", async () => {
    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.keepDraftAfterAiCheck("application-1");

    expect(updateApplicationRecord).toHaveBeenCalledWith(
      "application-1",
      expect.objectContaining({ ds_stage: 100000000, ds_submittedat: null }),
    );
  });
});

describe("DataverseService.createDecision", () => {
  beforeEach(() => {
    createDecisionRecord.mockReset();
    updateApplicationRecord.mockReset();
    createDecisionRecord.mockResolvedValue({
      success: true,
      data: { ds_decisionid: "decision-1", ds_name: "判断" },
    });
    updateApplicationRecord.mockResolvedValue({
      success: true,
      data: { ds_applicationid: "application-1" },
    });
  });

  it("creates ds_decision and updates ds_application stage for immediate Code Apps feedback", async () => {
    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.createDecision({
      ds_name: "申請 - 判断",
      ds_rationale: "承認します",
      _ds_applicationid_value: "application-1",
      _ds_deciderid_value: "user-1",
      _ds_decisionoptionid_value: "option-1",
      nextApplicationStage: 100000004,
    });

    expect(createDecisionRecord).toHaveBeenCalledTimes(1);
    expect(updateApplicationRecord).toHaveBeenCalledWith(
      "application-1",
      expect.objectContaining({
        ds_stage: 100000004,
      }),
    );
  });

  it("clears submittedAt when Code Apps returns an application to draft", async () => {
    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.createDecision({
      ds_name: "申請 - 判断",
      ds_rationale: "差し戻します",
      _ds_applicationid_value: "application-1",
      _ds_deciderid_value: "user-1",
      _ds_decisionoptionid_value: "option-1",
      nextApplicationStage: 100000000,
    });

    expect(updateApplicationRecord).toHaveBeenCalledWith(
      "application-1",
      expect.objectContaining({
        ds_stage: 100000000,
        ds_submittedat: null,
      }),
    );
  });
});

describe("DataverseService.getData", () => {
  beforeEach(() => {
    vi.resetModules();
    for (const mock of [
      getApplications,
      getCategories,
      createCategory,
      updateCategory,
      getDecisionOptions,
      createDecisionOption,
      getMessages,
      getMentions,
      getParticipants,
      getDecisions,
      getResources,
      getSystemUsers,
    ]) {
      mock.mockReset();
    }

    getApplications.mockResolvedValue({ success: true, data: [] });
    getMessages.mockResolvedValue({ success: true, data: [] });
    getMentions.mockResolvedValue({ success: true, data: [] });
    getParticipants.mockResolvedValue({ success: true, data: [] });
    getDecisions.mockResolvedValue({ success: true, data: [] });
    getResources.mockResolvedValue({ success: true, data: [] });
    getSystemUsers.mockResolvedValue({ success: true, data: [] });
    createCategory.mockResolvedValue({ success: true, data: {} });
    updateCategory.mockResolvedValue({ success: true, data: {} });
    createDecisionOption.mockResolvedValue({ success: true, data: {} });
  });

  it("creates startup categories when empty and missing fixed decision options before returning data", async () => {
    getCategories
      .mockResolvedValueOnce({
        success: true,
        data: [],
      })
      .mockResolvedValueOnce({
        success: true,
        data: [
          { ds_categoryid: "category-1", ds_name: "顧客案件" },
          { ds_categoryid: "category-2", ds_name: "部内案件" },
          { ds_categoryid: "category-3", ds_name: "課内案件" },
          { ds_categoryid: "category-4", ds_name: "他部署案件" },
          { ds_categoryid: "category-5", ds_name: "事務処理" },
        ],
      });
    getDecisionOptions
      .mockResolvedValueOnce({
        success: true,
        data: [{ ds_decisionoptionid: "option-1", ds_name: "承認" }],
      })
      .mockResolvedValueOnce({
        success: true,
        data: [
          { ds_decisionoptionid: "option-1", ds_name: "承認" },
          { ds_decisionoptionid: "option-2", ds_name: "却下" },
          { ds_decisionoptionid: "option-3", ds_name: "差し戻し" },
        ],
      });

    const { DataverseService } = await import("./dataverse-service");

    const data = await DataverseService.getData();

    expect(createCategory).toHaveBeenCalledTimes(5);
    expect(createCategory).toHaveBeenCalledWith(
      expect.objectContaining({
        ds_name: "顧客案件",
        ds_regulationtext: expect.stringContaining("顧客影響"),
      }),
    );
    expect(createDecisionOption).toHaveBeenCalledTimes(2);
    expect(createDecisionOption).toHaveBeenCalledWith(
      expect.objectContaining({ ds_name: "却下" }),
    );
    expect(data.categories.map((category) => category.ds_name)).toEqual([
      "顧客案件",
      "部内案件",
      "課内案件",
      "他部署案件",
      "事務処理",
    ]);
    expect(data.decisionOptions.map((option) => option.ds_name)).toEqual([
      "承認",
      "却下",
      "差し戻し",
    ]);
  });

  it("backfills regulation text for existing default categories without overwriting custom text", async () => {
    getCategories
      .mockResolvedValueOnce({
        success: true,
        data: [
          {
            ds_categoryid: "category-1",
            ds_name: "顧客案件",
            ds_regulationtext: "",
          },
          {
            ds_categoryid: "category-2",
            ds_name: "部内案件",
            ds_regulationtext: "既存の運用ルール",
          },
          {
            ds_categoryid: "category-x",
            ds_name: "独自カテゴリ",
            ds_regulationtext: "",
          },
        ],
      })
      .mockResolvedValueOnce({
        success: true,
        data: [
          {
            ds_categoryid: "category-1",
            ds_name: "顧客案件",
            ds_regulationtext: "顧客影響を確認する。",
          },
          {
            ds_categoryid: "category-2",
            ds_name: "部内案件",
            ds_regulationtext: "既存の運用ルール",
          },
          {
            ds_categoryid: "category-x",
            ds_name: "独自カテゴリ",
            ds_regulationtext: "",
          },
        ],
      });
    getDecisionOptions.mockResolvedValue({
      success: true,
      data: [
        { ds_decisionoptionid: "option-1", ds_name: "承認" },
        { ds_decisionoptionid: "option-2", ds_name: "却下" },
        { ds_decisionoptionid: "option-3", ds_name: "差し戻し" },
      ],
    });

    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.getData();

    expect(createCategory).not.toHaveBeenCalled();
    expect(updateCategory).toHaveBeenCalledTimes(1);
    expect(updateCategory).toHaveBeenCalledWith(
      "category-1",
      expect.objectContaining({
        ds_regulationtext: expect.stringContaining("顧客影響"),
      }),
    );
  });

  it("does not recreate default categories after administrators customize them", async () => {
    getCategories.mockResolvedValue({
      success: true,
      data: [{ ds_categoryid: "category-1", ds_name: "独自カテゴリ" }],
    });
    getDecisionOptions.mockResolvedValue({
      success: true,
      data: [
        { ds_decisionoptionid: "option-1", ds_name: "承認" },
        { ds_decisionoptionid: "option-2", ds_name: "却下" },
        { ds_decisionoptionid: "option-3", ds_name: "差し戻し" },
      ],
    });

    const { DataverseService } = await import("./dataverse-service");

    await DataverseService.getData();

    expect(createCategory).not.toHaveBeenCalled();
  });
});
