import { useCallback, useRef, useState } from "react";

import { MicrosoftCopilotStudioService } from "@/generated/services/MicrosoftCopilotStudioService";
import {
  buildCopilotMessageWithContext,
  type CopilotScreenContext,
} from "@/lib/copilot-context";
import {
  buildCopilotRequestBody,
  parseCopilotResponse,
} from "@/lib/copilot-response";

/**
 * Copilot Studio のエージェントスキーマ名。`ExecuteCopilotAsyncV2` の
 * `Copilot` パスパラメータへ渡す（body に入れてはいけない）。
 */
export const DECISIONFLOW_AGENT_SCHEMA_NAME = "ds_DecisionFlowAssistant";

export type CopilotChatMessage = {
  id: string;
  role: "user" | "agent";
  text: string;
};

function newMessageId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`;
}

export function useCopilotChat() {
  // useState だと連続送信で古い conversationId が使われ会話が途切れる。
  const conversationIdRef = useRef<string | undefined>(undefined);
  const [messages, setMessages] = useState<CopilotChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = useCallback(
    async (text: string, context?: CopilotScreenContext) => {
      const message = text.trim();
      if (!message || isSending) return;

      setError(null);
      setIsSending(true);
      // 画面には利用者が書いた文だけを残し、文脈は送信時にだけ付ける。
      setMessages((prev) => [
        ...prev,
        { id: newMessageId(), role: "user", text: message },
      ]);

      try {
        const result = await MicrosoftCopilotStudioService.ExecuteCopilotAsyncV2(
          DECISIONFLOW_AGENT_SCHEMA_NAME,
          buildCopilotRequestBody({
            message: context
              ? buildCopilotMessageWithContext(message, context)
              : message,
          }),
          conversationIdRef.current,
        );

        const parsed = parseCopilotResponse(result);
        if (parsed.conversationId) {
          conversationIdRef.current = parsed.conversationId;
        }
        if (!parsed.text) {
          throw new Error(
            `エージェントから応答本文を取得できませんでした: ${JSON.stringify(result)?.slice(0, 400)}`,
          );
        }

        setMessages((prev) => [
          ...prev,
          { id: newMessageId(), role: "agent", text: parsed.text },
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setIsSending(false);
      }
    },
    [isSending],
  );

  const reset = useCallback(() => {
    conversationIdRef.current = undefined;
    setMessages([]);
    setError(null);
  }, []);

  return { messages, isSending, error, send, reset };
}
