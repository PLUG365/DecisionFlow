# DecisionFlow Migrations

> 最終更新: 2026-05-19

## 2026-05-19 Adaptive Card 判断確定 MVP

### 目的

Copilot Studio チャット上の Adaptive Card submit から判断確定できるようにし、Code Apps と Copilot Studio の判断確定結果を同じ `Decision_OnCreated` 整合フローへ集約する。

### Dataverse metadata changes

- `ds_decisioncard` テーブルを追加
- `ds_decisioncard` は `ds_application` への Lookup `ds_applicationid` を持つ
- `ds_decisioncard` の主要列:
  - `ds_cardinstanceid`
  - `ds_actoraadobjectid`
  - `ds_actorupn`
  - `ds_status`
  - `ds_issuedat`
  - `ds_consumedat`
  - `ds_supersededat`
- `ds_status` choice values:
  - `100000000`: `Issued`
  - `100000001`: `Consumed`
  - `100000002`: `Superseded`
  - `100000003`: `Expired`

### Security role changes

- `ds_Applicant`: `ds_decisioncard` Basic Read のみ
- `ds_Decider`: `ds_decisioncard` Basic Create / Read / Write / Append / AppendTo / Share
- `ds_Admin`: `ds_decisioncard` Global full privileges

### Flow changes

- `Decision_OnCreated` が `ds_decisionoption.ds_name` から次ステージを導出する
- `差し戻し` は `Draft` (`100000000`) へ戻し、`ds_submittedat` をクリアする
- `承認` と `却下` は `Decided` (`100000004`) へ更新する
- 通知は案件ステージ整合後に実行する

### Code Apps changes

- `DataverseService.createDecision()` は `ds_decision` 作成だけを行う
- `ds_application` の直接更新は削除し、`Decision_OnCreated` に委譲する
- 500ms / 最大 3 秒の reconciliation polling 定数は追加済み。UI polling 実装は US3 で対応する

### Copilot Studio / Power Automate changes

- Adaptive Card JSON は Copilot Studio 専用 Topic 側で管理する
- Power Automate 側は、Copilot Studio からツールとして呼ぶ `issue_decision_card` と `confirm_decision` フローを提供する
- `issue_decision_card` は `ds_decisioncard` を `Issued` として作成し、`cardInstanceId` を返す
- `confirm_decision` は submit payload を検証し、`ds_decision` 作成後に `ds_decisioncard` を `Consumed` に更新する
- submit action は `ds_application` を直接更新しない

### Apply steps

1. `.env` に `DATAVERSE_URL`, `TENANT_ID`, `ENVIRONMENT_ID`, `SOLUTION_NAME=DecisionSupport`, `PUBLISHER_PREFIX=ds`, `BOT_ID` を設定する
2. `python scripts/setup_dataverse.py` を実行し、`ds_decisioncard` を含む Dataverse metadata を適用する
3. `python scripts/setup_security_roles.py` を実行し、`ds_decisioncard` privileges を適用する
4. `python scripts/deploy_notification_flows.py` を実行し、`Decision_OnCreated` の案件ステージ整合を適用する
5. `python scripts/deploy_adaptive_card_decision_confirmation.py` で `issue_decision_card` / `confirm_decision` ツールフロー 2 本を作成・有効化する
6. Copilot Studio 側に専用 Topic を作成し、作成済み Power Automate ツールフローをツールとして追加する
7. Copilot Studio UI で schema 1.5 / `Action.Submit` の Adaptive Card を専用 Topic に設定する
8. Teams チャネルで quickstart の正常系・入力検証・再利用カード拒否シナリオを確認する

### Validation result

- Python unit tests: `tests.test_adaptive_card_decision_confirmation tests.test_copilot_agent tests.test_notification_flows tests.test_security_roles` passed on 2026-05-19
- Code Apps unit tests: `npm test` passed on 2026-05-19
- Production build: `npm run build` passed on 2026-05-19
- Environment deployment: `setup_dataverse.py`, `setup_security_roles.py`, and `deploy_notification_flows.py` completed on 2026-05-19
- Adaptive Card agent flow deployment: `issue_decision_card` (`c37ed747-9153-f111-a824-3833c5de99c8`) and `confirm_decision` (`f8502159-9153-f111-a824-3833c5de99c8`) created with `Skills` trigger/response, activated, and Flow API started on 2026-05-19. `confirm_decision` accepts `decisionOption` labels (`承認` / `却下` / `差し戻し`) and resolves `ds_decisionoption` by `ds_name`; validation guards use Power Automate Condition actions with designer-friendly expression objects.
- Manual Copilot Studio Topic/tool wiring and Teams channel validation: pending

### Rollback notes

- まず Copilot Studio の判断確定 Topic / Power Automate ツールフローを無効化する
- `Decision_OnCreated` を無効化すると、Code Apps 由来の判断でも案件ステージが更新されないため、無効化中の判断確定は手動補正が必要
- `ds_decisioncard` は監査用の発行・消費履歴を含むため、rollback では原則削除せず無効化で止める
- 誤確定が発生した場合は `ds_decision` と `ds_application` の補正内容を本ファイルまたは運用記録へ残す

## 2026-05-09: 関係者ロールの簡素化と閲覧範囲の修正

Status: Applied 2026-05-09 / **既存環境のアップグレード時のみ実行**

> 新規セットアップ環境では `setup_dataverse.py` が最初から 3 ロールのみ・Cascade Share 付きで作成するため、本マイグレーションは不要。

### 背景（ロール簡素化 + Cascade Share）

関係者の役割を「申請者 / 判断者 / 関係者」の3種に簡素化した。`CoDecider`(共同判断者) と `Observer`(オブザーバー) は使われていなかったため廃止。関係者タブから追加するときは役割選択 UI を排除し、常に Contributor (関係者) として登録する。

また、関係者として共有された申請の子レコード（他の関係者・資料・コメント等）が見えない不具合を修正するため、`ds_application` から子テーブルへのリレーションシップに `Cascade Share` を設定した。

### 対象（ロール簡素化 + Cascade Share）

- `ds_participant.ds_role` の Choice 値
  - `100000002` CoDecider 削除
  - `100000004` Observer 削除
- リレーションシップの Cascade 設定変更（Share / Unshare → Cascade）
  - `ds_participant_ds_application`
  - `ds_message_ds_application`
  - `ds_decision_ds_application`
  - `ds_applicationresource_ds_application`
  - `ds_mention_ds_message`（連鎖用）

### 実行手順（ロール簡素化 + Cascade Share）

```powershell
py scripts/migrate_remove_unused_roles.py
py scripts/migrate_cascade_share.py
```

### 注意（ロール簡素化 + Cascade Share）

- `migrate_remove_unused_roles.py` は CoDecider/Observer の既存レコードを Contributor に変換してから Choice 値を削除する。
- `migrate_cascade_share.py` 適用後、既存の申請レコードと既に追加済みの関係者については、Code Apps で関係者を一度削除→再追加するか、Power Automate UI で `Participant_OnCreated_GrantAccess` を手動実行して共有を再付与する必要がある（Cascade Share は新規共有時にのみ適用されるため）。

## 2026-05-09: ds_mention に Assign 権限追加

Status: Applied 2026-05-09

### 背景（mention Assign）

関係者追加時に `addParticipantWithMention` が作成するメンションを target ユーザー所有として登録するため、`ds_Applicant` / `ds_Decider` ロールに `ds_mention` テーブルへの `Assign` (Basic) 権限を追加した。これにより、メンションされた本人がメンションを既読化できるようになる。

### 対象（mention Assign）

- ロール `ds_Applicant`: `ds_mention` の Assign=Basic 追加
- ロール `ds_Decider`: `ds_mention` の Assign=Basic 追加

### 実行手順（mention Assign）

```powershell
py scripts/setup_security_roles.py
```

スクリプトはべき等。既存ロールに不足している Privilege のみ追加する。

### 注意（mention Assign）

- 過去に作成済みのメンションは creator 所有のままなので、本人が既読化できない。新規メンションから正常動作する。
- 古いメンションを正常化する場合は、Dataverse UI または PowerShell で `ownerid` を target ユーザーへ手動移管する。

## 2026-05-03: 旧 AI 要約メタデータ cleanup

Status: Applied 2026-05-03

### 背景（旧 AI 要約 cleanup）

会話ログが一定数たまったら `ds_message.kind=AISummary` と `ds_application.ds_aisummary` に要約を蓄積する旧計画を廃止した。現在は `Application_GenerateAiDecision` が Submitted 保存時または手動更新時に、申請概要・会話概要・推奨判断をまとめて生成し、AI 判断列へ保存する。

### 対象（旧 AI 要約 cleanup）

- `ds_application`
  - `ds_aisummary`
  - `ds_summaryupdatedat`
- `ds_message.ds_kind` の旧 Choice 値
  - `100000004` AISummary

### 実行手順（旧 AI 要約 cleanup）

ドライラン:

```powershell
py scripts/migrate_cleanup_old_ai_summary.py
```

適用:

```powershell
py scripts/migrate_cleanup_old_ai_summary.py --apply
```

### 注意（旧 AI 要約 cleanup）

- `--apply` は Dataverse メタデータを削除する破壊的操作。
- 旧列に値が残っている場合は、削除前に `artifacts/migrations/old_ai_summary_backup_*.json` へ退避する。このバックアップは環境データのため Git 管理しない。
- `AISummary` 種別のメッセージが存在する場合は Choice 値を削除せず停止する。

### 適用結果（旧 AI 要約 cleanup）

- `AISummary` 種別のメッセージ: 0 件
- バックアップ対象の旧 AI 要約値を持つ申請: 2 件
- 削除済み Choice 値: `ds_message.ds_kind = 100000004`
- 削除済み列: `ds_aisummary`, `ds_summaryupdatedat`
- 適用後の `ds_message.ds_kind` Choice 値: `100000000`, `100000001`, `100000002`, `100000003`
- `ds_aiapplicationsummary` / `ds_aiconversationsummary` は継続利用中

## 2026-05-03: AI 判断列追加

Status: Applied 2026-05-03

### 背景（AI 判断列追加）

旧 AI 要約計画を廃止し、判断タブで AI 申請概要、AI 会話概要、推奨判断、判断コメント、リスク、類似案件を表示する方式に変更した。結果は `ds_application` に保存し、Submitted 保存時と手動更新の両方で同じ `Application_GenerateAiDecision` フローを使う。

### 対象（AI 判断列追加）

- `ds_application`
  - `ds_aiapplicationsummary` Memo
  - `ds_aiconversationsummary` Memo
  - `ds_aidecisionoptiontext` String
  - `ds_aidecisioncomment` Memo
  - `ds_aidecisionbasis` Memo
  - `ds_aidecisionupdatedat` DateTime

### 実行手順（AI 判断列追加）

既存環境では、べき等な Dataverse セットアップを再実行して不足列を追加する。

```powershell
py scripts/setup_dataverse.py
```

その後、AI Builder プロンプトと Power Apps V2 フローを作成する。

```powershell
py scripts/deploy_ai_decision.py
npx power-apps add-flow --flow-id {workflow_id}
npm run build
npx power-apps push
```

既存フロー ID が変わらない再デプロイでは、Code Apps 側のフロー登録は維持されるため `npx power-apps add-flow` の再実行は不要。`scripts/deploy_ai_decision.py` は既存 workflow を削除せず `clientdata` を更新する。

### 注意（AI 判断列追加）

- 追加列のみで破壊的変更はない。
- `ds_aisummary` / `ds_summaryupdatedat` は後続の旧 AI 要約 cleanup で削除済み。新 UI とフローは `ds_aiapplicationsummary` / `ds_aiconversationsummary` を使う。
- Power Apps V2 フローを Code Apps から呼ぶには `add-flow` 後の再ビルド/再デプロイが必要。

## 2026-05-01: 旧関連資料列・旧ステージ Choice の cleanup

Status: Applied

### 背景（cleanup）

関連資料はリンク専用に変更し、ファイル添付、種別、ステータス、差し替え履歴は Code Apps の操作対象外になった。申請ステージも `Draft` / `Submitted` / `Decided` の3値に整理したため、旧ステージ Choice 値は削除対象になった。

### 対象（cleanup）

- `ds_applicationresource`
  - `ds_type`
  - `ds_attachment`
  - `ds_status`
  - `ds_version`
  - `ds_replacedat`
  - `ds_replacedfromid`
- Relationship
  - `ds_applicationresource_ds_applicationresource_replacedfrom`
- `ds_application.ds_stage` の旧 Choice 値
  - `100000002` InReview
  - `100000003` NeedsInfo
  - `100000005` Cancelled

### 実行手順（cleanup）

ドライラン:

```powershell
py scripts/migrate_cleanup_obsolete_metadata.py
```

適用:

```powershell
py scripts/migrate_cleanup_obsolete_metadata.py --apply
```

### 注意（cleanup）

- `--apply` は Dataverse メタデータを削除する破壊的操作。
- 旧ステージ値を持つ既存申請は、Choice 削除前に `Submitted` へ移行する。
- migration 後に Code Apps SDK の生成物が古い場合は、Dataverse データソースを再生成する。
- 削除が依存関係で失敗した場合は、該当ビュー/フォーム/フロー依存を外して再実行する。

### 適用結果（旧関連資料・旧ステージ cleanup）

- 旧ステージ値を持つ申請: 0 件
- 削除済み Choice 値: `100000002`, `100000003`, `100000005`
- 削除済み Relationship: `ds_applicationresource_ds_applicationresource_replacedfrom`
- 削除済み列: `ds_type`, `ds_attachment`, `ds_status`, `ds_version`, `ds_replacedat`
- `ds_replacedfromid` は Relationship 削除により既に存在しない状態を確認
- 適用後の `ds_stage` Choice 値: `100000000`, `100000001`, `100000004`
