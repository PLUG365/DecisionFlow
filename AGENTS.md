# DecisionFlow Repository Guidance

## AI 開発ツール

Power Platform、Dataverse、Power Automate、Code Apps、Solution に関わる作業の前に、
[`docs/AI_DEVELOPMENT_TOOLING.md`](docs/AI_DEVELOPMENT_TOOLING.md) を読む。

DecisionFlow Assistant に書き込み系のツールを追加・変更する前に、
[`docs/AGENT_WRITE_BOUNDARY.md`](docs/AGENT_WRITE_BOUNDARY.md) を読む。許可・禁止・不変条件を
固定した表であり、**表を変更せずにツールを追加してはならない**。特に、実行者の識別子は
Copilot Studio の認証済みユーザー変数からのみ渡す（会話本文やモデルの推論から組み立てない）。

- FlowStudio はこのリポジトリの開発・設定・依存関係に含めない。
- AI 開発は「探索・試作」と「採用・運用」の二レーンで行う。探索・試作では、開発環境の
  新規かつ一時的な資産を MCP / AI スキルで作成・編集・検証してよい。採用・運用に昇格する
  変更は、Git 管理された正本（Python スクリプト、Solution、YAML、または版管理された
  Canvas 成果物）へ反映し、差分レビュー後に適用する。
- Dataverse MCP はメタデータと読取りクエリを既定とする。探索・試作での開発環境の新規・
  一時的なデータまたはスキーマ変更は、対象と復元方法を示して行える。既存の管理対象の変更、
  削除、セキュリティ変更、環境変更、Solution の import / publish は、対象と影響を示した
  明示承認後だけ実行する。
- 公式 Power Automate プラグインで生成した探索用の新規フローは、開発環境で停止状態に作成する。
  `validate_flow` / `preflight_flow` と接続参照のレビュー後、明示承認を得て有効化する。
- Codex で FlowAgent または Dataverse specialist skills を使うときは、Microsoft 公式
  `power-automate@power-platform-skills` と `dataverse@dataverse-skills` が開発者プロファイルで
  有効であることを先に確認する。
- 既存の DecisionFlow フローと Python デプロイスクリプトは採用・運用の正本として扱う。AI の
  生成結果で既存フローを直接削除・置換・公開せず、採用する試作はレビュー済みの再現可能な
  ソース変更へ昇格させる。
