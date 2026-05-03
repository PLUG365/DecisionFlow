import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import { ListTable, type TableColumn } from "@/components/list-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  useApplications,
  useMarkMentionRead,
  useMentionsForCurrentUser,
  useMessages,
} from "@/hooks/use-decisionflow";
import type { Mention } from "@/types/decisionflow";

type MentionRow = Mention & Record<string, unknown>;

export default function MentionsPage() {
  const navigate = useNavigate();
  const { data: mentions = [] } = useMentionsForCurrentUser();
  const { data: messages = [] } = useMessages();
  const { data: applications = [] } = useApplications();
  const markRead = useMarkMentionRead();

  const messageMap = useMemo(
    () => new Map(messages.map((item) => [item.ds_messageid, item])),
    [messages],
  );
  const applicationMap = useMemo(
    () => new Map(applications.map((item) => [item.ds_applicationid, item])),
    [applications],
  );

  const columns: TableColumn<MentionRow>[] = [
    {
      key: "application",
      label: "申請",
      render: (item) => {
        const message = item._ds_messageid_value
          ? messageMap.get(item._ds_messageid_value as string)
          : undefined;
        const application = message?._ds_applicationid_value
          ? applicationMap.get(message._ds_applicationid_value)
          : undefined;
        return application?.ds_name ?? "";
      },
    },
    {
      key: "message",
      label: "メッセージ",
      render: (item) => {
        const message = item._ds_messageid_value
          ? messageMap.get(item._ds_messageid_value as string)
          : undefined;
        return (
          <span className="line-clamp-2">
            {message?.ds_body ?? item.ds_name}
          </span>
        );
      },
    },
    {
      key: "ds_isread",
      label: "既読",
      render: (item) => (
        <Badge variant={item.ds_isread ? "outline" : "default"}>
          {item.ds_isread ? "既読" : "未読"}
        </Badge>
      ),
    },
    {
      key: "createdon",
      label: "作成日",
      render: (item) =>
        item.createdon ? new Date(item.createdon).toLocaleString("ja-JP") : "",
    },
    {
      key: "action",
      label: "操作",
      render: (item) => (
        <Button
          variant="outline"
          size="sm"
          disabled={item.ds_isread}
          onClick={(event) => {
            event.stopPropagation();
            markRead.mutate(item.ds_mentionid);
          }}
        >
          既読にする
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">メンション</h2>
        <p className="text-sm text-muted-foreground">
          自分宛ての確認依頼を一覧で追跡します。
        </p>
      </div>
      <ListTable
        data={mentions as MentionRow[]}
        columns={columns}
        searchKeys={["ds_name"]}
        onRowClick={(row) => {
          const message = row._ds_messageid_value
            ? messageMap.get(row._ds_messageid_value as string)
            : undefined;
          if (message?._ds_applicationid_value)
            navigate(`/applications/${message._ds_applicationid_value}`);
        }}
      />
    </div>
  );
}
