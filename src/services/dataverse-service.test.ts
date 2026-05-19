import { beforeEach, describe, expect, it, vi } from "vitest";

const createDecisionRecord = vi.fn();
const updateApplicationRecord = vi.fn();

vi.mock("@microsoft/power-apps/app", () => ({
  getContext: vi.fn(),
}));

vi.mock("@microsoft/power-apps/data", () => ({}));

vi.mock("@/generated/services/Ds_decisionsService", () => ({
  Ds_decisionsService: {
    create: createDecisionRecord,
  },
}));

vi.mock("@/generated/services/Ds_applicationsService", () => ({
  Ds_applicationsService: {
    update: updateApplicationRecord,
  },
}));

vi.mock("@/generated/services/Ds_applicationresourcesService", () => ({
  Ds_applicationresourcesService: {},
}));

vi.mock("@/generated/services/Ds_categoriesService", () => ({
  Ds_categoriesService: {},
}));

vi.mock("@/generated/services/Ds_decisionoptionsService", () => ({
  Ds_decisionoptionsService: {},
}));

vi.mock("@/generated/services/Ds_mentionsService", () => ({
  Ds_mentionsService: {},
}));

vi.mock("@/generated/services/Ds_messagesService", () => ({
  Ds_messagesService: {},
}));

vi.mock("@/generated/services/Ds_participantsService", () => ({
  Ds_participantsService: {},
}));

vi.mock("@/generated/services/SystemusersService", () => ({
  SystemusersService: {},
}));

vi.mock(
  "@/generated/services/Participant_PreDelete_RevokeAccessService",
  () => ({
    Participant_PreDelete_RevokeAccessService: {},
  }),
);

vi.mock("@/services/application-generate-ai-decision-service", () => ({
  Application_GenerateAiDecisionService: {},
}));

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
