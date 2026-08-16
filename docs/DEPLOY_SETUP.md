# セットアップ手順（デプロイ版）

ソースコードから DecisionFlow を構築・改修する場合の手順です。初めて環境を作る場合は、CLI 実行だけでは完結せず、Power Apps / Power Automate / Copilot Studio / Power Platform 管理センターでの手動操作が必要です。

> **エントリーポイント:** このドキュメントは [README.md](../README.md) から参照されます。Power Platform 環境の前提・セットアップ方法の選び方は README を参照してください。ソリューションインポート版だけで十分な場合はこのドキュメントは不要です。

## 1. 事前に必要なもの

- Windows + PowerShell
- Node.js 20 系以上
- Python 3.11 系以上
- PAC CLI
- 対象環境の Power Apps / Power Automate / Copilot Studio にアクセスできるアカウント
- README に記載の前提を満たす Power Platform 環境
- Copilot Studio を使う場合は、対象環境でエージェント作成権限があること

初回セットアップ前に依存関係をインストールします。

```powershell
npm install
pip install -r requirements.txt
```

## 2. 環境変数を作成する

`.env` はコミットしません。.env.example を複製して `.env` を作成し、まず以下を埋めます。

```powershell
Copy-Item .env.example .env
```

- `DATAVERSE_URL`, `TENANT_ID`, `ENVIRONMENT_ID`:
  Power Apps ポータル > 右上の ⚙ > セッション詳細
- `SOLUTION_NAME`, `PUBLISHER_PREFIX`:
  既定値のまま利用可
- `PAC_AUTH_PROFILE`:
  後続の `pac auth create` で作成するプロファイル名
- `BOT_ID`:
  Copilot Studio エージェント作成後に追記

値の取得方法の詳細は [.env.example](../.env.example) を参照してください。

## 3. 認証を準備する

### 3-1. PAC CLI 認証プロファイルを作成する

```powershell
pac auth create --name DecisionSupportProfile --environment {ENVIRONMENT_ID}
pac auth list
```

`.env` の `PAC_AUTH_PROFILE` と同じ名前で作成してください。

### 3-2. Python スクリプト用の認証を行う

以降の Python スクリプトは `auth_helper.py` 経由で認証します。初回実行時はブラウザまたはデバイスコード認証が走り、プロジェクト直下に `.auth_record.json` が生成されます。

> **Windows ユーザーへ:** Python スクリプト実行前に以下を設定してください。設定しないと絵文字を含む出力で `UnicodeEncodeError` が発生します。
>
> ```powershell
> $env:PYTHONUTF8="1"
> ```

## 4. Dataverse の事前チェックを行う

予定しているソリューション名・テーブル名が既存環境と衝突しないかを確認します。

```powershell
py scripts/check_dataverse_prereqs.py
```

`Collision detected` が出た場合は、そのまま進めずに `.env` の `SOLUTION_NAME` または `PUBLISHER_PREFIX` を見直してください。

## 5. Dataverse テーブルと初期データを構築する

以下で Publisher / Solution / テーブル / リレーション / Choice / 初期マスタを作成します。

```powershell
py scripts/setup_dataverse.py
```

このスクリプトは `.env` の `PUBLISHER_UNIQUE_NAME`, `PUBLISHER_DISPLAY_NAME`, `SOLUTION_DISPLAY_NAME` を必要に応じて `.env` に書き戻します。既定値のままで問題ありません。

## 6. セキュリティロールを作成する

```powershell
py scripts/setup_security_roles.py
```

この時点で `ds_Applicant`, `ds_Decider`, `ds_Admin` を Dataverse に作成します。

> **これらのロールは DecisionFlow の11テーブル分の権限しか持ちません。**
> ビュー・個人設定・メモといった基盤権限は含まないので、**`ds_Xxx` だけを割り当てても
> アプリは動きません。** 利用者には `Basic User`（または `Common Data Service User`）を
> 必ず併せて割り当ててください。Dataverse のロールは加算式です。
>
> 以前はロール作成時に環境の `Basic User` を丸ごとコピーして取り込んでいましたが、
> **移送元のベースラインを他テナントへ持ち込む**ことになり、権限の深度の可否が環境で違う場合に
> ソリューション import が失敗します（2026-08-12 に実測）。詳細は
> [UX_ROADMAP.md](UX_ROADMAP.md) の「ALM の実測ブロッカー」。

ロール権限の概要:

- `ds_Applicant`: カテゴリと判断選択肢は Read。カテゴリ別レギュレーションは申請画面で閲覧できるが編集できない
- `ds_Decider`: 判断コンテキストは Global Read。`ds_category` はレギュレーション管理のため Global Write を持つ
- `ds_Admin`: 全テーブル Global。マスタ管理 UI でカテゴリを編集できる

## 7. 管理センターで必須の手動設定を行う

このステップはスクリプトでは完結しません。

1. Microsoft Entra 管理センターで判断者用 M365 グループ `DecisionFlow-Deciders` を作成する
2. Power Platform 管理センターでそのグループを Dataverse のグループチームとして関連付ける
3. そのグループチームへ `ds_Decider` ロールを割り当てる
4. 必要に応じて申請者・管理者ユーザーへ `ds_Applicant`, `ds_Admin` を割り当てる
5. **DecisionFlow を使う全ユーザーが `Basic User`（または `Common Data Service User`）を
   保有していることを確認する。** `ds_Xxx` だけではアプリが動かない（上記5節の注記）

この手動設定を行わないと、判断者向けの閲覧・判断導線が期待通りに動作しません。

## 8. Power Automate 接続を確認してフローをデプロイする

通知フローとアクセス制御フローは、対象環境に接続が存在することを前提に動きます。事前に Power Automate UI で少なくとも以下の接続を作成してください。

- Microsoft Dataverse
- Office 365 Outlook
- Microsoft Teams

その後、以下の順でデプロイします。

```powershell
py scripts/deploy_access_flows.py
py scripts/deploy_notification_flows.py
py scripts/deploy_ai_decision.py
py scripts/deploy_delegation_flow.py --activate
py scripts/deploy_agent_message_flow.py
```

**`deploy_resource_description_flow.py` はここでは実行しません。** 先に AI Builder の
プロンプトを2本作る必要があります（次の 8-1）。手順を飛ばすと
`AI Builder プロンプト 'ResourceDescription' が見つかりません` で落ちます。

この順序で問題ありません。ソリューション `DecisionSupport` は [scripts/setup_dataverse.py](../scripts/setup_dataverse.py) が作成するため、Power Automate のデプロイは Code Apps より先に実行できます。

補足:

- `deploy_access_flows.py` は関係者追加・削除時の Dataverse 共有制御フローを作成します
- `deploy_notification_flows.py` は申請提出、判断確定、メンション、停滞リマインド通知を作成します
- `deploy_ai_decision.py` は AI Builder プロンプト連携フローを作成します
- `deploy_ai_decision.py` は `ds_category.ds_regulationtext` を prompt 入力へ追加し、AI結果は既存の `ds_application` AI列へ最新結果として上書き保存します
- `deploy_notification_flows.py` の各通知フローはバックグラウンド実行のため、Code Apps 側の `add-flow` は不要です
- `deploy_access_flows.py` の Revoke フローと `deploy_ai_decision.py` の AI 判断フローは、後続の Code Apps 手順で `npx power-apps add-flow` が必要です
- `deploy_delegation_flow.py` は担当変更要求フロー `Application_DelegationRequest_OnCreated` を作成します。**`--activate` を付けないと下書きのまま残ります**
- `deploy_agent_message_flow.py` は Copilot Studio エージェントが会話へ投稿する
  `post_application_message` を作成します。境界は [docs/AGENT_WRITE_BOUNDARY.md](AGENT_WRITE_BOUNDARY.md)

### 8-1. 関連資料の説明生成に使う AI Builder プロンプトを作る（G13）

**この2本は UI でしか作れません。** `code interpreter` を有効にしたプロンプトは
プラットフォームが発行する署名（`signature`）を持ち、`AIModelPublish` で再現できないためです
（潰した経路は `scripts/deploy_resource_description_flow.py` の `_require_prompt` の docstring に残してあります）。

[make.powerapps.com](https://make.powerapps.com) → **AI hub** → **プロンプト** → 独自のプロンプトを作成。

| プロンプト名 | code interpreter | 入力 | 出力 |
| --- | --- | --- | --- |
| `ResourceDescription` | **ON** | `File`（画像またはドキュメント） / `FileName`（テキスト） | Text |
| `ResourceDescriptionText` | **OFF** | `fileName` / `documentText`（どちらもテキスト） | Text |

**指示文の貼り付けは手作業です。スクリプトからは書き込めません。**
できるのは「正本を持っておいて、必要なときに表示する」ことだけです。

```powershell
py scripts/deploy_resource_description_flow.py
```

このコマンドは**検査だけ**を行い、形が違えば**貼るべき文面をそのまま出力して落ちます。**
出てきたものを AI Hub の指示欄へ貼り、`〔…〕` の位置に入力変数を差し込んでください。

検査するのは次の5点です。**どれも実行時まで見えない**ので手前で止めます。

| 見るもの | 通らないと何が起きるか |
| --- | --- |
| プロンプトが存在し Active か | フローが配備できない |
| 入力名（大文字小文字まで） | 実行時に**空が渡る**。静かに失敗する |
| code interpreter の ON / OFF | ON 忘れ → Office が読めない。OFF 忘れ → **モデルが文章を書かない** |
| 指示文の地の文が 100 文字以上あるか | 意味を成さない出力が静かに返る |
| （フロー側）接続参照・invoker・redeem 不在 | 資格の穴、または移送で壊れる |

2本とも整ったら、同じコマンドがフロー `ApplicationResource_DescribeLink` を配備します。

> **入力名は大文字小文字まで一致させてください。** `ResourceDescription` 側は
> `File` / `FileName`（先頭が大文字）です。UI の既定名のままにすると自動採番の id に
> 縛られ、フローが空を渡します。**実行時に静かに失敗する**ので、検査で落としています。

> **Test は押さなくてかまいません。** この環境では未保存プロンプトの Test が
> `Missing privilege definition: prvWritemsdyn_AIModel` で失敗しますが、
> **保存は通り、フローからの実行にも影響しません**（2026-08-16 実測）。

## 9. Code Apps を対象環境へ初回デプロイする

Code Apps 側は Dataverse テーブルができたあとで環境固有初期化を行います。

### 9-1. 初期化する

対象環境で Code Apps 機能が有効であることを確認したうえで、`power.config.json` が未生成なら PAC CLI で初期化します。

```powershell
pac code init -env {ENVIRONMENT_ID} -s {SOLUTION_NAME}
```

> `npx power-apps init` は PAC CLI をセッション親として必要とするため、単独では動作しません。必ず `pac code init` を使用してください。

### 9-2. Dataverse データソースを追加する

必要なテーブルは以下です。

- `ds_application`
- `ds_category`
- `ds_decisionoption`
- `ds_message`
- `ds_mention`
- `ds_participant`
- `ds_decision`
- `ds_applicationresource`
- `systemuser`

追加コマンドの例:

```powershell
pac code add-data-source --api-id /providers/xrm/api --resource-name ds_application --org-url {DATAVERSE_URL}
```

日本語表示名のサニタイズで失敗した場合は、先に以下を実行してから `add-data-source` を再度実行してください。

```powershell
node scripts/patch-pac-cli.cjs
```

### 9-3. Power Automate フローを追加する

Code Apps から呼び出すフローを追加します。**`add-data-source` ではなく `add-flow` を使います。**
`add-flow` は OpenAPI 定義の取得・型付きサービスの生成・接続参照の登録までを一括で行います。

- `py scripts/deploy_access_flows.py` 実行結果に出た `Participant_PreDelete_RevokeAccess` の `workflowid`
- `py scripts/deploy_ai_decision.py` 実行結果に出た `Application_GenerateAiDecision` の `workflowid`
- `py scripts/deploy_resource_description_flow.py` 実行結果に出た `ApplicationResource_DescribeLink` の `workflowid`

```powershell
npx power-apps add-flow --flow-id {Participant_PreDelete_RevokeAccess の workflowid} --non-interactive
npx power-apps add-flow --flow-id {Application_GenerateAiDecision の workflowid} --non-interactive
npx power-apps add-flow --flow-id {ApplicationResource_DescribeLink の workflowid} --non-interactive
```

> **`ApplicationResource_DescribeLink` は SharePoint 接続を使います。** 対象環境に
> SharePoint 接続が無ければ先に作ってください（`npx power-apps create-connection
> --api-id shared_sharepointonline` はブラウザでのサインインが開きます）。
> **この接続は設計時の束ね先で、実行時は利用者ごとの接続が使われます**（次の 9-4 の注記）。

> **2026-08-16 訂正。** ここには「PAC CLI をセッション親として必要とするため
> `py scripts/run_power_apps_cli.py` を使う」と書いてありましたが、**今は不要です。**
> ラッパーは `auth_helper` のトークンを流し込む仕組みで、**別テナントを相手にすると
> 無言でハングします**（MinoDev2 で踏みました）。CLI 自身のログイン
> （`npx power-apps` の MSAL キャッシュ）が対象環境を向いていれば直接叩けます。

**注意: `power.config.json` を手で編集しないこと。** 接続参照のキーは CLI が採番する
不透明な GUID で、規則から導出できません。手書きしたキーがあると `add-flow` はそれを
**温存する**ため、壊れた状態が残り続けます。作り直すときは `remove-flow` → `add-flow`。

**注意: `delete-data-source` は巻き添えを出します。** `--api-id shared_logicflows` に対して
実行すると、**無関係なフローの生成サービスまで消える**ことを確認しています。
`src/generated` は git 管理外で復元が効かないため、フローを外すときは
`remove-flow --flow-id ...` を使ってください。

### 9-4. Code Apps から呼び出すフローを実行できるようにする

**利用者には2つとも要ります。片方だけでは呼び出せません。**

| 要るもの | 内容 |
| --- | --- |
| Dataverse のセキュリティロール | App Opener 相当。`ds_Applicant` / `ds_Decider` / `ds_Admin` が満たす |
| Power Automate の **Run only users** | 各フローの詳細画面で、DecisionFlow 利用者グループ、または Applicant / Decider を含むグループを追加 |

編集権限（Owner）は開発・運用担当者に限定します。

#### 対象フロー

**Code Apps から呼ぶフロー、つまり Power Apps V2 トリガーを持つフローが対象です。**

- `Participant_PreDelete_RevokeAccess`
- `Application_GenerateAiDecision`
- `ApplicationResource_DescribeLink`

> **本数ではなくトリガーで判断してください。** フローを足したら、
> トリガーが Power Apps V2 かどうかを見て、この一覧に加えるかを決めます。
> Dataverse トリガー（`OpenApiConnectionWebhook`）、Recurrence、
> Copilot Studio の `Skills` トリガーは**対象外**です。
>
> 実環境で確認するには `workflow` の `clientdata` を引き、
> `properties.definition.triggers` の `kind` が `PowerAppV2` のものを拾います
> （2026-08-16 に MinoDev2 で照合し、上の3本と一致）。

#### 経緯: 「公式ドキュメントに書いていない」を「不要」の根拠にした

この節は**2回訂正しています。** 同じ誤りを繰り返さないために経緯を残します。

Code Apps 公式ドキュメントの制約表は、利用者側の要件としてこれだけを挙げています。

> **Dataverse permissions required** — End users need sufficient Dataverse permissions to
> invoke the flow. Assign the **App Opener** security role or an equivalent role.
>
> — [Add Power Automate flows to a code app](https://learn.microsoft.com/power-apps/developer/code-apps/how-to/add-flows)

ここに Run only users が出てこないことを根拠に、一度「不要」と書き換えました。
**実測が逆でした。**

| フロー | Run only users | 利用者からの呼び出し |
| --- | --- | --- |
| `Participant_PreDelete_RevokeAccess` / `Application_GenerateAiDecision` | 設定済み | 動く |
| `ApplicationResource_DescribeLink`（当時新規） | **未設定** | `Microsoft.Dynamics.CRM.install` が **403**、`connectivity/apis/shared_logicflows/connections/…` が **404**、呼び出し失敗 |

**記述の不在は仕様の否定ではありません。** 制約表に無いことは「要らない」を意味しません。
迷ったら設定せずに動かしてみて、**弾かれたら追加する**という順で実測に決めさせます。

#### 別件として混同しないこと

**「実行専用ユーザーが接続を提供」（`runtimeSource: invoker`）は別物です。**
ポータルでは run-only users と同じパネルに出ますが、**利用者の実行権限ではなく
フロー側の接続属性**で、呼び出した本人の資格で外部サービスを読ませたいフローだけが使います。
`ApplicationResource_DescribeLink` の SharePoint 接続がこれに当たります
（設計は [ARCHITECTURE.md](ARCHITECTURE.md) の 8.6）。



### 9-5. ビルドして push する

`add-flow` が `power.config.json` に追加するフロー接続情報（`workflowDetails`）を保持するため、`pac code push` は使いません。PAC CLI はこのフィールドを拒否し、フロー呼び出しが機能しなくなります。

まず SDK CLI の push を使用します。環境によって SDK CLI がテナント解決に失敗する場合だけ、ラッパースクリプトをフォールバックとして試します。

```powershell
npm run build
npx power-apps push --non-interactive

# SDK CLI がテナント解決で失敗する場合のみ
py scripts/run_power_apps_cli.py push
```

### 9-6. アプリ URL を控える

`npx power-apps push` 完了時に表示されるアプリ URL を控えておきます。通知メールの「申請を開く」リンクでは、後続 Step 11 でソリューション環境変数 `ds_DecisionFlowAppBaseUrl` に設定します。末尾スラッシュは付けません。

```dotenv
ds_DecisionFlowAppBaseUrl=https://apps.powerapps.com/play/e/{ENVIRONMENT_ID}/app/{APP_ID}
```

出力 URL から末尾の `?tenantId=...&hint=...&sourcetime=...` などのクエリ文字列は外します。

この値は `.env` やフロー定義には焼き込みません。ソリューション環境変数としてインポート先環境ごとに設定できるようにします。

未設定でも各スクリプトはエラーにならず、通知メール内の該当リンクだけ空になります。

## 10. Copilot Studio エージェントを構築する

Copilot Studio は bot 作成だけ UI 操作が必須です。次の順で行います。

1. Copilot Studio UI でソリューション `DecisionSupport` に `DecisionFlow Assistant` を手動作成する
2. エージェント URL から `botId` を取得し、`.env` の `BOT_ID` に設定する
3. エージェント定義（Instructions、推奨プロンプト、トピック、アクション、チャネル、AI設定）を YAML から反映する

```powershell
pac copilot push --project-dir copilot/DecisionFlowAssistant
```

4. アイコンと Teams マニフェストの説明文を反映する（YAML が持たない部分）

```powershell
py scripts/deploy_copilot_agent.py
```

### エージェント定義の正本は `copilot/DecisionFlowAssistant/`

Copilot Studio 側の定義は `pac copilot clone` で取り込んだ YAML が正本です。

| 操作 | コマンド |
| --- | --- |
| クラウド → ローカル | `pac copilot pull --project-dir copilot/DecisionFlowAssistant` |
| ローカル → クラウド（下書き） | `pac copilot push --project-dir "<絶対パス>\copilot\DecisionFlowAssistant"` |
| 下書きを公開 | `pac copilot publish` |

**`push` は `--project-dir` に絶対パスが要ります**（2026-08-09・pac 2.10.1 で確認）。相対パスだと
同じディレクトリでも `Error: No synced workspace found at the specified directory.` になります。
`pull` は相対パスでも通るので、片方だけ失敗して混乱しやすい箇所です。

**`pull` は差分適用です。** クラウド側で変わったコンポーネントだけを書き戻すため、
**ローカルだけの編集は pull で消えません**（2026-08-09 に確認）。下の「UI で編集したら先に
`pull` する」は、**push がローカルを正として上書きする**ことへの注意であって、pull が
ローカルを壊すという意味ではありません。

`push` が書き換えるのは**下書き**だけです。Teams などのチャネルに出るのは `publish` の後です。

守ること:

- **UI で編集したら先に `pull` する。** push はローカルを正として上書きするため、
  pull していない UI 変更は消えます。
- **YAML にコメントを書かない。** push / pull の往復で CLI が再生成するため残りません。
  設計意図は `docs/` 側に書きます。
- **`.mcs/` はコミットしない。** clone が生成する `.mcs/.gitignore`（`*`）が除外します。
  `conn.json` に Dataverse エンドポイントと環境 ID が入るためです。
- **`workflows/` は読み取り用と考える。** agent flow の正本は `scripts/deploy_*.py` です。
  フローを変えたら `pull` で同期します。
- **`pac` は 2.10.1 以降が必要**（`copilot clone` / `pull` / `push` は 2.6.4 に無い）。
  PATH 上に standalone 版が同居している場合は `C:\Users\<user>\.dotnet\tools\pac.exe` を明示します。

トピックを新規に作る場合は、既存の `topics/*.mcs.yml` を写して作ってください。
`inputType.properties` の宣言を落とすと、生成オーケストレーションが Topic 変数を
埋められず、条件分岐が常に「情報が取れなかった」側に落ちます。

### トピックが起動しないときに直す場所（generative orchestration）

このエージェントは `settings.mcs.yml` が `recognizer: GenerativeAIRecognizer` /
`GenerativeActionsEnabled: true` なので **generative orchestration** で動きます。
トピックの入口は `modelDescription` であって、**Trigger phrases ではありません**
（あれは classic orchestration の仕組みです）。効く順は次のとおりです。

| 順 | 直す場所 | 書くこと |
| --- | --- | --- |
| 1 | `modelDescription` | 目的、使う場面、**使わない場面**。語句を並べるだけにしない |
| 2 | `mcs.metadata.componentName` | 他のトピック・ナレッジと紛れない具体的な名前 |
| 3 | `inputType.properties.*.description` | 値の意味に加え、**どう解決してよいか**（例: タイトルから検索して GUID にしてよい） |
| 4 | `knowledge/*.mcs.yml` の説明文 | ナレッジが同じ話題を主張していると、トピックが競り負ける |

`intent:` に `triggerQueries` を足すのは**最後の手段**です。トリガーノードが
`User says a phrase` 側に倒れ、プランナーの候補からトピックごと消える恐れがあります。
根拠と実測は [UX_ROADMAP.md](UX_ROADMAP.md) の「次の作業」を参照してください。

`workflows/` の写しが古いと、VS Code 拡張が実在するバインドを
「見つかりません」と赤で出します。トピック側を書き換える前に `pull` してください。

### トピック YAML の書き方（2026-08-08 に実機で確定）

| やりたいこと | 書き方 |
| --- | --- |
| メッセージに変数を埋める | `activity: "投稿します: {Topic.messageBody}"` |
| 式を使う | `{Coalesce(Topic.message, "既定文")}` のように **`{}` の中**に書く |
| 段落を分ける | Markdown の**空行**（アプリのパネル向け） |
| フローを呼ぶ | `InvokeFlowAction` に `flowId` を直接書く。**ツール登録は不要** |

やってはいけないこと:

- **`activity: ="..." & Topic.x` と書かない。** `=` プレフィックスのスカラー式は
  評価されず、そのまま文字列として画面に出る。`condition:` は `=` で正しいので紛らわしい
- **`prompt:` に式を書かない。** `Question` の `prompt` は静的テキストのみ。
  動的な提示は直前の `SendActivity` に分ける
- **`<br />` を使わない。** Teams / Web チャット向けの書き方で、アプリのパネルは
  react-markdown が生 HTML を通さないため、タグがそのまま文字として出る

**書き込み系のフローをツール登録しない。** ツール登録すると、生成
オーケストレーションが専用トピックを迂回して直接呼び、実行者の識別子を
モデルが埋める。詳細と実測結果は `docs/AGENT_WRITE_BOUNDARY.md`。

次に Copilot Studio UI で以下を手動実施します。

1. 認証方式を Microsoft Entra ID ユーザー認証へ変更する
2. Dataverse ナレッジを追加する
3. Teams チャネルを公開する
4. 必要なら Microsoft 365 Copilot チャネル設定を確認する

Teams 公開後は、表示されたアプリマニフェストから以下を控えておきます。

- `ds_CopilotTeamsAppId` に設定する値 = `botChannelRegistrationAppId`
- manifest の `id`（titleId）は通知メールの Teams チャットリンクには使いません

`botChannelRegistrationAppId` の確認手順:

1. [Copilot Studio](https://copilotstudio.microsoft.com/) で `DecisionFlow Assistant` を開く
2. 左側の **チャネル** を開き、**Microsoft Teams** を選択する
3. Teams チャネルを公開し、**アプリを表示** またはマニフェストを表示/ダウンロードできる画面を開く
4. マニフェスト JSON の `bots[0].botId` を確認する
5. その UUID をソリューション環境変数 `ds_CopilotTeamsAppId` に設定する

例:

```json
{
  "id": "85680f01-0a96-58c1-9d89-04e337d8da75",
  "bots": [
    {
      "botId": "27a46150-7ea2-4863-8038-2abf010020b3"
    }
  ]
}
```

上の例では、`ds_CopilotTeamsAppId` に設定するのは `bots[0].botId` の `27a46150-7ea2-4863-8038-2abf010020b3` です。manifest 直下の `id` は `T_` で始まる値または titleId 相当の値になることがあり、ここには使いません。

## 11. 通知フローをデプロイしてリンク用の環境変数を設定する

通知フローは、ソリューション環境変数からリンク設定を実行時に読み取ります。フロー定義には発行元環境の Code Apps URL や Bot ID を直接埋め込みません。

```powershell
py scripts/deploy_notification_flows.py
```

実行後、Power Apps の対象ソリューションで以下の環境変数に現在の環境の値を設定します。ソリューションインポート版でも、インポート先環境で同じ 2 つを任意に設定してください。

| 環境変数スキーマ名          | 値                                              | 用途                                                                                  |
| --------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------- |
| `ds_DecisionFlowAppBaseUrl` | Code Apps の公開 URL ベース                     | Outlook メールの「申請を開く」リンク／Copilot Studio エージェントの申請詳細リンク案内 |
| `ds_CopilotTeamsAppId`      | Teams manifest の `botChannelRegistrationAppId` | Outlook メールの「申請について相談する」リンク                                        |

`ds_CopilotTeamsAppId` が `28:` で始まらない UUID の場合でも、通知フローが Teams チャット用に `28:` を補完します。`T_` で始まる titleId は設定しないでください。

「申請について相談する」のチャット初期メッセージには Code Apps URL を含めません。申請タイトルだけを渡し、エージェントが Dataverse ナレッジから申請を検索します。

### 11-1. Copilot Studio エージェントに「申請詳細リンク」ツールを追加する（任意機能）

`DecisionFlow Assistant` がチャットで申請詳細リンクを案内できるようにします。エージェントが固定 URL を埋め込まないように、`ds_DecisionFlowAppBaseUrl` を実行時に解決して URL を組み立てる Power Automate ツールフローを使います。リンク案内が不要な場合は丸ごとスキップして構いません。

```powershell
py scripts/deploy_application_link_flow.py
```

これで `Get_ApplicationDetailUrl` フローが Power Automate に作成・有効化されます。フローは `applicationId` を受け取り、`ds_DecisionFlowAppBaseUrl` を Dataverse の `environmentvariabledefinitions` / `environmentvariablevalues` から読み出して `?deepLink=%2Fapplications%2F{applicationId}` を付加した URL を返します。環境変数が空のときは空文字列を返し、エージェントはリンクなしの案内文を出します。

デプロイ後、Copilot Studio UI で以下を手動実施します。

1. `DecisionFlow Assistant` を開き、左メニュー **ツール** → **+ ツールを追加** → **Power Automate フローを追加** から `Get_ApplicationDetailUrl` を追加する
2. エージェントを **公開** する

Instructions の「申請詳細リンク」セクションが `Get_ApplicationDetailUrl` を呼び出す前提で書かれているため、ツールを登録するだけでエージェントは適切に呼び出します。

## 12. Copilot Studio チャットでの判断確定機能を追加する（任意機能）

判断者が Copilot Studio チャットから Adaptive Card 経由で判断確定できるようにします。**フロー 2 本のデプロイだけスクリプト化されており、Copilot Studio 側（ツール追加・トピック作成・フロー接続）は UI 操作**です。使わない場合はこの Step を丸ごとスキップして Step 13 へ進めて構いません。

仕様の全体像は [specs/001-confirm-adaptive-card/spec.md](../specs/001-confirm-adaptive-card/spec.md) を参照してください。

前提（既に完了している項目）:

- Step 5 (`setup_dataverse.py`) 実行済み → `ds_decisioncard` テーブルが作成されている
- Step 6 (`setup_security_roles.py`) 実行済み → `ds_Decider` / `ds_Admin` に `ds_decisioncard` への権限が付与されている
- Step 8 で Dataverse 接続が Power Automate に作成済み
- Step 10 で `DecisionFlow Assistant` が作成・初期設定済み

### 12-1. 判断確定用 Power Automate フローをデプロイする

```powershell
py scripts/deploy_adaptive_card_decision_confirmation.py
```

これで以下 2 本のフローが Power Automate に作成・有効化されます。

| フロー名              | 役割                                                                                                                                                                        |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `issue_decision_card` | 判断カード発行。実行者が systemuser として解決でき、`ds_application` が `Submitted` で、実行者が割り当て判断者であることを確認したうえで、`ds_decisioncard` を `Issued` で作成し `cardInstanceId` と `status: issued` を返す。検証に落ちたときは行を作らない。実行者が解決できない・判断者でない場合は `forbidden`、提出済みでない場合は `invalid_target` を返す。**不正または不存在の `applicationId` と、判断者が未割当ての申請では status を返さずフローがエラー終了する**（`confirm_decision` と同じ挙動）。2026-08-09 に検証を追加。それ以前は無検証だった |
| `confirm_decision`    | Adaptive Card submit を検証し、`ds_decision` を作成して `ds_decisioncard` を `Consumed` に更新。`status: succeeded / already_processed / forbidden / invalid_target` を返す |

入出力契約は [specs/001-confirm-adaptive-card/contracts/adaptive-card-decision-confirmation.md](../specs/001-confirm-adaptive-card/contracts/adaptive-card-decision-confirmation.md) を参照してください。

### 12-2. この 2 本はツールとして登録しない

**`issue_decision_card` と `confirm_decision` を「ツール」に追加してはいけません。**

ツール登録すると、生成オーケストレーションが「判断確定」トピックを経由せずフローを直接呼べるようになります。その経路ではトリガー引数の実行者をモデルが埋めるため、**他人の名前で判断を確定できます**。2 本とも登録されていると、作文した実行者でカードを発行し同じ実行者で確定する連鎖が成立し、`Validate_actor_is_decider` も `Validate_current_issued_card` も通過します。

トピックから呼ぶのにツール登録は不要です。`InvokeFlowAction` に `flowId` を直接書けば動きます（2026-08-08 に会話投稿フローで実測）。

既にツール登録されている場合は、`copilot/DecisionFlowAssistant/actions/` の該当 YAML を削除して push すると、クラウド側の登録も消えます。詳細は [docs/AGENT_WRITE_BOUNDARY.md](AGENT_WRITE_BOUNDARY.md)。

### 12-3. トピックを push する

「判断確定」トピックの正本は [copilot/DecisionFlowAssistant/topics/zdI.mcs.yml](../copilot/DecisionFlowAssistant/topics/zdI.mcs.yml) です。ポータルのコードエディタへ貼る手順は不要になりました。

```powershell
& "$env:USERPROFILE\.dotnet\tools\pac.exe" copilot pull --project-dir copilot/DecisionFlowAssistant
git diff
& "$env:USERPROFILE\.dotnet\tools\pac.exe" copilot push --project-dir copilot/DecisionFlowAssistant
```

`pull` を先に実行して差分を確認してください。push はローカルを正としてクラウドの下書きを上書きするため、ポータル側の変更があると消えます。

`flowId` は YAML に実 GUID で入っているので、UI でフローを選び直す作業はありません。

**公開は下書きでの確認より後にします。** push した時点では下書きだけが変わり、Teams などのチャネルには出ません。先に 12-4 の下書き確認を通してから **公開** してください。トピックが起動しない場合、先に公開すると Teams 利用者のチャットからの判断確定が失われます。

### 12-4. 下書きチャットで確認する（公開前）

Copilot Studio のテストパネルで、次の**2点を分けて**確認します。まとめて合否にしないでください。壊れ方が違います。

| 確認 | 見るもの | 落ちたときの意味 |
| --- | --- | --- |
| トピックに到達したか | 「この申請を判断したい」で **Adaptive Card が出る**。完了メッセージがトピックの固定文（`判断を確定しました。…`）である | 経路の問題。ツール登録を外したことで入口が `modelDescription` だけになっている。[docs/AGENT_WRITE_BOUNDARY.md](AGENT_WRITE_BOUNDARY.md) の「Instructions がトピックと逆を向いている」を参照 |
| なりすましが塞がったか | `confirm_decision` の実行履歴で、トリガー入力に `actorAadObjectId` が入っている | ツール登録が実際には消えていない |

両方を通ってから公開します。

### 12-5. 動作確認

Copilot Studio のテストパネル（または公開済み Teams チャネル）で:

1. 「申請○○を判断したい」「判断を確定したい」のような発話 → **判断確定**トピックが起動する
2. `applicationId` は Topic 入力なので、生成オーケストレーションが会話中の申請情報から埋めます（利用者に GUID を入力させません）→ `issue_decision_card` フローが走り、Adaptive Card が表示される
3. **承認 / 却下 / 差し戻し** を選択 + 理由を入力 → **確定** ボタン押下
4. `succeeded` 系メッセージが表示される
5. Power Apps メーカーで該当 `ds_application` を確認:
   - `ds_decision` レコードが 1 件作成されている
   - `ds_stage` が `Decided`（差し戻しの場合は `Draft`）に更新されている
   - `ds_decisioncard` が `Consumed` 状態になっている
6. 既存の `Decision_OnCreated` フロー実行履歴で申請者・関係者宛通知が送信されている

異常系も一通り確認すると安心です:

- 未割り当てユーザーで同じ動線 → `forbidden`
- 既に確定済み案件で実行 → `already_processed`
- 同一カードを 2 回 submit → `already_processed`（`ds_decisioncard.ds_status = Consumed` で弾かれる）

検証シナリオ詳細は [specs/001-confirm-adaptive-card/quickstart.md](../specs/001-confirm-adaptive-card/quickstart.md) を参照してください。

## 13. 動作確認を行う

最低限、以下は確認してください。

1. 申請を 1 件作成して提出できる
2. 判断者ユーザーで判断キューに表示される（判断者選択肢は `DecisionFlow-Deciders` チームメンバーのみ表示される）
3. 関係者追加後に対象申請を閲覧でき、他の関係者が追加した関係者・資料・コメントも見える
4. 関係者追加時に自動的にメンションがメッセージリストとメンションリストに追加され、追加された本人が既読化できる
5. コメント投稿とメンション通知が動く（メッセージスレッドにメンション先がバッジ表示される）
6. 資料タブにアップロード者と日時が表示される
7. AI 判断更新が実行できる
8. Copilot Studio で申請概要を問い合わせできる
9. Applicant には「マスタ管理」が表示されるがカテゴリ/判断選択肢は読取り専用で、ds_Admin / ds_Decider ではカテゴリを編集できる
10. Step 12 を実施した場合: Copilot Studio チャットから判断確定でき、`ds_decision` 作成と `ds_application` ステージ更新が反映される
11. **関連資料の「説明を生成」が動く**（G13）。**申請者ロールの利用者で**、
    自分が読める Office ファイルの URL を貼って押し、説明欄の**末尾に文章が足される**こと

> **11 は管理者で測っても意味がありません。** このフローは
> **呼び出した本人の資格**で SharePoint を読みます（`runtimeSource: invoker`）。
> 管理者は大抵のファイルを読めるので、**配線が壊れていても成功して見えます。**
> 逆に「本人が読めないファイルで失敗すること」まで見て、初めて確かめたことになります。

> **8-1 を飛ばした場合、ここに来る前に落ちます。** プロンプトが無ければ
> `deploy_resource_description_flow.py` が配備を拒否するので、
> **フロー自体が存在せず** Code Apps の `add-flow` もできません。

コード変更を伴う場合の確認コマンド:

```powershell
npm run build
npm test
py -m unittest tests.test_ai_decision tests.test_notification_flows tests.test_access_flows tests.test_security_roles tests.test_copilot_agent
```

Code Apps の詳細な再生成手順は [docs/CODE_APPS_UI_DESIGN.md](CODE_APPS_UI_DESIGN.md)、全体の進捗と手動作業の要点は [docs/PLAN.md](PLAN.md) を参照してください。

---

## 次のステップ

セットアップ完了後、UI 確認用のサンプル申請を投入するには README の「[デモデータを試す](../README.md#デモデータを試す)」セクションを参照してください。
