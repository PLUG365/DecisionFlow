# Codex の Power Platform 開発体験を統一する設計

**日付:** 2026-08-05
**状態:** 実装前レビュー

## 目的

DecisionFlow を Codex で開発するときも、Claude Code と GitHub Copilot CLI と同様に、会話から
Power Automate フロー、Dataverse、PAC CLI を扱えるようにする。

対象は開発環境での設計、調査、検証、停止状態のフロー作成・編集・実行・診断である。既存フローの
正本は引き続きリポジトリの Python デプロイスクリプトおよび Solution 成果物とする。

## 採用する構成

公式の実装を優先し、独自に FlowAgent を複製・改変しない。

1. Codex のプラグイン・マーケットプレースから、公式 Power Automate プラグインと公式 Dataverse
   プラグインを導入する。
2. リポジトリの `.codex/config.toml` には、資格情報を持たない PAC MCP だけを登録する。
3. Dataverse MCP は開発者ごとの `~/.codex/config.toml` に、公式の `@microsoft/dataverse` stdio
   プロキシを通じて登録する。実環境 URL と認証情報をリポジトリに記録しない。
4. Power CAT は Codex 用の公式マニフェストがないため、公式 Power CAT の運用ガイドを参照する
   Codex 用の skill-only プラグインとして追加する。外部接続や実行エンジンは含めない。
5. Codex、Claude Code、GitHub Copilot CLI のいずれも `AGENTS.md` と
   `docs/AI_DEVELOPMENT_TOOLING.md` の同じ運用ルールに従う。

この構成により、FlowAgent は公式の自己完結 MCP エンジンをそのまま使い、Dataverse は公式プラグインの
Codex 対応設定を用いる。公式プラグイン導入が Codex で読み込めない場合だけ、失敗理由を記録して
FlowAgent の薄いローカル起動アダプターを代替案として検討する。実装時に先にフォークやコピーを作らない。

## 操作境界

| 操作 | 開発環境 | 本番環境 | 必要な条件 |
| --- | --- | --- | --- |
| フロー一覧・定義・実行履歴の閲覧、診断 | 許可 | 許可しない | 開発者の認証と最小権限 |
| 新規フローの作成・編集・実行 | 許可 | 許可しない | 停止状態で作成、`validate_flow` と `preflight_flow`、接続参照レビュー |
| フローの公開、有効化、削除、既存フローの置換 | 明示承認後 | 明示承認後 | 対象、影響、ロールバック方法を示す |
| Dataverse のメタデータ・データ閲覧 | 許可 | 許可しない | 開発者の認証と最小権限 |
| Dataverse の書込み、削除、ロール・環境変更 | 明示承認後 | 明示承認後 | 対象、影響、バックアップを示す |
| PAC の list、inspect、validate、pack | 許可 | 許可しない | 読取り・検証中心 |
| PAC の import、publish、push、delete | 明示承認後 | 明示承認後 | 対象、影響、ロールバック方法を示す |

skill の指示と Codex の確認画面は事故防止の補助であり、認可境界そのものではない。Dataverse と
Power Platform 側の開発環境の選択、MCP クライアント許可、最小権限ロールを必須の強制境界とする。

## 変更範囲

### 追跡するもの

- `.codex/config.toml` — PAC MCP のみ。URL、トークン、秘密情報を含めない。
- Codex 用の Power CAT skill-only プラグインと、その導入・更新手順。
- `AGENTS.md`、AI ツール運用ドキュメント、漏えい防止テスト。

### 開発者ごとに保持するもの

- Codex のプラグイン・マーケットプレース登録と、公式 Power Automate／Dataverse プラグイン導入。
- `~/.codex/config.toml` の Dataverse MCP URL と `DATAVERSE_OPERATION_CONTEXT`。
- Azure CLI と Dataverse CLI の対話認証キャッシュ、Power Platform 管理センターの MCP クライアント許可。

### 対象外

- FlowStudio の導入。
- 本番環境への接続、認証、書込み、フロー公開。
- DecisionFlow アプリの機能・スキーマ・既存フロー定義の変更。
- Power CAT の実行エンジンまたは独自の Dataverse/FlowAgent 実装。

## 導入順序と検証

1. Codex の公式プラグイン導入可否を、Power Automate と Dataverse で確認する。
2. PAC MCP をプロジェクト設定から起動できることを確認する。
3. Codex を再起動し、FlowAgent、PAC、Dataverse の各ツールが検出されることを確認する。
4. 開発者が開発環境を選択して対話認証と Power Platform 側のクライアント許可を完了する。
5. 読取りだけのフロー一覧・Dataverse テーブル一覧で、認証、到達性、環境選択を確認する。
6. 新規フロー作成の実地確認が必要な場合は、専用の停止状態フローを対象と影響を明示して別途承認後に行う。

機械的な合格条件は、(a) `codex plugin list` と `codex mcp list` が設定を示すこと、(b) 追跡ファイルに
環境 URL、トークン、API キー、認証ヘッダーがないこと、(c) 専用の設定テストが通ること、(d)
`git diff --check` が通ることである。認証と Power Platform テナントの許可は人による確認を必要とする。

## 残るリスク

- FlowAgent の公式配布面は Claude Code／GitHub Copilot CLI が中心である。Codex のマーケットプレース
  導入が失敗した場合、独自アダプターは別途レビュー対象となる。
- Dataverse MCP はツール上は書込み能力を持つ。誤操作を完全に防ぐには、開発環境と Dataverse ロールを
  最小権限にする必要がある。
- プラグインと MCP の追加は Codex の再起動後に初めて検出できる。導入直後に実利用可能と断定しない。
