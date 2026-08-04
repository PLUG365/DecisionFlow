# AI 開発ツールの利用規約

DecisionFlow の開発では、公式 Power Platform / Dataverse ツールと Power CAT を使って設計、実装、監査を補助する。
FlowStudio は外部有償 MCP であり、このリポジトリでは使用も設定もしない。

## 共有設定

リポジトリ直下の [`.mcp.json`](../.mcp.json) は Claude Code / GitHub Copilot CLI 向け、
[`.codex/config.toml`](../.codex/config.toml) は Codex 向けの PAC MCP の**資格情報を含まない**宣言である。

- `DATAVERSE_URL` は追跡しない `.env` にだけ設定する。
- Dataverse MCP の実URLは環境・開発者ごとに異なるため、共有 `.mcp.json` または
  `.codex/config.toml` に置かない。
  Dataverse プラグインの `dv-connect` が、Power Platform 管理センターで許可された開発環境へ
  ユーザー設定として接続を登録する。
- MCP のプロジェクト設定はクライアントで承認してから利用する。接続しただけで書込みを許可しない。
- PAC MCP はローカル開発・検証用である。`dnx` が .NET 10 以上で PAC MCP を起動する。

## 開発端末への導入

### Claude Code

```powershell
claude plugin marketplace add microsoft/power-platform-skills
claude plugin install power-automate@power-platform-skills
claude plugin install dataverse@claude-plugins-official
```

### Codex

Codex はプラグインを開発者プロファイルへ導入し、リポジトリの `.codex/config.toml` は
PAC MCP だけを共有する。Power Automate (FlowAgent) と Dataverse は Microsoft 公式の
マーケットプレースから開発者プロファイルへ導入する。

```powershell
codex plugin marketplace add microsoft/power-platform-skills --ref main
codex plugin add power-automate@power-platform-skills
codex plugin marketplace add microsoft/Dataverse-skills --ref main
codex plugin add dataverse@dataverse-skills
```

プラグイン導入または MCP 登録後は Codex を再起動し、実ユーザー環境で次を確認する。

```powershell
codex plugin list --available --json
codex mcp list
```

`power-automate@power-platform-skills` は FlowAgent MCP を、
`dataverse@dataverse-skills` は Dataverse の specialist skills を提供する。

Dataverse MCP は `.env` の `DATAVERSE_URL` を使い、開発者ごとの `~/.codex/config.toml` へ
公式 `@microsoft/dataverse` stdio プロキシとして登録する。URL、認証キャッシュ、
`DATAVERSE_OPERATION_CONTEXT` は追跡ファイルに保存しない。

Power CAT の公式マーケットプレースは GitHub Copilot CLI / Microsoft Scout 向けである。Codex では、
公式リポジトリからユーザースキルとして導入した `powercat-overflow`、
`eval-generator-code-app`、`design-guide` を共通の補助ツールとして使う。スキルの導入先は
開発者プロファイルに限り、評価・設計結果を既存フローまたは Code App に自動反映しない。
スキルを追加した直後は、新しい Codex 会話で利用を開始する。

### GitHub Copilot CLI

Power CAT は GitHub Copilot CLI（または Microsoft Scout）用である。Copilot CLI が無い場合は、Node.js 22 以上で先に導入する。

```powershell
npm install -g @github/copilot
copilot plugin marketplace add microsoft/power-platform-skills
copilot plugin marketplace add microsoft/power-cat-skills
copilot plugin install code-apps-preview@power-platform-skills
copilot plugin install power-automate@power-platform-skills
copilot plugin install dataverse@awesome-copilot
copilot plugin install powercat-code-apps@power-cat-skills
copilot plugin install powercat-dataverse@power-cat-skills
copilot plugin install powercat-procode-eval@power-cat-skills
copilot plugin install powercat-overflow@power-cat-skills
```

### Copilot Studio の標準エージェント

標準エージェント（YAML）の作成、編集、検証、テストには Microsoft 公式
`copilot-studio@skills-for-copilot-studio` を Claude Code と GitHub Copilot CLI の
開発者プロファイルへ導入する。Codex では同じ公式リポジトリのスキルを開発者プロファイルへ
導入して利用する。

- VS Code の公式 `ms-CopilotStudio.vscode-copilotstudio` 拡張は、エージェントの clone /
  pull / push に必要である。
- VS Code の **Apply changes** と Copilot Studio プラグインの push は、開発環境の
  エージェントを即時変更する。その前に対象、差分、接続、公開状態を確認し、明示承認を得る。
- 新しいエクスペリエンス向けの `mcs-assistant@copilot-studio-plugin` は実験的であるため、
  この標準構成には含めない。評価する場合も開発環境に限定し、別途明示承認を得る。

初回の GitHub Copilot CLI 利用時は、開発者自身が `/login` を実行して認証する。トークンを `.env`、MCP 設定、シェル履歴、またはリポジトリに保存してはならない。

Power Pages、Canvas Apps、Generative Pages は現在の DecisionFlow の対象外であり、導入対象に含めない。

## ツールルーティング

| 開発作業 | 第一候補 | 制約 |
| --- | --- | --- |
| フローの設計・新規生成・接続調査・失敗診断 | 公式 Power Automate プラグイン（FlowAgent） | 開発環境だけ。作成直後は停止状態。公開は明示承認後 |
| 現行 7 フローの変更 | リポジトリの Python デプロイスクリプト | FlowAgent の出力をレビューしてから、再現可能なソース変更へ反映する |
| Dataverse メタデータ・レコードの確認 | `dv-query` / Dataverse MCP | 読取り専用。書込み、削除、ロール変更、環境変更は明示承認後 |
| Code Apps のデザイン・静的評価 | `powercat-code-apps` / `powercat-procode-eval` | 評価結果はレビュー対象。自動修正しない |
| Solution 内フローの品質監査 | `powercat-overflow` | Solution Zip を監査し、指摘を確認してから修正する |
| Power Platform CLI 操作の支援 | PAC MCP | list / inspect / validate / pack が既定。push / import / delete / publish は明示承認後 |

## 開発環境での有効化

プラグインの導入だけでは、Power Platform テナントには接続しない。実際に使う開発者が、対象の**開発環境**を選んで次を実施する。

1. Power Platform 管理センターで、対象環境の Dataverse MCP と使用するクライアントを許可する。
2. ローカルの追跡しない `.env` を読み、`DATAVERSE_URL` を起動するシェルの環境変数に設定する。URL の実値は共有設定へ書かない。
3. `az login` と必要な Power Platform / Dataverse 認証を、開発者自身のアカウントで行う。
4. Dataverse プラグインの `dv-connect` を使い、開発環境の Dataverse MCP をユーザー設定として登録する。Claude Code / Copilot CLI とも、接続先と要求権限を確認して承認する。
5. まず `dv-query`、Dataverse MCP のメタデータ取得、PAC MCP の一覧・検証だけで接続を確認する。

本番環境を対象にした認証、接続、書込み、フローの有効化は、このリポジトリの設定作業には含めない。

## フロー生成の必須手順

1. フロー名、トリガー、アクション、接続参照、データ入出力、失敗時の挙動を設計レビューで承認する。
2. FlowAgent で既存フロー・コネクタ操作・接続状態を読み取り確認する。
3. `validate_flow` と `preflight_flow` を通す。既存の DecisionFlow フロー名と衝突した場合は作成せず停止する。
4. 新規フローは**開発環境かつ停止状態**で作成する。接続は既存のソリューション接続参照を使い、接続の自動作成はしない。
5. 定義、接続参照、最小スモークテストの結果をレビューする。
6. 有効化・公開・Solution への取り込みは、対象環境と影響を示した明示承認後に実行する。
7. 採用したフローは、リポジトリのスクリプトまたはSolution成果物へ再現可能な形で反映する。

## 参考

- [Power Platform Skills / Power Automate](https://github.com/microsoft/power-platform-skills/tree/main/plugins/power-automate)
- [Dataverse Skills](https://github.com/microsoft/Dataverse-skills)
- [Power CAT Skills](https://github.com/microsoft/power-cat-skills)
- [PAC CLI 内蔵 MCP](https://learn.microsoft.com/en-us/power-platform/developer/howto/use-mcp)
- [Dataverse MCP の許可設定](https://learn.microsoft.com/en-us/power-apps/maker/data-platform/data-platform-mcp-disable)
