# DecisionFlow Backlog

> 後回しにした作業、移行時の保留、実機確認で見つかった追跡事項をここに集約する。

## 運用ルール

- 新しい未対応事項はこのファイルに追加し、関連ファイルや発生日を添える。
- 仕様判断が必要なものは `Decision needed`、実装待ちは `Todo`、外部手順待ちは `Manual` として記録する。
- 完了した項目は `Done` に移し、対応日と検証方法を残す。

## Open

- [ ] Manual: `DecisionFlow-Deciders` グループチーム紐付け（2026-05-01）  
       Power Platform 管理センターで Dataverse グループチームを作成し、`ds_Decider` ロールを付与する。
- [ ] Todo: Power Apps 実機操作確認（2026-05-01）  
       Code Apps 上で申請作成、下書き/提出ラジオ、申請削除、関連資料リンク追加/削除、関係者追加/削除、判断確定を確認する。
- [ ] Todo: SDK データソース再生成（2026-05-01）  
       cleanup migration 実行後、必要に応じて `npx power-apps add-data-source` を再実行して `src/generated/` を環境に同期する。
- [ ] Todo: Power Automate アクセス制御の実機確認（2026-05-02）  
       関係者追加後に対象申請を閲覧できること、関係者削除後に閲覧できないこと、`RevokeAccess` 失敗時に関係者レコードが残ることを Power Apps 実機で確認する。
- [ ] Todo: Power Automate 通知フローの実機配信確認（2026-05-03）  
       申請提出、判断作成、メンション作成、停滞リマインドで Outlook メールが対象ユーザーへ届くことを確認する。Teams チャネル投稿を使う場合は Teams チャネルリンクから `TEAMS_NOTIFICATION_GROUP_ID` / `TEAMS_NOTIFICATION_CHANNEL_ID` を設定して再デプロイする。
- [ ] Todo: AI 判断生成の実機確認（2026-05-03）  
       Power Apps 実機で Submitted 保存時に `Application_GenerateAiDecision` が実行され、判断タブの AI 判断カードに申請概要、会話概要、推奨判断、コメント、リスク、類似案件が保存・表示されることを確認する。あわせて「AI判断更新」ボタンで再生成できることを確認する。
- [ ] Todo: Code Apps の権限別操作表示制御（2026-05-03）  
       関係者追加・削除などの操作ボタンを、設計方針どおり申請者/判断者/共同判断者へ限定するか確認し、必要なら UI 側にも表示制御を追加する。Dataverse セキュリティロールを最終判定とする前提は維持する。

## Done

- 2026-05-04: Code Apps の画面名を「自分の申請」から「申請リスト」に変更し、判断キューを現在ユーザーが判断者に設定されている申請だけ表示するようにした。検証: `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `npx power-apps push`
- 2026-05-03: 旧 AI 要約メタデータを cleanup。`ds_application.ds_aisummary` / `ds_application.ds_summaryupdatedat` と `ds_message.ds_kind=100000004 (AISummary)` を設計・Code Apps 型・Dataverse setup から削除し、実環境にも `py scripts/migrate_cleanup_old_ai_summary.py --apply` で適用。旧列の値 2 件は `artifacts/migrations/old_ai_summary_backup_*.json` に退避。検証: `py scripts/migrate_cleanup_old_ai_summary.py`, `py scripts/migrate_cleanup_old_ai_summary.py --apply`, Dataverse メタデータ確認, `py -m unittest tests.test_ai_decision tests.test_notification_flows tests.test_access_flows tests.test_security_roles`, `npm run build`, `npx power-apps push`
- 2026-05-03: ドキュメント整合性チェックを実施し、現在実装済みの DecisionFlow 状態と将来予定を整理。Copilot Studio / `IssueExtraction` を Phase 3 以降の予定として明記し、通知チャネル、メンション時の挙動、関連資料追加場所、AI 判断フロー再デプロイ手順、README のプロジェクト説明を実装実態に合わせた。検証: stale 語句検索、Markdown diagnostics
- 2026-05-03: AI 判断生成の Code Apps/UI/スクリプト実装を追加。`ds_application` に AI 申請概要、AI 会話概要、AI 推奨判断、AI 判断コメント、AI 判断根拠、AI 判断更新日時の列定義を追加し、判断タブ右側に AI 判断カードを配置。Submitted 保存時と「AI判断更新」ボタンから同じ `Application_GenerateAiDecision` を呼ぶ。検証: `npm test -- src/lib/decisionflow-utils.test.ts src/lib/ai-decision.test.ts`, `py -m unittest tests.test_ai_decision tests.test_notification_flows tests.test_access_flows tests.test_security_roles`, `npm run build`
- 2026-05-03: AI 判断生成を実環境へデプロイ。Dataverse AI 判断列を追加し、AI Builder `DecisionRecommendation` と Power Apps V2 フロー `Application_GenerateAiDecision` を作成・有効化。`npx power-apps add-flow` 後に Code Apps を再ビルドして push。検証: `py scripts/setup_dataverse.py`, `py scripts/deploy_ai_decision.py`, `npx power-apps add-flow --flow-id c690997e-4e46-f111-bec6-7c1e525c11fc`, `npm run build`, `npx power-apps push`
- 2026-05-03: AI 判断生成の過去類似案件候補を、同一カテゴリの判断済み最大 30 件 + 補助候補の直近判断済み最大 10 件へ変更。候補には申請本文全文を含めず、AI 申請概要・AI 推奨判断・AI 判断コメントを渡してトークン消費を抑える。既存フローは削除せず workflow を更新し、認証不備のある Dataverse 接続候補はスキップして有効な接続参照で更新するようにした。検証: `py scripts/deploy_ai_decision.py`, 実環境 `workflows.clientdata` で `$top=30/10` と `ds_body` 非含有を確認, `py -m unittest tests.test_ai_decision tests.test_notification_flows tests.test_access_flows tests.test_security_roles`
- 2026-05-03: 通知フロー 3 本を実装・有効化。`Application_OnSubmitted` は Dataverse Create or Update トリガーで、作成時点で Submitted の申請と既存申請の提出更新を同じフローで通知する。検証: `py -m unittest tests.test_notification_flows tests.test_access_flows tests.test_security_roles`, `py scripts/deploy_notification_flows.py`
- 2026-05-03: `Application_StalledReminder` を追加。毎日 9:00 JST に Submitted 申請を走査し、希望期限超過または `ds_submittedat` から3日以上経過した申請を判断者へ Outlook メール通知する。停滞判定には `modifiedon` を使わない。検証: `py -m unittest tests.test_notification_flows`, `py scripts/deploy_notification_flows.py`
- 2026-05-03: 通知フローの Dataverse トリガーが実行履歴を作らない事象を調査し、Flow Management API `/start` を既存 3 本に実行。再デプロイ時も自動で `/start` するようスクリプト化。検証: `py -m unittest tests.test_notification_flows`
- 2026-05-03: アクセス制御フローにも Flow Management API `/start` を追加し、既存の `Participant_OnCreated_GrantAccess` / `Participant_PreDelete_RevokeAccess` にも実行。検証: `py -m unittest tests.test_access_flows`
- 2026-05-03: 申請詳細の会話タブでコメント投稿時に申請者・判断者・関係者からメンション先を選び、`ds_message` に紐づく `ds_mention` を作成できるようにした。あわせてダッシュボードの Recharts Tooltip をライト/ダーク共通の半透明背景に変更。検証: `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `npx power-apps push`
- 2026-05-03: 最新判断の判断選択肢名を申請リスト・判断キュー・申請詳細の判断タブに表示。判断選択肢が「差し戻し」の場合は、判断作成後に申請ステージを Draft へ戻すようにした。検証: `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `npx power-apps push`
- 2026-05-03: 差し戻し後に再提出された申請で、過去判断が残っていても新しい判断を追加できるよう判断フォーム表示条件を修正。通知フローがイベントを拾っていなかったため、既存通知フロー 3 本へ `/start` を再実行し、`--start-existing` オプションを追加。検証: `py scripts/deploy_notification_flows.py --start-existing`, `py -m unittest tests.test_notification_flows`, `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `npx power-apps push`
- 2026-05-03: 提出済み申請の通常編集を禁止し、申請者本人は下書きへ戻す操作だけできるようにした。検証: `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `npx power-apps push`

| 完了日     | 項目                                                         | 検証                                                                                                                                     |
| ---------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-05-01 | 申請ステージを下書き/提出済み/判断済みに整理                 | `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `pac code push`                                                       |
| 2026-05-01 | 関連資料をリンク専用 UI に整理                               | `npm run build`, `pac code push`                                                                                                         |
| 2026-05-01 | cleanup migration で旧関連資料列・旧ステージ Choice を削除   | `py scripts/migrate_cleanup_obsolete_metadata.py --apply`, ステージ Choice 値確認                                                        |
| 2026-05-01 | 申請詳細から関係者を確認付きで削除できるようにした           | `npm run build`, `pac code push`                                                                                                         |
| 2026-05-02 | 関係者削除処理中の waiting 表示を追加                        | `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `pac code push`                                                       |
| 2026-05-02 | Phase 2.5 Power Automate アクセス制御設計を承認              | 削除前 revoke 方式で実装へ移行                                                                                                           |
| 2026-05-02 | 関係者追加時の `GrantAccess` フローを実装・有効化            | `py scripts/deploy_access_flows.py`, `py -m unittest tests.test_access_flows`                                                            |
| 2026-05-02 | 関係者削除前の `RevokeAccess` フローと Code Apps 連携を実装  | `npx power-apps add-flow`, `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `npx power-apps push`                      |
| 2026-05-02 | アクセス制御フローを接続参照版で再作成                       | `py scripts/deploy_access_flows.py`, `workflows.clientdata` で `runtimeSource: embedded` と `item` を確認                                |
| 2026-05-02 | アクセス制御フローの payload を UI 編集可能な Compose に分離 | `py -m unittest tests.test_access_flows`, `py scripts/deploy_access_flows.py`, `workflows.clientdata` で `Build_*_access_payload` を確認 |
