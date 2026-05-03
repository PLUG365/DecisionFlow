import { getContext } from "@microsoft/power-apps/app";
import type { IOperationResult } from "@microsoft/power-apps/data";

import { Ds_applicationresourcesService } from "@/generated/services/Ds_applicationresourcesService";
import { Ds_applicationsService } from "@/generated/services/Ds_applicationsService";
import { Ds_categoriesService } from "@/generated/services/Ds_categoriesService";
import { Ds_decisionoptionsService } from "@/generated/services/Ds_decisionoptionsService";
import { Ds_decisionsService } from "@/generated/services/Ds_decisionsService";
import { Ds_mentionsService } from "@/generated/services/Ds_mentionsService";
import { Ds_messagesService } from "@/generated/services/Ds_messagesService";
import { Ds_participantsService } from "@/generated/services/Ds_participantsService";
import { Participant_PreDelete_RevokeAccessService } from "@/generated/services/Participant_PreDelete_RevokeAccessService";
import { Application_GenerateAiDecisionService } from "@/services/application-generate-ai-decision-service";
import { SystemusersService } from "@/generated/services/SystemusersService";
import {
  ApplicationStage,
  ParticipantRole,
  type Application,
  type ApplicationStageValue,
  type ApplicationResource,
  type Category,
  type Decision,
  type DecisionOption,
  type Message,
  type Mention,
  type Participant,
  type SystemUser,
} from "@/types/decisionflow";

type CreateApplication = Partial<Application> & Pick<Application, "ds_name">;
type CreateCategory = Partial<Category> & Pick<Category, "ds_name">;
type CreateDecisionOption = Partial<DecisionOption> &
  Pick<DecisionOption, "ds_name">;
type CreateMessage = Partial<Message> & Pick<Message, "ds_name">;
type CreateMention = Partial<Mention> & Pick<Mention, "ds_name">;
type CreateResource = Partial<ApplicationResource> &
  Pick<ApplicationResource, "ds_name">;
type CreateDecision = Partial<Decision> &
  Pick<Decision, "ds_name"> & {
    nextApplicationStage?: ApplicationStageValue;
  };
type CreateParticipant = Partial<Participant> & Pick<Participant, "ds_name">;
type DeleteParticipantInput = {
  participantId: string;
  applicationId: string;
  userId: string;
};

function requireData<T>(result: IOperationResult<T>, operation: string): T {
  if (!result.success) {
    throw result.error ?? new Error(`${operation} failed`);
  }
  return result.data;
}

function bind(entitySetName: string, id?: string) {
  return id ? `/${entitySetName}(${id})` : undefined;
}

function stripUndefined<T extends Record<string, unknown>>(record: T) {
  return Object.fromEntries(
    Object.entries(record).filter(([, value]) => value !== undefined),
  ) as Partial<T>;
}

export const DataverseService = {
  async getData() {
    const [
      applications,
      categories,
      decisionOptions,
      messages,
      mentions,
      participants,
      decisions,
      resources,
      users,
    ] = await Promise.all([
      this.getApplications(),
      this.getCategories(),
      this.getDecisionOptions(),
      this.getMessages(),
      this.getMentions(),
      this.getParticipants(),
      this.getDecisions(),
      this.getResources(),
      this.getSystemUsers(),
    ]);

    return {
      applications,
      categories,
      decisionOptions,
      messages,
      mentions,
      participants,
      decisions,
      resources,
      users,
    };
  },

  async getApplications(): Promise<Application[]> {
    return requireData(
      await Ds_applicationsService.getAll({ orderBy: ["createdon desc"] }),
      "getApplications",
    ) as Application[];
  },

  async getCategories(): Promise<Category[]> {
    return requireData(
      await Ds_categoriesService.getAll({
        orderBy: ["ds_sortorder asc", "ds_name asc"],
      }),
      "getCategories",
    ) as Category[];
  },

  async getDecisionOptions(): Promise<DecisionOption[]> {
    return requireData(
      await Ds_decisionoptionsService.getAll({
        orderBy: ["ds_sortorder asc", "ds_name asc"],
      }),
      "getDecisionOptions",
    ) as DecisionOption[];
  },

  async getMessages(applicationId?: string): Promise<Message[]> {
    const filter = applicationId
      ? `_ds_applicationid_value eq ${applicationId}`
      : undefined;
    return requireData(
      await Ds_messagesService.getAll({ filter, orderBy: ["createdon desc"] }),
      "getMessages",
    ) as Message[];
  },

  async getMentions(): Promise<Mention[]> {
    return requireData(
      await Ds_mentionsService.getAll({ orderBy: ["createdon desc"] }),
      "getMentions",
    ) as Mention[];
  },

  async getParticipants(applicationId?: string): Promise<Participant[]> {
    const filter = applicationId
      ? `_ds_applicationid_value eq ${applicationId}`
      : undefined;
    return requireData(
      await Ds_participantsService.getAll({
        filter,
        orderBy: ["createdon desc"],
      }),
      "getParticipants",
    ) as Participant[];
  },

  async getDecisions(applicationId?: string): Promise<Decision[]> {
    const filter = applicationId
      ? `_ds_applicationid_value eq ${applicationId}`
      : undefined;
    return requireData(
      await Ds_decisionsService.getAll({
        filter,
        orderBy: ["ds_decidedat desc", "createdon desc"],
      }),
      "getDecisions",
    ) as Decision[];
  },

  async getResources(applicationId?: string): Promise<ApplicationResource[]> {
    const filter = applicationId
      ? `_ds_applicationid_value eq ${applicationId}`
      : undefined;
    return requireData(
      await Ds_applicationresourcesService.getAll({
        filter,
        orderBy: ["createdon desc"],
      }),
      "getResources",
    ) as ApplicationResource[];
  },

  async getSystemUsers(): Promise<SystemUser[]> {
    return requireData(
      await SystemusersService.getAll({
        select: [
          "systemuserid",
          "fullname",
          "internalemailaddress",
          "azureactivedirectoryobjectid",
        ],
        filter: "isdisabled eq false",
        orderBy: ["fullname asc"],
      }),
      "getSystemUsers",
    ) as SystemUser[];
  },

  async getCurrentSystemUserId(): Promise<string | null> {
    try {
      const context = await getContext();
      const entraObjectId = context.user?.objectId;
      if (!entraObjectId) return null;
      const users = requireData(
        await SystemusersService.getAll({
          select: ["systemuserid"],
          filter: `azureactivedirectoryobjectid eq '${entraObjectId}'`,
          top: 1,
        }),
        "getCurrentSystemUserId",
      ) as SystemUser[];
      return users[0]?.systemuserid?.toLowerCase() ?? null;
    } catch (error) {
      console.warn("[DecisionFlow] current user resolution failed", error);
      return null;
    }
  },

  async createApplication(application: CreateApplication) {
    const created = requireData(
      await Ds_applicationsService.create(
        stripUndefined({
          ds_name: application.ds_name,
          ds_body: application.ds_body,
          ds_stage: application.ds_stage ?? ApplicationStage.Draft,
          ds_duedate: application.ds_duedate,
          ds_submittedat: application.ds_submittedat,
          "ds_categoryid@odata.bind": bind(
            "ds_categories",
            application._ds_categoryid_value,
          ),
          "ds_deciderid@odata.bind": bind(
            "systemusers",
            application._ds_deciderid_value,
          ),
        }) as Parameters<typeof Ds_applicationsService.create>[0],
      ),
      "createApplication",
    ) as Application;

    const currentUserId = await this.getCurrentSystemUserId();
    const participantsToCreate: CreateParticipant[] = [];
    if (currentUserId) {
      participantsToCreate.push({
        ds_name: `${created.ds_name} - 申請者`,
        ds_role: ParticipantRole.Applicant,
        _ds_applicationid_value: created.ds_applicationid,
        _ds_userid_value: currentUserId,
        _ds_addedbyid_value: currentUserId,
      });
    }
    if (
      application._ds_deciderid_value &&
      application._ds_deciderid_value.toLowerCase() !== currentUserId
    ) {
      participantsToCreate.push({
        ds_name: `${created.ds_name} - 判断者`,
        ds_role: ParticipantRole.Decider,
        _ds_applicationid_value: created.ds_applicationid,
        _ds_userid_value: application._ds_deciderid_value,
        _ds_addedbyid_value: currentUserId ?? undefined,
      });
    }

    await Promise.allSettled(
      participantsToCreate.map((participant) =>
        this.createParticipant(participant),
      ),
    );
    return created;
  },

  async createCategory(category: CreateCategory) {
    return requireData(
      await Ds_categoriesService.create(
        stripUndefined({
          ds_name: category.ds_name,
          ds_description: category.ds_description,
          ds_template: category.ds_template,
          ds_sortorder: category.ds_sortorder,
        }) as Parameters<typeof Ds_categoriesService.create>[0],
      ),
      "createCategory",
    ) as Category;
  },

  async updateCategory(payload: Partial<Category> & { id: string }) {
    const { id, ...changes } = payload;
    return requireData(
      await Ds_categoriesService.update(
        id,
        stripUndefined({
          ds_name: changes.ds_name,
          ds_description: changes.ds_description,
          ds_template: changes.ds_template,
          ds_sortorder: changes.ds_sortorder,
        }) as Parameters<typeof Ds_categoriesService.update>[1],
      ),
      "updateCategory",
    ) as Category;
  },

  async createDecisionOption(option: CreateDecisionOption) {
    return requireData(
      await Ds_decisionoptionsService.create(
        stripUndefined({
          ds_name: option.ds_name,
          ds_description: option.ds_description,
          ds_sortorder: option.ds_sortorder,
        }) as Parameters<typeof Ds_decisionoptionsService.create>[0],
      ),
      "createDecisionOption",
    ) as DecisionOption;
  },

  async updateDecisionOption(
    payload: Partial<DecisionOption> & { id: string },
  ) {
    const { id, ...changes } = payload;
    return requireData(
      await Ds_decisionoptionsService.update(
        id,
        stripUndefined({
          ds_name: changes.ds_name,
          ds_description: changes.ds_description,
          ds_sortorder: changes.ds_sortorder,
        }) as Parameters<typeof Ds_decisionoptionsService.update>[1],
      ),
      "updateDecisionOption",
    ) as DecisionOption;
  },

  async updateApplication(payload: Partial<Application> & { id: string }) {
    const { id, ...changes } = payload;
    return requireData(
      await Ds_applicationsService.update(
        id,
        stripUndefined({
          ds_name: changes.ds_name,
          ds_body: changes.ds_body,
          ds_stage: changes.ds_stage,
          ds_duedate: changes.ds_duedate,
          ds_submittedat: changes.ds_submittedat,
          ds_aiapplicationsummary: changes.ds_aiapplicationsummary,
          ds_aiconversationsummary: changes.ds_aiconversationsummary,
          ds_aidecisionoptiontext: changes.ds_aidecisionoptiontext,
          ds_aidecisioncomment: changes.ds_aidecisioncomment,
          ds_aidecisionbasis: changes.ds_aidecisionbasis,
          ds_aidecisionupdatedat: changes.ds_aidecisionupdatedat,
          "ds_categoryid@odata.bind": bind(
            "ds_categories",
            changes._ds_categoryid_value,
          ),
          "ds_deciderid@odata.bind": bind(
            "systemusers",
            changes._ds_deciderid_value,
          ),
        }) as Parameters<typeof Ds_applicationsService.update>[1],
      ),
      "updateApplication",
    ) as Application;
  },

  async deleteApplication(applicationId: string) {
    await Ds_applicationsService.delete(applicationId);
  },

  async generateAiDecision(applicationId: string) {
    const result = requireData(
      await Application_GenerateAiDecisionService.Run({ text: applicationId }),
      "generateAiDecision",
    );
    if (result.ok !== "true") {
      throw new Error(result.message || "generateAiDecision failed");
    }
    return result;
  },

  async createMessage(message: CreateMessage) {
    return requireData(
      await Ds_messagesService.create(
        stripUndefined({
          ds_name: message.ds_name,
          ds_body: message.ds_body,
          ds_kind: message.ds_kind,
          "ds_applicationid@odata.bind": bind(
            "ds_applications",
            message._ds_applicationid_value,
          ),
          "ds_parentmessageid@odata.bind": bind(
            "ds_messages",
            message._ds_parentmessageid_value,
          ),
        }) as Parameters<typeof Ds_messagesService.create>[0],
      ),
      "createMessage",
    ) as Message;
  },

  async markMentionRead(mentionId: string) {
    return requireData(
      await Ds_mentionsService.update(mentionId, { ds_isread: true }),
      "markMentionRead",
    ) as Mention;
  },

  async createMention(mention: CreateMention) {
    return requireData(
      await Ds_mentionsService.create(
        stripUndefined({
          ds_name: mention.ds_name,
          ds_isread: mention.ds_isread ?? false,
          "ds_messageid@odata.bind": bind(
            "ds_messages",
            mention._ds_messageid_value,
          ),
          "ds_targetuserid@odata.bind": bind(
            "systemusers",
            mention._ds_targetuserid_value,
          ),
        }) as Parameters<typeof Ds_mentionsService.create>[0],
      ),
      "createMention",
    ) as Mention;
  },

  async createResource(resource: CreateResource) {
    return requireData(
      await Ds_applicationresourcesService.create(
        stripUndefined({
          ds_name: resource.ds_name,
          ds_description: resource.ds_description,
          ds_url: resource.ds_url,
          "ds_applicationid@odata.bind": bind(
            "ds_applications",
            resource._ds_applicationid_value,
          ),
        }) as Parameters<typeof Ds_applicationresourcesService.create>[0],
      ),
      "createResource",
    ) as ApplicationResource;
  },

  async deleteResource(resourceId: string) {
    await Ds_applicationresourcesService.delete(resourceId);
  },

  async createDecision(decision: CreateDecision) {
    const created = requireData(
      await Ds_decisionsService.create(
        stripUndefined({
          ds_name: decision.ds_name,
          ds_rationale: decision.ds_rationale,
          ds_decidedat: decision.ds_decidedat ?? new Date().toISOString(),
          "ds_applicationid@odata.bind": bind(
            "ds_applications",
            decision._ds_applicationid_value,
          ),
          "ds_deciderid@odata.bind": bind(
            "systemusers",
            decision._ds_deciderid_value,
          ),
          "ds_decisionoptionid@odata.bind": bind(
            "ds_decisionoptions",
            decision._ds_decisionoptionid_value,
          ),
        }) as Parameters<typeof Ds_decisionsService.create>[0],
      ),
      "createDecision",
    ) as Decision;
    if (decision._ds_applicationid_value) {
      const nextStage =
        decision.nextApplicationStage ?? ApplicationStage.Decided;
      await this.updateApplication({
        id: decision._ds_applicationid_value,
        ds_stage: nextStage,
        ds_submittedat: nextStage === ApplicationStage.Draft ? null : undefined,
      });
    }
    return created;
  },

  async createParticipant(participant: CreateParticipant) {
    return requireData(
      await Ds_participantsService.create(
        stripUndefined({
          ds_name: participant.ds_name,
          ds_role: participant.ds_role,
          ds_addedat: participant.ds_addedat ?? new Date().toISOString(),
          "ds_applicationid@odata.bind": bind(
            "ds_applications",
            participant._ds_applicationid_value,
          ),
          "ds_userid@odata.bind": bind(
            "systemusers",
            participant._ds_userid_value,
          ),
          "ds_addedbyid@odata.bind": bind(
            "systemusers",
            participant._ds_addedbyid_value,
          ),
        }) as Parameters<typeof Ds_participantsService.create>[0],
      ),
      "createParticipant",
    ) as Participant;
  },

  async deleteParticipant({
    participantId,
    applicationId,
    userId,
  }: DeleteParticipantInput) {
    const revokeResult = requireData(
      await Participant_PreDelete_RevokeAccessService.Run({
        text: participantId,
        text_1: applicationId,
        text_2: userId,
      }),
      "revokeParticipantAccess",
    );
    if (revokeResult.ok !== "true") {
      throw new Error(revokeResult.message || "revokeParticipantAccess failed");
    }
    await Ds_participantsService.delete(participantId);
  },
};
