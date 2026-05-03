# DecisionFlow

DecisionFlow は、申請者が判断者へ意思決定を依頼し、会話・関連資料・判断結果・AI 判断を Dataverse 上で一元管理する Power Apps Code Apps アプリです。

現在の主な構成:

- Code Apps: ダッシュボード、申請リスト、判断キュー、申請詳細、メンション、関連資料、マスタ管理
- Dataverse: `ds_application`, `ds_message`, `ds_mention`, `ds_participant`, `ds_decision`, `ds_applicationresource`, `ds_category`, `ds_decisionoption`
- Power Automate: 通知、停滞リマインド、関係者共有/共有解除、AI 判断生成
- AI Builder: `DecisionRecommendation` による申請概要・会話概要・推奨判断・コメント生成

## 現在の状態

- ソリューション: `DecisionSupport`
- パブリッシャープレフィックス: `ds`
- AI 判断フロー: `Application_GenerateAiDecision`
- AI Builder プロンプト: `DecisionRecommendation`
- Copilot Studio エージェント: Phase 3 予定。2026-05-03 時点では未構築

実装状況と未完了事項は [docs/DESIGN_DRAFT.md](docs/DESIGN_DRAFT.md)、[docs/CODE_APPS_UI_DESIGN.md](docs/CODE_APPS_UI_DESIGN.md)、[docs/BACKLOG.md](docs/BACKLOG.md) を正とします。

## セットアップ概要

`.env` には環境固有値を置き、Git には含めません。値は Power Apps ポータルのセッション詳細から取得します。

必須値:

```env
DATAVERSE_URL=https://{your-org}.crm.dynamics.com/
TENANT_ID=00000000-0000-0000-0000-000000000000
ENVIRONMENT_ID=00000000-0000-0000-0000-000000000000
SOLUTION_NAME=DecisionSupport
PUBLISHER_PREFIX=ds
PAC_AUTH_PROFILE=DecisionSupportProfile
```

主要コマンド:

```powershell
npm install
py scripts/setup_dataverse.py
py scripts/setup_security_roles.py
py scripts/deploy_access_flows.py
py scripts/deploy_notification_flows.py
py scripts/deploy_ai_decision.py
npm run build
npx power-apps push
```

Power Apps Code Apps の初期化やデータソース追加が必要な場合は、[docs/CODE_APPS_UI_DESIGN.md](docs/CODE_APPS_UI_DESIGN.md) のデプロイ計画を参照してください。既存の `Application_GenerateAiDecision` フロー ID が変わらない再デプロイでは、`npx power-apps add-flow` の再実行は不要です。

## 検証

よく使う検証コマンド:

```powershell
npm test -- src/lib/decisionflow-utils.test.ts src/lib/ai-decision.test.ts
py -m unittest tests.test_ai_decision tests.test_notification_flows tests.test_access_flows tests.test_security_roles
npm run build
```

直近の検証では、上記 Python unittest は成功済みです。Power Apps 実機での Submitted 保存時 AI 判断生成、通知配信、関係者共有/共有解除は [docs/BACKLOG.md](docs/BACKLOG.md) の Open 項目として追跡しています。

## 主要ドキュメント

- [docs/DESIGN_DRAFT.md](docs/DESIGN_DRAFT.md): 全体設計、データモデル、Power Automate、AI/Copilot 方針
- [docs/CODE_APPS_UI_DESIGN.md](docs/CODE_APPS_UI_DESIGN.md): Code Apps 画面、Hooks、サービス層、UI 実装状況
- [docs/BACKLOG.md](docs/BACKLOG.md): 未完了タスク、実機確認、完了履歴
- [docs/MIGRATIONS.md](docs/MIGRATIONS.md): Dataverse メタデータ変更と適用履歴
- [docs/POWER_PLATFORM_DEVELOPMENT_STANDARD.md](docs/POWER_PLATFORM_DEVELOPMENT_STANDARD.md): Power Platform コードファースト開発標準
- [docs/DATAVERSE_GUIDE.md](docs/DATAVERSE_GUIDE.md): Dataverse 実装ガイド

## 注意事項

- `.env`, `.auth_record.json`, `power.config.json`, `.power/`, `src/generated/` は環境固有情報を含むため Git 管理しません。
- Dataverse 接続は環境内に事前作成が必要です。スクリプトは接続候補を検索し、接続参照を更新します。
- `DecisionFlow-Deciders` の Dataverse グループチーム紐付けと `ds_Decider` ロール付与は、Power Platform 管理センターで手動実施します。
- Copilot Studio エージェントはまだ未構築です。構築時は設計提示と承認を経て Phase 3 として進めます。

## ライセンス

MIT License。詳細は [LICENSE](LICENSE) を参照してください。
