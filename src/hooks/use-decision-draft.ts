import { useCallback, useEffect, useRef, useState } from "react";

import {
  decisionDraftKey,
  parseDecisionDraft,
  serializeDecisionDraft,
} from "@/lib/decision-draft";

/**
 * 判断理由の下書きをブラウザに退避する。判定と期限は `@/lib/decision-draft` の純関数側にあり、
 * ここは保存先への出し入れだけを持つ。
 *
 * ストレージが使えない環境（プライベートモード、埋め込み時の制限など）では**黙って諦める**。
 * 下書きは補助機能なので、ここで落として判断パネル全体を壊さない。
 */
function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) {
      window.localStorage.removeItem(key);
      return;
    }
    window.localStorage.setItem(key, value);
  } catch {
    // 保存できなくても入力は続けられる
  }
}

export function useDecisionDraft({
  systemUserId,
  applicationId,
}: {
  systemUserId: string | null | undefined;
  applicationId: string | null | undefined;
}) {
  // 判断パネルが出ていない申請でも復元してよい。書き込みはテキスト入力からしか起きず、
  // 差し戻し後の再判断では同じ下書きを続けられる方が望ましいため。
  const key = decisionDraftKey(systemUserId, applicationId);
  const [text, setText] = useState("");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const restoredKey = useRef<string | null>(null);

  /**
   * `systemUserId` が遅れて解決したときに、先に打ち始めていた入力を復元で潰す競合は起きない。
   * 判断パネルは `canDecideApplication` が true のときだけ描画され、その関数は
   * `currentSystemUserId` が空なら false を返すので、ID が揃う前は入力欄自体が無い。
   * 申請を切り替えたときは key が変わるので、前の申請の下書きは引きずらない。
   */
  useEffect(() => {
    if (!key) {
      restoredKey.current = null;
      return;
    }
    if (restoredKey.current === key) return;

    restoredKey.current = key;
    const stored = parseDecisionDraft(readStorage(key), new Date());
    setText(stored?.text ?? "");
    setSavedAt(stored?.savedAt ?? null);
  }, [key]);

  const update = useCallback(
    (value: string) => {
      setText(value);
      if (!key) return;

      const now = new Date();
      const serialized = serializeDecisionDraft(value, now);
      writeStorage(key, serialized);
      setSavedAt(serialized ? now.toISOString() : null);
    },
    [key],
  );

  /** 判断が確定したときと、利用者が明示的に捨てたときに呼ぶ */
  const clear = useCallback(() => {
    setText("");
    setSavedAt(null);
    if (key) writeStorage(key, null);
  }, [key]);

  return { text, savedAt, update, clear };
}
