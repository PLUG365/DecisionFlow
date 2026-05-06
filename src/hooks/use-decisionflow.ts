import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { filterRowsForCurrentUser } from "@/lib/decisionflow-utils";
import { DataverseService } from "@/services/dataverse-service";
import {
  type Application,
  type ApplicationStageValue,
  type ApplicationResource,
  type Category,
  type Decision,
  type DecisionOption,
  type Mention,
  type Message,
  type Participant,
} from "@/types/decisionflow";

type CreateResourceInput = {
  resource: Omit<ApplicationResource, "ds_applicationresourceid">;
};

type DeleteParticipantInput = {
  participantId: string;
  applicationId: string;
  userId: string;
};

type CreateDecisionInput = Omit<Decision, "ds_decisionid"> & {
  nextApplicationStage?: ApplicationStageValue;
};

const queryKeys = {
  all: ["decisionflow"] as const,
  data: ["decisionflow", "data"] as const,
  currentUser: ["decisionflow", "currentUser"] as const,
};

export function useDecisionFlowData() {
  return useQuery({
    queryKey: queryKeys.data,
    queryFn: () => DataverseService.getData(),
  });
}

export function useCurrentSystemUser() {
  const dataQuery = useDecisionFlowData();
  const userIdQuery = useQuery({
    queryKey: queryKeys.currentUser,
    queryFn: () => DataverseService.getCurrentSystemUserId(),
    staleTime: Infinity,
  });

  const user = dataQuery.data?.users.find(
    (u) => u.systemuserid === userIdQuery.data,
  );

  return {
    ...userIdQuery,
    data: user ?? null,
    systemUserId: userIdQuery.data ?? null,
  };
}

export function useApplications() {
  const query = useDecisionFlowData();
  return { ...query, data: query.data?.applications ?? [] };
}

export function useApplication(id?: string) {
  const query = useDecisionFlowData();
  return {
    ...query,
    data: query.data?.applications.find((item) => item.ds_applicationid === id),
  };
}

export function useCategories() {
  const query = useDecisionFlowData();
  return { ...query, data: query.data?.categories ?? [] };
}

export function useDecisionOptions() {
  const query = useDecisionFlowData();
  return { ...query, data: query.data?.decisionOptions ?? [] };
}

export function useSystemUsers() {
  const query = useDecisionFlowData();
  return { ...query, data: query.data?.users ?? [] };
}

export function useDeciders() {
  const query = useDecisionFlowData();
  return { ...query, data: query.data?.deciders ?? [] };
}

export function useMessages(applicationId?: string) {
  const query = useDecisionFlowData();
  const messages = query.data?.messages ?? [];
  return {
    ...query,
    data: applicationId
      ? messages.filter(
          (item) => item._ds_applicationid_value === applicationId,
        )
      : messages,
  };
}

export function useParticipants(applicationId?: string) {
  const query = useDecisionFlowData();
  const participants = query.data?.participants ?? [];
  return {
    ...query,
    data: applicationId
      ? participants.filter(
          (item) => item._ds_applicationid_value === applicationId,
        )
      : participants,
  };
}

export function useResources(applicationId?: string) {
  const query = useDecisionFlowData();
  const resources = query.data?.resources ?? [];
  return {
    ...query,
    data: applicationId
      ? resources.filter(
          (item) => item._ds_applicationid_value === applicationId,
        )
      : resources,
  };
}

export function useDecisions(applicationId?: string) {
  const query = useDecisionFlowData();
  const decisions = query.data?.decisions ?? [];
  return {
    ...query,
    data: applicationId
      ? decisions.filter(
          (item) => item._ds_applicationid_value === applicationId,
        )
      : decisions,
  };
}

export function useMentionsForCurrentUser() {
  const query = useDecisionFlowData();
  const { systemUserId } = useCurrentSystemUser();
  const mentions = query.data?.mentions ?? [];
  return {
    ...query,
    data: filterRowsForCurrentUser(
      mentions,
      systemUserId,
      "_ds_targetuserid_value",
    ),
  };
}

export function useUpdateApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Application> & { id: string }) =>
      DataverseService.updateApplication(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useDeleteApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) =>
      DataverseService.deleteApplication(applicationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useGenerateAiDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (applicationId: string) =>
      DataverseService.generateAiDecision(applicationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useCreateApplication() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (application: Omit<Application, "ds_applicationid">) =>
      DataverseService.createApplication(application),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useCreateMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: Omit<Message, "ds_messageid">) =>
      DataverseService.createMessage(message),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useMarkMentionRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mentionId: string) =>
      DataverseService.markMentionRead(mentionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useCreateMention() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mention: Omit<Mention, "ds_mentionid">) =>
      DataverseService.createMention(mention),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useCreateResource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateResourceInput) =>
      DataverseService.createResource(payload.resource),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useDeleteResource() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (resourceId: string) =>
      DataverseService.deleteResource(resourceId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (category: Omit<Category, "ds_categoryid">) =>
      DataverseService.createCategory(category),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useUpdateCategory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Category> & { id: string }) =>
      DataverseService.updateCategory(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useCreateDecisionOption() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (option: Omit<DecisionOption, "ds_decisionoptionid">) =>
      DataverseService.createDecisionOption(option),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useUpdateDecisionOption() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<DecisionOption> & { id: string }) =>
      DataverseService.updateDecisionOption(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useCreateDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (decision: CreateDecisionInput) =>
      DataverseService.createDecision(decision),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useCreateParticipant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (participant: Omit<Participant, "ds_participantid">) =>
      DataverseService.createParticipant(participant),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}

export function useDeleteParticipant() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: DeleteParticipantInput) =>
      DataverseService.deleteParticipant(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.all }),
  });
}
