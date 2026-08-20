# デプロイ手順（デプロイ版）の検証ログ

`docs/DEPLOY_SETUP.md` に書く手順は「何をするか」だけに絞っている。**なぜその手順になったか、
何を試して何が失敗したか**はこちらに置く。DEPLOY_SETUP.md の該当箇所からリンクする。

## Step 8-1: AI Builder プロンプトは API 経由で新規作成・更新できない（2026-08-20〜21）

`ResourceDescription` / `ResourceDescriptionText` / `DecisionRecommendation` の3本とも、
この環境の権限では API 経由の新規作成・更新が最後まで通らないことを実測で確認した。

**新規作成:** `msdyn_aimodel` 作成 → training 用 `msdyn_aiconfigurations` 作成 →
`AIModelPublish`（training を公開）までは通るが、最後の run 側
`PublishAIConfiguration` が `400 Missing privilege definition: prvWritemsdyn_AIModel`
で落ちる。エラー後も model/run config ともに Draft のままで活性化されていないことまで
確認済み（HTTP ステータスだけで判断せず、レコードの実状態を読んで確定した）。

**既存プロンプトへの直接更新:** `msdyn_aiconfigurations(id)` へ `msdyn_customconfiguration`
を PATCH すると `400 Unexpected parameter(s) msdyn_customconfiguration`
（本番の run config へ自分自身の現在値を書き戻すテストで確認。内容は変化していないので
実害なし）。

本番の `DecisionRecommendation`（MinoDev2）を `msdyn_name` の一時リネームで退避し、
同じ経路を踏ませても同様に失敗し、リネームを戻して復元したことも確認済み。

潰した経路の詳細は `scripts/deploy_resource_description_flow.py` の `_require_prompt` と
`scripts/deploy_ai_decision.py` の `deploy_ai_prompt` の docstring に一次情報として残してある。

`deploy_ai_decision.py` の `deploy_ai_prompt()` には、この調査で見つけた実害バグも修正した。
旧コードは更新失敗時に `delete_ai_prompt_model()` で**動いている本物を削除したあと**、
確実に失敗する新規作成コードへ突入していた。削除せず `RuntimeError` で止まるよう書き換え、
確実に失敗する新規作成コードごと削除した。

## Step 8-1: register_ai_prompts.py の検証（2026-08-20〜21、MinoDev2）

`AddSolutionComponent` の `ComponentType`（AI Model 用）は標準の `componenttype` グローバル
選択肢に載っていない。MinoDev2 で実際に UI から「既存を追加」したプロンプトの
`solutioncomponent` 行を読んで `401`（`componenttypename` = 「AI プロジェクト」）と実測した。

追加の冪等性: 既に追加済みの状態で `AddSolutionComponent` を呼んでも成功し、
`solutioncomponentid` が変わらず重複行が増えないことを確認済み。

検査ロジックは自前で持たず、`deploy_resource_description_flow.py` /
`deploy_ai_decision.py` の検査関数（`find_ai_prompt` / `find_text_prompt` /
`deploy_ai_prompt`）をそのまま呼ぶ構成にした。バッチ失敗時の挙動も実測済み: 1本
（`DecisionRecommendation`）だけ意図的に見つからない状態（リネームで退避）にしても、
残り2本は正常に検査・ソリューション登録まで完了したうえで、失敗した1本だけがエラーに
まとまることを確認した。

## Step 8-2: SharePoint 接続参照の循環依存（2026-08-21）

`deploy_resource_description_flow.py` の旧 `find_sharepoint_connection_reference()` は
SharePoint の Dataverse `connectionreferences` 行を**読むだけ**で、無ければ
「`npx power-apps add-flow` で作られるか、手で作成してください」というエラーで落ちていた。
しかし `add-flow`（Step 9-3）はこのフロー自身の `workflowid` を要求するため、**フローを
初めて作るときは循環していた**。

MinoruEnv・MinoDev2 とも反復開発の過程で接続参照が既に存在していたため、この経路は
これまで一度も踏まれたことが無かった。手順書の記述は動作確認済みであることを意味しない
（実際に真っさらな状態で辿ると落ちる経路が、記述の完成度とは無関係に残っていた）。

同じ Step 8-2 で先に走る `deploy_access_flows.py` / `deploy_notification_flows.py` /
`deploy_ai_decision.py` は、いずれも「既存の生の接続から接続参照を自動作成/更新する」
`ensure_connection_reference()` パターンを持っていた。SharePoint だけこれが無かったのは
一貫性の欠如で、意図的な制約ではなかった。同じパターンを追加して解消した
（`ensure_sharepoint_connection_reference()`）。

**実装中に踏んだ失敗:** 固定の論理名（`{PREFIX}_{connector}` 形式、他スクリプトと同じ
命名規則）で無条件に作成する実装にしたところ、MinoDev2 に既に `add-flow` が作った別名
（`ds_sharedsharepointonline_5ebaa`、ランダムサフィックス付き）の接続参照があったため、
**同じ生の接続を指す重複行**を作ってしまった（同一 `connectionid` を指すので実害は無いが、
フローの束ね先が意図せず変わった）。「固定名で作る前にコネクタに紐づく既存の束ね済み参照を
まず探す」に直し、`$orderby=createdon asc` で決定的に最古の行を優先するようにして解消した。
書き込みを伴う自動化コードは「既存を壊さず安全に冪等か」を実際に2回走らせて確認すること。

## Step 10: Copilot Studio の push は新環境の bot に向かない（2026-08-20）

`pac copilot push --project-dir copilot/DecisionFlowAssistant` は `.mcs/conn.json`
（gitignore 対象、`push`/`pull` がどの bot に向けるかを持つ）に依存する。このリポジトリの
`.mcs/conn.json` は開発時に使っていた既存 bot を指したままで、新環境向けに配布されていない。

### 検証1: 本物と同じ環境に使い捨て bot を作り push

Copilot Studio UI で `ZZZ_BindingTest_DeleteMe` という使い捨て agent を MinoDev2 に作成し、
`pac copilot clone --bot <新bot> --environment <MinoDev2> --output-dir <temp>` で新 bot 向けの
`.mcs/conn.json` を生成。clone が作ったひな形コンテンツを削除し、リポジトリの実際の
`copilot/DecisionFlowAssistant/` の中身（`.mcs/` 以外）をコピーして push したところ、

```
DataverseBadRequestException: [0x80072013:ExportKeyInvalidCreate]
schemaname: ds_DecisionFlowAssistant.topic.__0ncZDgZ_Stnsh3i00IUVu が既存レコードと衝突
```

トピック YAML のコンポーネント識別子（schemaname）には元の bot の識別子
（`ds_DecisionFlowAssistant`）が焼き込まれており、これは Dataverse 環境内でグローバルに
一意。同じ MinoDev2 環境に本物の `DecisionFlow Assistant` bot が既に存在するため衝突した。

### 検証2: 衝突要因を除いても別の失敗（同日中に追加検証）

「スキーマ名の衝突が原因なら、衝突しない状況を作れば通るはず」という仮説を検証した。
使い捨て bot A を作り、A 自身のスキーマ名（`cr46d_ZZZMechTestADeleteMe`）でコンテンツを
持たせたあと、**A を削除してそのスキーマ名を環境から完全に空にした**（`botcomponent` に
残骸が無いことも確認）うえで、別の使い捨て bot B へその内容を push した。結果、
**スキーマ名の衝突ではない、別の失敗**にぶつかった:

```
Error: Remote changes conflict with local changes. Run 'pac copilot pull' first to resolve conflicts before pushing.
```

指示どおり `pull` すると、`pull` は差分適用のため**差し替えたはずの内容が bot B 自身の
実際のリモート状態（既定のスキーマ名・トピック）で上書きされ**、A の内容は消えた。

### 結論

2つの独立した失敗モード（スキーマ名衝突／同期 conflict）が同じ帰結に収束した — `push` は
対象 bot 自身の同期履歴（`changetoken`）と食い違う内容を単純には受け付けない。「clone して
`.mcs/` だけ差し替えて push する」という迂回策は、**衝突要因を除いても機能しなかった**。

正真正銘の新規環境（`ds_DecisionFlowAssistant` 相当の bot が一度も存在しない環境）で
この手順自体が通るかは、まだ実機確認できていない（そこまで確かめるには実際に新しい環境を
用意する必要があり、今回は行っていない）。新規作成直後の bot（`changetoken` が何とも
競合していない状態）に対する一発目の push が通るかは、次に確かめる価値がある論点。

現時点で確実に動く代替手段は、**新環境では YAML を持ち込まず、`docs/DEPLOY_SETUP.md` の
「エージェント定義の正本」の内容を見ながら Copilot Studio の UI で手動構築する**こと。
`docs/PLAN.md` の Phase 3 チェックリストは実際に手動構築したときの記録であり、
「移送手順」を意味するものではない（引用時に誤って移送手順であるかのように書いたため、
ここで訂正しておく）。

検証はすべて MinoDev2 上の使い捨て bot（Playwright でUI操作して作成）で行い、検証後は
UI から削除して後始末済み。リポジトリの実ファイル・本物の `DecisionFlow Assistant` には
一切触れていない。
