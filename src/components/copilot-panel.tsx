import { useEffect, useRef, useState } from "react";
import { Bot, RotateCcw, Send, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useCopilotChat } from "@/hooks/use-copilot-chat";

/**
 * DecisionFlow Assistant の右サイドパネル。
 * パネル内での対話が Dataverse を更新した場合は、閉じたときに再取得させる
 * （アプリ側は画面操作を実装しない）。
 */
export function CopilotPanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { messages, isSending, error, send, reset } = useCopilotChat();
  const [draft, setDraft] = useState("");
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, isSending]);

  if (!open) return null;

  const handleSend = () => {
    const text = draft;
    setDraft("");
    void send(text);
  };

  return (
    <aside
      className="fixed right-0 top-16 bottom-0 z-40 flex w-full max-w-[400px] flex-col border-l border-border bg-background shadow-xl"
      aria-label="DecisionFlow Assistant"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">DecisionFlow Assistant</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={reset}
            aria-label="会話をリセット"
            disabled={isSending || messages.length === 0}
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onClose}
            aria-label="アシスタントを閉じる"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.length === 0 && !isSending && (
          <p className="py-8 text-center text-xs text-muted-foreground">
            申請や判断について聞いてみてください。
          </p>
        )}
        {messages.map((message) => (
          <div
            key={message.id}
            className={
              message.role === "user"
                ? "ml-6 rounded-lg bg-primary/10 px-3 py-2"
                : "mr-6 rounded-lg border border-border px-3 py-2"
            }
          >
            <p className="whitespace-pre-wrap text-sm leading-6">
              {message.text}
            </p>
          </div>
        ))}
        {isSending && (
          <p className="mr-6 rounded-lg border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
            考えています…
          </p>
        )}
        {error && (
          <p className="rounded-lg border border-destructive/50 px-3 py-2 text-xs text-destructive">
            {error}
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="space-y-2 border-t border-border px-4 py-3">
        <Textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="メッセージを入力"
          rows={3}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
              event.preventDefault();
              handleSend();
            }
          }}
        />
        <Button
          className="w-full"
          onClick={handleSend}
          disabled={!draft.trim() || isSending}
        >
          <Send className="mr-2 h-4 w-4" />
          送信
        </Button>
      </div>
    </aside>
  );
}
