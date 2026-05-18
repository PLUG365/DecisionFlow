# Research: Copilot Studio チャットで Adaptive Card 判断確定

## Decision 1: 判断確定の競合は先着確定優先（first-write-wins）

- Decision: 同一案件に対する同時確定は最初の成功のみ有効にし、後続操作は「既に確定済み」で拒否する。
- Rationale: 既存の「判断済みは単一確定」要件と整合し、監査ログの一貫性を維持しやすい。
- Alternatives considered:
  - 後着上書き: 監査整合性とユーザー期待を崩すため不採用。
  - 手動解決: 運用負荷が高く、チャット完結体験を損なうため不採用。

## Decision 2: Adaptive Card は 1 回表示限り（再表示時は再発行）

- Decision: カードインスタンスは使い切りとし、同一案件の再確認時は新規カードを再発行する。
- Rationale: リプレイ操作の抑止と誤操作低減に有効で、状態管理を明確化できる。
- Alternatives considered:
  - 固定期限（24h）: 有効期限管理の実装・運用コストが増えるため不採用。
  - 無期限有効: 古いカードからの確定リスクが増えるため不採用。

## Decision 3: 確定入力は判断選択肢と判断理由を必須

- Decision: Code Apps と同じく、判断選択肢（承認・却下・差し戻しの3択）と判断理由の2項目を必須入力にする。
- Rationale: Code Apps と Copilot Studio の入力契約を揃えることで、判断履歴 (`ds_decision`) のデータ品質と後続の Power Automate 整合処理を同じ前提で扱える。
- Alternatives considered:
  - 判断選択肢のみ必須: Code Apps 由来の判断履歴と情報量が揃わず、監査・通知内容に差が出るため不採用。
  - 自由入力の判断結果: 既存判断選択肢マスタと分岐し、ステージ判定（差し戻し）を安定して導出できないため不採用。

## Decision 4: 結果共有は案件詳細画面 + 既存通知フロー

- Decision: 確定後は案件詳細画面へ即時反映し、既存通知フロー（Outlook/Teams）で関係者通知を行う。
- Rationale: 既存資産を活用しつつ、閲覧系と通知系の双方で到達保証を高める。
- Alternatives considered:
  - 画面のみ: 能動確認が必要で到達性が低い。
  - 通知のみ: システムオブレコードとしての画面整合性確認導線が弱い。

## Decision 5: カード確定は案件に割り当て済み判断者のみ許可

- Decision: 判断者ロールに加え、対象案件の割り当て判断者であることを実行条件にする。
- Rationale: 権限過大適用を防ぎ、誤確定リスクを抑える。
- Alternatives considered:
  - 判断者ロール全員許可: 対象外案件への操作余地が残る。
  - メール一致のみ: ロール統制を迂回するため不採用。

## Integration Pattern Decisions

### Copilot Studio 連携

- Decision: Copilot Studio からのアクション呼び出しで Adaptive Card submit を受理し、サーバー側で案件状態・実行者妥当性を再検証する。
- Rationale: クライアント改ざん耐性を確保するため、最終判定はサーバー主導にする。
- Alternatives considered:
  - カード側のみ検証: 改ざん防止が不十分。

### Dataverse 更新単位

- Decision: `ds_decision` 作成を判断確定の正本イベントとし、Power Automate の判断後整合フローが `ds_application` のステージ更新・通知・表示整合を自動実行する。
- Rationale: Code Apps と Copilot Studio がそれぞれ同じ案件状態更新ロジックを持つと分岐・重複・競合が起きやすい。判断履歴作成イベントに集約すると、既存 Code Apps からの判断作成と Copilot Studio カードからの判断作成を同じ後続処理で整合できる。
- Alternatives considered:
  - 案件状態のみ更新: 監査証跡が不足。
  - カード処理内で案件状態も直接更新: Code Apps 側と二重実装になり、差し戻し等のステージ判定が分岐するため不採用。
  - 履歴のみ作成して後続処理なし: UI 反映遅延・不整合が発生。

### Code Apps / Copilot Studio 整合パターン

- Decision: Code Apps は既存の判断作成 UX を維持し、Copilot Studio は Adaptive Card submit から `ds_decision` を作成する。両経路の後続整合は `ds_decision` 作成トリガーの Power Automate フローに集約する。
- Rationale: ユーザー体験ごとの入口は分けつつ、案件状態・通知・監査の最終整合を Dataverse イベント駆動で揃えられる。
- Alternatives considered:
  - Code Apps からも Copilot 用アクションを呼ぶ: 既存画面の責務が増え、Code Apps 側にチャット用処理を持ち込むため不採用。
  - Copilot 側だけ専用確定処理を持つ: Code Apps 経路との差異が残るため不採用。

## Testing Strategy Decisions

- Decision: 既存テスト体系（Python unit + TypeScript unit/build）に寄せて、フロー定義検証とクライアント側状態更新検証を追加する。
- Rationale: 現行CI/手動検証手順に適合させ、導入コストを抑える。
- Alternatives considered:
  - E2E のみ: 失敗原因の切り分けが困難。
  - 単体のみ: チャット連携境界の検証不足。
