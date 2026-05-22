# DecisionFlow プロジェクト計画

> **ステータス**: IMPLEMENTATION（カテゴリ別レギュレーションAIチェック環境反映済み / ユーザー実機検証待ち）
> **最終更新**: 2026-05-23
> **次フェーズ**: 追加の本番化 hardening（厳密ロック、運用監視、補正手順）

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

<!-- markdownlint-disable MD060 -->

| Phase | 内容                     | 成果物                                                                 | 状況   |
| ----- | ------------------------ | ---------------------------------------------------------------------- | ------ |
| 0     | アーキテクチャ設計       | ARCHITECTURE.md                                                        | ✅完了 |
| 1     | Dataverse 構築           | テーブル / リレーション / マスタ / デモデータ                          | ✅完了 |
| 1.5   | セキュリティロール構築   | `ds_Applicant` / `ds_Decider` / `ds_Admin` + M365 グループチーム紐付け | ✅完了 |
| 2     | Code Apps（設計 → 実装） | 7 画面 + Dataverse 接続 + 主要フォーム/マスタ永続化                    | ✅完了 |
| 2.5   | Power Automate           | 7 フロー（アクセス制御フロー含む）                                     | ✅完了 |
| 3     | Copilot Studio           | DecisionFlow Assistant                                                 | ✅完了 |
| 4     | AI Builder               | `DecisionRecommendation`（実装済み）+ 追加プロンプト検討               | ✅完了 |
| 5     | Adaptive Card 判断確定   | 専用 Topic + agent flow 2 本 + `ds_decisioncard`                       | 実装中 |

<!-- markdownlint-enable MD060 -->

---

## 3. 実装状況チェックリスト

### Phase 2: Code Apps

- [x] 申請作成/編集
- [x] 申請者が選べる下書き/提出ステージのラジオ選択
- [x] 提出時に判断者未選択の申請保存を禁止
- [x] 提出済み申請の通常編集を禁止し、下書きに戻す操作だけ許可
- [x] 判断確定時の判断済み自動更新
- [x] 申請削除（確認モーダル付き）
- [x] 申請作成時の申請者/判断者 `ds_participant` 自動登録
- [x] 申請詳細からの関係者追加
- [x] 申請詳細からの関係者削除（確認モーダル付き）
- [x] 申請詳細の会話タブからコメント投稿時にメンション作成
- [x] 判断タブに AI 判断カードを追加し、申請概要・会話概要・推奨判断・コメント・リスク・類似案件を表示
- [x] Submitted 保存時と判断タブの「AI判断更新」から `Application_GenerateAiDecision` を起動
- [x] 申請提出時はいったん Draft 保存し、AI判断確認後に `本提出` または `下書き維持` を選択する
- [x] 申請作成/詳細画面で選択カテゴリのレギュレーションを申請者・判断者が読取りできる
- [x] 関連資料リンク追加
- [x] 関連資料リンクの確認付き削除
- [x] マスタ追加/更新
- [x] カテゴリマスタで `ds_regulationtext` を編集できる（`ds_Admin` / `ds_Decider`）
- [x] 申請者本人向けの編集操作表示
- [x] Choice フィルタ
- [x] Power Apps 実機で SDK postMessage、リンク登録、申請削除、関係者追加/削除、セキュリティロールの動作を確認する

### Phase 2.5: Power Automate

- [x] `Application_OnSubmitted` を設計・実装する
- [x] `Application_StalledReminder` を設計・実装する
- [x] `Decision_OnCreated` を設計・実装する
- [x] `Mention_OnCreated` を設計・実装する
- [x] `Application_GenerateAiDecision` を設計・実装する
- [x] `Application_GenerateAiDecision` はカテゴリ別レギュレーションを prompt 入力へ追加し、既存AI列のみを最新結果として更新する
- [x] `Participant_OnCreated_GrantAccess` を設計・実装する
- [x] `Participant_PreDelete_RevokeAccess` を設計・実装する
- [x] `Decision_OnCreated` で判断結果 `ds_decision` を申請者・関係者へ読取り共有し、`ds_Decider` は判断結果を全体閲覧できるようにする
- [x] `ds_application` から関連資料・会話履歴・判断結果などの子レコードへ Cascade Share/Unshare を適用し、既存関係者分の申請共有を再付与する
- [x] 関係者追加後に、申請者/判断者以外の関係者が対象申請を閲覧できることを実機確認する
- [x] 関係者削除後に、対象ユーザーの申請閲覧権限が除外されることを実機確認する

### Phase 3: Copilot Studio

- [x] Copilot Studio UI で `DecisionFlow Assistant` を手動作成する
- [x] `py scripts/deploy_copilot_agent.py` を実行し、生成オーケストレーション・Instructions・推奨プロンプト・アイコン・チャネル設定を適用する
- [x] Copilot Studio UI で認証を Microsoft Entra ID ユーザー認証に設定する
- [x] Copilot Studio UI で Dataverse ナレッジを追加する
- [x] Teams チャネルを利用可能にし、`botChannelRegistrationAppId` を確認する
- [x] `py scripts/deploy_notification_flows.py` で Outlook メール内リンク用のソリューション環境変数を作成し、環境ごとに設定可能にする
- [x] `py scripts/deploy_application_link_flow.py` で `Get_ApplicationDetailUrl` agent flow を `Skills` トリガーで作成・有効化し、Copilot Studio UI でエージェントツールとして登録する。エージェントは固定 URL を埋め込まず、このツール経由で `ds_DecisionFlowAppBaseUrl` を実行時解決して申請詳細リンクを案内する

### Phase 5: Adaptive Card 判断確定

- [x] `ds_decisioncard` テーブル定義を追加する
- [x] `ds_decisioncard` のセキュリティロール権限を追加する
- [x] Code Apps の `createDecision` は画面の即時反映のため `ds_application.ds_stage` を同じ操作内で更新し、通知・最終整合・判断結果共有は `Decision_OnCreated` に任せる
- [x] `Decision_OnCreated` で判断選択肢から `ds_application.ds_stage` を導出し、`差し戻し` の場合だけ `ds_submittedat` をクリアする
- [x] Adaptive Card submit 用の `confirm_decision` flow definition builder を追加し、`ds_decision` 作成と `ds_decisioncard` 消費を定義する
- [x] Adaptive Card 発行用の `issue_decision_card` flow definition builder を追加し、`cardInstanceId` を返す定義を追加する
- [x] Copilot Studio は Generative Orchestration を維持し、専用 Adaptive Card Topic でカード表示・submit 受信を扱う方針を記録する
- [x] 対象環境へ `ds_decisioncard` metadata、security role、`Decision_OnCreated` 更新済み通知フローを反映する
- [x] `deploy_adaptive_card_decision_confirmation.py` で `issue_decision_card` / `confirm_decision` agent flow 2 本を `Skills` トリガー/レスポンスで作成・有効化・Flow API start する
- [x] Copilot Studio UI で作成済み Power Automate agent flow 2 本をツールとして追加し、専用 Topic を YAML テンプレートから作成して Teams チャネルで実機確認する
- [x] US2: 未割り当てユーザー、古いカード、再利用カード、無効入力を拒否する詳細 validation を実装する
- [x] US3: Code Apps の判断作成直後に `ds_application` を即時更新し、画面更新後にステージが変わって見えるようにする

### Phase 5 手動操作メモ

- 手順書: [specs/001-confirm-adaptive-card/quickstart.md](../specs/001-confirm-adaptive-card/quickstart.md)
- Copilot Studio UI で作成済みの `issue_decision_card` / `confirm_decision` Power Automate agent flow をツールとして追加し、専用 Topic は [specs/001-confirm-adaptive-card/decision-confirmation.topic.template.yaml](../specs/001-confirm-adaptive-card/decision-confirmation.topic.template.yaml) をコードビューに貼って作成する
- Adaptive Card JSON は Topic 側で保持し、schema 1.5 + `Action.Submit` を使う
- Teams 実機確認と T061 完了反映は完了済み

---

## 4. 確定済み事項

- ✅ セキュリティ方針: ロール（判断者の全体閲覧権）× Share API（申請者・関係者の案件単位閲覧）のハイブリッド
- ✅ 判断者の管理: **M365 グループ** + Dataverse グループチーム経由でロール付与
- ✅ 申請者の閲覧範囲: **自分の申請のみ**（関係者追加時のみ案件単位で拡張。メンションは通知・既読管理のみで閲覧権を拡張しない）
- ✅ ソリューション名・プレフィックス: `DecisionSupport` / `ds`
- ✅ カテゴリ初期マスタ: 顧客案件 / 部内案件 / 課内案件 / 他部署案件 / 事務処理。各カテゴリにデモ用レギュレーション初期値も補完する
- ✅ 判断選択肢: 承認 / 却下 / 差し戻し（固定システムマスタ。フロー・Copilot Studio・Adaptive Card が名称で参照するため追加・名称変更・削除しない）
- ✅ ソリューション配布時の注意: 通常のソリューションZipには `ds_category` / `ds_decisionoption` の行データは含まれないため、Code Apps 初回起動時に初期カテゴリと固定判断選択肢を自動補完する
- ✅ 判断確定の正本イベント: `ds_decision` 作成
- ✅ 案件ステージ整合: `Decision_OnCreated` が `ds_decisionoption` から導出して更新
- ✅ Adaptive Card 表示 JSON: Copilot Studio 専用 Topic 側で管理。Power Automate はカード表示 JSON を所有しない
- ✅ Adaptive Card submit: schema 1.5 + `Action.Submit` を使用し、`Action.Execute` は MVP では使わない
- ✅ Code Apps: `createDecision` は `ds_decision` 作成後、利用者に結果がすぐ分かるよう `ds_application.ds_stage` も即時更新する。`Decision_OnCreated` は通知・最終整合・判断結果共有を担当する
- ✅ first-write-wins MVP: lookup-then-insert で現在提出サイクル内の既存判断を確認し、差し戻し後の再提出では再判断できる。厳密な同時実行制御は ETag / optimistic concurrency を将来検討
- ✅ 停滞リマインド閾値: 3 営業日（`ds_submittedat` 基準）
- ✅ AI 判断生成方針: Submitted 保存時に自動生成し、判断タブの「AI判断更新」から同じフローを手動再実行できる
- ✅ カテゴリ別レギュレーション: `ds_category.ds_regulationtext` に1カテゴリ1文章で保持し、申請者の提出前確認と判断者向けAI判断に利用する。履歴テーブルやレギュレーション本文スナップショットは作成しない
- ✅ 提出確認フロー: 申請者の提出操作は Draft 保存 → AI判断 → `本提出` / `下書き維持` の確認を経て、`本提出` のときだけ `ds_stage=Submitted` と `ds_submittedat` を設定する
- ✅ AI 判断の入力: 初回提出時も類似過去案件を検索対象にし、会話履歴は存在する分だけ使用する
- ✅ 会話自動要約: 会話ログが一定数たまったら要約するバッチは実装しない
- ✅ M365 グループ名: `DecisionFlow-Deciders`

---

## 5. GitHub 公開方針

### 5.1 シークレット管理

| 項目                         | 扱い                | 備考                                                                                 |
| ---------------------------- | ------------------- | ------------------------------------------------------------------------------------ |
| `.env`                       | ❌ コミット禁止     | `.gitignore` に追加。`DATAVERSE_URL`, `TENANT_ID` 等を含む                           |
| `.env.example`               | ✅ コミット         | キー名のみ記載・値は空 or プレースホルダー                                           |
| `.auth_record.json`          | ❌ コミット禁止     | Azure Identity の認証キャッシュ（個人情報相当）                                      |
| `power.config.json`          | ❌ コミット禁止     | テナント固有の `appId`・`environmentId` を含む                                       |
| `src/generated/`             | ❌ コミット禁止     | テーブル GUID・環境固有値を含む可能性。`add-data-source` で再生成                    |
| `.power/`                    | ❌ コミット禁止     | `dataSourcesInfo.ts` 等の SDK 生成物。`add-data-source` で再生成                     |
| ソリューション ZIP           | ❌ コミット禁止     | Managed Solution は Release Assets として配布。作業用置き場は `artifacts/solutions/` |
| Copilot Studio Bot ID        | △ 環境変数化        | `.env` の `BOT_ID` で管理                                                            |
| 接続 ID（Power Automate）    | ❌ ハードコード禁止 | スクリプトで毎回検索                                                                 |
| アイコン PNG/SVG             | ✅ 公開可           | `assets/` に配置                                                                     |
| スクリプト・設計ドキュメント | ✅ 公開可           | テナント固有値を埋め込まない                                                         |

### 5.2 公開チェックリスト

- [x] `.gitignore` 整備
- [x] `.env.example` を作成（キー名のみ）
- [x] README にセットアップ手順を記載
- [x] スクリプト・コードにテナント ID / ユーザー ID / メールアドレスがハードコードされていないか確認
- [x] デモデータの個人情報・社内固有名詞を `example.com` / 架空名に置換
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
# 通知メールのリンクは .env ではなく、ソリューション環境変数で設定する:
# ds_DecisionFlowAppBaseUrl / ds_CopilotTeamsAppId

# ===== Copilot Studio =====
# エージェント作成後に設定
BOT_ID=

# ===== セキュリティロール =====
# Dataverse グループチーム紐付けは Power Platform 管理センターで手動実施
DECIDER_GROUP_NAME=DecisionFlow-Deciders
```
