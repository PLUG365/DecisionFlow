import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { COPILOT_CONVERSATION_STARTERS } from "../src/lib/copilot-starters";

/**
 * **同じものが2箇所にある**のを、片方だけ古くならないように縛る。
 *
 * 正本は Copilot Studio へ push される `agent.mcs.yml` の `conversationStarters`。
 * Teams などのチャネルはそれをボタンにするが、Code Apps の埋め込みパネルには出ないので、
 * アプリ側に写しを置いてチップとして描画している。
 *
 * 写しが増えた時点で「両方のテストが緑のまま食い違う」余地ができる。TS と YAML の
 * またぎなので `tools/module-hygiene.test.ts`（lib 内の重複を見る）では捕まらない。
 * ここで直接突き合わせる。
 *
 * **YAML パーサを使っていない。** `js-yaml` は node_modules にあるが `package.json` の
 * 依存ではなく推移的に入っているだけで、依存が変われば消える。この節の構造は単純なので
 * 行を読む方が壊れにくい。
 */

const REPO_ROOT = fileURLToPath(new URL("..", import.meta.url));
const AGENT_YAML = path.join(
  REPO_ROOT,
  "copilot",
  "DecisionFlowAssistant",
  "agent.mcs.yml",
);

function readYamlStarters(): { title: string; text: string }[] {
  const lines = readFileSync(AGENT_YAML, "utf8").split("\n");
  const startIndex = lines.findIndex((line) =>
    /^conversationStarters:\s*$/.test(line),
  );
  if (startIndex < 0) return [];

  const starters: { title: string; text: string }[] = [];
  for (const line of lines.slice(startIndex + 1)) {
    // 次のトップレベルキーに来たら終わり（`aISettings:` など）
    if (/^\S/.test(line)) break;
    const title = /^\s*-\s*title:\s*(.+?)\s*$/.exec(line);
    if (title) {
      starters.push({ title: title[1], text: "" });
      continue;
    }
    const text = /^\s*text:\s*(.+?)\s*$/.exec(line);
    if (text && starters.length > 0) {
      starters[starters.length - 1].text = text[1];
    }
  }
  return starters;
}

describe("パネルのチップは agent.mcs.yml の写しとして正しい", () => {
  const yamlStarters = readYamlStarters();

  /** 読めていないのに緑、を防ぐ。空配列同士は一致してしまう。 */
  it("YAML から会話のきっかけを実際に読めている", () => {
    expect(yamlStarters.length).toBeGreaterThan(0);
    expect(yamlStarters.every((starter) => starter.text.length > 0)).toBe(true);
  });

  it("タイトルと本文が正本と一致する", () => {
    expect(COPILOT_CONVERSATION_STARTERS).toEqual(yamlStarters);
  });
});
