import type { LucideIcon } from "lucide-react";
import { CheckCircle2, CircleDashed, FileQuestion } from "lucide-react";

export const ApplicationStage = {
  Draft: 100000000,
  Submitted: 100000001,
  Decided: 100000004,
} as const;

export const MessageKind = {
  Comment: 100000000,
  Question: 100000001,
  Answer: 100000002,
  System: 100000003,
} as const;

export const ParticipantRole = {
  Applicant: 100000000,
  Decider: 100000001,
  Contributor: 100000003,
} as const;

export type ApplicationStageValue =
  (typeof ApplicationStage)[keyof typeof ApplicationStage];
export type MessageKindValue = (typeof MessageKind)[keyof typeof MessageKind];
export type ParticipantRoleValue =
  (typeof ParticipantRole)[keyof typeof ParticipantRole];

export type StageMeta = {
  label: string;
  shortLabel: string;
  className: string;
  icon: LucideIcon;
};

export const stageMeta: Record<ApplicationStageValue, StageMeta> = {
  [ApplicationStage.Draft]: {
    label: "下書き",
    shortLabel: "下書き",
    className: "border-slate-300 bg-slate-50 text-slate-700",
    icon: CircleDashed,
  },
  [ApplicationStage.Submitted]: {
    label: "提出済み",
    shortLabel: "提出",
    className: "border-sky-300 bg-sky-50 text-sky-700",
    icon: FileQuestion,
  },
  [ApplicationStage.Decided]: {
    label: "判断済み",
    shortLabel: "判断済み",
    className: "border-emerald-300 bg-emerald-50 text-emerald-700",
    icon: CheckCircle2,
  },
};

export const participantRoleLabels: Record<ParticipantRoleValue, string> = {
  [ParticipantRole.Applicant]: "申請者",
  [ParticipantRole.Decider]: "判断者",
  [ParticipantRole.Contributor]: "関係者",
};

export type SystemUser = {
  systemuserid: string;
  fullname?: string;
  internalemailaddress?: string;
  azureactivedirectoryobjectid?: string;
};

export type Category = {
  ds_categoryid: string;
  ds_name: string;
  ds_description?: string;
  ds_template?: string;
  ds_sortorder?: number;
};

export type DecisionOption = {
  ds_decisionoptionid: string;
  ds_name: string;
  ds_description?: string;
  ds_sortorder?: number;
};

export type Application = {
  ds_applicationid: string;
  ds_name: string;
  ds_body?: string;
  ds_stage?: ApplicationStageValue;
  ds_duedate?: string;
  ds_submittedat?: string | null;
  ds_aiapplicationsummary?: string;
  ds_aiconversationsummary?: string;
  ds_aidecisionoptiontext?: string;
  ds_aidecisioncomment?: string;
  ds_aidecisionbasis?: string;
  ds_aidecisionupdatedat?: string;
  modifiedon?: string;
  createdon?: string;
  _ds_categoryid_value?: string;
  _ds_deciderid_value?: string;
  _createdby_value?: string;
};

export type Message = {
  ds_messageid: string;
  ds_name: string;
  ds_body?: string;
  ds_kind?: MessageKindValue;
  createdon?: string;
  _ds_applicationid_value?: string;
  _ds_parentmessageid_value?: string;
  _createdby_value?: string;
};

export type Mention = {
  ds_mentionid: string;
  ds_name: string;
  ds_isread?: boolean;
  createdon?: string;
  _ds_messageid_value?: string;
  _ds_targetuserid_value?: string;
};

export type Participant = {
  ds_participantid: string;
  ds_name: string;
  ds_role?: ParticipantRoleValue;
  ds_addedat?: string;
  _ds_applicationid_value?: string;
  _ds_userid_value?: string;
  _ds_addedbyid_value?: string;
};

export type Decision = {
  ds_decisionid: string;
  ds_name: string;
  ds_rationale?: string;
  ds_decidedat?: string;
  _ds_applicationid_value?: string;
  _ds_deciderid_value?: string;
  _ds_decisionoptionid_value?: string;
};

export type ApplicationResource = {
  ds_applicationresourceid: string;
  ds_name: string;
  ds_url?: string;
  ds_description?: string;
  createdon?: string;
  _ds_applicationid_value?: string;
  _createdby_value?: string;
};

export type DecisionFlowData = {
  applications: Application[];
  categories: Category[];
  decisionOptions: DecisionOption[];
  messages: Message[];
  mentions: Mention[];
  participants: Participant[];
  decisions: Decision[];
  resources: ApplicationResource[];
  users: SystemUser[];
};
