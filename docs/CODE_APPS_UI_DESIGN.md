# DecisionFlow Code Apps UI 設計

> ステータス: Phase 2 フォーム強化済み（実機確認は継続）
> 作成日: 2026-05-01
> 対象範囲: Code Apps UI、Dataverse SDK アクセスパターン、ナビゲーション、画面・コンポーネント構成

## 1. 設計ゴール

DecisionFlow は日常業務で繰り返し使う意思決定支援ツールであり、ランディングページや説明中心のサイトではない。Power Apps / モデル駆動型アプリ内の iframe で利用されることを前提に、素早く状況を読み取り、短い操作で判断に進める UI を目指す。

設計原則:

- モバイルファースト: 小さい画面では 1 カラム、デスクトップでは分割表示に拡張する。
- 業務密度を重視: 大きな装飾やヒーロー領域ではなく、コンパクトなカード、テーブル、バッジ、サイドパネルで構成する。
- 判断コンテキストを安定表示: 申請詳細では、申請本文、関連資料、会話、関係者、判断タブを近い場所に保ち、AI 判断は判断タブ内で判断入力と並べて表示する。
- 権限を意識した操作表示: 申請者、判断者、管理者に応じて必要な操作を表示する。ただし最終的な権限判定は Dataverse セキュリティロールを正とする。

## 2. ルートと画面一覧

| ルート              | 画面           | 主なユーザー             | 目的                                                        |
| ------------------- | -------------- | ------------------------ | ----------------------------------------------------------- |
| `/dashboard`        | ダッシュボード | 全ユーザー / 管理者      | 全体負荷、キュー件数、停滞申請、直近判断を確認する          |
| `/applications`     | 申請リスト     | 申請者                   | 自分が起票した申請を作成・確認する                          |
| `/queue`            | 判断キュー     | 判断者                   | 自分が判断者の Submitted / Decided 申請を確認する           |
| `/applications/:id` | 申請詳細       | 申請者 / 判断者 / 関係者 | 会話、資料、関係者、AI 判断、判断入力をまとめて扱う作業画面 |
| `/mentions`         | メンション     | 全ユーザー               | 自分宛てメンションの未読・既読を確認する                    |
| `/resources`        | 関連資料       | 申請者 / 判断者          | 申請に紐づく関連リンクを横断確認・追加・削除する            |
| `/masters`          | マスタ管理     | 管理者                   | カテゴリと判断選択肢を保守する                              |

初期実装の優先順:

1. `/dashboard`
2. `/applications`
3. `/queue`
4. `/applications/:id`
5. `/mentions`
6. `/resources`
7. `/masters`

## 3. ナビゲーション

サイドバー構成:

| セクション       | 項目                                   | アイコン                                  |
| ---------------- | -------------------------------------- | ----------------------------------------- |
| 業務             | ダッシュボード、申請リスト、判断キュー | `LayoutDashboard`, `FileText`, `Columns3` |
| コラボレーション | メンション、関連資料                   | `AtSign`, `Paperclip`                     |
| 管理             | マスタ管理（**ds_Admin のみ表示**）    | `Settings2`                               |

ヘッダー表示:

- タイトル: `DecisionFlow`
- サブタイトル: `Decision Support`

## 4. コンポーネント構成

### ダッシュボード

使用コンポーネント:

- 既存依存関係の Recharts によるグラフ表示。
- `ListTable` による直近申請・停滞申請一覧。

グラフ:

- ステージ分布のドーナツチャート。
- カテゴリ別申請件数の棒グラフ。
- `_ds_deciderid_value` と systemuser Map を使った判断者別負荷の棒グラフ。
- Recharts Tooltip はライト/ダーク共通の半透明濃色背景と白文字にし、Power Apps iframe 内でもラベルが読めるようにする。

### 申請リスト

使用コンポーネント:

- 自分が起票した申請に絞った、検索、ステージフィルタ、カテゴリフィルタ付き `ListTable`。
- 申請作成・編集用 `FormModal`。
- 削除確認用 `ConfirmDialog`。

列定義:

| 列       | フィールド             | 表示方法                                                                       |
| -------- | ---------------------- | ------------------------------------------------------------------------------ |
| タイトル | `ds_name`              | 省略表示 + 行クリック                                                          |
| ステージ | `ds_stage`             | ステージ色のバッジ。フォームでは下書き/提出のラジオ選択                        |
| 判断結果 | latest decision option | 最新 `ds_decision` の `_ds_decisionoptionid_value` を判断選択肢 Map で名前解決 |
| カテゴリ | `_ds_categoryid_value` | カテゴリ Map で名前解決                                                        |
| 判断者   | `_ds_deciderid_value`  | systemuser Map で名前解決                                                      |
| 希望期限 | `ds_duedate`           | 日本語ロケールの短い日付                                                       |
| 更新日   | `modifiedon`           | 相対表示または日本語ロケール日付                                               |

主要操作:

- 申請を作成する。初期ステージは下書き。
- 自分の下書き申請を編集する。フォームで選べるステージは下書き/提出のみ。
- 提出済みにする場合は判断者を必須にし、未選択なら保存前にエラー表示する。
- 提出済み申請は通知重複を避けるため通常編集不可とし、申請者本人の操作は「下書きに戻す」のみに限定する。
- 不要な申請を確認モーダル付きで削除する。
- 申請詳細を開く。
- 関連資料画面から資料リンクを追加し、申請詳細では紐づく資料リンクを確認する。

### 判断キュー

使用コンポーネント:

- ステージ別のカードリスト。
- テキスト省略が必要な箇所では Radix `ScrollArea` を使わず、素の `div overflow-y-auto overflow-x-hidden` を使う。
- カテゴリ、希望期限、判断結果を `Badge` で表示する。

キュー列:

| 列       | ステージ値  |
| -------- | ----------- |
| 提出済み | `100000001` |
| 判断済み | `100000004` |

ステージ操作:

- 判断キューではステージを直接変更しない。
- 判断キューは現在ユーザーの `systemuserid` と申請の `_ds_deciderid_value` が一致する申請だけを表示する。
- 判断済みへの変更は詳細画面の判断タブで `ds_decision` を作成した時に自動実行する。ただし判断選択肢が「差し戻し」の場合は申請ステージを Draft に戻し、申請者が修正できる状態にする。
- 申請者が選べるステージは申請作成・編集フォームの下書き/提出ラジオのみ。

### 申請詳細

使用コンポーネント:

- レスポンシブな 2 ペインレイアウト。
- モバイルでは Summary / Thread / Resources / People / Decision のタブ表示。
- デスクトップでもタブ内に文脈別の操作を配置する。
- `Tabs`, `Card`, `Textarea`, `Combobox`, `Button`, `ConfirmDialog`。

セクション:

- 申請内容: `ds_application` の本文、ステージ、カテゴリ、判断者、希望期限
- AI 判断: 判断タブ右側に申請概要、会話概要、推奨判断、コメント、リスク、類似案件を表示する。「AI判断更新」ボタンから再生成でき、Submitted 保存時にも同じ生成フローが自動実行される。
- スレッド: 申請で絞り込んだ `ds_message`。`_ds_parentmessageid_value` で返信構造を表現
- メンション: 会話タブのコメント投稿時に申請者・判断者・関係者から対象ユーザーを任意選択し、投稿された `ds_message` に紐づく `ds_mention` を作成
- 関連資料: `ds_applicationresource` のリンク資料
- 関係者: `ds_participant` の役割とユーザー Lookup。追加と確認付き削除を行う。
- 判断: 左側に最新判断結果と理由、判断入力フォームを表示する。右側に AI 判断カードを配置し、申請概要・会話概要・推奨判断・AI コメント・リスク・類似案件を表示する。

判断確定操作:

- 判断選択肢と判断理由を必須入力にする。
- `ds_decision` を作成する。
- Code Apps で判断した場合は、画面の即時反映のため `ds_decision` 作成後に `ds_application.ds_stage` も同じ操作内で更新する。
- 承認/却下は申請ステージを Decided に更新し、差し戻しは Draft に戻して `ds_submittedat` をクリアする。通知と最終整合は `Decision_OnCreated` が担当する。
- 最新判断が存在しても、差し戻し後に再提出された申請では判断入力フォームを再表示し、新しい `ds_decision` を追加できるようにする。
- 判断入力フォームは、申請の `_ds_deciderid_value` と現在の `systemuserid` が一致し、`ds_stage` が Submitted の場合のみ表示する。

AI 判断カード:

- 判断タブをモバイル 1 カラム、デスクトップ 2 カラムにし、右カラムへ配置する。
- `AI判断更新` ボタンは Submitted の申請で使用できる。押下時に Power Apps V2 フロー `Application_GenerateAiDecision` を呼び出す。
- フローは申請情報、関連資料、会話履歴、過去類似案件、判断選択肢を集め、AI Builder `DecisionRecommendation` で JSON を生成する。
- 過去類似案件候補は同一カテゴリの判断済み案件を最大 30 件、補助候補として直近判断済み案件を最大 10 件に制限する。申請本文全文ではなく AI 申請概要・AI 判断コメントなどの短い情報だけを渡して、トークン消費を抑えつつ候補母数を確保する。
- 申請が Submitted になった保存時点でも同じ生成フローを実行する。初回提出時は会話履歴が空でも実行し、過去類似案件は検索対象にする。
- AI 判断根拠のリスクは文字列配列と AI Builder の `{ item: string }` 形式の両方を表示できるようにする。
- 既存計画の「会話ログが一定数たまったら要約する」自動要約バッチは実装しない。

### メンション

使用コンポーネント:

- 未読切替付き `ListTable`。
- 既読化用 `Button`。

列定義:

| 列         | フィールド            | 表示方法                         |
| ---------- | --------------------- | -------------------------------- |
| 申請       | message → application | メッセージ Map と申請 Map で解決 |
| メッセージ | message body          | 2 行省略表示                     |
| 既読       | `ds_isread`           | バッジ                           |
| 作成日     | `createdon`           | 日本語ロケール日付               |

### 関連資料

使用コンポーネント:

- リンク一覧用 `ListTable`。
- リンク作成用 `FormModal`。
- 削除前確認用 `ConfirmDialog`。

列定義:

| 列       | フィールド                 | 表示方法                    |
| -------- | -------------------------- | --------------------------- |
| タイトル | `ds_name`                  | 行クリック                  |
| 申請     | `_ds_applicationid_value`  | 申請 Map で名前解決         |
| URL      | `ds_url`                   | 外部リンクボタン            |
| 操作     | `ds_applicationresourceid` | 削除アイコン + 確認モーダル |

### マスタ管理

使用コンポーネント:

- カテゴリ / 判断選択肢の `Tabs`。
- カテゴリは簡易編集用 `InlineEditTable` で追加・編集・削除に対応。
- 判断選択肢は `InlineEditTable` で参照のみ表示し、追加・編集・削除は行わない。

対象テーブル:

- `ds_category`: 名前、説明、推奨フォーマット、並び順。
- `ds_decisionoption`: 名前、説明、並び順。固定値は `承認` / `却下` / `差し戻し`。フロー・チャット・Adaptive Card の契約値のため変更不可。

アクセス制御:

- `useIsAdmin()` Hook で ds_Admin ロール保有を判定。
- 非 Admin ユーザーがアクセスした場合は `/dashboard` にリダイレクト。
- サイドバーの「管理」セクションも非 Admin には非表示。
- 削除に失敗した場合（参照中レコードがあるなど）はトーストで通知。

## 5. Dataverse サービスと Hooks

DecisionFlow 専用のサービス層を作成する。

| ファイル                            | 役割                                                                                                       |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `src/types/decisionflow.ts`         | Choice ラベル、色、UI 補助型                                                                               |
| `src/services/dataverse-service.ts` | 生成済み SDK サービスの薄いラッパー                                                                        |
| `src/hooks/use-decisionflow.ts`     | application、message、mention、participant、decision、resource、master、systemuser 用 TanStack Query hooks |

初回起動時の初期データ補完:

- `DataverseService.getData()` は画面データ取得前にカテゴリと判断選択肢を確認する。
- カテゴリが空の場合だけ、初期カテゴリ（顧客案件 / 部内案件 / 課内案件 / 他部署案件 / 事務処理）を作成する。
- 判断選択肢は固定システムマスタとして、`承認` / `却下` / `差し戻し` の不足分を作成する。
- 補完後にカテゴリと判断選択肢を再取得し、初回表示から選択肢が利用できる状態にする。

Hook グループ:

- `useApplications`, `useApplication(id)`, `useCreateApplication`, `useUpdateApplication`, `useDeleteApplication`
- `useCategories`, `useDecisionOptions`
- `useMessages(applicationId)`, `useCreateMessage`
- `useMentionsForCurrentUser`, `useCreateMention`, `useMarkMentionRead`
- `useParticipants(applicationId)`, `useCreateParticipant`, `useDeleteParticipant`
- `useResources(applicationId)`, `useCreateResource`, `useDeleteResource`
- `useCreateDecision`
- `useSystemUsers`
- `useCurrentSystemUser`

ログインユーザー解決:

- Code Apps SDK `getContext().user.objectId` で Entra object ID を取得する。
- `systemuser.azureactivedirectoryobjectid` で Dataverse `systemuserid` に変換する。
- 現在ユーザーを解決できない場合、ユーザー依存の hooks は全件取得にフォールバックせず空配列を返す。

## 6. Lookup 名前解決

`_xxx_value` + `useMemo` Map パターンを使う。生成 SDK の Lookup 表示名フィールドには依存しない。

必要な Map:

| Lookup 値                    | Map の元データ      | 利用箇所                                       |
| ---------------------------- | ------------------- | ---------------------------------------------- |
| `_ds_categoryid_value`       | `ds_category`       | 申請一覧、判断キュー、申請詳細                 |
| `_ds_deciderid_value`        | `systemuser`        | 申請一覧、ダッシュボード、判断キュー           |
| `_ds_applicationid_value`    | `ds_application`    | メッセージ、関係者、判断、関連資料、メンション |
| `_ds_messageid_value`        | `ds_message`        | メンション                                     |
| `_ds_targetuserid_value`     | `systemuser`        | メンション                                     |
| `_ds_userid_value`           | `systemuser`        | 関係者                                         |
| `_ds_addedbyid_value`        | `systemuser`        | 関係者                                         |
| `_ds_decisionoptionid_value` | `ds_decisionoption` | 判断                                           |

## 7. 追加するデータソース

初回 Code Apps デプロイ後、`--org-url` を明示して以下の Dataverse データソースを追加する。

1. `ds_application`
2. `ds_category`
3. `ds_decisionoption`
4. `ds_message`
5. `ds_mention`
6. `ds_participant`
7. `ds_decision`
8. `ds_applicationresource`
9. `systemuser`

## 8. 実装メモ

- スターターに含まれるインシデント・資産画面は残さず、DecisionFlow 用画面に置き換える。
- 既存の再利用可能コンポーネントは活用する: `ListTable`, `FormModal`, `InlineEditTable`, `LoadingSkeletonGrid`, `Sidebar`, `ModeToggle`, shadcn/ui プリミティブ。
- キュー列や幅制約のあるカードリストでは `ScrollArea` を避け、`div overflow-y-auto overflow-x-hidden` を使う。
- カードはコンパクトに保ち、ページセクションをカードの入れ子にしない。
- フォームは controlled fields とし、タイトル、判断理由、判断選択肢など必須項目は明示的に検証する。
- 関連資料はリンク専用とし、Code Apps では `ds_url` を登録する。過去設計の File 列、種別、ステータス、差し替え関連列は cleanup migration で削除する。

## 9. 承認後のビルド・デプロイ計画

1. 対象環境で Code Apps が有効化されていることを確認する。
2. `.env` の `ENVIRONMENT_ID` に対応する PAC 認証プロファイルがあることを確認する。
3. `power.config.json` が存在しない、または環境固有の初期化が必要な場合のみ `npx power-apps init` を実行する。
4. 依存関係が不足している場合は `npm install` を実行する。
5. `npm run build` を実行する。
6. 初回デプロイは `pac code push -env {ENVIRONMENT_ID} -s {SOLUTION_NAME}` を使う。
7. `npx power-apps add-data-source --api-id dataverse --resource-name {table} --org-url {DATAVERSE_URL}` で Dataverse データソースを追加する。
8. 日本語表示名のサニタイズで失敗する場合は `node patch-nameutils.cjs` を実行する。
9. 承認済み設計に沿って UI とサービス層を実装する。
10. `npm run build` を実行し、`pac code push -env {ENVIRONMENT_ID} -s {SOLUTION_NAME}` で再デプロイする。

## 10. 実装状況

- 初回 Code Apps デプロイ済み: `DecisionFlow`
- Dataverse データソース追加済み: `ds_application`, `ds_category`, `ds_decisionoption`, `ds_message`, `ds_mention`, `ds_participant`, `ds_decision`, `ds_applicationresource`, `systemuser`
- 実装済み画面: ダッシュボード、申請リスト、判断キュー、申請詳細、メンション、関連資料、マスタ管理
- 実装済みサービス層: [src/services/dataverse-service.ts](../src/services/dataverse-service.ts) と [src/hooks/use-decisionflow.ts](../src/hooks/use-decisionflow.ts)
- 実装済みフォーム/操作:
  - [x] 申請作成・編集
  - [x] 申請者が選べる下書き/提出ステージのラジオ選択
  - [x] 提出済み申請は通常編集を禁止し、下書きに戻す操作だけ許可
  - [x] 判断確定時の判断済み自動更新
  - [x] 申請削除（確認モーダル付き）
  - [x] 申請作成時の申請者/判断者 `ds_participant` 自動登録
  - [x] 申請詳細からの関係者追加（役割選択UIなし、常に Contributor=関係者で固定。`addParticipantWithMention` で system message + mention を自動作成し、追加対象者へ通知）
  - [x] 申請詳細からの関係者削除（確認モーダル付き）
  - [x] 申請詳細の会話タブからコメント投稿時にメンション作成。各メッセージに付随する mention 先を `@ユーザー名` バッジで表示
  - [x] 関連資料カードにアップロード者と日時を表示
  - [x] 判断者選択肢を `DecisionFlow-Deciders` Dataverse チームメンバーのみに絞り込み（`useDeciders()`）
  - [x] 概要タブの旧 AI 要約カードを廃止
  - [x] 判断タブをモバイル 1 カラム / デスクトップ 2 カラムにし、右側に AI 判断カードを配置
  - [x] `AI判断更新` ボタンと Submitted 保存時の `Application_GenerateAiDecision` 起動
  - [x] 関連資料リンク追加
  - [x] 関連資料リンクの確認付き削除
  - [x] カテゴリの追加・更新・削除（ds_Admin のみアクセス可能、サイドバー表示制御 + ルートガード）
  - [x] 判断選択肢は固定システムマスタとして参照のみ表示（承認 / 却下 / 差し戻し）
  - [x] 申請者本人向け編集ボタン
  - [x] Choice フィルタ
  - [x] 関係者削除処理中の waiting 表示（権限除外/フロー待ち用スピナー）
  - [x] Power Automate による関係者追加時の `GrantAccess`
  - [x] Power Automate による関係者削除前の `RevokeAccess`
- 関係者削除は、`Participant_PreDelete_RevokeAccess` フロー成功後に `ds_participant` を削除する。フロー失敗時は関係者レコードを残し、削除失敗として通知する。ただしデモ用 `Support User` など、対象ユーザー自体が有効な共有権限を持てず `has insufficient privileges ... PrincipalId` が返る場合は、共有解除済み相当として関係者レコード削除を続行する。
- 関係者削除中は `OperationWaitOverlay` で画面操作をブロックし、Power Automate の処理待ちであることを表示する。
- `Participant_PreDelete_RevokeAccess` は `npx power-apps add-flow` で SDK 生成済み。アクセス制御フローを UI 編集しやすい Compose payload + 接続参照版に再作成したため、2026-05-02 に新しいフロー ID で再同期済み。サービス層は [src/services/dataverse-service.ts](../src/services/dataverse-service.ts) で `Run` の `ok` が `true`、または共有解除不要と判定できる既知エラーの場合のみ削除する。
- cleanup migration: [scripts/migrate_cleanup_obsolete_metadata.py](../scripts/migrate_cleanup_obsolete_metadata.py) で旧関連資料列と旧ステージ Choice 値を削除する
- 検証済み: `npm test -- src/lib/decisionflow-utils.test.ts src/lib/ai-decision.test.ts`, `py -m unittest tests.test_ai_decision tests.test_notification_flows tests.test_access_flows tests.test_security_roles`, `npm run build`, `npx power-apps push`
- 次の確認対象: Power Apps 実機での SDK postMessage 動作、申請削除、関連資料リンク追加・削除、関係者追加後の共有権限、関係者削除後の共有解除、メンション通知フロー、Dataverse セキュリティロール適用後の操作表示
- 未実装/要調整: 関係者追加・削除ボタンなどの UI 表示制御は、現時点では Dataverse 権限を最終判定として扱う。必要に応じて Code Apps 側の表示制御を追加する。マスタ管理は `useIsAdmin()` でサイドバー表示・ルートアクセス両方を制御済み。
