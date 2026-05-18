# Contract: Adaptive Card Decision Confirmation

## 1. Purpose

Copilot Studio チャット上の Adaptive Card submit で判断確定を実行するための入出力契約。

## 2. Request Contract (logical)

```json
{
  "action": "confirm_decision",
  "applicationId": "<guid>",
  "decisionOptionId": "<guid>",
  "comment": "<string, optional>",
  "cardInstanceId": "<string>",
  "actor": {
    "aadObjectId": "<guid>",
    "upn": "<string>"
  }
}
```

### Request Rules

- `applicationId` required
- `decisionOptionId` required
- `comment` optional
- `cardInstanceId` required, single-use
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
- single-use-card: `cardInstanceId` の再利用は禁止
- authorization: 案件割り当て済み判断者のみ許可
- propagation: 成功時は案件詳細画面反映 + 既存通知フロー送信

## 5. Idempotency / Concurrency Expectations

- 同一 submit の再送時は `already_processed` または `forbidden` / `invalid_target` を返す
- 決して成功応答を二重返却しない
