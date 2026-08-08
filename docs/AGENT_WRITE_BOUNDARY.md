# エージェントの書き込み境界

DecisionFlow Assistant が Dataverse へ書き込む範囲を固定する。**この表を変更せずに書き込み系のツールを追加してはならない。**

- 対象: Copilot Studio エージェント `ds_DecisionFlowAssistant` と、そのツールとして登録された Power Automate agent flow
- 適用: Teams 単独利用と Code Apps 右サイドパネルの**両方**（経路で防御を変えない）
- 最終更新: 2026-08-08

## 前提: 実行者の身元はトリガー引数で渡る

agent flow は**接続参照の identity** で実行される。エンドユーザーの権限では実行されない。「誰の操作として扱うか」は、フローのトリガー引数 `actorAadObjectId` / `actorUpn` で決まる。

したがって次が最重要のルールになる。

> **実行者の識別子は、Copilot Studio の認証済みユーザー変数（`System.User.Id` / `System.User.PrincipalName`）からのみ渡す。**
> 会話の本文、モデルの推論結果、ユーザーが打った文字列から組み立ててはならない。

これを破ると、エージェントを説得するだけで他人として書き込めるようになる。ツールを追加するときは、トリガー引数の出どころを必ず確認する。

## 許可する操作

| 操作 | 経路 | 必須ゲート |
| --- | --- | --- |
| 申請・会話・資料・判断・マスタの読み取り | エージェント直接 | Dataverse の行アクセス（利用者が閲覧できる範囲に限る） |
| 判断コメントのドラフト生成 | エージェント直接 | なし（書き込まないため） |
| 会話への投稿（`ds_message`） | agent flow | 実行者が解決できる / 実行者がその申請の**関係者**である / 本文が空でない |
| AI判断の再生成 | agent flow | 実行者が解決できる / 実行者がその申請の関係者である |
| 判断の確定（`ds_decision`） | `issue_decision_card` → `confirm_decision` | 下記6段すべて |

### 判断確定の6段ゲート（既存・変更しない）

1. `Validate_user_found` — 実行者が systemuser として解決できる
2. `Validate_decision_option_found` — 判断選択肢名が実在する
3. `Validate_submitted_application` — 申請が提出済みである
4. `Validate_actor_is_decider` — 実行者がその申請の判断者である
5. `Validate_rationale_exists` — 判断理由が空でない
6. `Validate_current_issued_card` — 現在の提出サイクルで発行された未使用のカードが存在する

**パネルから判断を確定する場合も、必ず `issue_decision_card` を経由して同じ6段を通す。** カードを介さない確定経路を作らない。カードは二重判断防止の実体でもある。

## 禁止する操作

| 操作 | 理由 |
| --- | --- |
| 関係者の追加・削除（`ds_participant`） | `Participant_OnCreated_GrantAccess` / `Participant_PreDelete_RevokeAccess` が Share API で閲覧権を付与・剥奪する。アクセス制御そのものであり、エージェントに触らせない |
| 申請の削除 | 不可逆 |
| 申請の作成・編集 | 申請者の意思表示そのもの。代筆の是非を決めていない（保留） |
| マスタ（`ds_category` / `ds_decisionoption`）の変更 | 全申請へ影響する。判断選択肢はフロー・カード・プロンプトが名称で参照している |
| セキュリティロール、環境設定、Solution import / publish | 範囲外 |
| 本番環境に対する一切の書き込み | 開発環境限定 |

## 守る不変条件

1. 1つの提出サイクルにつき判断は1件（カードの消費で担保）
2. 判断者以外は判断を確定できない
3. 提出済み以外の申請は判断できない
4. 理由なしの判断は作られない
5. エージェントは、実行者が閲覧できない申請を操作できない
6. 経路（Teams / パネル）によって防御の強さが変わらない

## 既知の弱点

**Code Apps 側の `createDecision` はカードを見ていない。** アプリの判断タブから確定する経路は、6段ゲートのうちカード消費チェック（6）を通らない。`docs/PLAN.md` §4 が「first-write-wins MVP。厳密な同時実行制御は ETag / optimistic concurrency を将来検討」と記録しているとおり、現状は緩い。

パネルとアプリ画面を同時に開けるようになったことで、この非対称は踏みやすくなった。**両経路の防御を揃えるのは別タスクとする**（本番投入前に判断が必要）。

**トピックを足しても、ツール登録された agent flow は隠れない。**

2026-08-08 に実測した。`post_application_message` をツール登録したまま「この申請にコメントして」と依頼すると、生成オーケストレーションは**トピックを経由せずツールを直接呼んだ**。判定した根拠は3つ:

| 観察 | トピック経由なら | 実際 |
| --- | --- | --- |
| 完了メッセージ | トピックの固定文 | モデルの生成文 |
| 投稿前の確認 | 無い（即 InvokeFlowAction） | 表形式で確認を求めた |
| `actorAadObjectId` | 必ず送る | payload に無い |

つまり `actorUpn` はモデルが埋めていた。値がたまたま正しかっただけで、`System.User.PrincipalName` からの束縛は一度も働いていない。Instructions の禁止文も、トピックの `modelDescription` も、迂回を止めなかった。

**対処（2026-08-08）: `post_application_message` のツール登録を外し、トピックを唯一の入口にした。実測で塞がったことを確認済み。**

- `actions/post_application_message.mcs.yml` を削除して `pac copilot push`。ツール登録（`botcomponents` の `.action.` 行）はクラウドからも消える
- **`InvokeFlowAction` はツール登録が無くても `flowId` 直指定で動く**（着手前の最大の未知だった）
- ツール登録が消えると Instructions 経由の「投稿前の同意取得」も効かなくなるため、トピック側に `Question`（`BooleanPrebuiltEntity`）で確認ステップを実装した
- `tests/test_copilot_agent.py` が、この action YAML が**存在しないこと**と確認ステップの存在を固定する。ポータルでツール登録し直して `pull` すると、テストが落ちて気づける

修正後のトリガー payload（`ds_message` 8件目、フロー実行 Succeeded）:

```json
{
  "actorAadObjectId": "43691e79-...",   ← 修正前は欠落していた
  "actorUpn": "minoru@minoru365.com",
  "applicationId": "05badc87-...",
  "body": "4回目の確認です"
}
```

完了メッセージもトピックの固定文になった。実行者はモデルが触れない経路で決まっている。

### 判断確定（`zdI`）にも同じ手当てをした（2026-08-08・実機未確認）

こちらは会話投稿より**悪い**。理由は、ツール登録されているのが 2 本あることにある。

| 段 | 内容 | 直接呼びで通ってしまう理由 |
| --- | --- | --- |
| 4 | `Validate_actor_is_decider` | 実行者は**渡された引数**。判断者の identity を作文すれば一致する |
| 6 | `Validate_current_issued_card` | `issue_decision_card` も直接呼べるので、**同じ作文した実行者でカードを発行**すれば満たせる |

つまり「カードの発行と消費」は二重判断を防ぐが、**なりすましは防がない**。カードは攻撃者自身が発行できる。会話投稿の穴が「他人の名前でコメントされる」だったのに対し、こちらは**他人の名前で判断が確定する**。より深刻なので、同じ手当てを入れた。

- `actions/confirm_decision.mcs.yml` と `actions/issue_decision_card.mcs.yml` を削除。**2 本とも外さないと意味がない**（片方だけ残すと連鎖の入口が残る）
- `Get_ApplicationDetailUrl` は読み取り専用なのでツール登録のまま
- トピック `zdI` は既に `System.User.PrincipalName` / `System.User.Id` から束縛しており、`inputType` は `applicationId` だけ。変更不要
- `InvokeFlowAction` は `flowId` 直指定で動く（会話投稿で実測済み）
- 手順書（`docs/DEPLOY_SETUP.md` 12-2〜12-3、`specs/001-confirm-adaptive-card/quickstart.md`）がツール登録を指示していたので、そこも書き換えた。**手順書を直さないと、次のセットアップで穴が開き直る**
- `specs/001-confirm-adaptive-card/decision-confirmation.topic.template.yaml` を削除した。正本が YAML へ移ったあとも残っていた写しで、実際に空欄チェックの式が本体と分岐していた（`=Or(IsBlank(a), IsBlank(b))` と `=IsBlank(a) || IsBlank(b)`）。6段ゲートのテストはこの写しを読んでおり、デプロイされないファイルを守ったまま緑だった。テストの参照先を `topics/zdI.mcs.yml` へ移した

**ツール登録が消えたことは Dataverse で直接確認済み（2026-08-09）。** `botcomponent` を読むと、このエージェントの `.action.` 行は**1件しかない**。

```sql
SELECT name, componenttype, schemaname FROM botcomponent
WHERE schemaname LIKE 'ds_DecisionFlowAssistant%'
```

| schemaname | 種別 |
| --- | --- |
| `ds_DecisionFlowAssistant.action.Get_ApplicationDetailUrl` | ツール登録（読み取り専用。残す） |
| `ds_DecisionFlowAssistant.topic.zdI` | 判断確定トピック |
| `ds_DecisionFlowAssistant.topic.postApplicationMessage` | 会話へ投稿トピック |

`action.confirm_decision` / `action.issue_decision_card` / `action.post_application_message` は**存在しない**。CLI の往復（`push` 6 changes → `pull` 0 changes）とは独立に、データの側で確認できている。

**これでなりすましの経路は塞がったと言える。** 呼び出せるコンポーネントが無い以上、生成オーケストレーションはフローを直接呼べない。実行者はトピックの `SetVariable` 経由でしか入らない。

### 実機確認の結果（2026-08-09、下書きチャット）

Draft の申請を対象にした。`Validate_submitted_application` が弾くので `ds_decision` は作られず通知メールも飛ばない。**それでもフローは実行されるので、トリガー入力は観測できる。**

**確認2: 実行者の束縛は成立している。** `confirm_decision` の実行履歴（run `08584154018934607825762989810CU01`、`ChannelId:pva-studio`）のトリガー payload:

```json
{
  "actorAadObjectId": "43691e79-13b4-4b4a-be2c-d5707a8d9cf7",
  "actorUpn": "minoru@minoru365.com",
  "applicationId": "a14587cd-5046-f111-bec6-7c1e525c11fc",
  "cardInstanceId": "6a0933d6-1d5c-4035-94a5-1624ac5707e2",
  "decisionOption": "承認"
}
```

`actorAadObjectId` は認証済みユーザーの Entra Object Id と一致する。`System.User.Id` からの束縛が働いている。

**カード経路も成立している。** `AdaptiveCardPrompt` → `Action.Submit` → 2 本目の `InvokeFlowAction` → status 分岐 → 固定文（`対象案件が無効、または提出済みではありません。`＝`sendInvalidTarget`）まで通った。**ツール登録なしで動く。** 着手前の最大の未知が消えた。

**確認1: ルーティングは言い方に依存する。** これは落ちた。

| 入力 | 結果 |
| --- | --- |
| 「〇〇」の申請を判断したい | ❌ ナレッジ検索が先に走り、トピックに来ない |
| 判断を確定 | ✅ トピック起動。`applicationId` は会話文脈から補完される |
| 申請ID &lt;GUID&gt; を承認したい | ✅ トピック起動 |

Instructions に `## 判断の確定` を足し、`最終判断は Code Apps の判断タブで確定してください` を削除した（2026-08-09、push 済み）。効果はあり、応答の文面は「判断確定まで支援できます」に変わった。**ただしナレッジ検索が先に走る経路は残っている。** 申請を特定する意図の発話は、トピックより先にナレッジ検索へ吸われることがある。

次の手は `zdI` に Trigger phrases（`判断を確定` / `この申請を承認` / `この申請を却下` / `この申請を差し戻し`）を足すこと。`intent: {}` のままで `modelDescription` だけに頼っている状態。**未実施。**

### 見つかった欠陥: `issue_decision_card` に検証が無い

実機確認の副産物。`scripts/deploy_adaptive_card_decision_confirmation.py` の `build_issue_decision_card_clientdata` を読むと、アクションは次の5つだけで、**検証が1つも無い**。

1. `Compose_cardInstanceId`
2. `List_prior_issued_decisioncards`
3. `Supersede_prior_issued_decisioncards`
4. `Create_decisioncard`
5. `Return_card_context`

`ds_application` が Submitted かどうかも、実行者が判断者かどうかも見ていない。実測でも、**Draft の申請に対してカードが発行された**（`ds_decisioncard` a38ee74d、2026-08-09T01:00:41、Issued）。

この文書と `DEPLOY_SETUP.md` は「`ds_application` が `Submitted` かつ実行者が割り当て判断者であることを確認し」と書いていた。**誤り。**

**影響の範囲（確定）**

- **6段ゲートの6段目は、それ自体はゲートではない。** 「発行済みカードの存在」は実行者自身がいつでも作れる。ツール登録を外す判断の根拠にした推論が、実装レベルで裏付けられた形になる
- **なりすましは成立しない。** 判断の確定は `confirm_decision` の6段（実行者解決・Submitted・判断者一致）が守る。カードを持っていても、判断者でなければ確定できない
- **他人のカードへの妨害も成立しない。** `_actor_card_filter` は `ds_actoraadobjectid` / `ds_actorupn` で絞るため、`Supersede_prior_issued_decisioncards` が触るのは**実行者自身のカードだけ**
- 実害は「Submitted でない申請・判断者でない実行者にも `ds_decisioncard` 行が作られる」こと。ゴミ行と、文書が実装より強い保証を約束している状態

## 設計: `issue_decision_card` に検証を入れる（2026-08-09 固定）

認可に触る変更のため、実装前にここで範囲を固定する。**この表を変えずに実装を広げない。**

### 許可する状態と操作 / 拒否する状態と操作

| # | 状態 | カード発行 | 返す status |
| --- | --- | --- | --- |
| 1 | 実行者が systemuser として解決できない | 拒否 | `forbidden` |
| 2 | 申請が取得できない | 拒否 | `invalid_target` |
| 3 | 申請が `Submitted`（100000001）でない | 拒否 | `invalid_target` |
| 4 | 実行者が当該申請の判断者でない | 拒否 | `forbidden` |
| 5 | 1〜4 をすべて満たす | 許可（自分の未使用カードを Superseded にして新規発行） | `issued` |

判定順は 1 → 2 → 3 → 4。**式と失敗メッセージは `confirm_decision` と同じものを使うが、順序は同一にできない。** `confirm_decision` は 実行者 → 判断選択肢 → 申請 → 判断者 の順だが、`issue_decision_card` のトリガーには `decisionOption` が無いため、判断選択肢の段は存在しない。ここを探して迷わないように書いておく。

**#2 は既存の穴をそのまま引き継ぐ。** `_get_record_action` は Dataverse の `GetItem` で、存在しない GUID を渡すとアクション自体が失敗する（空を返さない）。`confirm_decision` の `Validate_submitted_application` も `runAfter: {"Get_application": ["Succeeded"]}` しか持たないため、不正な GUID ではフローがエラー終了する。**今回はこの挙動に合わせるだけで、直さない。** 直すなら両方のフローに `Failed` 分岐を足す別タスクになる。

### 評価時点

- すべて `Create_decisioncard` の**前**。Dataverse の読み取りはコミット前の1回だけ
- 発行後に申請の状態が変わっても再検証しない。**確定時に `confirm_decision` が同じ4条件を再評価する**のが本来の防御線であり、この変更はその手前に同じ判定を重ねるもの（多層防御）
- トランザクションは無い。`Supersede` → `Create` の順で、`Create` が失敗すると自分の旧カードだけ Superseded になり手持ちゼロになる。**この性質は変更しない**（再発行すれば回復する。現状の挙動と同じ）

### 守る不変条件

1. Submitted でない申請にカードは発行されない
2. 判断者以外にカードは発行されない
3. 他人のカードは Superseded にされない（フィルタは実行者単位・**現状維持**）
4. 拒否されたとき、`ds_decisioncard` に行が増えない
5. `confirm_decision` の6段は変更しない。ここを弱めない
6. 拒否された場合、**トピックは Adaptive Card を表示しない**

### 6 が必要な理由

現在トピックは `issue_decision_card` の結果を見ていない（`output.binding` は `applicationId` / `cardInstanceId` のみ）。検証を足しただけでは、拒否されても `cardInstanceId` が空のままカードが表示され、利用者は入力してから `confirm_decision` に弾かれる。**フロー側だけ直すと、体験は今より悪くなる。** トピックに結果を渡して分岐させるところまでが1つの変更。

**変数名は `Topic.issueStatus` にする。`Topic.status` を使わない。** トピックの後段で `confirm_decision` の出力を `status: Topic.status` に束縛しており、同じ名前を使うと2本目の呼び出しが1本目の結果を上書きする。分岐が古い値を読む事故になる。

拒否メッセージは素の文字列か `{}` 補間で書く。`="..." & Topic.x` は評価されない（このセッションで2回踏んだ）。

### 担保

| 条件 | 自動テスト | 人間が実機で確認 |
| --- | --- | --- |
| 1〜4 の検証が正しい順序で存在する | フロー定義を読んで assert | — |
| 拒否時に行が増えない | `Create_decisioncard` の `runAfter` が最終検証の Succeeded であること | — |
| トピックが status で分岐する | `zdI.mcs.yml` を読んで assert | — |
| 実際に拒否される | — | **Draft の申請でカードが出ないこと**（今回出てしまった経路）。副作用なしで確認できる |
| 正常系が壊れていない | — | Submitted の申請で発行 → 確定が通ること。**申請の提出が必要で `Application_OnSubmitted` がメールを送る。承認を得てから行う** |

**正常系の実機確認には副作用がある。** 提出済みの申請が1件も無いため、確認するには申請を提出する必要があり、通知メールが飛ぶ。承認が取れないうちは**正常系は未確認のまま出す**ことになる。その場合は「拒否側だけ実測、正常系は自動テストのみ」と明記する。

`deploy_tool_flow` は既存フローを名前で引いて `workflowid` に PATCH するため、**再デプロイしても flowId は変わらない**（確認済み）。`zdI.mcs.yml` にハードコードした `flowId` とテストの assert は壊れない。

### 実装の結果（2026-08-09）

表のとおり実装した。ローカルのゲートは python 105 / vitest 106 / lint すべて緑。

- `issue_decision_card` に `List_current_user` → `Validate_user_found` → `Get_application` → `Validate_submitted_application` → `Validate_actor_is_decider` を追加。式と失敗メッセージは `confirm_decision` から流用
- 書き込み（`List_prior_issued_decisioncards` / `Supersede` / `Create_decisioncard`）を `Validate_actor_is_decider` の後ろへ移した。**不変条件4はこの `runAfter` の鎖だけで担保される**
- 拒否は `_return_and_stop` で Response + Terminate。返して終わりにしない
- レスポンスに `status` を追加（`issued` / `forbidden` / `invalid_target`）
- `zdI.mcs.yml` に `validateIssueResult` を追加し、`Topic.issueStatus <> "issued"` ならカードを出さずに終える

**まだクラウドへ反映していない。** デプロイと実機確認は下の「担保」に従う。

### 変更する範囲 / 変更しない範囲

| 変更する | 変更しない |
| --- | --- |
| `scripts/deploy_adaptive_card_decision_confirmation.py` の `build_issue_decision_card_clientdata` | `confirm_decision` の6段 |
| `copilot/DecisionFlowAssistant/topics/zdI.mcs.yml`（issue の status で分岐） | `ds_decisioncard` のスキーマ |
| `tests/test_adaptive_card_decision_confirmation.py` | Code Apps 側の `createDecision` |
| この文書と `DEPLOY_SETUP.md` の記述 | 他のフロー、セキュリティロール |

### 後片付け

上のテストで `ds_decisioncard` a38ee74d が Issued のまま残っている（Draft 申請 a14587cd に紐づく）。次に同じ実行者がカードを発行すれば Superseded になるので害はないが、テストの痕跡である。

**懸念: Instructions がトピックと逆を向いている。**

`agent.mcs.yml` には会話投稿の `## 会話への投稿` に相当する**判断確定の節が無い**。それどころか次の2箇所が Code Apps へ誘導している。

- `## 推奨判断と判断コメントドラフト`: 最後に「最終判断は Code Apps の判断タブで確定してください」と案内する
- `## 申請詳細リンク`: 判断確定、申請編集、関係者追加など Code Apps への誘導時は…

ツール登録があった間は、Instructions が何を言おうとオーケストレーションがフローを直接呼べたので、これは表面化しなかった。**外した今、入口は `zdI` の `modelDescription` だけ**（`intent: {}` で Trigger phrases も無い）。確認1が落ちたら、直すのは YAML ではなく Instructions 側。

なお、この誘導は Step 12 が**任意機能**である設計と整合してもいる。「チャットから判断確定できるようにするか」は、塞ぐ / 塞がないとは別の判断。

代替の入口は `specs/001-confirm-adaptive-card/quickstart.md` の Trigger phrases（`判断を確定` ほか）。ルーティングが不安定ならこれを足す。

**この懸念は push を止めない。** コンポーネントが存在しない以上、どのモデルからも呼べないため、なりすましは構造的に塞がっている。止まるのは「機能として動く」と言えるかどうか。

なりすましの実測（2026-08-08）は `Sonnet46` で取ったが、**この対処はモデルに依存しない**。存在しないコンポーネントは呼べない。ポータル側でモデルが `GPT55Chat` に変わっていたが、測り直しは要らない。ただし上のルーティングはモデル依存なので、確認1はモデルを変えたら取り直す。

**Code Apps パネルは対象外。** パネルは react-markdown で描いており、Adaptive Card をレンダリングできるか未確認。パネル経由の判断確定については、この変更で何かが良くなったとも悪くなったとも言えない。確認するまで、上の主張はポータル / Teams に限定する。

## 検証

| 対象 | 自動テスト | 実機確認 |
| --- | --- | --- |
| 判断確定の6段ゲート | `tests/test_adaptive_card_decision_confirmation.py` | 判断者以外・未提出・理由なし・カード再利用の各拒否 |
| 判断確定の実行者の出どころ | 同上（`zdI.mcs.yml` の束縛と、action YAML 2 本が存在しないこと） | **2026-08-09 実施済み。** `confirm_decision` のトリガー payload に `actorAadObjectId` が入っていることを確認 |
| 判断確定トピックのルーティング | — | **不十分。** 「〇〇の申請を判断したい」ではナレッジ検索に吸われる。Trigger phrases 未設定 |
| 会話投稿の関係者チェック | フロー定義のテストで assert | 関係者でないユーザーからの投稿が拒否される |
| 実行者の出どころ | `tests/test_copilot_agent.py` | 投稿後にフロー実行履歴のトリガー payload を見て、`actorAadObjectId` が入っていること |
| パネルを閉じたら反映 | — | エージェントが書き込んだ内容がパネルを閉じた後の画面に出る |

**実行者の出どころは、トピック YAML の2点をテストで固定している。**

- `SetVariable` が `System.User.PrincipalName` / `System.User.Id` から束縛していること
- `inputType` に `actorUpn` / `actorAadObjectId` が**無い**こと

2つ目が重要。`inputType` に置くと生成オーケストレーションが埋めてしまい、モデルが実行者を作文できる。

守れる理由は、Copilot Studio の定義が Dataverse 側だけでなく
`copilot/DecisionFlowAssistant/` の YAML として Git にあるため。
ただしテストが見るのは**ローカルの YAML**であり、クラウドの下書きではない。
UI で直接編集された場合は検知できないので、ツールやトピックを増やしたら
`pac copilot pull` で取り込んでから差分を見る。

| トピック | ファイル |
| --- | --- |
| 判断確定 | `copilot/DecisionFlowAssistant/topics/zdI.mcs.yml` |
| 会話へ投稿 | `copilot/DecisionFlowAssistant/topics/postApplicationMessage.mcs.yml` |

YAML にコメントは書けない（push / pull で CLI が再生成して消える）。設計意図はこの文書が持つ。
