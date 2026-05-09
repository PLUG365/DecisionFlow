import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ExternalLink,
  MessageSquarePlus,
  Sparkles,
  Trash2,
  UserPlus,
} from "lucide-react";

import { FormModal, FormSection } from "@/components/form-modal";
import { OperationWaitOverlay } from "@/components/operation-wait-overlay";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Combobox } from "@/components/ui/combobox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  useAddParticipantWithMention,
  useApplication,
  useCategories,
  useCreateDecision,
  useCreateMention,
  useCreateMessage,
  useCurrentSystemUser,
  useDeleteParticipant,
  useDecisionOptions,
  useDecisions,
  useGenerateAiDecision,
  useMentionsByMessage,
  useMessages,
  useParticipants,
  useResources,
  useSystemUsers,
} from "@/hooks/use-decisionflow";
import {
  ApplicationStage,
  MessageKind,
  participantRoleLabels,
  stageMeta,
  type Participant,
} from "@/types/decisionflow";
import {
  canDecideApplication,
  getDecisionNextApplicationStage,
  getParticipantDeleteWaitState,
  normalizeApplicationStage,
  normalizeGuid,
  validateMentionInput,
} from "@/lib/decisionflow-utils";
import {
  formatAiDecisionUpdatedAt,
  parseAiDecisionBasis,
} from "@/lib/ai-decision";
import { toast } from "sonner";

export default function ApplicationDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data: application, isLoading: isApplicationLoading } =
    useApplication(id);
  const { data: categories = [] } = useCategories();
  const { data: users = [] } = useSystemUsers();
  const { data: messages = [] } = useMessages(id);
  const { data: mentionsByMessage } = useMentionsByMessage(id);
  const { data: resources = [] } = useResources(id);
  const { data: participants = [] } = useParticipants(id);
  const { data: decisions = [] } = useDecisions(id);
  const { data: decisionOptions = [] } = useDecisionOptions();
  const { systemUserId } = useCurrentSystemUser();
  const createMessage = useCreateMessage();
  const createMention = useCreateMention();
  const createDecision = useCreateDecision();
  const addParticipant = useAddParticipantWithMention();
  const deleteParticipant = useDeleteParticipant();
  const generateAiDecision = useGenerateAiDecision();
  const [messageBody, setMessageBody] = useState("");
  const [mentionTargetUserId, setMentionTargetUserId] = useState("");
  const [decisionOptionId, setDecisionOptionId] = useState("");
  const [rationale, setRationale] = useState("");
  const [isParticipantFormOpen, setIsParticipantFormOpen] = useState(false);
  const [participantUserId, setParticipantUserId] = useState("");
  const [participantToDelete, setParticipantToDelete] =
    useState<Participant | null>(null);

  const categoryMap = useMemo(
    () => new Map(categories.map((item) => [item.ds_categoryid, item.ds_name])),
    [categories],
  );
  const userMap = useMemo(
    () =>
      new Map(
        users.map((item) => [
          item.systemuserid,
          item.fullname || item.internalemailaddress || "",
        ]),
      ),
    [users],
  );
  const participantUserIds = useMemo(
    () => new Set(participants.map((item) => item._ds_userid_value)),
    [participants],
  );
  const mentionTargetUserIds = useMemo(() => {
    const userIds = new Set<string>();
    const creatorId = normalizeGuid(application?._createdby_value);
    const deciderId = normalizeGuid(application?._ds_deciderid_value);
    if (creatorId) userIds.add(creatorId);
    if (application?._ds_deciderid_value) {
      userIds.add(deciderId ?? application._ds_deciderid_value);
    }
    participants.forEach((participant) => {
      const participantUserId = normalizeGuid(participant._ds_userid_value);
      if (participantUserId) userIds.add(participantUserId);
    });
    return userIds;
  }, [
    application?._createdby_value,
    application?._ds_deciderid_value,
    participants,
  ]);
  const availableUserOptions = users
    .filter(
      (user) =>
        !participantUserIds.has(user.systemuserid) &&
        Boolean(user.azureactivedirectoryobjectid?.trim()),
    )
    .map((user) => ({
      value: user.systemuserid,
      label: user.fullname || user.internalemailaddress || "名前なし",
    }));
  const mentionTargetOptions = users
    .filter(
      (user) =>
        normalizeGuid(user.systemuserid) !== normalizeGuid(systemUserId) &&
        Boolean(normalizeGuid(user.systemuserid)) &&
        Boolean(user.azureactivedirectoryobjectid?.trim()) &&
        mentionTargetUserIds.has(normalizeGuid(user.systemuserid) ?? ""),
    )
    .map((user) => ({
      value: user.systemuserid,
      label: user.fullname || user.internalemailaddress || "名前なし",
    }));
  const decisionOptionMap = useMemo(
    () =>
      new Map(
        decisionOptions.map((option) => [
          option.ds_decisionoptionid,
          option.ds_name,
        ]),
      ),
    [decisionOptions],
  );

  if (isApplicationLoading) {
    return (
      <div className="flex min-h-[400px] items-center justify-center">
        <div className="flex flex-col items-center gap-2">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">読み込み中...</p>
        </div>
      </div>
    );
  }

  if (!application) {
    return (
      <div className="space-y-4">
        <Button variant="outline" onClick={() => navigate(-1)}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          戻る
        </Button>
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            申請が見つかりません。
          </CardContent>
        </Card>
      </div>
    );
  }

  const stage = normalizeApplicationStage(application.ds_stage);
  const latestDecision = decisions[0];
  const latestDecisionOptionName = latestDecision?._ds_decisionoptionid_value
    ? decisionOptionMap.get(latestDecision._ds_decisionoptionid_value)
    : undefined;
  const deciderName = application._ds_deciderid_value
    ? userMap.get(application._ds_deciderid_value)
    : "";
  const canDecide = canDecideApplication({
    application,
    currentSystemUserId: systemUserId,
  });
  const participantDeleteWaitState = getParticipantDeleteWaitState(
    deleteParticipant.isPending,
  );
  const aiDecisionBasis = parseAiDecisionBasis(application.ds_aidecisionbasis);

  const handleGenerateAiDecision = () => {
    if (!id) return;
    generateAiDecision.mutate(id, {
      onSuccess: () => toast.success("AI判断を更新しました"),
      onError: () => toast.error("AI判断の更新に失敗しました"),
    });
  };

  const handleCreateMessage = () => {
    if (!messageBody.trim() || !id) return;
    const mentionValidation = mentionTargetUserId
      ? validateMentionInput({ targetUserId: mentionTargetUserId })
      : { valid: true, fieldErrors: {} };
    if (!mentionValidation.valid) {
      toast.error(Object.values(mentionValidation.fieldErrors)[0]);
      return;
    }
    const body = messageBody.trim();
    const targetUserId = mentionTargetUserId;
    createMessage.mutate(
      {
        ds_name: body.slice(0, 80),
        ds_body: body,
        ds_kind: MessageKind.Comment,
        _ds_applicationid_value: id,
      },
      {
        onSuccess: (message) => {
          setMessageBody("");
          setMentionTargetUserId("");
          if (!targetUserId) {
            toast.success("コメントを投稿しました");
            return;
          }
          const targetName = userMap.get(targetUserId) ?? "ユーザー";
          createMention.mutate(
            {
              ds_name: `${application.ds_name} - ${targetName} メンション`,
              ds_isread: false,
              _ds_messageid_value: message.ds_messageid,
              _ds_targetuserid_value: targetUserId,
            },
            {
              onSuccess: () =>
                toast.success("コメントとメンションを投稿しました"),
              onError: () => toast.error("メンションの作成に失敗しました"),
            },
          );
        },
        onError: () => toast.error("コメントの投稿に失敗しました"),
      },
    );
  };

  const handleDecision = () => {
    if (!id || !canDecide || !decisionOptionId || !rationale.trim()) return;
    const selectedDecisionOptionName = decisionOptionMap.get(decisionOptionId);
    createDecision.mutate({
      ds_name: `${application.ds_name} - 判断`,
      ds_rationale: rationale.trim(),
      _ds_applicationid_value: id,
      _ds_deciderid_value: application._ds_deciderid_value,
      _ds_decisionoptionid_value: decisionOptionId,
      nextApplicationStage: getDecisionNextApplicationStage(
        selectedDecisionOptionName,
      ),
    });
    setRationale("");
    setDecisionOptionId("");
  };

  const resetParticipantForm = () => {
    setParticipantUserId("");
  };

  const handleAddParticipant = () => {
    if (!id || !systemUserId) return;
    if (!participantUserId.trim()) {
      toast.error("ユーザーを選択してください");
      return;
    }
    const userName = userMap.get(participantUserId) ?? "関係者";
    const addedByUserName = userMap.get(systemUserId) ?? "ユーザー";
    addParticipant.mutate(
      {
        application: {
          ds_applicationid: application.ds_applicationid,
          ds_name: application.ds_name,
        },
        userId: participantUserId,
        userName,
        addedByUserId: systemUserId,
        addedByUserName,
      },
      {
        onSuccess: () => {
          toast.success("関係者を追加しました");
          setIsParticipantFormOpen(false);
          resetParticipantForm();
        },
        onError: () => toast.error("関係者の追加に失敗しました"),
      },
    );
  };

  const handleDeleteParticipant = () => {
    if (!participantToDelete) return;
    if (
      !participantToDelete._ds_applicationid_value ||
      !participantToDelete._ds_userid_value
    ) {
      toast.error("共有解除に必要な関係者情報が不足しています");
      return;
    }
    deleteParticipant.mutate(
      {
        participantId: participantToDelete.ds_participantid,
        applicationId: participantToDelete._ds_applicationid_value,
        userId: participantToDelete._ds_userid_value,
      },
      {
        onSuccess: () => {
          toast.success("関係者を削除しました");
          setParticipantToDelete(null);
        },
        onError: () => toast.error("関係者の削除に失敗しました"),
      },
    );
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-2">
          <Button variant="ghost" className="px-0" onClick={() => navigate(-1)}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            戻る
          </Button>
          <h2 className="truncate text-xl font-semibold tracking-tight">
            {application.ds_name}
          </h2>
          <div className="flex flex-wrap gap-2">
            {stage && (
              <Badge variant="outline" className={stageMeta[stage].className}>
                {stageMeta[stage].label}
              </Badge>
            )}
            {application._ds_categoryid_value && (
              <Badge variant="secondary">
                {categoryMap.get(application._ds_categoryid_value)}
              </Badge>
            )}
            {deciderName && (
              <Badge variant="outline">判断者: {deciderName}</Badge>
            )}
          </div>
        </div>
      </div>

      <Tabs defaultValue="summary" className="min-w-0">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="summary">概要</TabsTrigger>
          <TabsTrigger value="thread">会話</TabsTrigger>
          <TabsTrigger value="resources">資料</TabsTrigger>
          <TabsTrigger value="people">関係者</TabsTrigger>
          <TabsTrigger value="decision">判断</TabsTrigger>
        </TabsList>

        <TabsContent value="summary" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">申請内容</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="whitespace-pre-wrap text-sm leading-6">
                {application.ds_body}
              </p>
              <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                <div>
                  <span className="text-muted-foreground">希望期限</span>
                  <p>
                    {application.ds_duedate
                      ? new Date(application.ds_duedate).toLocaleDateString(
                          "ja-JP",
                        )
                      : "未設定"}
                  </p>
                </div>
                <div>
                  <span className="text-muted-foreground">提出日</span>
                  <p>
                    {application.ds_submittedat
                      ? new Date(application.ds_submittedat).toLocaleDateString(
                          "ja-JP",
                        )
                      : "未提出"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="thread" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">会話スレッド</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {messages.map((message) => {
                const messageMentions =
                  mentionsByMessage?.get(message.ds_messageid) ?? [];
                const mentionTargets = messageMentions
                  .map((m) =>
                    m._ds_targetuserid_value
                      ? userMap.get(m._ds_targetuserid_value)
                      : undefined,
                  )
                  .filter((name): name is string => Boolean(name));
                return (
                  <div
                    key={message.ds_messageid}
                    className="rounded-md border p-3"
                  >
                    <div className="mb-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                      <span>
                        {message._createdby_value
                          ? (userMap.get(message._createdby_value) ?? "")
                          : "システム"}
                      </span>
                      <span>
                        {message.createdon
                          ? new Date(message.createdon).toLocaleString("ja-JP")
                          : ""}
                      </span>
                    </div>
                    {mentionTargets.length > 0 && (
                      <div className="mb-2 flex flex-wrap gap-1">
                        {mentionTargets.map((name, index) => (
                          <Badge
                            key={`${message.ds_messageid}-mention-${index}`}
                            variant="secondary"
                            className="text-[10px]"
                          >
                            @{name}
                          </Badge>
                        ))}
                      </div>
                    )}
                    <p className="text-sm leading-6">{message.ds_body}</p>
                  </div>
                );
              })}
              <div className="space-y-2 pt-2">
                <Textarea
                  value={messageBody}
                  onChange={(event) => setMessageBody(event.target.value)}
                  placeholder="コメントを入力"
                />
                <div className="grid grid-cols-1 gap-2 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                  <div className="space-y-2">
                    <Label>メンション先（任意）</Label>
                    <Combobox
                      options={mentionTargetOptions}
                      value={mentionTargetUserId}
                      onValueChange={setMentionTargetUserId}
                      placeholder="通知したいユーザーを選択"
                      searchPlaceholder="ユーザーを検索"
                    />
                  </div>
                  <Button
                    onClick={handleCreateMessage}
                    disabled={
                      !messageBody.trim() ||
                      createMessage.isPending ||
                      createMention.isPending
                    }
                  >
                    <MessageSquarePlus className="mr-2 h-4 w-4" />
                    投稿
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="resources" className="space-y-3">
          {resources.map((resource) => (
            <Card key={resource.ds_applicationresourceid}>
              <CardContent className="space-y-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">{resource.ds_name}</p>
                  <span className="text-xs text-muted-foreground">
                    {resource._createdby_value
                      ? (userMap.get(resource._createdby_value) ?? "")
                      : ""}
                    {resource.createdon
                      ? ` ・ ${new Date(resource.createdon).toLocaleString("ja-JP")}`
                      : ""}
                  </span>
                </div>
                {resource.ds_description && (
                  <p className="text-sm text-muted-foreground">
                    {resource.ds_description}
                  </p>
                )}
                {resource.ds_url && (
                  <Button variant="outline" size="sm" asChild>
                    <a href={resource.ds_url} target="_blank" rel="noreferrer">
                      <ExternalLink className="mr-2 h-4 w-4" />
                      開く
                    </a>
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="people" className="space-y-3">
          <div className="flex justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsParticipantFormOpen(true)}
            >
              <UserPlus className="mr-2 h-4 w-4" />
              関係者を追加
            </Button>
          </div>
          {participants.map((participant) => (
            <Card key={participant.ds_participantid}>
              <CardContent className="flex items-center justify-between p-4">
                <div>
                  <p className="font-medium">
                    {participant._ds_userid_value
                      ? userMap.get(participant._ds_userid_value)
                      : ""}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {participant.ds_role
                      ? participantRoleLabels[participant.ds_role]
                      : ""}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  disabled={deleteParticipant.isPending}
                  onClick={() => setParticipantToDelete(participant)}
                  aria-label="関係者を削除"
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </CardContent>
            </Card>
          ))}
          {participants.length === 0 && (
            <Card>
              <CardContent className="p-4 text-sm text-muted-foreground">
                関係者はまだ登録されていません。
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="decision" className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="space-y-4">
              {latestDecision && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">最新判断</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    {latestDecisionOptionName && (
                      <Badge variant="outline">
                        判断結果: {latestDecisionOptionName}
                      </Badge>
                    )}
                    <p>{latestDecision.ds_rationale}</p>
                    <p className="text-muted-foreground">
                      {latestDecision.ds_decidedat
                        ? new Date(latestDecision.ds_decidedat).toLocaleString(
                            "ja-JP",
                          )
                        : ""}
                    </p>
                  </CardContent>
                </Card>
              )}
              {canDecide && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      {latestDecision ? "再判断パネル" : "判断パネル"}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <Select
                      value={decisionOptionId}
                      onValueChange={setDecisionOptionId}
                    >
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="判断選択肢" />
                      </SelectTrigger>
                      <SelectContent>
                        {decisionOptions.map((option) => (
                          <SelectItem
                            key={option.ds_decisionoptionid}
                            value={option.ds_decisionoptionid}
                          >
                            {option.ds_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Textarea
                      value={rationale}
                      onChange={(event) => setRationale(event.target.value)}
                      placeholder="判断理由"
                    />
                    <Button
                      className="w-full"
                      onClick={handleDecision}
                      disabled={!decisionOptionId || !rationale.trim()}
                    >
                      判断を確定
                    </Button>
                  </CardContent>
                </Card>
              )}
              {!latestDecision && !canDecide && (
                <Card>
                  <CardContent className="p-4 text-sm text-muted-foreground">
                    判断はまだ確定されていません。
                  </CardContent>
                </Card>
              )}
            </div>

            <Card>
              <CardHeader className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <CardTitle className="text-base">AI判断</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleGenerateAiDecision}
                    disabled={
                      stage !== ApplicationStage.Submitted ||
                      generateAiDecision.isPending
                    }
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    AI判断更新
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  更新日時:{" "}
                  {formatAiDecisionUpdatedAt(
                    application.ds_aidecisionupdatedat,
                  )}
                </p>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="space-y-1">
                  <p className="font-medium">申請概要</p>
                  <p className="whitespace-pre-wrap text-muted-foreground">
                    {application.ds_aiapplicationsummary ||
                      "まだ生成されていません。"}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="font-medium">会話概要</p>
                  <p className="whitespace-pre-wrap text-muted-foreground">
                    {application.ds_aiconversationsummary ||
                      "まだ生成されていません。"}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="font-medium">推奨判断</p>
                  {application.ds_aidecisionoptiontext ? (
                    <Badge variant="outline">
                      {application.ds_aidecisionoptiontext}
                    </Badge>
                  ) : (
                    <p className="text-muted-foreground">未生成</p>
                  )}
                </div>
                <div className="space-y-1">
                  <p className="font-medium">コメント</p>
                  <p className="whitespace-pre-wrap text-muted-foreground">
                    {application.ds_aidecisioncomment ||
                      "まだ生成されていません。"}
                  </p>
                </div>
                <div className="space-y-2">
                  <p className="font-medium">リスク</p>
                  {aiDecisionBasis.risks.length > 0 ? (
                    <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                      {aiDecisionBasis.risks.map((risk) => (
                        <li key={risk}>{risk}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-muted-foreground">未生成</p>
                  )}
                </div>
                <div className="space-y-2">
                  <p className="font-medium">類似案件</p>
                  {aiDecisionBasis.similarCases.length > 0 ? (
                    <div className="space-y-2">
                      {aiDecisionBasis.similarCases.map((item) => (
                        <div key={item.title} className="rounded-md border p-2">
                          <p className="font-medium">{item.title}</p>
                          {item.decision && (
                            <p className="text-muted-foreground">
                              判断: {item.decision}
                            </p>
                          )}
                          {item.reason && (
                            <p className="text-muted-foreground">
                              {item.reason}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted-foreground">
                      {aiDecisionBasis.rawText || "未生成"}
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <FormModal
        open={isParticipantFormOpen}
        onOpenChange={(open) => {
          setIsParticipantFormOpen(open);
          if (!open) resetParticipantForm();
        }}
        title="関係者を追加"
        description="申請に参加するユーザーと役割を登録します。"
        onSave={handleAddParticipant}
        saveLabel="追加"
        isSaving={addParticipant.isPending}
      >
        <FormSection title="関係者">
          <div className="space-y-2">
            <Label>ユーザー *</Label>
            <Combobox
              options={availableUserOptions}
              value={participantUserId}
              onValueChange={setParticipantUserId}
              placeholder="ユーザーを選択"
              searchPlaceholder="ユーザーを検索"
            />
          </div>
        </FormSection>
      </FormModal>

      <ConfirmDialog
        open={Boolean(participantToDelete)}
        onOpenChange={(open) => {
          if (!open) setParticipantToDelete(null);
        }}
        title="関係者を削除しますか？"
        description={
          participantToDelete
            ? `「${
                participantToDelete._ds_userid_value
                  ? (userMap.get(participantToDelete._ds_userid_value) ??
                    "関係者")
                  : "関係者"
              }」をこの申請の関係者から削除します。`
            : "関係者を削除します。"
        }
        confirmLabel="削除"
        variant="destructive"
        onConfirm={handleDeleteParticipant}
      />

      <OperationWaitOverlay
        open={participantDeleteWaitState.visible}
        title={participantDeleteWaitState.title}
        description={participantDeleteWaitState.description}
      />
    </div>
  );
}
