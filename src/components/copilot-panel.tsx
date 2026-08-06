import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { Bot, RotateCcw, Send, X } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useCopilotChat } from "@/hooks/use-copilot-chat";
import { getCopilotScreenContext } from "@/lib/copilot-context";

/** エージェントの応答は Markdown（見出し・表・リスト）で返るため整形して描画する。 */
const markdownComponents: Components = {
  h1: (props) => <h3 className="mt-3 text-sm font-semibold" {...props} />,
  h2: (props) => <h3 className="mt-3 text-sm font-semibold" {...props} />,
  h3: (props) => <h4 className="mt-3 text-sm font-semibold" {...props} />,
  p: (props) => <p className="leading-6" {...props} />,
  ul: (props) => <ul className="list-disc space-y-1 pl-5" {...props} />,
  ol: (props) => <ol className="list-decimal space-y-1 pl-5" {...props} />,
  strong: (props) => <strong className="font-semibold" {...props} />,
  hr: () => <hr className="my-3 border-border" />,
  a: (props) => (
    <a
      className="text-primary underline underline-offset-2"
      target="_blank"
      rel="noreferrer noopener"
      {...props}
    />
  ),
  code: (props) => (
    <code className="rounded bg-muted px-1 py-0.5 text-xs" {...props} />
  ),
  pre: (props) => (
    <pre
      className="overflow-x-auto rounded bg-muted p-2 text-xs"
      {...props}
    />
  ),
  table: (props) => (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs" {...props} />
    </div>
  ),
  th: (props) => (
    <th className="border border-border px-2 py-1 text-left font-semibold" {...props} />
  ),
  td: (props) => <td className="border border-border px-2 py-1" {...props} />,
};

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
  const { pathname } = useLocation();
  const screenContext = useMemo(
    () => getCopilotScreenContext(pathname),
    [pathname],
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, isSending]);

  if (!open) return null;

  const handleSend = () => {
    const text = draft;
    setDraft("");
    void send(text, screenContext);
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
            {message.role === "user" ? (
              <p className="whitespace-pre-wrap text-sm leading-6">
                {message.text}
              </p>
            ) : (
              <div className="space-y-2 text-sm">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {message.text}
                </ReactMarkdown>
              </div>
            )}
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
