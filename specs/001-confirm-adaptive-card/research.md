# Research: Copilot Studio チャットで Adaptive Card 判断確定

## Decision 1: 判断確定の競合は先着確定優先（first-write-wins）

- Decision: 同一案件に対する同時確定は最初の成功のみ有効にし、後続操作は「既に確定済み」で拒否する。
- Rationale: 既存の「判断済みは単一確定」要件と整合し、監査ログの一貫性を維持しやすい。
- MVP implementation: 初期実装では `ds_application` が `Submitted` であることと既存 `ds_decision` の有無を確認してから作成する lookup-then-insert 方式とする。`ds_decision` は差し戻し後の再提出で複数履歴を持ち得るため、案件単位の Dataverse Alternate Key では強制しない。本番化時に同時確定リスクが高い場合は、`ds_application` の ETag / optimistic concurrency を使った厳密ロックを検討する。
- Alternatives considered:
  - 後着上書き: 監査整合性とユーザー期待を崩すため不採用。
  - 手動解決: 運用負荷が高く、チャット完結体験を損なうため不採用。
  - `ds_decision` の案件単位 Alternate Key: 差し戻し→再提出→再判断の履歴を保持できなくなるため不採用。

## Decision 2: Adaptive Card は 1 回表示限り（再表示時は再発行）

- Decision: カードインスタンスは使い切りとし、同一案件の再確認時は新規カードを再発行する。
- Rationale: リプレイ操作の抑止と誤操作低減に有効で、状態管理を明確化できる。
- Alternatives considered:
  - 固定期限（24h）: 有効期限管理の実装・運用コストが増えるため不採用。
  - 無期限有効: 古いカードからの確定リスクが増えるため不採用。
  - `ds_application` に最新 `cardInstanceId` 列を追加: 主テーブルにチャットUI固有の一時状態を持ち込み、監査・再発行履歴が追いにくいため不採用。

## Decision 2.1: cardInstanceId は `ds_decisioncard` 子テーブルで永続化する

- Decision: Adaptive Card の発行状態は新規子テーブル `ds_decisioncard` に保存する。カード再発行時は同一案件・同一判断者の未使用カードを `Superseded` にし、新しい `Issued` レコードを作成する。
- Rationale: 「同案件に既に `ds_decision` があるか」だけでは、再発行後に古いカードを拒否する要件を表現できない。カード発行・消費・再発行を子テーブルで追跡すると、single-use と監査を分離して扱える。
- Alternatives considered:
  - `ds_decision` の有無だけで拒否: 判断前に古いカードを失効できないため不採用。
  - `ds_application` に最新カードIDを保持: シンプルだが履歴が残らず、複数チャネル・再発行・障害調査に弱いため不採用。

## Decision 3: 確定入力は判断選択肢と判断理由を必須

- Decision: Code Apps と同じく、判断選択肢（承認・却下・差し戻しの3択）と判断理由の2項目を必須入力にする。
- Rationale: Code Apps と Copilot Studio の入力契約を揃えることで、判断履歴 (`ds_decision`) のデータ品質と後続の Power Automate 整合処理を同じ前提で扱える。
- Alternatives considered:
  - 判断選択肢のみ必須: Code Apps 由来の判断履歴と情報量が揃わず、監査・通知内容に差が出るため不採用。
  - 自由入力の判断結果: 既存判断選択肢マスタと分岐し、ステージ判定（差し戻し）を安定して導出できないため不採用。

## Decision 3.1: Adaptive Card は schema 1.5 + Action.Submit に固定

- Decision: Adaptive Card 表示定義は schema 1.5 と `Action.Submit` のみで設計する。
- Rationale: Teams チャネル互換性を優先し、Copilot Studio test pane / Teams / Web Chat の差異による手戻りを抑える。`Action.Execute` や schema 1.6 前提にするとチャネルごとの対応差が出るため、初期リリースでは使わない。
- Alternatives considered:
  - schema 1.6: test pane や一部 Web Chat では使えるが Teams 互換性が弱いため不採用。
  - `Action.Execute`: Bot Framework Web Chat 等で非対応ケースがあり、チャネル横断の初期リリースには不向きなため不採用。

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

- Decision: エージェント全体は生成オーケストレーションで運用し、Adaptive Card の表示・入力取得だけは専用 Topic（Ask with Adaptive Card ノード相当）を実装サーフェスとして使う。Topic 内で `issue_decision_card` Power Automate アクションを呼び出して `ds_decisioncard` と表示用データを取得し、schema 1.5 / `Action.Submit` の Adaptive Card で入力を受け、submit 後に `confirm_decision` Power Automate アクションを呼び出す。
- Rationale: プロジェクト標準の生成オーケストレーション方針を維持しつつ、Copilot Studio でカード表示→入力→submit→次アクションを安定して扱う well-supported な実装経路に乗せる。ここでの Topic は rigid な trigger phrase matching に依存する会話設計ではなく、カードUIの実装単位として扱う。
- Alternatives considered:
  - カード側のみ検証: 改ざん防止が不十分。
  - Topic を一切使わない純粋なアクション応答: Adaptive Card の表示・submit 受信・次アクション連携の実装がチャネル依存になりやすいため不採用。
  - trigger phrase matching に依存する従来型 Topic 設計: 生成オーケストレーションとの責務が分岐するため不採用。

### Adaptive Card 表示定義とスクリプト境界

- Decision: Adaptive Card の表示レイアウト JSON と専用 Topic 定義は Copilot Studio 側のカード/応答定義として管理する。`scripts/deploy_adaptive_card_decision_confirmation.py` は Adaptive Card 発行/submit 用 Power Automate フロー定義、カード発行状態 (`ds_decisioncard`) 管理、Dataverse 検証・作成アクション定義を所有する。`scripts/deploy_copilot_agent.py` は Copilot Studio 側の Instructions 更新、カード表示 Topic の手動設定案内または botcomponents YAML デプロイ、Power Automate ツール追加案内、既存エージェント設定の確認を所有する。
- Rationale: カードの見た目・入力コントロールは会話体験に属するため Copilot Studio 側に置く方が自然で、Power Automate 側はサーバーサイドの発行ID・検証・永続化に集中できる。フロー定義とエージェント設定を分けることで、Power Automate の接続参照・有効化失敗と Copilot Studio の YAML/設定更新を独立して検証できる。
- Alternatives considered:
  - すべて `deploy_copilot_agent.py` に統合: ファイルが肥大化し、フロー定義テストとエージェント設定テストが分離できないため不採用。
  - Copilot wiring を新規フロー側に含める: Bot 設定のディープマージや公開処理と責務が重なるため不採用。
  - カードJSONテンプレートを Power Automate デプロイスクリプトに持たせる: 表示変更のたびにフロー定義側の責務が増え、Copilot Studio UI での調整と二重管理になりやすいため不採用。

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

### Code Apps UI の即時性

- Decision: Code Apps は `ds_decision` 作成成功時に選択肢名から導出した次ステージを TanStack Query のキャッシュへ楽観更新し、その後 500ms 間隔・最大 3 秒の短時間ポーリングで `Decision_OnCreated` による Dataverse 側の `ds_application` 更新を確認する。ポーリングで一致しない場合は通常の query invalidation に戻し、整合待ち状態を表示する。
- Rationale: 従来の同期更新と同等の操作感を保ちつつ、最終的な正本は Power Automate 整合フローに置ける。単純な query invalidation だけでは、フロー実行前の古い `ds_stage` を再取得する可能性がある。
- Alternatives considered:
  - query invalidation のみ: 非同期フロー前の古いステージを取得し、UI が一瞬戻る可能性があるため不採用。
  - 楽観更新のみ: Power Automate 失敗時に画面と Dataverse の差異に気づきにくいため不採用。

## Testing Strategy Decisions

- Decision: 既存テスト体系（Python unit + TypeScript unit/build）に寄せて、フロー定義検証とクライアント側状態更新検証を追加する。
- Rationale: 現行CI/手動検証手順に適合させ、導入コストを抑える。
- Alternatives considered:
  - E2E のみ: 失敗原因の切り分けが困難。
  - 単体のみ: チャット連携境界の検証不足。
