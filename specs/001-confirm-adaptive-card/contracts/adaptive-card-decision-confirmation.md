# Contract: Adaptive Card Decision Confirmation

## 1. Purpose

Copilot Studio チャット上の Adaptive Card submit で判断確定を実行するための入出力契約。

## 2. Request Contract (logical)

Adaptive Card の表示定義は Copilot Studio 側で管理し、schema 1.5 と `Action.Submit` のみを使用する。`Action.Execute` は初期リリースでは使用しない。

```json
{
  "action": "confirm_decision",
  "applicationId": "<guid>",
  "decisionOptionId": "<guid>",
  "rationale": "<string>",
  "cardInstanceId": "<string>",
  "actor": {
    "aadObjectId": "<guid>",
    "upn": "<string>"
  }
}
```

### Request Rules

- `applicationId` required
- `decisionOptionId` required; must resolve to one of `承認`, `却下`, `差し戻し`
- `rationale` required; must be non-empty after trimming
- `cardInstanceId` required, single-use; must match the latest `Issued` `ds_decisioncard` for the application and actor
- `actor` required for authorization check

## 3. Response Contract

### 3.1 Success

```json
{
  "status": "succeeded",
  "applicationId": "<guid>",
  "decidedAt": "<iso-8601>",
  "decisionRecordId": "<guid>",
  "message": "判断を確定しました。"
}
```

### 3.2 Already Processed

```json
{
  "status": "already_processed",
  "applicationId": "<guid>",
  "message": "この案件は既に判断確定済みです。"
}
```

### 3.3 Forbidden

```json
{
  "status": "forbidden",
  "applicationId": "<guid>",
  "message": "この案件を確定する権限がありません。"
}
```

### 3.4 Invalid Target

```json
{
  "status": "invalid_target",
  "applicationId": "<guid>",
  "message": "対象案件が無効または参照できません。"
}
```

## 4. Behavioral Contract

- first-write-wins: 同一案件への同時確定は最初の成功のみ有効
- first-write-wins-mvp: 初期実装は `Submitted` 状態と既存判断履歴の lookup-then-insert で制御する。厳密な同時実行制御が必要になった場合は `ds_application` の ETag / optimistic concurrency を追加検討する
- single-use-card: `cardInstanceId` の再利用は禁止
- card-reissue: 同一案件で新しいカードが発行された場合、以前の未使用カードは `Superseded` として無効化される
- authorization: 案件割り当て済み判断者のみ許可
- input-parity-with-code-apps: Adaptive Card は Code Apps と同じく、判断選択肢（承認・却下・差し戻しの3択）と判断理由の2項目を必須にする
- decision-record-source: 成功時は `ds_decision` を作成し、この履歴を判断確定の正本イベントとする
- propagation: 案件詳細画面反映 + 既存通知フロー送信は `ds_decision` 作成トリガーの Power Automate 整合フローが自動実行する
- consistency-with-code-apps: Code Apps 由来の `ds_decision` 作成も同じ整合フローで処理され、Copilot Studio 由来と同じ案件状態・通知結果になる

## 5. Idempotency / Concurrency Expectations

- 同一 submit の再送時は `already_processed` または `forbidden` / `invalid_target` を返す
- 古いカード、消費済みカード、再発行により失効したカードの submit は `already_processed` を返す
- 決して成功応答を二重返却しない
- カード処理は `ds_application` を直接更新せず、`ds_decision` 作成後の整合フローに委譲する
