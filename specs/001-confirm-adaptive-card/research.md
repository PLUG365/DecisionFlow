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

## Decision 3: 確定入力は判断結果のみ必須

- Decision: 必須は判断結果のみ。コメントと理由コードは任意入力。
- Rationale: チャット上の操作負荷を最小化し、SC-001（60秒以内）に寄与する。
- Alternatives considered:
  - コメント必須: 入力負荷上昇による完了率低下リスク。
  - 理由コード必須: 初期導入時の運用負荷が高く、不達時の失敗率上昇が懸念。

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

- Decision: 確定時に `ds_application` のステージ更新と `ds_decision` レコード作成（または同等履歴）を同一処理フローで実施する。
- Rationale: 画面整合性（案件状態）と監査整合性（判断履歴）を同時に満たす。
- Alternatives considered:
  - 案件状態のみ更新: 監査証跡が不足。
  - 履歴のみ作成: UI 反映遅延・不整合が発生。

## Testing Strategy Decisions

- Decision: 既存テスト体系（Python unit + TypeScript unit/build）に寄せて、フロー定義検証とクライアント側状態更新検証を追加する。
- Rationale: 現行CI/手動検証手順に適合させ、導入コストを抑える。
- Alternatives considered:
  - E2E のみ: 失敗原因の切り分けが困難。
  - 単体のみ: チャット連携境界の検証不足。
