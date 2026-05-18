# Quickstart: Copilot Studio チャットで Adaptive Card 判断確定

## 1. Preconditions

- `.env` が設定済み（Dataverse / Solution / Copilot 関連）
- 既存の DecisionFlow 資産がデプロイ済み
  - Dataverse テーブル
  - Notification flows
  - Copilot Studio Agent
- 対象案件が `Submitted` 状態で存在
- 案件に割り当て済みの判断者ユーザーが存在

## 2. Implement

1. Adaptive Card submit を受けるフロー/アクションを追加
2. サーバー側で以下を検証
  - 案件存在・状態 (`Submitted`)
  - 実行者が案件割り当て済み判断者
  - カード使い回しでない（1回表示限り）
  - 判断選択肢が `承認`、`却下`、`差し戻し` のいずれか
  - 判断理由が空でない
3. 確定処理を実行
  - `ds_decision` を作成（判断選択肢と判断理由はいずれも必須）
  - `ds_application` はカード処理内で直接更新しない
4. `ds_decision` 作成トリガーの Power Automate 整合フローを追加/拡張
  - 判断選択肢から次ステージを導出（`差し戻し` は `Draft`、それ以外は `Decided`）
  - `ds_application` のステージを自動更新
  - 既存通知フローで結果共有
5. 案件詳細画面へ反映

## 3. Validate (minimum)

- 正常系
  - 割り当て済み判断者が、判断選択肢（承認・却下・差し戻し）と判断理由を入力してカードで確定できる
  - 案件詳細画面に最新判断結果が反映される
  - 既存通知が送信される
- 入力検証系
  - 判断選択肢未選択の場合は確定できない
  - 判断理由が空の場合は確定できない
- Code Apps 整合系
  - Code Apps で判断を作成した場合も同じ Power Automate 整合フローで案件ステージと通知が反映される
  - Copilot Studio で判断を作成した場合も Code Apps と同じステージ判定になる
- 競合系
  - 同時操作で最初の成功のみ反映、後続は既処理エラー
- 認可系
  - 未割り当て判断者は拒否される
- カード再利用系
  - 同一カード再submitは拒否される

## 4. Suggested test commands

```powershell
npm run build
npm test
py -m unittest tests.test_notification_flows tests.test_security_roles
```

## 5. Rollback guidance

- 本機能の Copilot submit フロー/アクションを無効化
- 判断後整合フローを無効化する場合は、Code Apps 側の既存ステージ更新・通知影響を確認する
- 画面側のトリガー導線を feature flag で停止（導入する場合）
- 監査影響があるため、誤確定はデータ補正手順を `docs/PLAN.md` に記録
