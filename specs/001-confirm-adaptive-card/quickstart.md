# Quickstart: Copilot Studio チャットで Adaptive Card 判断確定

## 1. Preconditions

- `.env` が設定済み（Dataverse / Solution / Copilot 関連）
- 既存の DecisionFlow 資産がデプロイ済み
  - Dataverse テーブル
  - Notification flows
  - Copilot Studio Agent
- 対象案件が `Submitted` 状態で存在
- 案件に割り当て済みの判断者ユーザーが存在

### Local setup variables

- `DATAVERSE_URL`, `TENANT_ID`, `ENVIRONMENT_ID`: Dataverse / Flow / Copilot Studio API 用
- `SOLUTION_NAME=DecisionSupport`, `PUBLISHER_PREFIX=ds`: すべての追加テーブル・フロー・Bot component を同一ソリューションへ含めるために使用
- `BOT_ID`: Copilot Studio UI で作成済みの DecisionFlow Assistant の Bot URL または GUID
- `ds_DecisionFlowAppBaseUrl`: 通知メールから Code Apps 申請詳細へ誘導する場合に使うソリューション環境変数
- `ds_CopilotTeamsAppId`: 通知メールから Copilot Studio Teams チャットへ誘導する場合に使うソリューション環境変数

### Copilot Studio wiring assumptions

- Adaptive Card の表示 JSON は Copilot Studio の専用 Topic / カード応答定義で管理する
- Power Automate 側の `issue_decision_card` と `confirm_decision` は `scripts/deploy_adaptive_card_decision_confirmation.py` で作成済み。Copilot Studio 側では、この 2 本をツールとして追加するだけでよい。カード表示 JSON は Power Automate では所有しない
- `scripts/deploy_copilot_agent.py` で botcomponents YAML デプロイが難しい環境では、専用 Topic と Power Automate ツール追加を手動設定し、結果を `docs/PLAN.md` に記録する
- Teams 互換性のため、カードは schema 1.5 と `Action.Submit` のみを使う

### Implementation notes

- `ds_decision` 作成を判断確定の正本イベントとする
- Code Apps から作成された `ds_decision` では、画面の分かりやすさを優先して Code Apps が同じ操作内で `ds_application.ds_stage` も即時更新する。`Decision_OnCreated` は通知と最終整合を担当する
- Copilot Studio の submit 処理は `ds_application` を直接更新しない。カード処理内で行う Dataverse 書き込みは `ds_decision` 作成と `ds_decisioncard` 消費に限定し、ステージ変更と通知は `Decision_OnCreated` が担当する
- `Decision_OnCreated` は判断選択肢名が `差し戻し` の場合だけ `Draft` に戻し、同時に `ds_submittedat` をクリアする。それ以外は `Decided` にする
- `ds_decisioncard` は `Issued` / `Consumed` / `Superseded` / `Expired` でカード発行・単回利用・再発行無効化を追跡する
- MVP の first-write-wins は lookup-then-insert 方式で定義する。ただし差し戻し後の再提出を妨げないよう、`confirm_decision` は現在の `ds_submittedat` 以降に作られた `ds_decision` だけを重複判断として扱う。厳密な同時実行制御が必要になった場合は `ds_application` ETag / optimistic concurrency を追加検討する

## 2. Implement

### Environment deployment commands

以下はエージェントが 2026-05-19 に対象環境へ適用済み。

```powershell
c:/Users/rnmgy/PowerAppsCodeApps/DecisionSupport/.venv/Scripts/python.exe scripts/setup_dataverse.py
c:/Users/rnmgy/PowerAppsCodeApps/DecisionSupport/.venv/Scripts/python.exe scripts/setup_security_roles.py
c:/Users/rnmgy/PowerAppsCodeApps/DecisionSupport/.venv/Scripts/python.exe scripts/deploy_notification_flows.py
c:/Users/rnmgy/PowerAppsCodeApps/DecisionSupport/.venv/Scripts/python.exe scripts/deploy_adaptive_card_decision_confirmation.py
```

適用済みの範囲:

- `ds_decisioncard` テーブル、列、`ds_application` Lookup、ソリューション含有
- `ds_decisioncard` を含む `ds_Applicant` / `ds_Decider` / `ds_Admin` 権限
- `Decision_OnCreated` のステージ整合を含む通知フロー再デプロイと Flow API start
- `deploy_adaptive_card_decision_confirmation.py` による `issue_decision_card` / `confirm_decision` agent flow 2 本の作成、有効化、Flow API start

未適用の範囲:

- Copilot Studio 専用 Topic の作成
- Copilot Studio への `issue_decision_card` / `confirm_decision` ツール追加
- Teams チャネルでの Adaptive Card 表示・submit 実機確認

### Copilot Studio manual wiring

Copilot Studio の Topic / tool は UI で手動追加する。API で Topic / tool を直接作ると接続・プロビジョニング不整合が起きやすいため、MVP では UI 設定を正とする。

#### 1. エージェントを開く

1. Power Apps または Copilot Studio で対象環境を開く
1. ソリューション `DecisionSupport` を開く
1. `DecisionFlow Assistant` を開く
1. 生成オーケストレーションが有効であることを確認する
1. 認証が Microsoft Entra ID ユーザー認証であることを確認する

#### 2. 作成済み Power Automate ツールフローを確認する

以下の 2 本は `scripts/deploy_adaptive_card_decision_confirmation.py` で作成済み。Copilot Studio の Topic から **ツールとして呼ぶ Power Automate agent flow**であり、Power Automate だけで自動起動する通知フローではない。

どちらも `When an agent calls the flow` 相当の `Skills` トリガーと、`Respond to the agent` 相当の `Skills` レスポンスを持つ。Power Automate デザイナーで `Manually trigger a flow` と表示される場合は古い定義を開いているため、一覧へ戻って最新の Workflow ID のフローを開き直す。

Copilot Studio UI でフローを新規作成しない。既存フローをツールとして追加する。

| フロー名              | Copilot Studio で呼ぶタイミング     | 役割                                                                         |
| --------------------- | ----------------------------------- | ---------------------------------------------------------------------------- |
| `issue_decision_card` | Adaptive Card を表示する直前        | `ds_decisioncard` を `Issued` で作り、`cardInstanceId` を返す                |
| `confirm_decision`    | Adaptive Card の `Action.Submit` 後 | 入力を検証し、`ds_decision` を作成し、`ds_decisioncard` を `Consumed` にする |

作成済みフロー ID:

| フロー名              | Workflow ID                            |
| --------------------- | -------------------------------------- |
| `issue_decision_card` | `c37ed747-9153-f111-a824-3833c5de99c8` |
| `confirm_decision`    | `f8502159-9153-f111-a824-3833c5de99c8` |

##### 2-1. `issue_decision_card` のツール入力・出力

目的: カードを表示する前にカード発行レコードを作り、Topic に `cardInstanceId` を返す。

ツール入力:

| 入力名             | 型   | 値の渡し元                                                                                                                   |
| ------------------ | ---- | ---------------------------------------------------------------------------------------------------------------------------- |
| `applicationId`    | Text | Topic で特定した `ds_applicationid`                                                                                          |
| `actorAadObjectId` | Text | Copilot Studio の認証済みユーザーの Entra object id。取得できない場合は空でも MVP 検証は可能だが、US2 認可強化時に必須化する |
| `actorUpn`         | Text | Copilot Studio の認証済みユーザーの UPN / メールアドレス                                                                     |

ツール出力:

| 出力名           | 型   | 用途                                        |
| ---------------- | ---- | ------------------------------------------- |
| `applicationId`  | Text | 後続の `confirm_decision` にそのまま渡す    |
| `cardInstanceId` | Text | Adaptive Card の hidden data として保持する |

このフローの内部構成はスクリプト管理とする。Copilot Studio UI や Power Automate UI で同じフローを手動再作成しない。

##### 2-2. `confirm_decision` のツール入力・出力

目的: submit payload を検証して `ds_decision` を作り、カードを消費済みにする。

ツール入力:

| 入力名             | 型   | 値の渡し元                                               |
| ------------------ | ---- | -------------------------------------------------------- |
| `applicationId`    | Text | Adaptive Card `data.applicationId`                       |
| `decisionOption`   | Text | Adaptive Card の `decisionOption` 入力                   |
| `rationale`        | Text | Adaptive Card の `rationale` 入力                        |
| `cardInstanceId`   | Text | Adaptive Card `data.cardInstanceId`                      |
| `actorAadObjectId` | Text | Copilot Studio の認証済みユーザーの Entra object id      |
| `actorUpn`         | Text | Copilot Studio の認証済みユーザーの UPN / メールアドレス |

`decisionOption` の値は Dataverse row ID ではなく、`承認` / `却下` / `差し戻し` のラベルを渡す。`confirm_decision` はフロー内部で `ds_decisionoption.ds_name` を検索して、対応する判断選択肢レコードに変換する。

ツール出力:

| 出力名             | 型   | 用途                                                               |
| ------------------ | ---- | ------------------------------------------------------------------ |
| `status`           | Text | `succeeded` / `already_processed` / `invalid_target` / `forbidden` |
| `applicationId`    | Text | 対象申請 ID                                                        |
| `decisionRecordId` | Text | `succeeded` の場合に作成された `ds_decision` ID                    |
| `decidedAt`        | Text | `succeeded` の場合の確定日時                                       |
| `message`          | Text | Topic で利用者に表示するメッセージ                                 |

内部では、現在ユーザー解決、Submitted 状態確認、判断者一致確認、判断選択肢確認、判断理由必須確認、発行済みカード確認、現在提出サイクル内の既存判断確認、`ds_decision` 作成、`ds_decisioncard` 消費を行う。この内部構成もスクリプト管理とし、Power Automate UI で手動再作成しない。

このフローでも `ds_application` は更新しない。`ds_decision` 作成後のステージ変更と通知は、デプロイ済みの `Decision_OnCreated` が担当する。

##### 2-3. Copilot Studio に 2 本をツールとして追加する

1. Copilot Studio の `DecisionFlow Assistant` に戻る
1. `ツール` を開く
1. `ツールの追加` から既存の Power Automate フローを選ぶ
1. `issue_decision_card` と `confirm_decision` を追加する
1. それぞれの入力説明を、上記の入力表に合わせて設定する
1. Topic 内では、カード表示前に `issue_decision_card`、submit 後に `confirm_decision` を呼ぶ
1. 保存後、エージェントを公開する

#### 3. 専用 Topic を作成する

<!-- markdownlint-disable MD060 -->

ここで作る Topic は、申請検索や AI 判断生成を担う汎用 Topic ではない。**カードを表示して submit を受け取り、作成済み agent flow 2 本を順番に呼ぶだけの薄い Topic** として作る。

##### 3-1. Topic を YAML で作る

この Topic は YAML を正として作る。UI でノードを個別に積み上げると、Adaptive Card の submit 変数が record として扱われず、`Identifier not recognized` が出やすい。まずコードビューへ YAML を貼り、ツール呼び出しノードだけ Copilot Studio が生成した YAML に差し替える。

テンプレート: [decision-confirmation.topic.template.yaml](decision-confirmation.topic.template.yaml)

YAML 内の `#` で始まる行はコメントなので、貼り付け時に削除しなくてよい。コメントを外して有効化する行もない。差し替えが必要なのは、以下の 3 ノードだけ。

| 差し替え対象ノード ID         | 差し替える内容                                  |
| ----------------------------- | ----------------------------------------------- |
| `callIssueDecisionCard`       | `issue_decision_card` ツール呼び出しノード YAML |
| `askDecisionWithAdaptiveCard` | `Ask with Adaptive Card` ノード YAML            |
| `callConfirmDecision`         | `confirm_decision` ツール呼び出しノード YAML    |

この 3 つはコメントを外すのではなく、該当する `- kind: ...` ノード全体を、Copilot Studio が生成した実ノード YAML で置き換える。

手順:

1. Copilot Studio で `DecisionFlow Assistant` を開く
1. `ツール` で `issue_decision_card` と `confirm_decision` が追加済みであることを確認する
1. 左メニューの `Topics` を開き、`+ Add a topic` を選ぶ
1. `From blank` / `空白から作成` を選ぶ
1. Topic 名を `Decision confirmation adaptive card` にする
1. コードビューを開く
1. [decision-confirmation.topic.template.yaml](decision-confirmation.topic.template.yaml) の内容を貼り付ける
1. YAML 内の `callIssueDecisionCard` ノードを、Copilot Studio が生成した `issue_decision_card` ツール呼び出しノード YAML に差し替える
1. YAML 内の `askDecisionWithAdaptiveCard` ノードを、`Ask with Adaptive Card` ノードが生成した YAML に差し替える
1. YAML 内の `callConfirmDecision` ノードを、Copilot Studio が生成した `confirm_decision` ツール呼び出しノード YAML に差し替える
1. 保存してデザイナーに戻り、赤い検証エラーがないことを確認する

Trigger phrases を併用する場合は以下を追加する。

Trigger phrases:

- `判断を確定`
- `この申請を承認`
- `この申請を却下`
- `この申請を差し戻し`
- `Adaptive Card で判断`

`modelDescription` が生成オーケストレーション向けの説明になる。ただし、テスト画面で呼び出しが安定しない場合は、Trigger phrases も追加する。

##### 3-2. 申請 ID は Topic 入力として受け取る

判断確定 Topic は、利用者に `ds_applicationid` を直接入力させない。生成オーケストレーションが会話中の Dataverse 申請情報、または Code Apps 申請詳細リンクから `applicationId` を埋めてから Topic を実行する。

YAML テンプレートでは `applicationId` を Topic input として宣言し、`Topic.applicationId` を後続の `issue_decision_card` / `confirm_decision` に渡す。`Topic.applicationId` が空の場合はカード発行前に停止し、申請詳細画面または申請リンクから再実行するよう案内する。

Copilot Studio の Topic 詳細で `applicationId` input を確認し、生成オーケストレーションの入力設定は「Dynamically fill with the best option」にする。これにより、Dataverse 申請レコードや申請リンクが会話コンテキストにある場合は自動で値が入る。

`applicationId` が見つからない場合もユーザーに GUID を質問しない。入力の追加設定で、再質問回数は `Don't repeat`、`No valid entity found` は空値のまま次へ進む設定にする。Topic 先頭の `validateApplicationContext` が空値を検知し、「申請詳細画面または申請リンクから再実行してください」と案内して停止する。

##### 3-3. 実行者情報を用意する

`issue_decision_card` と `confirm_decision` には実行者情報を渡す。Copilot Studio の UI で選べるシステム変数名は環境やキャンバスの版で表示が揺れるため、以下の優先順で設定する。

| Topic 変数            | 推奨値                                                    | MVP 代替                                     |
| --------------------- | --------------------------------------------------------- | -------------------------------------------- |
| `varActorUpn`         | 認証済みユーザーの UPN / メールアドレスを表すシステム変数 | 自分のメールアドレスを一時的な固定値で入れる |
| `varActorAadObjectId` | 認証済みユーザーの Entra object ID を表すシステム変数     | 空文字 `""`                                  |

MVP の `confirm_decision` は `actorAadObjectId` が空の場合、`actorUpn` から `systemuser` を検索する。まずは `varActorUpn` が正しく渡ることを優先する。

##### 3-4. `issue_decision_card` を呼ぶ

YAML テンプレートの `TOOL NODE PLACEHOLDER: issue_decision_card` を、Copilot Studio が生成したツール呼び出しノードへ差し替える。入力は以下のように割り当てる。

| `issue_decision_card` 入力 | 渡す値                |
| -------------------------- | --------------------- |
| `applicationId`            | `Topic.applicationId` |
| `actorAadObjectId`         | `varActorAadObjectId` |
| `actorUpn`                 | `varActorUpn`         |

出力 `cardInstanceId` は Topic 変数 `varCardInstanceId` に保存する。出力 `applicationId` は `Topic.applicationId` のままでよい。

##### 3-5. Adaptive Card を表示して submit を受ける

YAML テンプレートの `askDecisionWithAdaptiveCard` を、`Ask with Adaptive Card` ノードが生成した YAML へ差し替える。[4. Adaptive Card JSON を設定する](#4-adaptive-card-json-を設定する) の JSON を使い、JSON 内の以下の値を Topic 変数に置き換える。

| JSON placeholder     | 置き換える値          |
| -------------------- | --------------------- |
| `{{applicationId}}`  | `Topic.applicationId` |
| `{{cardInstanceId}}` | `varCardInstanceId`   |

判断選択肢の `value` は Dataverse row ID ではなく、`承認` / `却下` / `差し戻し` のラベルを入れる。`confirm_decision` はこのラベルを受け取り、フロー内部で `ds_decisionoption.ds_name` から対応する判断選択肢レコードを検索する。

submit 結果の `decisionOption` は `varDecisionOption`、`rationale` は `varRationale` に保存する。この 2 つの値の出どころは、Adaptive Card JSON 内の `Input.ChoiceSet` の `id: decisionOption` と `Input.Text` の `id: rationale` である。`Topic.rationale` や `Topic.decisionOption` という変数が最初から存在するわけではない。

Copilot Studio の Adaptive Card ノードは、カード JSON の `Input.*.id` から出力変数を自動生成する。`Topic.varDecisionSubmit.decisionOption` のように submit 結果をレコードとしてドット参照しない。Power Fx で `Identifier not recognized` が出る場合は、以下の順で直す。

1. Adaptive Card ノードの `Properties` を開く
1. `Edit Schema` を開き、`decisionOption` と `rationale` が Text 出力として存在することを確認する。存在しない場合は追加する
1. Adaptive Card ノードの生成 YAML または出力設定で、`decisionOption` 出力を `Topic.varDecisionOption` に保存する
1. 同様に `rationale` 出力を `Topic.varRationale` に保存する
1. 生成された出力変数名が `decisionOption` / `rationale` と異なる場合は、画面に表示される実際の出力を使う

正常な割り当ては、概念的には以下の形になる。

| Topic 変数          | 保存する Adaptive Card 出力                            |
| ------------------- | ------------------------------------------------------ |
| `varDecisionOption` | Adaptive Card ノードが生成した `decisionOption` の出力 |
| `varRationale`      | Adaptive Card ノードが生成した `rationale` の出力      |

判断選択肢 row ID を Topic に埋め込む必要はない。ラベルは `confirm_decision` 側で `ds_decisionoption` の active な `ds_name` と照合する。

###### `decisionOption` が空で `FlowActionBadRequest` になる場合

`confirm_decision` の呼び出しで `decisionOption` が空または空白という `FlowActionBadRequest` が出る場合、Power Automate フローではなく Topic 側の Adaptive Card 出力が `Topic.varDecisionOption` に保存されていない可能性が高い。

確認する箇所:

1. Adaptive Card JSON の `Input.ChoiceSet.id` が `decisionOption` である
1. Adaptive Card ノードの `Edit Schema` に `decisionOption` と `rationale` が Text 出力として存在する
1. Adaptive Card ノードの出力で `decisionOption` を `Topic.varDecisionOption`、`rationale` を `Topic.varRationale` に保存している
1. `confirm_decision` ツール呼び出しの `decisionOption` 入力に `Topic.varDecisionOption` を渡している

テンプレートでは、`confirm_decision` 呼び出し前に `decisionOption` / `rationale` の空値ガードを入れている。このガードに入る場合は、フロー呼び出し前の Topic 変数割り当てを直す。

##### 3-6. `confirm_decision` を呼ぶ

YAML テンプレートの `TOOL NODE PLACEHOLDER: confirm_decision` を、Copilot Studio が生成したツール呼び出しノードへ差し替える。入力は以下のように割り当てる。

| `confirm_decision` 入力 | 渡す値                |
| ----------------------- | --------------------- |
| `applicationId`         | `Topic.applicationId` |
| `decisionOption`        | `varDecisionOption`   |
| `rationale`             | `varRationale`        |
| `cardInstanceId`        | `varCardInstanceId`   |
| `actorAadObjectId`      | `varActorAadObjectId` |
| `actorUpn`              | `varActorUpn`         |

出力 `status` は `varConfirmStatus`、`message` は `varConfirmMessage` に保存する。必要に応じて `decisionRecordId` と `decidedAt` も保存する。

##### 3-7. status ごとに応答する

YAML テンプレートでは `ConditionGroup` で `varConfirmStatus` を分岐条件にする。応答は以下の通り。

| `varConfirmStatus`  | 応答文                                                                                   |
| ------------------- | ---------------------------------------------------------------------------------------- |
| `succeeded`         | `判断を確定しました。案件ステージと通知は Decision_OnCreated で反映されます。`           |
| `already_processed` | `この案件は既に判断確定済みです。最新状態を Code Apps で確認してください。`              |
| `invalid_target`    | `対象案件が無効、または提出済みではありません。Code Apps で案件状態を確認してください。` |
| `forbidden`         | `この案件の判断者として割り当てられていないため、判断を確定できません。`                 |

迷った場合は、まず分岐を作らず `varConfirmMessage` をそのまま Send message で表示してもよい。正常系の疎通確認後に分岐を追加する。

<!-- markdownlint-enable MD060 -->

#### 4. Adaptive Card JSON を設定する

カードは Copilot Studio Topic 側に保持する。Power Automate flow はカード表示 JSON を所有しない。

最小カード構造:

```json
{
  "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
  "type": "AdaptiveCard",
  "version": "1.5",
  "body": [
    {
      "type": "TextBlock",
      "text": "判断を確定",
      "weight": "Bolder",
      "size": "Medium"
    },
    {
      "type": "Input.ChoiceSet",
      "id": "decisionOption",
      "label": "判断選択肢",
      "isRequired": true,
      "errorMessage": "判断選択肢を選択してください。",
      "style": "expanded",
      "choices": [
        { "title": "承認", "value": "承認" },
        { "title": "却下", "value": "却下" },
        { "title": "差し戻し", "value": "差し戻し" }
      ]
    },
    {
      "type": "Input.Text",
      "id": "rationale",
      "label": "判断理由",
      "isRequired": true,
      "errorMessage": "判断理由を入力してください。",
      "isMultiline": true,
      "maxLength": 20000
    }
  ],
  "actions": [
    {
      "type": "Action.Submit",
      "title": "確定",
      "data": {
        "action": "confirm_decision",
        "applicationId": "{{applicationId}}",
        "cardInstanceId": "{{cardInstanceId}}"
      }
    }
  ]
}
```

`{{applicationId}}`, `{{cardInstanceId}}` は Topic 内の変数で置換する。判断選択肢は row ID ではなく `承認` / `却下` / `差し戻し` のラベル値を送る。

#### 5. 応答メッセージを設定する

`succeeded`:

- 「判断を確定しました。案件ステージと通知は Decision_OnCreated で反映されます。」

`already_processed`:

- 「この案件は既に判断確定済みです。最新状態を Code Apps で確認してください。」

`invalid_target`:

- 「対象案件が無効、または提出済みではありません。Code Apps で案件状態を確認してください。」

`forbidden`:

- 「この案件の判断者として割り当てられていないため、判断を確定できません。」

#### 6. Publish と Teams 確認

1. Topic とツール設定の保存後、Copilot Studio でエージェントを公開する
1. Teams チャネルで `DecisionFlow Assistant` を開く
1. Submitted 状態の申請を指定して判断確定カードを表示する
1. `承認` / `却下` / `差し戻し` のいずれかと判断理由を入力して submit する
1. Dataverse で `ds_decision` が作成され、`ds_decisioncard` が `Consumed` になることを確認する
1. Code Apps で案件ステージが判断作成直後に反映され、`Decision_OnCreated` による通知と最終整合も実行されることを確認する

## 3. Validate (minimum)

- 正常系
  - 割り当て済み判断者が、判断選択肢（承認・却下・差し戻し）と判断理由を入力してカードで確定できる
  - 案件詳細画面に最新判断結果が反映される
  - 既存通知が送信される
- 入力検証系
  - 判断選択肢未選択の場合は確定できない
  - 判断理由が空の場合は確定できない
- Code Apps 整合系
  - Code Apps で判断を作成した場合は画面上のステージが即時反映され、同じ Power Automate 整合フローで通知と最終整合も実行される
  - Copilot Studio で判断を作成した場合も Code Apps と同じステージ判定になる
  - Code Apps で判断作成直後にステージ Badge が更新され、Dataverse の `ds_application.ds_stage` も同じ操作内で更新される
- 競合系
  - 同時操作で最初の成功のみ反映、後続は既処理エラー
    - MVP は lookup-then-insert 方式で検証し、本番化時の厳密ロックは別途検討する
- 認可系
  - 未割り当て判断者は拒否される
- カード再利用系
  - 同一カード再submitは拒否される
  - 同一案件でカード再発行後、古いカードの submit は拒否される

### MVP validation scope

2026-05-19 時点では、環境スクリプト反映、Power Automate ツールフロー 2 本の作成、Copilot Studio UI の専用 Topic / ツール wiring、Teams 実機確認まで完了済み。

- まず T061 では、正常系、入力必須、`ds_decision` 作成、`ds_decisioncard` 消費、`Decision_OnCreated` によるステージ整合を確認する
- 未割り当てユーザー拒否、古いカード拒否、再利用カード拒否の詳細 validation は US2 実装でフロー定義テストとデプロイ反映済み
- Code Apps の即時ステージ更新は `DataverseService.createDecision()` のテストと build で検証済み

## 4. Suggested test commands

```powershell
npm run build
npm test
py -m unittest tests.test_adaptive_card_decision_confirmation tests.test_copilot_agent tests.test_notification_flows tests.test_security_roles
```

## 5. Rollback guidance

- 本機能の Copilot submit ツールフローを無効化
- 判断後整合フローを無効化する場合、Code Apps では即時ステージ更新は継続するが通知と最終整合が止まり、Copilot Studio 由来の判断ではステージ反映も止まる。復旧まで `Decision_OnCreated` を再有効化するか、暫定補正手順を `docs/PLAN.md` に記録する
- 既存環境へ `ds_decisioncard` を追加する場合は [../../docs/MIGRATIONS.md](../../docs/MIGRATIONS.md) に適用手順と結果を記録する
- `ds_decisioncard` を削除する rollback は既存カード発行履歴の監査影響があるため、削除ではなく関連フロー/Topic の無効化を優先する
- 画面側のトリガー導線を feature flag で停止（導入する場合）
- 監査影響があるため、誤確定はデータ補正手順を `docs/PLAN.md` に記録
