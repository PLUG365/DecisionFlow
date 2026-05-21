# DecisionFlow

DecisionFlow は、申請者が判断者へ意思決定を依頼し、会話・関連資料・判断結果・AI 判断を一元管理するプラットフォームです。

**主な機能:**

- 申請の作成・提出・判断キュー管理
- スレッド型会話とメンション通知
- AI による申請概要・推奨判断・判断コメントドラフト生成
- 関係者への自動通知・停滞リマインド
- Copilot Studio エージェントによる Teams / Microsoft 365 Copilot からの対話型照会

**技術スタック:**

| レイヤー        | 技術                                                                                              |
| --------------- | ------------------------------------------------------------------------------------------------- |
| フロントエンド  | Power Apps Code Apps（TypeScript + React + Vite、Tailwind CSS + shadcn/ui、TanStack React Query） |
| データ          | Microsoft Dataverse（Power Apps Code SDK 経由）                                                   |
| バックエンド    | Power Automate（7 フロー）、AI Builder（`DecisionRecommendation` プロンプト）                     |
| AI エージェント | Copilot Studio `DecisionFlow Assistant`（生成オーケストレーション）                               |
| デプロイ自動化  | Python スクリプト群（`scripts/`）、PAC CLI、Power Apps Code Apps SDK                              |

## 謝辞

本プロジェクトは [geekfujiwara](https://github.com/geekfujiwara) 氏の成果物を土台に構築しています。
Power Platform コードファースト開発の知見を惜しみなく公開・共有いただいたことに、心より感謝申し上げます。

- **[CodeAppsDevelopmentStandard](https://github.com/geekfujiwara/CodeAppsDevelopmentStandard)**  
  本リポジトリのクローン元。デプロイスクリプト・Dataverse 連携パターン・開発標準の大部分はここから学び、拡張しています。
- **[CodeAppsStarter](https://github.com/geekfujiwara/CodeAppsStarter)**  
  Code Apps の UI コンポーネント構成・shadcn/ui 活用パターンの設計参考にさせていただきました。

## ドキュメント構成

このリポジトリの設計・実装・運用に関する情報は以下のドキュメントに集約しています。
**README はセットアップ手順のエントリーポイントです。** 詳細な設計・実装状況は各ドキュメントを参照してください。

| ドキュメント                                                                               | 役割                                                                                                        |
| ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------- |
| **README.md**（本ファイル）                                                                | セットアップ手順の入口。初めてリポジトリを触る人向けのガイド                                                |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)                                               | コンポーネント構成、データモデル、フロー設計、AI/Copilot 仕様。**設計の正として扱う**                       |
| [docs/PLAN.md](docs/PLAN.md)                                                               | プロジェクト概要、フェーズ進捗、実装チェックリスト、GitHub 公開方針。**実装状況・未完了事項の正として扱う** |
| [docs/CODE_APPS_UI_DESIGN.md](docs/CODE_APPS_UI_DESIGN.md)                                 | Code Apps 画面、Hooks、サービス層、UI 実装状況                                                              |
| [docs/MIGRATIONS.md](docs/MIGRATIONS.md)                                                   | Dataverse メタデータ変更と適用履歴                                                                          |
| [docs/POWER_PLATFORM_DEVELOPMENT_STANDARD.md](docs/POWER_PLATFORM_DEVELOPMENT_STANDARD.md) | Power Platform コードファースト開発標準                                                                     |
| [docs/DATAVERSE_GUIDE.md](docs/DATAVERSE_GUIDE.md)                                         | Dataverse 実装ガイド                                                                                        |

## Power Platform 環境の前提

DecisionFlow を導入する前に、対象の Power Platform 環境で以下を確認してください。ソリューションインポート版・デプロイ版のどちらでも必要になる前提です。

- Dataverse が有効な Power Platform 環境であること（DecisionFlow のテーブルはソリューションインポートまたはデプロイスクリプトで作成されます）
- Power Apps Code Apps を利用できる環境であること
- Power Automate で Microsoft Dataverse / Office 365 Outlook / Microsoft Teams の接続を作成できること
- 対象環境でソリューションのインポート、フローの有効化、セキュリティロールの割り当てができる権限を持っていること
- Copilot Studio を使う場合は、対象環境でエージェント作成・公開・Teams チャネル公開が許可されていること
- 組織の DLP ポリシーで、Dataverse / Outlook / Teams / Copilot Studio の利用がブロックされていないこと

検証や試用では、既存業務アプリと分けた専用の開発・検証環境を使うことを推奨します。

## セットアップ方法を選ぶ

DecisionFlow は、Dataverse、Power Automate、Power Apps Code Apps、Copilot Studio を組み合わせて構成します。まず利用したい場合は **ソリューションインポート版**、コードから環境を再構築・開発したい場合は **デプロイ版** を使ってください。

| 方法                       | 向いている人                                                   | 内容                                                                                                             |
| -------------------------- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| ソリューションインポート版 | とりあえず試したい人、既存環境に導入したい人                   | GitHub Release のソリューションZipを Power Platform 環境へインポートする                                         |
| デプロイ版                 | 開発・改修したい人、テーブルやフローをコードから再生成したい人 | このリポジトリを clone し、Python スクリプトと CLI で Dataverse / フロー / Code Apps / Copilot Studio を構築する |

## セットアップ手順（ソリューションインポート版）

GitHub Release に公開されたソリューションZipを使って、DecisionFlow を対象の Power Platform 環境へ導入する手順です。ソースコードをビルドせずに利用を開始したい場合は、こちらから進めてください。

### 1. 事前に必要なもの

- 上記の前提を満たす Power Platform 環境
- 対象環境でソリューションをインポートできる権限
- Power Automate の接続を作成・認証できるアカウント
- Microsoft Dataverse / Office 365 Outlook / Microsoft Teams 接続
- Copilot Studio エージェントを使う場合は、対象環境でエージェントを利用・公開できる権限

### 2. ソリューションZipを取得する

1. GitHub リポジトリの **Releases** を開く
2. 最新リリースの Assets から `DecisionSupport` のソリューションZipをダウンロードする
3. 管理対象ソリューションが提供されている場合は、通常は管理対象Zipを選択する

リリースにソリューションZipがない場合は、まだ配布用パッケージが公開されていません。リポジトリ管理者が手動でZipを用意し、Release Assets として添付します。作業用の置き場は [artifacts/solutions/](artifacts/solutions/) です。

### 3. Power Platform にインポートする

1. [Power Apps](https://make.powerapps.com/) を開き、右上の環境セレクターで導入先環境を選択する
2. 左メニュー **ソリューション** を開く
3. **ソリューションのインポート** を選択する
4. ダウンロードしたソリューションZipを選択する
5. 接続参照の画面が表示された場合は、対象環境の Dataverse / Outlook / Teams 接続を割り当てる
6. インポートを実行し、完了するまで待つ

### 4. インポート後の設定を行う

インポートだけでは、利用者・接続・チャネル公開など環境依存の設定は完了しません。少なくとも以下を確認してください。

1. Power Automate でインポートされたフローを開き、接続エラーがないことを確認する
2. 必要なフローがオフになっている場合はオンにする
3. Code Apps のアプリを一度開き、初期カテゴリと固定判断選択肢が自動作成されることを確認する
4. `Participant_PreDelete_RevokeAccess` と `Application_GenerateAiDecision` の Power Automate 詳細画面で **Run only users** に DecisionFlow 利用者グループ、または Applicant/Decider を含むグループを追加する
5. Power Platform 管理センターで `DecisionFlow-Deciders` グループチームを作成・関連付けし、`ds_Decider` ロールを割り当てる
6. 利用者に `ds_Applicant`、管理者に `ds_Admin` を割り当てる
7. Code Apps のアプリを開き、申請作成・提出・判断キュー表示が動くことを確認する
8. Copilot Studio を使う場合は、認証、Dataverse ナレッジ、Teams チャネル公開を環境に合わせて確認する

> 通常のソリューションエクスポートには、カスタムテーブルの定義は含まれますが、`ds_category` / `ds_decisionoption` のような通常テーブルの行データは含まれません。DecisionFlow は Code Apps 初回起動時に、カテゴリが空の場合は初期カテゴリを作成し、固定判断選択肢 `承認` / `却下` / `差し戻し` は不足分だけ自動補完します。

固定判断選択肢:

| 名前     | 説明                           | 並び順 |
| -------- | ------------------------------ | ------ |
| 承認     | 申請内容を承認する             | 1      |
| 却下     | 申請内容を却下する             | 2      |
| 差し戻し | 追加情報や修正を求めて差し戻す | 3      |

詳細な確認観点は、この README の「動作確認を行う」を参照してください。

## セットアップ手順（デプロイ版）

ソースコードから DecisionFlow を構築・改修する場合の手順です。初めて環境を作る場合は、CLI 実行だけでは完結せず、Power Apps / Power Automate / Copilot Studio / Power Platform 管理センターでの手動操作が必要です。

### 1. 事前に必要なもの

- Windows + PowerShell
- Node.js 20 系以上
- Python 3.11 系以上
- PAC CLI
- 対象環境の Power Apps / Power Automate / Copilot Studio にアクセスできるアカウント
- 上記の前提を満たす Power Platform 環境
- Copilot Studio を使う場合は、対象環境でエージェント作成権限があること

初回セットアップ前に依存関係をインストールします。

```powershell
npm install
pip install -r requirements.txt
```

### 2. 環境変数を作成する

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
- `BOT_ID`, `COPILOT_TEAMS_APP_ID`, `COPILOT_TEAMS_TITLE_ID`:
  Copilot Studio / Teams 公開後に追記
- `DECISIONFLOW_APP_BASE_URL`:
  Code Apps を初回 push して URL が確定した後（Step 9-5 で設定）

値の取得方法の詳細は [.env.example](.env.example) を参照してください。

### 3. 認証を準備する

#### 3-1. PAC CLI 認証プロファイルを作成する

```powershell
pac auth create --name DecisionSupportProfile --environment {ENVIRONMENT_ID}
pac auth list
```

`.env` の `PAC_AUTH_PROFILE` と同じ名前で作成してください。

#### 3-2. Python スクリプト用の認証を行う

以降の Python スクリプトは `auth_helper.py` 経由で認証します。初回実行時はブラウザまたはデバイスコード認証が走り、プロジェクト直下に `.auth_record.json` が生成されます。

> **Windows ユーザーへ:** Python スクリプト実行前に以下を設定してください。設定しないと絵文字を含む出力で `UnicodeEncodeError` が発生します。
>
> ```powershell
> $env:PYTHONUTF8="1"
> ```

### 4. Dataverse の事前チェックを行う

予定しているソリューション名・テーブル名が既存環境と衝突しないかを確認します。

```powershell
py scripts/check_dataverse_prereqs.py
```

`Collision detected` が出た場合は、そのまま進めずに `.env` の `SOLUTION_NAME` または `PUBLISHER_PREFIX` を見直してください。

### 5. Dataverse テーブルと初期データを構築する

以下で Publisher / Solution / テーブル / リレーション / Choice / 初期マスタを作成します。

```powershell
py scripts/setup_dataverse.py
```

このスクリプトは `.env` の `PUBLISHER_UNIQUE_NAME`, `PUBLISHER_DISPLAY_NAME`, `SOLUTION_DISPLAY_NAME` を必要に応じて `.env` に書き戻します。既定値のままで問題ありません。

### 6. セキュリティロールを作成する

```powershell
py scripts/setup_security_roles.py
```

この時点で `ds_Applicant`, `ds_Decider`, `ds_Admin` を Dataverse に作成します。

ロール権限の概要:

- `ds_Applicant` / `ds_Decider`: マスタ（`ds_category`, `ds_decisionoption`）は Read のみ。`ds_mention` には Assign 権限を含み、関係者追加時にメンションを target ユーザー所有として作成できる
- `ds_Admin`: 全テーブル Global。マスタ管理 UI もこのロール保持者のみに表示

### 7. 管理センターで必須の手動設定を行う

このステップはスクリプトでは完結しません。

1. Microsoft Entra 管理センターで判断者用 M365 グループ `DecisionFlow-Deciders` を作成する
2. Power Platform 管理センターでそのグループを Dataverse のグループチームとして関連付ける
3. そのグループチームへ `ds_Decider` ロールを割り当てる
4. 必要に応じて申請者・管理者ユーザーへ `ds_Applicant`, `ds_Admin` を割り当てる

この手動設定を行わないと、判断者向けの閲覧・判断導線が期待通りに動作しません。

### 8. Power Automate 接続を確認してフローをデプロイする

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

この順序で問題ありません。ソリューション `DecisionSupport` は [scripts/setup_dataverse.py](scripts/setup_dataverse.py) が作成するため、Power Automate のデプロイは Code Apps より先に実行できます。

補足:

- `deploy_access_flows.py` は関係者追加・削除時の Dataverse 共有制御フローを作成します
- `deploy_notification_flows.py` は申請提出、判断確定、メンション、停滞リマインド通知を作成します
- `deploy_ai_decision.py` は AI Builder プロンプト連携フローを作成します
- `deploy_notification_flows.py` の各通知フローはバックグラウンド実行のため、Code Apps 側の `add-flow` は不要です
- `deploy_access_flows.py` の Revoke フローと `deploy_ai_decision.py` の AI 判断フローは、後続の Code Apps 手順で `npx power-apps add-flow` が必要です

### 9. Code Apps を対象環境へ初回デプロイする

Code Apps 側は Dataverse テーブルができたあとで環境固有初期化を行います。

#### 9-1. 初期化する

対象環境で Code Apps 機能が有効であることを確認したうえで、`power.config.json` が未生成なら PAC CLI で初期化します。

```powershell
pac code init -env {ENVIRONMENT_ID} -s {SOLUTION_NAME}
```

> `npx power-apps init` は PAC CLI をセッション親として必要とするため、単独では動作しません。必ず `pac code init` を使用してください。

#### 9-2. Dataverse データソースを追加する

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

#### 9-3. Power Automate フローを追加する

Code Apps から呼び出すフローを追加します。`npx power-apps add-flow` は PAC CLI をセッション親として必要とするため、ラッパースクリプトを使用します。

- `py scripts/deploy_access_flows.py` 実行結果に出た `Participant_PreDelete_RevokeAccess` の `workflowid`
- `py scripts/deploy_ai_decision.py` 実行結果に出た `Application_GenerateAiDecision` の `workflowid`

```powershell
py scripts/run_power_apps_cli.py add-flow --flow-id {Participant_PreDelete_RevokeAccess の workflowid}
py scripts/run_power_apps_cli.py add-flow --flow-id {Application_GenerateAiDecision の workflowid}
```

#### 9-4. Code Apps から呼び出すフローの Run only users を設定する

Power Apps V2 トリガーのフローを Code Apps から実行するユーザーには、Power Automate の **Run only users** 権限が必要です。これは環境・テナント内のユーザー/グループに紐づく設定のため、このリポジトリを別環境で使う場合は利用者側で手動設定します。ソリューションインポート版でもデプロイ版でも必要です。

対象フロー:

- `Participant_PreDelete_RevokeAccess`
- `Application_GenerateAiDecision`

Power Automate の各フロー詳細画面で **Run only users** に DecisionFlow 利用者グループ、または Applicant/Decider を含むグループを追加してください。編集権限（Owner）は開発・運用担当者に限定します。

#### 9-5. ビルドして push する

`add-flow` が `power.config.json` に追加するフロー接続情報（`workflowDetails`）を保持するため、`pac code push` は使いません。PAC CLI はこのフィールドを拒否し、フロー呼び出しが機能しなくなります。

まず SDK CLI の push を使用します。環境によって SDK CLI がテナント解決に失敗する場合だけ、ラッパースクリプトをフォールバックとして試します。

```powershell
npm run build
npx power-apps push --non-interactive

# SDK CLI がテナント解決で失敗する場合のみ
py scripts/run_power_apps_cli.py push
```

#### 9-6. アプリ URL を `.env` に設定する

`pac code push` 完了時に表示されるアプリ URL を、`.env` の `DECISIONFLOW_APP_BASE_URL` に設定します。末尾スラッシュは付けません。

```dotenv
DECISIONFLOW_APP_BASE_URL=https://apps.powerapps.com/play/e/{ENVIRONMENT_ID}/app/{APP_ID}
```

`pac code push` の出力 URL から末尾の `?tenantId=...&hint=...&sourcetime=...` などのクエリ文字列は外します。

設定すると後続の Step 10（Copilot Studio）と Step 11（通知フロー再デプロイ）で以下が有効になります。

- 提出通知メール・停滞リマインドメールに「申請を開く」直リンクが入る
- Copilot Studio エージェントが回答内で申請詳細URLを案内する

未設定でも各スクリプトはエラーにならず、リンク埋め込みのみスキップされます。

### 10. Copilot Studio エージェントを構築する

Copilot Studio は bot 作成だけ UI 操作が必須です。次の順で行います。

1. Copilot Studio UI でソリューション `DecisionSupport` に `DecisionFlow Assistant` を手動作成する
2. エージェント URL から `botId` を取得し、`.env` の `BOT_ID` に設定する
3. 以下を実行して Instructions、推奨プロンプト、アイコン、チャネル設定を反映する

```powershell
py scripts/deploy_copilot_agent.py
```

> Step 9-5 で `DECISIONFLOW_APP_BASE_URL` を設定済みであれば、この実行で Instructions に申請詳細URLの案内が含まれます。

次に Copilot Studio UI で以下を手動実施します。

1. 認証方式を Microsoft Entra ID ユーザー認証へ変更する
2. Dataverse ナレッジを追加する
3. Teams チャネルを公開する
4. 必要なら Microsoft 365 Copilot チャネル設定を確認する

Teams 公開後は、表示されたアプリマニフェストから以下を `.env` に設定します。

- `COPILOT_TEAMS_APP_ID` = `botChannelRegistrationAppId`
- `COPILOT_TEAMS_TITLE_ID` = manifest の `id`

### 11. 通知フローを再実行してリンクを有効化する

`COPILOT_TEAMS_APP_ID` を設定したあと、通知フローを再実行すると Outlook メールに AI アシスタント相談リンクが入ります。Step 9-5 で `DECISIONFLOW_APP_BASE_URL` も設定済みであれば、提出通知メールと停滞リマインドメールに「申請を開く」直リンクも併せて入ります。

```powershell
py scripts/deploy_notification_flows.py
```

### 12. Copilot Studio チャットでの判断確定機能を追加する（任意機能）

判断者が Copilot Studio チャットから Adaptive Card 経由で判断確定できるようにします。**フロー 2 本のデプロイだけスクリプト化されており、Copilot Studio 側（ツール追加・トピック作成・フロー接続）は UI 操作**です。使わない場合はこの Step を丸ごとスキップして Step 13 へ進めて構いません。

仕様の全体像は [specs/001-confirm-adaptive-card/spec.md](specs/001-confirm-adaptive-card/spec.md) を参照してください。

前提（既に完了している項目）:

- Step 5 (`setup_dataverse.py`) 実行済み → `ds_decisioncard` テーブルが作成されている
- Step 6 (`setup_security_roles.py`) 実行済み → `ds_Decider` / `ds_Admin` に `ds_decisioncard` への権限が付与されている
- Step 8 で Dataverse 接続が Power Automate に作成済み
- Step 10 で `DecisionFlow Assistant` が作成・初期設定済み

#### 12-1. 判断確定用 Power Automate フローをデプロイする

```powershell
py scripts/deploy_adaptive_card_decision_confirmation.py
```

これで以下 2 本のフローが Power Automate に作成・有効化されます。

| フロー名              | 役割                                                                                                                                                                        |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `issue_decision_card` | 判断カード発行。`ds_application` が `Submitted` かつ実行者が割り当て判断者であることを確認し、`ds_decisioncard` を `Issued` で作成、`cardInstanceId` を返す                 |
| `confirm_decision`    | Adaptive Card submit を検証し、`ds_decision` を作成して `ds_decisioncard` を `Consumed` に更新。`status: succeeded / already_processed / forbidden / invalid_target` を返す |

入出力契約は [specs/001-confirm-adaptive-card/contracts/adaptive-card-decision-confirmation.md](specs/001-confirm-adaptive-card/contracts/adaptive-card-decision-confirmation.md) を参照してください。

#### 12-2. Copilot Studio エージェントに 2 つのフローを「ツール」として追加する

`DecisionFlow Assistant` を開き、左メニュー **ツール** → **+ ツールを追加** → **Power Automate フローを追加** から以下 2 本を追加します。

- `issue_decision_card`
- `confirm_decision`

ここで追加することで、後段のトピックからフローを呼び出せるようになります。

#### 12-3. 「判断確定」トピックを新規作成して YAML を貼り付ける

1. `DecisionFlow Assistant` の左メニュー **トピック** → **+ 新しいトピック** → **空のトピックから作成** を選択
2. トピック名: `判断確定`
3. トピック画面右上の `…` メニュー → **コードエディタを開く**
4. [specs/001-confirm-adaptive-card/decision-confirmation.topic.template.yaml](specs/001-confirm-adaptive-card/decision-confirmation.topic.template.yaml) の全文をコピーして、エディタの内容を**全置換**
5. **保存** ← この時点では `flowId` がプレースホルダ (`00000000-...`) のままなので、2 つの「Power Automate フローを呼び出す」ノードでエラー表示が出ますが、想定通りです

#### 12-4. UI で 2 つのフロー接続を修正する

コードエディタを閉じてビジュアルエディタに戻ります。エラーになっている 2 つの **「Power Automate フローを呼び出す」** ノードを順番にクリックして、右側プロパティパネルから対応するフローを選択し直します。

- 1 つ目のノード（`issue_decision_card` 呼び出し用）→ プロパティパネルで **`issue_decision_card`** を選択
- 2 つ目のノード（`confirm_decision` 呼び出し用）→ プロパティパネルで **`confirm_decision`** を選択

選択すると Copilot Studio が内部的に `flowId` を実 GUID に置換し、エラーが消えます。入出力のバインドは YAML 上で既に正しい変数名に揃えてあるので、再マッピング不要のはずです（もし入力欄に「未設定」が出たら、Topic 変数を選択し直す）。

最後にエージェント全体を **公開** します。

#### 12-5. 動作確認

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

検証シナリオ詳細は [specs/001-confirm-adaptive-card/quickstart.md](specs/001-confirm-adaptive-card/quickstart.md) を参照してください。

### 13. 動作確認を行う

最低限、以下は確認してください。

1. 申請を 1 件作成して提出できる
2. 判断者ユーザーで判断キューに表示される（判断者選択肢は `DecisionFlow-Deciders` チームメンバーのみ表示される）
3. 関係者追加後に対象申請を閲覧でき、他の関係者が追加した関係者・資料・コメントも見える
4. 関係者追加時に自動的にメンションがメッセージリストとメンションリストに追加され、追加された本人が既読化できる
5. コメント投稿とメンション通知が動く（メッセージスレッドにメンション先がバッジ表示される）
6. 資料タブにアップロード者と日時が表示される
7. AI 判断更新が実行できる
8. Copilot Studio で申請概要を問い合わせできる
9. ds_Admin 以外のユーザーにはサイドバーの「マスタ管理」が表示されない
10. Step 12 を実施した場合: Copilot Studio チャットから判断確定でき、`ds_decision` 作成と `ds_application` ステージ更新が反映される

コード変更を伴う場合の確認コマンド:

```powershell
npm run build
npm test
py -m unittest tests.test_ai_decision tests.test_notification_flows tests.test_access_flows tests.test_security_roles tests.test_copilot_agent
```

Code Apps の詳細な再生成手順は [docs/CODE_APPS_UI_DESIGN.md](docs/CODE_APPS_UI_DESIGN.md)、全体の進捗と手動作業の要点は [docs/PLAN.md](docs/PLAN.md) を参照してください。

## 注意事項

- `.env`, `.auth_record.json`, `power.config.json`, `.power/`, `src/generated/` は環境固有情報を含むため Git 管理しません。
- Dataverse 接続は環境内に事前作成が必要です。スクリプトは接続候補を検索し、接続参照を更新します。
- `DecisionFlow-Deciders` の Dataverse グループチーム紐付けと `ds_Decider` ロール付与は、Power Platform 管理センターで手動実施します。
- Copilot Studio `DecisionFlow Assistant` の再構築手順は [docs/PLAN.md](docs/PLAN.md) を参照してください。

## ライセンス

MIT License。詳細は [LICENSE](LICENSE) を参照してください。
