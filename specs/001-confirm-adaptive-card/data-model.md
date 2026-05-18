# Data Model: Copilot Studio チャットで Adaptive Card 判断確定

## Entity: 判断対象案件 (`ds_application`)

- Purpose: 申請のライフサイクル管理と判断状態の保持
- Key fields:
  - `ds_applicationid` (PK)
  - `ds_stage` (Draft/Submitted/Decided)
  - `modifiedon` / `createdon`
  - 既存の AI 判断補助列群（参照のみ）
- Validation rules:
  - 確定処理の対象は `ds_stage=Submitted` のみ
  - `Deleted/Cancelled` 相当は確定不可
- State transitions:
  - `Submitted -> Decided`（成功時のみ）
  - `Submitted -> Submitted`（権限不足/重複/対象外時）

## Entity: 判断履歴 (`ds_decision`)

- Purpose: 判断確定の監査証跡
- Key fields:
  - `ds_decisionid` (PK)
  - `ds_applicationid@odata.bind` (FK to application)
  - `ds_decisionoptionid@odata.bind` (FK to decision option)
  - `ds_comment` (optional)
  - `ownerid` / `createdby`
  - `createdon`
- Validation rules:
  - 判断結果（option）は必須
  - コメント・理由コードは任意
  - 同一案件の確定は first-write-wins（後続は作成不可）

## Entity: 判断選択肢 (`ds_decisionoption`)

- Purpose: 確定時に選択される判断結果マスタ
- Key fields:
  - `ds_decisionoptionid` (PK)
  - `ds_name`
  - `statecode`
- Validation rules:
  - `statecode=Active` の選択肢のみ利用可

## Entity: 判断確定操作イベント（論理エンティティ）

- Purpose: Adaptive Card submit 入力と処理結果の追跡
- Key fields:
  - `applicationId`
  - `decisionOptionId`
  - `comment` (optional)
  - `actorAadObjectId` / `actorUpn`
  - `cardInstanceId`（1回表示限り管理）
  - `processedAt`
  - `result` (`succeeded|already_processed|forbidden|invalid_target`)
- Validation rules:
  - カード操作者は案件に割り当て済み判断者であること
  - `cardInstanceId` の再利用は禁止

## Entity: 通知対象関係者 (`ds_participant` + applicant + decider)

- Purpose: 確定結果の配信先判定
- Key fields:
  - `ds_participantid`
  - `ds_applicationid@odata.bind`
  - `ds_userid@odata.bind`
  - `ds_role`
- Validation rules:
  - 通知は同一案件・同一イベントで重複送信しない

## Relationships

- `ds_application (1) -> (N) ds_decision`
- `ds_decisionoption (1) -> (N) ds_decision`
- `ds_application (1) -> (N) ds_participant`

## Concurrency / Idempotency Rules

- Rule 1: 案件確定は `Submitted` からの単一遷移のみ許可
- Rule 2: 同一案件の重複確定は後続拒否（already processed）
- Rule 3: 同一 `cardInstanceId` の submit は一度だけ受理

## Audit & Traceability

- 監査最小要件:
  - 誰が（actor）
  - いつ（processedAt）
  - 何を（applicationId + decisionOptionId）
  - 結果（result）
