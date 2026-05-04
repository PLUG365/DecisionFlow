# DecisionFlow プロジェクト計画

> **ステータス**: IMPLEMENTATION（Phase 2.5 実装・実機確認済み / Phase 3 Copilot Studio 実機確認済み）
> **最終更新**: 2026-05-04
> **次フェーズ**: 必要に応じて Teams 利用者展開 / 複数名判断者運用のグループチーム設定

---

## 1. プロジェクト概要

### 1.1 背景・課題

申請者が判断者に意思決定を依頼するプロセスにおいて、以下の課題がある:

- **申請者**: 入力負荷が大きい / 案件が停滞しても気づけない / 判断理由が不透明
- **判断者**: 申請フォーマットがバラバラで読みにくい / 過去判断との一貫性が取りにくい / 案件が属人化し負荷が偏る / 全件を熟読する時間がない
- **両者共通**: 関係者を巻き込んだ会話が散在し、後から追えない

### 1.2 ゴール

意思決定を **迅速・的確・納得感のある** プロセスにする統合プラットフォーム **「DecisionFlow」** を構築する。

| ステークホルダー | メリット                                                                             |
| ---------------- | ------------------------------------------------------------------------------------ |
| 申請者           | 停滞日数の可視化 / 自動フォロー / 判断理由の明確化                                   |
| 判断者           | フォーマット化された申請 / 過去履歴の参照 / 負荷平準化 / AI による論点要約と推奨判断 |
| 関係者           | 必要な議論にだけ参加 / メンション通知で見逃さない                                    |
| 経営・管理者     | 判断者別の負荷比較 / 意思決定スループット可視化                                      |

### 1.3 システム名

| 項目                         | 値                              |
| ---------------------------- | ------------------------------- |
| プロダクト名                 | DecisionFlow                    |
| ソリューション表示名         | 意思決定支援 (Decision Support) |
| ソリューション一意名         | `DecisionSupport`               |
| パブリッシャープレフィックス | `ds`                            |

---

## 2. 開発フェーズ

| Phase | 内容                     | 成果物                                                                 | 状況   |
| ----- | ------------------------ | ---------------------------------------------------------------------- | ------ |
| 0     | アーキテクチャ設計       | ARCHITECTURE.md                                                        | ✅完了 |
| 1     | Dataverse 構築           | テーブル / リレーション / マスタ / デモデータ                          | ✅完了 |
| 1.5   | セキュリティロール構築   | `ds_Applicant` / `ds_Decider` / `ds_Admin` + M365 グループチーム紐付け | ✅完了 |
| 2     | Code Apps（設計 → 実装） | 7 画面 + Dataverse 接続 + 主要フォーム/マスタ永続化                    | ✅完了 |
| 2.5   | Power Automate           | 7 フロー（アクセス制御フロー含む）                                     | ✅完了 |
| 3     | Copilot Studio           | DecisionFlow Assistant                                                 | ✅完了 |
| 4     | AI Builder               | `DecisionRecommendation`（実装済み）+ 追加プロンプト検討               | ✅完了 |

---

## 3. 実装状況チェックリスト

### Phase 2: Code Apps

- [x] 申請作成/編集
- [x] 申請者が選べる下書き/提出ステージのラジオ選択
- [x] 提出済み申請の通常編集を禁止し、下書きに戻す操作だけ許可
- [x] 判断確定時の判断済み自動更新
- [x] 申請削除（確認モーダル付き）
- [x] 申請作成時の申請者/判断者 `ds_participant` 自動登録
- [x] 申請詳細からの関係者追加
- [x] 申請詳細からの関係者削除（確認モーダル付き）
- [x] 申請詳細の会話タブからコメント投稿時にメンション作成
- [x] 判断タブに AI 判断カードを追加し、申請概要・会話概要・推奨判断・コメント・リスク・類似案件を表示
- [x] Submitted 保存時と判断タブの「AI判断更新」から `Application_GenerateAiDecision` を起動
- [x] 関連資料リンク追加
- [x] 関連資料リンクの確認付き削除
- [x] マスタ追加/更新
- [x] 申請者本人向けの編集操作表示
- [x] Choice フィルタ
- [ ] Power Apps 実機で SDK postMessage、リンク登録、申請削除、関係者追加/削除、セキュリティロールの動作を確認する

### Phase 2.5: Power Automate

- [x] `Application_OnSubmitted` を設計・実装する
- [x] `Application_StalledReminder` を設計・実装する
- [x] `Decision_OnCreated` を設計・実装する
- [x] `Mention_OnCreated` を設計・実装する
- [x] `Application_GenerateAiDecision` を設計・実装する
- [x] `Participant_OnCreated_GrantAccess` を設計・実装する
- [x] `Participant_PreDelete_RevokeAccess` を設計・実装する
- [ ] 関係者追加後に、申請者/判断者以外の関係者が対象申請を閲覧できることを実機確認する
- [ ] 関係者削除後に、対象ユーザーの申請閲覧権限が除外されることを実機確認する

### Phase 3: Copilot Studio

- [x] Copilot Studio UI で `DecisionFlow Assistant` を手動作成する
- [x] `py scripts/deploy_copilot_agent.py` を実行し、生成オーケストレーション・Instructions・推奨プロンプト・アイコン・チャネル設定を適用する
- [x] Copilot Studio UI で認証を Microsoft Entra ID ユーザー認証に設定する
- [x] Copilot Studio UI で Dataverse ナレッジを追加する
- [x] Teams チャネルを利用可能にし、`botChannelRegistrationAppId` を `.env` の `COPILOT_TEAMS_APP_ID` に設定する
- [x] `py scripts/deploy_notification_flows.py` を再実行し、Outlook メール内のエージェント相談リンクを有効化する

---

## 4. 確定済み事項

- ✅ セキュリティ方針: ロール（全体閲覧権）× テーブル（案件参加）のハイブリッド
- ✅ 判断者の管理: **M365 グループ** + Dataverse グループチーム経由でロール付与
- ✅ 申請者の閲覧範囲: **自分の申請のみ**（メンション / 関係者追加時のみ拡張）
- ✅ ソリューション名・プレフィックス: `DecisionSupport` / `ds`
- ✅ カテゴリ初期マスタ: 顧客案件 / 部内案件 / 課内案件 / 他部署案件 / 事務処理
- ✅ 判断選択肢: 承認 / 却下 / 差し戻し
- ✅ 停滞リマインド閾値: 3 営業日（`ds_submittedat` 基準）
- ✅ AI 判断生成方針: Submitted 保存時に自動生成し、判断タブの「AI判断更新」から同じフローを手動再実行できる
- ✅ AI 判断の入力: 初回提出時も類似過去案件を検索対象にし、会話履歴は存在する分だけ使用する
- ✅ 会話自動要約: 会話ログが一定数たまったら要約するバッチは実装しない
- ✅ M365 グループ名: `DecisionFlow-Deciders`

---

## 5. GitHub 公開方針

### 5.1 シークレット管理

| 項目                         | 扱い                | 備考                                                              |
| ---------------------------- | ------------------- | ----------------------------------------------------------------- |
| `.env`                       | ❌ コミット禁止     | `.gitignore` に追加。`DATAVERSE_URL`, `TENANT_ID` 等を含む        |
| `.env.example`               | ✅ コミット         | キー名のみ記載・値は空 or プレースホルダー                        |
| `.auth_record.json`          | ❌ コミット禁止     | Azure Identity の認証キャッシュ（個人情報相当）                   |
| `power.config.json`          | ❌ コミット禁止     | テナント固有の `appId`・`environmentId` を含む                    |
| `src/generated/`             | ❌ コミット禁止     | テーブル GUID・環境固有値を含む可能性。`add-data-source` で再生成 |
| `.power/`                    | ❌ コミット禁止     | `dataSourcesInfo.ts` 等の SDK 生成物。`add-data-source` で再生成  |
| ソリューション ZIP           | ❌ コミット禁止     | Managed Solution は Release Assets として配布                     |
| Copilot Studio Bot ID        | △ 環境変数化        | `.env` の `BOT_ID` で管理                                         |
| 接続 ID（Power Automate）    | ❌ ハードコード禁止 | スクリプトで毎回検索                                              |
| アイコン PNG/SVG             | ✅ 公開可           | `assets/` に配置                                                  |
| スクリプト・設計ドキュメント | ✅ 公開可           | テナント固有値を埋め込まない                                      |

### 5.2 公開チェックリスト

- [ ] `.gitignore` 整備
- [ ] `.env.example` を作成（キー名のみ）
- [ ] README にセットアップ手順を記載
- [ ] スクリプト・コードにテナント ID / ユーザー ID / メールアドレスがハードコードされていないか確認
- [ ] デモデータの個人情報・社内固有名詞を `example.com` / 架空名に置換
- [ ] `git secrets` または GitHub の Push Protection でシークレット流出を防止
- [ ] 過去コミットに機密情報が含まれていないか確認
- [ ] LICENSE を明記（MIT）

### 5.3 テンプレートファイル方針

コミット禁止ファイルのうち、**`.example` を用意するのは `.env` のみ**。他は SDK / CLI が自動生成するため `.example` は作らない。

`.env.example` の構成:

```env
# ===== 必須（全フェーズ共通）=====
# Power Apps ポータル > 設定（右上の⚙）> セッション詳細 から取得
DATAVERSE_URL=https://{your-org}.crm.dynamics.com/
TENANT_ID=00000000-0000-0000-0000-000000000000
ENVIRONMENT_ID=00000000-0000-0000-0000-000000000000

# ===== ソリューション =====
SOLUTION_NAME=DecisionSupport
PUBLISHER_PREFIX=ds

# ===== Code Apps =====
PAC_AUTH_PROFILE=DecisionSupportProfile
COPILOT_TEAMS_APP_ID=
COPILOT_TEAMS_TITLE_ID=

# ===== Copilot Studio =====
# エージェント作成後に設定
BOT_ID=

# ===== セキュリティロール =====
# Dataverse グループチーム紐付けは Power Platform 管理センターで手動実施
DECIDER_GROUP_NAME=DecisionFlow-Deciders
```
