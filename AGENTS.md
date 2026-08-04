# DecisionFlow Repository Guidance

## AI 開発ツール

Power Platform、Dataverse、Power Automate、Code Apps、Solution に関わる作業の前に、
[`docs/AI_DEVELOPMENT_TOOLING.md`](docs/AI_DEVELOPMENT_TOOLING.md) を読む。

- FlowStudio はこのリポジトリの開発・設定・依存関係に含めない。
- Dataverse MCP はメタデータと読取りクエリを既定とする。書込み、削除、セキュリティ変更、
  環境変更、Solution の import / publish は、対象と影響を示した明示承認後だけ実行する。
- 公式 Power Automate プラグインで生成したフローは、開発環境で停止状態に作成する。
  `validate_flow` / `preflight_flow` と接続参照のレビュー後、明示承認を得て有効化する。
- Codex で FlowAgent または Dataverse specialist skills を使うときは、Microsoft 公式
  `power-automate@power-platform-skills` と `dataverse@dataverse-skills` が開発者プロファイルで
  有効であることを先に確認する。
- 既存の DecisionFlow フローと Python デプロイスクリプトを正本として扱う。AI の生成結果で
  既存フローを直接削除・置換・公開せず、レビュー済みの再現可能なソース変更へ反映する。
