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
```

この順序で問題ありません。ソリューション `DecisionSupport` は [scripts/setup_dataverse.py](../scripts/setup_dataverse.py) が作成するため、Power Automate のデプロイは Code Apps より先に実行できます。

補足:

- `deploy_access_flows.py` は関係者追加・削除時の Dataverse 共有制御フローを作成します
- `deploy_notification_flows.py` は申請提出、判断確定、メンション、停滞リマインド通知を作成します
- `deploy_ai_decision.py` は AI Builder プロンプト連携フローを作成します
- `deploy_ai_decision.py` は `ds_category.ds_regulationtext` を prompt 入力へ追加し、AI結果は既存の `ds_application` AI列へ最新結果として上書き保存します
- `deploy_notification_flows.py` の各通知フローはバックグラウンド実行のため、Code Apps 側の `add-flow` は不要です
- `deploy_access_flows.py` の Revoke フローと `deploy_ai_decision.py` の AI 判断フローは、後続の Code Apps 手順で `npx power-apps add-flow` が必要です

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

Code Apps から呼び出すフローを追加します。`npx power-apps add-flow` は PAC CLI をセッション親として必要とするため、ラッパースクリプトを使用します。

- `py scripts/deploy_access_flows.py` 実行結果に出た `Participant_PreDelete_RevokeAccess` の `workflowid`
- `py scripts/deploy_ai_decision.py` 実行結果に出た `Application_GenerateAiDecision` の `workflowid`

```powershell
py scripts/run_power_apps_cli.py add-flow --flow-id {Participant_PreDelete_RevokeAccess の workflowid}
py scripts/run_power_apps_cli.py add-flow --flow-id {Application_GenerateAiDecision の workflowid}
```

### 9-4. Code Apps から呼び出すフローの Run only users を設定する

Power Apps V2 トリガーのフローを Code Apps から実行するユーザーには、Power Automate の **Run only users** 権限が必要です。これは環境・テナント内のユーザー/グループに紐づく設定のため、このリポジトリを別環境で使う場合は利用者側で手動設定します。ソリューションインポート版でもデプロイ版でも必要です。

対象フロー:

- `Participant_PreDelete_RevokeAccess`
- `Application_GenerateAiDecision`

Power Automate の各フロー詳細画面で **Run only users** に DecisionFlow 利用者グループ、または Applicant/Decider を含むグループを追加してください。編集権限（Owner）は開発・運用担当者に限定します。

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
3. 以下を実行して Instructions、推奨プロンプト、アイコン、チャネル設定を反映する

```powershell
py scripts/deploy_copilot_agent.py
```

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
| `issue_decision_card` | 判断カード発行。`ds_application` が `Submitted` かつ実行者が割り当て判断者であることを確認し、`ds_decisioncard` を `Issued` で作成、`cardInstanceId` を返す                 |
| `confirm_decision`    | Adaptive Card submit を検証し、`ds_decision` を作成して `ds_decisioncard` を `Consumed` に更新。`status: succeeded / already_processed / forbidden / invalid_target` を返す |

入出力契約は [specs/001-confirm-adaptive-card/contracts/adaptive-card-decision-confirmation.md](../specs/001-confirm-adaptive-card/contracts/adaptive-card-decision-confirmation.md) を参照してください。

### 12-2. Copilot Studio エージェントに 2 つのフローを「ツール」として追加する

`DecisionFlow Assistant` を開き、左メニュー **ツール** → **+ ツールを追加** → **Power Automate フローを追加** から以下 2 本を追加します。

- `issue_decision_card`
- `confirm_decision`

ここで追加することで、後段のトピックからフローを呼び出せるようになります。

### 12-3. 「判断確定」トピックを新規作成して YAML を貼り付ける

1. `DecisionFlow Assistant` の左メニュー **トピック** → **+ 新しいトピック** → **空のトピックから作成** を選択
2. トピック名: `判断確定`
3. トピック画面右上の `…` メニュー → **コードエディタを開く**
4. [specs/001-confirm-adaptive-card/decision-confirmation.topic.template.yaml](../specs/001-confirm-adaptive-card/decision-confirmation.topic.template.yaml) の全文をコピーして、エディタの内容を**全置換**
5. **保存** ← この時点では `flowId` がプレースホルダ (`00000000-...`) のままなので、2 つの「Power Automate フローを呼び出す」ノードでエラー表示が出ますが、想定通りです

### 12-4. UI で 2 つのフロー接続を修正する

コードエディタを閉じてビジュアルエディタに戻ります。エラーになっている 2 つの **「Power Automate フローを呼び出す」** ノードを順番にクリックして、右側プロパティパネルから対応するフローを選択し直します。

- 1 つ目のノード（`issue_decision_card` 呼び出し用）→ プロパティパネルで **`issue_decision_card`** を選択
- 2 つ目のノード（`confirm_decision` 呼び出し用）→ プロパティパネルで **`confirm_decision`** を選択

選択すると Copilot Studio が内部的に `flowId` を実 GUID に置換し、エラーが消えます。入出力のバインドは YAML 上で既に正しい変数名に揃えてあるので、再マッピング不要のはずです（もし入力欄に「未設定」が出たら、Topic 変数を選択し直す）。

最後にエージェント全体を **公開** します。

### 12-5. 動作確認

Copilot Studio のテストパネル（または公開済み Teams チャネル）で:

1. 「申請○○を判断したい」「判断を確定したい」のような発話 → **判断確定**トピックが起動する
2. `askApplicationId` で対象案件 ID（GUID）を入力 → `issue_decision_card` フローが走り、Adaptive Card が表示される
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
