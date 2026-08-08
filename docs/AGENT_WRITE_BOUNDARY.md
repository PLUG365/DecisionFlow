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

**クラウドへの反映は確認済み（2026-08-08）。** `push`（6 changes）のあと `pull` を戻したら 0 changes で、`actions/` に残っているのは読み取り専用の `Get_ApplicationDetailUrl` だけだった。クラウド側にツール登録が残っていれば、pull が 2 本を書き戻す。**ただしこれは成果物の確認**であって、挙動の確認ではない。

**未確認: 実機で 1 回も動かしていない。** 会話投稿と違い、`AdaptiveCardPrompt` → `Action.Submit` → 2 本目の `InvokeFlowAction` の経路がツール登録なしで成立するかは実測していない。`zdI.mcs.yml` は TaskDialog コンポーネントを参照しておらず（`data.action: "confirm_decision"` は出力バインドが受け取る payload であって呼び出し先の指定ではない）成立するはずだが、**YAML が push を通ることは成果物の確認にすぎない**。次の確認が済むまで、この節を「実測確認済み」に格上げしない。

確認は**2つに分ける**。壊れ方が違うため、まとめて合否にしない。

| # | 見るもの | 何が分かるか | 落ちたときの意味 |
| --- | --- | --- | --- |
| 1 | 下書きチャットで判断確定を頼み、**カードが出る**／完了メッセージがトピックの固定文（`判断を確定しました。案件ステージと通知は Decision_OnCreated で反映されます。`）である | トピックに到達したか | **経路の問題**。ツール登録を外した結果、`modelDescription` だけが入口になった。下の懸念を参照 |
| 2 | `confirm_decision` の実行履歴で、トリガー入力に `actorAadObjectId` が入っている | なりすましが塞がったか | ツール登録が実際には消えていない |

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
| 判断確定の実行者の出どころ | 同上（`zdI.mcs.yml` の束縛と、action YAML 2 本が存在しないこと） | **未実施。** 判断確定を 1 回通し、`confirm_decision` の実行履歴で `actorAadObjectId` を確認する |
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
