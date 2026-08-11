import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, MessageSquare, Paperclip, Search, Scale } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useDecisionFlowData } from "@/hooks/use-decisionflow";
import {
  searchDecisionFlow,
  type CrossSearchResultKind,
} from "@/lib/cross-search";

const kindMeta: Record<
  CrossSearchResultKind,
  { label: string; icon: typeof FileText }
> = {
  application: { label: "申請", icon: FileText },
  message: { label: "メッセージ", icon: MessageSquare },
  decision: { label: "判断理由", icon: Scale },
  resource: { label: "関連資料", icon: Paperclip },
};

export default function SearchPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const { data } = useDecisionFlowData();
  const results = useMemo(
    () =>
      searchDecisionFlow({
        applications: data?.applications ?? [],
        messages: data?.messages ?? [],
        decisions: data?.decisions ?? [],
        resources: data?.resources ?? [],
        query,
      }),
    [data, query],
  );
  const hasQuery = query.trim().length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">横断検索</h2>
        <p className="text-sm text-muted-foreground">
          申請、メッセージ、判断理由、関連資料をまとめて検索します。
        </p>
      </div>
      <div className="relative">
        <Search
          className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="キーワードを入力..."
          aria-label="横断検索キーワード"
          className="pl-9"
          autoFocus
        />
      </div>
      {!hasQuery ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            キーワードを入力すると、閲覧可能なデータから検索します。
          </CardContent>
        </Card>
      ) : results.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-muted-foreground">
            該当する結果はありません。
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">{results.length}件</p>
          {results.map((result) => {
            const meta = kindMeta[result.kind];
            const Icon = meta.icon;
            return (
              <Card
                key={result.id}
                className={result.applicationId ? "cursor-pointer hover:shadow-md" : ""}
              >
                <button
                  type="button"
                  className="block w-full text-left disabled:cursor-default"
                  disabled={!result.applicationId}
                  onClick={() =>
                    result.applicationId &&
                    navigate(`/applications/${result.applicationId}`)
                  }
                >
                  <CardContent className="space-y-2 p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="secondary">
                        <Icon aria-hidden="true" />
                        {meta.label}
                      </Badge>
                      <span className="text-sm text-muted-foreground">
                        {result.applicationTitle}
                      </span>
                    </div>
                    <h3 className="font-medium">{result.title}</h3>
                    <p className="line-clamp-2 text-sm text-muted-foreground">
                      {result.excerpt}
                    </p>
                  </CardContent>
                </button>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
