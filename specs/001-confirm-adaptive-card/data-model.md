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
  - `Submitted -> Decided`（判断後整合フローが、差し戻し以外の判断履歴作成時に反映）
  - `Submitted -> Draft`（判断後整合フローが、差し戻し判断履歴作成時に反映）
  - `Submitted -> Submitted`（権限不足/重複/対象外時）

## Entity: 判断履歴 (`ds_decision`)

- Purpose: 判断確定の監査証跡
- Key fields:
  - `ds_decisionid` (PK)
  - `ds_applicationid@odata.bind` (FK to application)
  - `ds_decisionoptionid@odata.bind` (FK to decision option)
  - `ds_rationale` (required)
  - `ownerid` / `createdby`
  - `createdon`
- Validation rules:
  - 判断選択肢（option）は必須
  - 判断理由（rationale）は必須
  - 同一案件の確定は first-write-wins（後続は作成不可）
  - Code Apps と Copilot Studio のどちらから作成されても、このレコードを判断確定の正本イベントとする

## Entity: 判断後整合フロー (`Decision_OnCreated` / Power Automate)

- Purpose: `ds_decision` 作成を契機に、案件状態・通知・画面表示の整合を自動反映する
- Trigger:
  - `ds_decision` created
- Inputs:
  - `ds_decisionid`
  - `_ds_applicationid_value`
  - `_ds_decisionoptionid_value`
  - `ds_decidedat`
- Derived values:
  - 判断選択肢名が `差し戻し` の場合: next stage = `Draft`
  - それ以外: next stage = `Decided`
- Effects:
  - `ds_application.ds_stage` を next stage へ更新
  - next stage が `Draft` の場合は `ds_application.ds_submittedat` をクリア
  - 既存通知フローで申請者・関係者へ通知
- Validation rules:
  - 対象案件が存在しない場合は処理を失敗記録し、通知しない
  - 既に同じステージへ整合済みの場合は冪等に成功扱いとする
  - Code Apps 由来と Copilot Studio 由来を分岐させず、同一ルールで処理する

## Entity: 判断選択肢 (`ds_decisionoption`)

- Purpose: 確定時に選択される判断結果マスタ
- Key fields:
  - `ds_decisionoptionid` (PK)
  - `ds_name`
  - `statecode`
- Validation rules:
  - `statecode=Active` の選択肢のみ利用可
  - Adaptive Card では Code Apps と同じく `承認`、`却下`、`差し戻し` の3択のみ提示する

## Entity: 判断確定操作イベント（論理エンティティ）

- Purpose: Adaptive Card submit 入力と処理結果の追跡
- Key fields:
  - `applicationId`
  - `decisionOptionId`
  - `rationale` (required)
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
- Rule 2: `ds_decision` 作成を正本イベントとし、案件状態更新は判断後整合フローで自動反映
- Rule 3: 同一案件の重複確定は後続拒否（already processed）
- Rule 4: 同一 `cardInstanceId` の submit は一度だけ受理
- Rule 5: Code Apps と Copilot Studio 由来の判断履歴は同じ整合フローで処理

## Audit & Traceability

- 監査最小要件:
  - 誰が（actor）
  - いつ（processedAt）
  - 何を（applicationId + decisionOptionId）
  - 結果（result）
