# DecisionFlow Migrations

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
