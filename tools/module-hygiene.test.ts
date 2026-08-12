import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * 2026-08-12 に実際に踏んだ2つの壊れ方を、**文章ではなくゲートとして**残す。
 *
 * 1. `src/lib/decision-confirmation.ts` は本番コードから一度も import されておらず、
 *    参照は自分のテストだけだった。テスト2件は緑のまま**何も守っていなかった**。
 *    しかも同じ関数を別モジュールと二重定義していて、実装が食い違っていた
 *    （trim あり / なし）。名前からは死んでいる方が本命に見えた。
 * 2. `calendarDateKey` が `queue-priority.ts` と `dashboard-actions.ts` へ
 *    正規表現ごと写経されていた。期限超過の判定そのもので、**両方のテストが
 *    緑のまま意味が食い違える**状態だった。
 *
 * どちらも「テストを増やす」では防げない。**テストの向き先**の問題なので、
 * 向き先そのものを検査する。手順を docs に書くだけでは腐るため、ここで落とす。
 *
 * **`src/` の外に置いてある。** `tsconfig.app.json` の `types` は `vite/client` だけで、
 * ブラウザ向けアプリに node のグローバルを混ぜないようにしてある。このファイルは
 * `node:fs` を使うので、node の型を持つ `tsconfig.node.json` 側で型検査する。
 */

const REPO_ROOT = fileURLToPath(new URL("..", import.meta.url));
const SRC_ROOT = path.join(REPO_ROOT, "src");
const LIB_DIR = path.join(SRC_ROOT, "lib");

function listSourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) return listSourceFiles(full);
    return /\.tsx?$/.test(entry) ? [full] : [];
  });
}

const isTestFile = (file: string) => /\.test\.tsx?$/.test(file);

const productionFiles = listSourceFiles(SRC_ROOT).filter(
  (file) => !isTestFile(file),
);
const libModules = readdirSync(LIB_DIR)
  .filter((entry) => /\.ts$/.test(entry) && !isTestFile(entry))
  .map((entry) => entry.replace(/\.ts$/, ""));

describe("lib モジュールは本番コードから参照されている", () => {
  /**
   * 参照ゼロなら、そのモジュールを守るテストは**出荷されないコードを守っている**。
   * 新しく作って配線がまだなら、配線するまでこのテストは落ち続ける。それが意図。
   */
  it.each(libModules)("%s", (moduleName) => {
    const selfPath = path.join(LIB_DIR, `${moduleName}.ts`);
    const importers = productionFiles.filter((file) => {
      if (file === selfPath) return false;
      const source = readFileSync(file, "utf8");
      if (source.includes(`@/lib/${moduleName}`)) return true;
      // lib 内からの相対 import（`./calendar-date` など）
      return (
        path.dirname(file) === LIB_DIR &&
        new RegExp(`["']\\./${moduleName}["']`).test(source)
      );
    });

    expect(
      importers.length,
      `src/lib/${moduleName}.ts が本番コードから参照されていない。` +
        `テストがあっても出荷されないコードを守っているだけになる。` +
        `使うか、消すこと（2026-08-12 の decision-confirmation.ts と同じ形）。`,
    ).toBeGreaterThan(0);
  });
});

describe("同じ名前の定義が複数の lib モジュールに無い", () => {
  /**
   * 同じ規則を2箇所に書くと、**両方のテストが緑のまま食い違える**。
   * 共有したいなら1本にして import する。
   *
   * **export しているものだけでは足りない。** 実際に食い違った `calendarDateKey` は
   * 両方とも module-private だった。公開しているかどうかは、写経かどうかと関係ない。
   *
   * 別物なのに名前が同じ、という正当な衝突が出たら、そのときに許可リストを足す。
   * **先に逃げ道を作らない**（黙らせる手段があると、本物の指摘も黙らされる）。
   */
  it("重複した定義名が無い", () => {
    const owners = new Map<string, string[]>();

    libModules.forEach((moduleName) => {
      const source = readFileSync(path.join(LIB_DIR, `${moduleName}.ts`), "utf8");
      source.split("\n").forEach((line) => {
        // `export { x } from "./y"` の再輸出は定義ではないので数えない
        if (/^export\s+.*\bfrom\b/.test(line)) return;
        // 行頭固定でトップレベルだけ見る（入れ子の関数は数えない）
        const match =
          /^(?:export\s+)?(?:async\s+)?(?:function|const)\s+([A-Za-z0-9_]+)/.exec(
            line,
          );
        if (!match) return;
        owners.set(match[1], [...(owners.get(match[1]) ?? []), moduleName]);
      });
    });

    const duplicated = [...owners.entries()]
      .filter(([, modules]) => modules.length > 1)
      .map(([name, modules]) => `${name}: ${modules.join(" と ")}`);

    expect(
      duplicated,
      `同じ名前の定義が複数の lib モジュールにある。写経なら1本にして import すること` +
        `（2026-08-12 の calendarDateKey と getDecisionNextApplicationStage と同じ形）。`,
    ).toEqual([]);
  });
});
