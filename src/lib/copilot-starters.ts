export type CopilotStarter = {
  title: string;
  text: string;
};

/**
 * パネルの空状態に出す会話のきっかけ。
 *
 * **正本は `copilot/DecisionFlowAssistant/agent.mcs.yml` の `conversationStarters`。**
 * Teams や Copilot Studio のチャネルではプラットフォームがそれをボタンとして出すが、
 * Code Apps の埋め込みパネルは出さないので、ここに写しを置いている。
 *
 * **これは「同じものが2箇所にある」形なので、放っておくと片方だけ古くなる。**
 * `tools/copilot-starters.test.ts` が YAML と突き合わせて落とす。文言を変えるときは
 * **YAML を直してから**ここを合わせること（逆をやると正本が写しに引きずられる）。
 *
 * 能力そのものは 2026-08-12 に実機で確認済み。「私が判断すべき提出済みの申請を一覧で」
 * と聞くと、タイトル・申請者・希望期限・提出日時・AI推奨判断が返る。
 */
export const COPILOT_CONVERSATION_STARTERS: CopilotStarter[] = [
  {
    title: "判断待ち一覧",
    text: "私が判断すべき提出済みの申請を一覧で教えてください",
  },
  {
    title: "申請の概要",
    text: "この申請の背景・目的・論点を要約してください",
  },
  {
    title: "関連資料",
    text: "この申請の関連資料リンクを一覧で教えてください",
  },
  {
    title: "類似案件",
    text: "過去の類似案件と判断結果を教えてください",
  },
  {
    title: "判断ドラフト",
    text: "この申請の推奨判断と判断コメントのドラフトを作成してください",
  },
];

/**
 * 申請を1件開いているときだけ意味を持つものと、どこでも使えるものを分ける。
 * 判断キューやダッシュボードで「この申請の…」を出すと、指すものが無いまま送られる。
 */
const APPLICATION_SCOPED_TITLES = new Set([
  "申請の概要",
  "関連資料",
  "類似案件",
  "判断ドラフト",
]);

export function getCopilotStartersForScreen({
  hasApplicationContext,
}: {
  hasApplicationContext: boolean;
}): CopilotStarter[] {
  if (hasApplicationContext) return COPILOT_CONVERSATION_STARTERS;
  return COPILOT_CONVERSATION_STARTERS.filter(
    (starter) => !APPLICATION_SCOPED_TITLES.has(starter.title),
  );
}
