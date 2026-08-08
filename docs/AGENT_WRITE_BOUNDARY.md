# エージェントの書き込み境界

DecisionFlow Assistant が Dataverse へ書き込む範囲を固定する。**この表を変更せずに書き込み系のツールを追加してはならない。**

- 対象: Copilot Studio エージェント `ds_DecisionFlowAssistant` と、そのツールとして登録された Power Automate agent flow
- 適用: Teams 単独利用と Code Apps 右サイドパネルの**両方**（経路で防御を変えない）
- 最終更新: 2026-08-07

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

## 検証

| 対象 | 自動テスト | 実機確認 |
| --- | --- | --- |
| 判断確定の6段ゲート | `tests/test_adaptive_card_decision_confirmation.py` | 判断者以外・未提出・理由なし・カード再利用の各拒否 |
| 会話投稿の関係者チェック | フロー定義のテストで assert | 関係者でないユーザーからの投稿が拒否される |
| 実行者の出どころ | `tests/test_copilot_agent.py` | Copilot Studio UI の下書きチャットで、投稿が実行者名義になること |
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
