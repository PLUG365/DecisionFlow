# Research: カテゴリ別レギュレーションAIチェック

## Decision: `ds_category` に1つのMemo列としてレギュレーション文章を追加する

**Rationale**: 仕様はカテゴリごとに1つの複数行テキストを求めている。既存の `ds_category` はカテゴリ名、説明、推奨フォーマット、並び順を持つマスタであり、カテゴリの業務ルールを保持する自然な場所である。追加テーブルを作らないことで参照、権限、UI、AIプロンプト入力を単純に保てる。

**Alternatives considered**: レギュレーション専用テーブル、レギュレーション履歴テーブル、複数レギュレーション項目テーブル。いずれも履歴や複数項目管理を伴い、今回の最新のみ・1カテゴリ1文章という要件より重い。

## Decision: 既存 `Application_GenerateAiDecision` フローを拡張する

**Rationale**: 既存フローは Code Apps から申請IDを受け取り、申請、会話、資料、判断選択肢、類似案件を収集し、AI Builder prompt `DecisionRecommendation` を実行して既存AI判断列へ保存している。仕様は同等目的のAI判断フローを増やさないことを明示しているため、カテゴリレギュレーション取得と prompt 入力追加を既存フローに入れる。

**Alternatives considered**: 申請者向け事前確認専用フロー、判断者向けレギュレーションチェック専用フロー。どちらもフロー増殖と出力形式分岐を招き、既存AI判断格納列の再利用方針に反する。

## Decision: AI出力と保存先は既存AI判断列に準拠する

**Rationale**: 既存列は `ds_aiapplicationsummary`、`ds_aiconversationsummary`、`ds_aidecisionoptiontext`、`ds_aidecisioncomment`、`ds_aidecisionbasis`、`ds_aidecisionupdatedat`。仕様は最新結果のみ保存、履歴なし、スナップショットなし、固定判定状態の新設なしを求めている。レギュレーション観点は既存コメント、根拠JSON、リスク配列に自然に含められる。

**Alternatives considered**: 新しいAI判定状態列、レギュレーションチェック結果テーブル、使用レギュレーション本文スナップショット列。いずれもユーザー相談なしに保存形式を増やすため不採用。

## Decision: 提出操作は下書き保存、AI実行、確認、本提出のUI状態遷移で扱う

**Rationale**: 既存UIは Submitted 保存後にAI判断を非同期実行している。新要件では提出操作時に直接 Submitted にせず、保存済み下書きレコードをもとにAI判断取得フローを必ず実行し、申請者がAI結果を見て本提出または下書き維持を選ぶ。通知フローは `ds_stage == Submitted` に反応するため、本提出前は Draft を維持することで通知や判断者キュー投入を避けられる。

**Alternatives considered**: 保存前にAI実行、Submittedにしてから戻す、AI結果で提出ブロック。保存前AI実行は既存フローの申請ID入力と合わない。Submittedから戻す方式は通知副作用が起きやすい。AI結果ブロックは仕様に反する。

## Decision: カテゴリ必須はカテゴリマスタ有無で切り替える

**Rationale**: 仕様はカテゴリマスタが存在する場合のみカテゴリ必須、存在しない場合はカテゴリなしで既存AI判断を継続すると定義している。Code Apps は既にカテゴリ一覧を取得しているため、`categories.length > 0` を基準にUI validationを行える。フロー側もカテゴリ未設定時はレギュレーションなしとして継続する。

**Alternatives considered**: 常にカテゴリ必須、常に任意。どちらも仕様の移行/初期環境対応に合わない。

## Decision: 判断者ロールは全カテゴリのレギュレーションを編集できる

**Rationale**: Clarificationで判断者ロール保持者は全カテゴリ編集可能と決定済み。既存 `ds_Decider` は `ds_category` を読み取りのみとしているため、`ds_category` に Write を付与する必要がある。申請者は read-only のままとする。

**Alternatives considered**: カテゴリ担当者別編集、管理者のみ編集、申請カテゴリ割当ベース編集。追加の所有者管理やロール設計が必要になり、現在のロール運用より複雑になる。

## Decision: VerificationはPython構造テスト、Vitest、ビルド、手動Power Platform確認を組み合わせる

**Rationale**: Dataverse/Power Automate/AI Builderは定義生成のテストとデプロイ出力確認が必要。Code AppsはロジックとUIフローのVitest、TypeScript buildで確認する。AI Builder実行は環境依存のため、quickstartに手動ランタイム確認を含める。

**Alternatives considered**: 手動確認のみ、全環境自動E2Eのみ。前者は回帰検出が弱く、後者はPower Platform接続と認証に依存しすぎる。
