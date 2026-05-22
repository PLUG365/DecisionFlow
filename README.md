# DecisionFlow

DecisionFlow は、申請者が判断者へ意思決定を依頼し、会話・関連資料・判断結果・AI 判断を一元管理するプラットフォームです。

**主な機能:**

- 申請の作成・提出・判断キュー管理
- スレッド型会話とメンション通知
- AI による申請概要・推奨判断・判断コメントドラフト生成
- カテゴリ別レギュレーションを使った提出前AI確認と判断者向けAI判断支援
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
| [docs/DEPLOY_SETUP.md](docs/DEPLOY_SETUP.md)                                               | デプロイ版の詳細セットアップ手順（Step 1〜13）。README から切り出した本体                                   |
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
3. Code Apps のアプリを一度開き、初期カテゴリ、各カテゴリの初期レギュレーション、固定判断選択肢が自動作成されることを確認する
4. `Participant_PreDelete_RevokeAccess` と `Application_GenerateAiDecision` の Power Automate 詳細画面で **Run only users** に DecisionFlow 利用者グループ、または Applicant/Decider を含むグループを追加する
5. Power Platform 管理センターで `DecisionFlow-Deciders` グループチームを作成・関連付けし、`ds_Decider` ロールを割り当てる
6. 利用者に `ds_Applicant`、管理者に `ds_Admin` を割り当てる
7. Code Apps のアプリを開き、申請作成・提出・判断キュー表示が動くことを確認する
8. 通知メールにリンクを入れる場合は、ソリューション環境変数 `ds_DecisionFlowAppBaseUrl` / `ds_CopilotTeamsAppId` を導入先環境の値に設定する
9. Copilot Studio を使う場合は、認証、Dataverse ナレッジ、Teams チャネル公開を環境に合わせて確認する

リンク用のソリューション環境変数:

| 環境変数スキーマ名          | 値                                              | 用途                                                                                  |
| --------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------- |
| `ds_DecisionFlowAppBaseUrl` | Code Apps の公開 URL ベース                     | Outlook メールの「申請を開く」リンク／Copilot Studio エージェントの申請詳細リンク案内 |
| `ds_CopilotTeamsAppId`      | Teams manifest の `botChannelRegistrationAppId` | Outlook メールの「申請について相談する」リンク                                        |

`botChannelRegistrationAppId` は、Copilot Studio で対象エージェントを開き、**チャネル** > **Microsoft Teams** から Teams チャネルを公開したあと、Teams アプリの詳細またはマニフェストを表示して確認します。マニフェスト JSON を表示またはダウンロードできる場合は、`bots[0].botId` として入っている UUID が `botChannelRegistrationAppId` です。manifest 直下の `id` は titleId であり、通知メールの Teams チャットリンクには使いません。

## セットアップ手順（デプロイ版）

ソースコードから DecisionFlow を構築・改修する場合の手順は、長くなるため別ドキュメントに切り出しています。

**👉 [docs/DEPLOY_SETUP.md](docs/DEPLOY_SETUP.md) を参照してください。**

全体の流れ:

| Step | 内容                                                                   |
| ---- | ---------------------------------------------------------------------- |
| 1〜3 | 事前準備（ツール、`.env`、PAC CLI / Python 認証）                      |
| 4〜6 | Dataverse 構築（事前チェック → テーブル → セキュリティロール）         |
| 7    | 管理センターで判断者グループチームを手動設定                           |
| 8    | Power Automate フローのデプロイ（access / notification / ai_decision） |
| 9    | Code Apps を対象環境へ初回デプロイ                                     |
| 10   | Copilot Studio エージェントの構築（任意）                              |
| 11   | 通知フローのデプロイとリンク用環境変数の設定                           |
| 12   | Copilot Studio チャットでの判断確定機能（任意）                        |
| 13   | 動作確認                                                               |

事前に必要なもの（クイックリファレンス）:

- Windows + PowerShell
- Node.js 20 系以上
- Python 3.11 系以上
- PAC CLI
- 対象環境の Power Apps / Power Automate / Copilot Studio にアクセスできるアカウント
- 「Power Platform 環境の前提」を満たす Power Platform 環境
- Copilot Studio を使う場合は、対象環境でエージェント作成権限があること

```powershell
npm install
pip install -r requirements.txt
```

デプロイ完了後、UI 確認用のサンプル申請を投入するには次の [デモデータを試す](#デモデータを試す) を参照してください。

## デモデータを試す

UI 確認や動作デモのために、5 件のサンプル申請（初期カテゴリ各 1 件）と関連資料を一括投入できます。スクリプトは [scripts/seed_demo_applications.py](scripts/seed_demo_applications.py) です。

### 前提条件

実行前に対象環境で以下が完了している必要があります。

- **Dataverse テーブルと初期カテゴリ・判断選択肢が作成済み**
  - ソリューションインポート版: 上記 Step 3〜4 を完了し、Code Apps を一度起動して初期カテゴリ（顧客案件 / 部内案件 / 課内案件 / 他部署案件 / 事務処理）が自動作成されていること
  - デプロイ版: [docs/DEPLOY_SETUP.md](docs/DEPLOY_SETUP.md) の Step 5 (`setup_dataverse.py`) 完了済みであること
- **実行ユーザーに `ds_Applicant` 以上のセキュリティロールが付与済み**（`ds_Decider` / `ds_Admin` でも可）
- **Python 3.11 系以上**、および `pip install -r requirements.txt` 済み
- ブラウザまたはデバイスコード認証ができる状態（初回のみ対話認証が走り、`.auth_record.json` が生成されます）

> このスクリプトは `.env` を読み込みません。接続先は CLI オプションまたは対話プロンプトで都度指定する設計です（複数環境を意図せず取り違えないため）。

### 投入されるデータ

| カテゴリ   | 申請名                                   | 関連資料数 |
| ---------- | ---------------------------------------- | ---------- |
| 顧客案件   | 戦略顧客向け新製品の特別価格適用         | 3          |
| 部内案件   | ナレッジ共有会の月次定例化               | 2          |
| 課内案件   | 週次報告フォーマットの簡素化             | 3          |
| 他部署案件 | マーケ・開発合同レビュー会の実施         | 2          |
| 事務処理   | 海外出張精算の例外承認（領収書一部欠落） | 3          |

各申請は **下書き (Draft)** ステージで作成され、判断者は未設定です。AI 判断のサンプル値・初期コメント・申請者参加者も同時に登録されます。
申請者・参加者・レコード所有者 (createdby / ownerid) はすべて **実行ユーザー** になります。

### 実行方法

CLI オプションで接続先を明示する場合:

```powershell
$env:PYTHONUTF8="1"
py scripts/seed_demo_applications.py `
    --dataverse-url https://contoso.crm.dynamics.com `
    --tenant-id 12345678-1234-1234-1234-1234567890ab
```

オプションを省略すると対話プロンプトで入力できます:

```powershell
$env:PYTHONUTF8="1"
py scripts/seed_demo_applications.py
```

`PUBLISHER_PREFIX`（既定: `ds`）/ `SOLUTION_NAME`（既定: `DecisionSupport`）を変更している環境では、`--publisher-prefix` / `--solution-name` で上書きしてください。

スクリプトは冪等です。`ds_name` を一致キーとして既存レコードを検索するため、同一ユーザーで再実行しても申請は重複作成されません。

### 注意

- カテゴリが 5 種揃っていない場合はエラーで停止します。事前に Dataverse 初期化が完了していることを確認してください。
- `ds_Applicant` ロールユーザーが実行する場合、`find_by_name` の検索が自分所有レコードに限定されるため、別ユーザーが先に同名申請を作成済みの環境では重複が発生する可能性があります。
- デモデータ削除用のスクリプトは現在ありません。不要になった場合は Power Apps / Code Apps UI から個別削除してください。

## 注意事項

- `.env`, `.auth_record.json`, `power.config.json`, `.power/`, `src/generated/` は環境固有情報を含むため Git 管理しません。
- Dataverse 接続は環境内に事前作成が必要です。スクリプトは接続候補を検索し、接続参照を更新します。
- `DecisionFlow-Deciders` の Dataverse グループチーム紐付けと `ds_Decider` ロール付与は、Power Platform 管理センターで手動実施します。
- Copilot Studio `DecisionFlow Assistant` の再構築手順は [docs/PLAN.md](docs/PLAN.md) を参照してください。

## ライセンス

MIT License。詳細は [LICENSE](LICENSE) を参照してください。
