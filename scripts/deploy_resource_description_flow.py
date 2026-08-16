"""関連資料の説明文を自動生成するフロー（G13）を配備する。

**第2段: 本人の資格でファイルを読み、AI Builder のプロンプトに直接渡して説明文を作る。**

このフローの肝は「**誰の資格で SharePoint を読むか**」で、第1段でそこを実測した
（呼び出した本人の UPN が返り、管理者の OneDrive は 403 になった）。所有者の接続で読むと、
利用者が URL を貼るだけで**管理者が読めるファイルを何でも読める**穴になる
（SharePoint は Dataverse の外なので `ds_*` ロールでは止められない）。

そこで SharePoint 接続だけ `runtimeSource: "invoker"` にする。Dataverse 側は `embedded`
のままでよい。**同じフローの中で混在させられる**のが要点。

段の構成:

    GetFileMetadataByPath  (SharePoint / invoker)  … 存在とサイズを見る
      → 25 MB を超えていたらここで止める（AI Builder の上限）
    GetFileContentByPath   (SharePoint / invoker)  … 中身を取る
    aibuilderpredict_customprompt (Dataverse / embedded) … 説明文を作る

**OCR も PDF 変換も挟まない。** AI Builder のプロンプトは code interpreter を有効に
すると Office ファイルをドキュメント入力としてそのまま受け取れる。

**プロンプトはこのスクリプトでは作れない。** code interpreter 付きのプロンプトは
`code`（生成された Python）と `signature`（プラットフォームが発行する整合性トークン）を
持ち、署名を手元で作れないため。名前で引いて、無ければ落とす。作成は AI Hub の UI で行う
（`docs/UX_ROADMAP.md`「第2段の構成」）。形は `scripts/capture_prompt_config.py` で読める。

使い方（MinoDev2 へ向ける場合）:

    $env:PP_AUTH_RECORD_PATH="<repo>\\.auth_record.minodev2.json"
    $env:PP_TOKEN_CACHE_NAME="power_platform_token_cache_minodev2"
    py scripts/deploy_resource_description_flow.py

**主環境の認証レコードを上書きしないため、この2つは必ずセットで指定する。**
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL, api_get, get_session  # noqa: E402

load_dotenv()

API = f"{DATAVERSE_URL}/api/data/v9.2"
SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")

DATAVERSE_CONNECTOR = "shared_commondataserviceforapps"
# AI Builder のアクションは Dataverse コネクタの**別名**を connectionName に取る。
# `deploy_ai_decision.py` と同じ形。apiId は素のコネクタのままで、参照だけ増やす。
DATAVERSE_CONNECTOR_AI = "shared_commondataserviceforapps_1"
SHAREPOINT_CONNECTOR = "shared_sharepointonline"
FLOW_NAME = "ApplicationResource_DescribeLink"
FLOW_DESCRIPTION = (
    "Code Apps から関連資料の URL を受け取り、呼び出した本人の資格で SharePoint を"
    "読んで説明文を作る。SharePoint 接続は invoker（実行専用ユーザー提供）。"
)

AI_PROMPT_NAME = "ResourceDescription"

# 抽出プロンプトの指示文（UI に貼る正典の写し。スクリプトからは書き込めない）。
#
# **一時ファイルを書かせないことが肝。** 生成コードが
# `C:\app\outputs\outputs_{RequestId}\{FileName}` へコピーしてから開く形になり、
# 書いたはずの場所に無い（`Package not found`）という失敗をした。
# 直叩きでは `RequestId` が空で偶然通っていたので、実機まで見えなかった。
EXTRACT_PROMPT_INSTRUCTIONS = """
添付された資料からテキストを抽出してください。

ファイル名: 〔FileName を挿入〕
資料: 〔File を挿入〕

- 拡張子は FileName から判定し、どのライブラリで開くかを決めること。
- **一時ファイルを書き出さないこと。ディスクにコピーしないこと。**
  受け取ったバイト列を io.BytesIO に包んで、そのままライブラリに渡すこと。
  os.makedirs や open(..., "wb") を使ってはならない。

      data = io.BytesIO(<File の中身>)
      .pptx → Presentation(data)
      .docx → Document(data)
      .xlsx → load_workbook(data)
      .pdf  → pdfminer.high_level.extract_text(data)

  すでにパス文字列で渡されている場合は、そのパスを直接ライブラリに渡すこと。
- 抽出したテキストを、そのまま全文返すこと。
  要約・切り詰め・整形・文字数制限を一切かけないこと。
- 抽出できなかった場合は EXTRACT_FAILED とだけ返し、例外の内容をログに出すこと。
""".strip()

# **プロンプトを2つに割っている。**
#
# code interpreter のコードに「抽出」と「文章を書く」を両方やらせたら、生成器は
# 後者も Python で実装した（先頭 1500 文字を「。」で切って4つ繋ぐだけの処理）。
# **説明文を書く主体がどこにもいなくなる。** しかも生成コードの中身は保存するまで
# 分からないので、機能の中心をそこに預けたくない。
#
#   ResourceDescription      … 抽出だけ（code interpreter あり）
#   ResourceDescriptionText  … 抽出テキストを読んで説明文を書く（text 専用）
#
# **どちらも UI でしか書けない。** 当初は後者をスクリプトから作る／更新する前提で
# 割ったが、この環境ではその経路が全部塞がっていた（`find_text_prompt` の docstring）。
# 割ったこと自体は無駄になっていない。抽出は決定的な処理で一度固めれば動き続け、
# 文章の質だけを別プロンプトとして扱える。
AI_TEXT_PROMPT_NAME = "ResourceDescriptionText"

# 抽出側が「取れなかった」を伝える合図。指示文と揃えること。
EXTRACT_FAILED_MARKER = "EXTRACT_FAILED"

# 説明文プロンプトの入力 id。UI で作るときの名前と揃える。
TEXT_INPUT_FILENAME = "fileName"
TEXT_INPUT_DOCUMENT = "documentText"

# UI に貼る指示文。**スクリプトから書き込めないので、ここは「正典の写し」**。
# 検査に失敗したときにそのまま出力して、貼り直せるようにする。
#
# `〔…〕` の位置に入力変数を差し込む。手順の列ではなく**依頼**として書くこと。
# 手順の列として書いたら、抽出側では生成器がそれを Python として実装した。
TEXT_PROMPT_INSTRUCTIONS = """
あなたは企業内の意思決定を支援するアシスタントです。
申請に添付された資料から抜き出したテキストを読み、判断者がその資料の位置づけを
素早く掴めるように、日本語で簡潔な説明文を書いてください。

ファイル名: 〔fileName を挿入〕

資料から抜き出したテキスト:
〔documentText を挿入〕

制約:
- 2〜4文。見出しや箇条書きは使わず、地の文で書く。
- 「何の資料か」「何が書かれているか」「判断者が見るべき点」をこの順で含める。
- テキストに書かれていないことを補わない。推測した内容を断定で書いてはならない。
- 「この資料は」のような定型の書き出しを付けず、本文から始める。
- テキストが空、EXTRACT_FAILED、または内容として意味をなさない場合は
  「この資料の内容を読み取れませんでした。」とだけ返す。
""".strip()


# AI Builder のドキュメント入力の上限。これを超えるとプロンプト側で失敗するので、
# **中身を取りに行く前に**メタデータのサイズで止める。大きなファイルを丸ごと
# 転送してから不透明に失敗するより、理由の言える失敗のほうがよい。
MAX_FILE_BYTES = 25 * 1024 * 1024

# プロンプトの入力 id。**UI が採番した実物**（`PredictionSchema` で確認）。
# 小文字で頼んだが `File` / `FileName` になっていたので、実物に合わせる。
PROMPT_INPUT_FILE = "File"
PROMPT_INPUT_FILENAME = "FileName"


def _escape_odata_string(value: str) -> str:
    return value.replace("'", "''")


def _connector_id(connector: str) -> str:
    return f"/providers/Microsoft.PowerApps/apis/{connector}"


def _workflow_definition(actions: dict, triggers: dict) -> dict:
    return {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {
            "$authentication": {"defaultValue": {}, "type": "SecureObject"},
            "$connections": {"defaultValue": {}, "type": "Object"},
        },
        "triggers": triggers,
        "actions": actions,
    }


def build_clientdata(
    dataverse_connection_reference: str,
    sharepoint_connection_reference: str,
    ai_model_id: str,
    text_model_id: str,
) -> str:
    """フローの clientdata を組む。

    **`runtimeSource` がこの機能の中心。** Dataverse は `embedded`（今までどおり
    所有者の接続で申請レコードを読み書きする）、SharePoint だけ `invoker`
    （呼び出した本人の接続で読む）。**同じフローの中で混在させられる。**
    """
    triggers = {
        "manual": {
            "type": "Request",
            "kind": "PowerAppV2",
            "inputs": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "title": "siteUrl",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                            "description": "SharePoint サイトの URL",
                        },
                        "text_1": {
                            "title": "filePath",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                            "description": "サイト内のファイルパス",
                        },
                    },
                    "required": ["text", "text_1"],
                }
            },
        }
    }

    actions = {
        # **身元を推測せず、名乗らせる。**
        # `_api/web/currentUser` は「この接続が誰として動いているか」を直接返す。
        # invoker が効いていれば呼び出した本人、効いていなければ接続所有者（管理者）。
        #
        # 当初はアクセス権の差（読めた/読めなかった）から身元を推測する A/B 対照を
        # 組む予定だったが、それは間接証拠でしかない。Learn が
        # 「This action may execute any SharePoint REST API **you have access to**」
        # と書いているとおり、この操作は接続の資格で動くので、そのまま身元の直接証拠になる。
        "Probe_identity": {
            "type": "OpenApiConnection",
            "runAfter": {},
            "inputs": {
                "host": {
                    "apiId": _connector_id(SHAREPOINT_CONNECTOR),
                    "connectionName": SHAREPOINT_CONNECTOR,
                    "operationId": "HttpRequest",
                },
                "parameters": {
                    "dataset": "@{triggerBody()?['text']}",
                    "parameters/method": "GET",
                    "parameters/uri": "_api/web/currentUser",
                    "parameters/headers": {
                        "accept": "application/json;odata=nometadata"
                    },
                },
                "authentication": "@parameters('$authentication')",
            },
        },
        # 読み取りの成否も併せて返す。**アクセス権で結果が変わる**ので、
        # 上の直接証拠に対する裏取りになる。両方が同じ結論を指すことを確認する。
        # 第2段ではここが**サイズの門番**も兼ねる（`Size` は SPBlobMetadataResponse の int64）。
        "Read_file_metadata": {
            "type": "OpenApiConnection",
            "runAfter": {"Probe_identity": ["Succeeded", "Failed", "TimedOut"]},
            "inputs": {
                "host": {
                    "apiId": _connector_id(SHAREPOINT_CONNECTOR),
                    "connectionName": SHAREPOINT_CONNECTOR,
                    "operationId": "GetFileMetadataByPath",
                },
                "parameters": {
                    "dataset": "@{triggerBody()?['text']}",
                    "path": "@{triggerBody()?['text_1']}",
                },
                "authentication": "@parameters('$authentication')",
            },
        },
        # **中身を取りに行く前に**サイズで止める。25 MB を超えるとプロンプト側で
        # 失敗するが、そこまで行くと「読み取りに失敗しました」に埋もれて、
        # 利用者にも我々にも理由が分からない失敗になる。
        "Describe_if_within_limit": {
            "type": "If",
            "runAfter": {"Read_file_metadata": ["Succeeded"]},
            "expression": {
                "lessOrEquals": [
                    "@int(coalesce(outputs('Read_file_metadata')?['body/Size'], 0))",
                    MAX_FILE_BYTES,
                ]
            },
            "actions": {
                "Get_file_content": {
                    "type": "OpenApiConnection",
                    "runAfter": {},
                    "inputs": {
                        "host": {
                            "apiId": _connector_id(SHAREPOINT_CONNECTOR),
                            "connectionName": SHAREPOINT_CONNECTOR,
                            "operationId": "GetFileContentByPath",
                        },
                        "parameters": {
                            "dataset": "@{triggerBody()?['text']}",
                            "path": "@{triggerBody()?['text_1']}",
                        },
                        "authentication": "@parameters('$authentication')",
                    },
                },
                # ファイルを**そのまま**プロンプトへ渡す。OCR も PDF 変換も挟まない。
                #
                # 値の形は推測していない。`PredictionSchema` が
                # `File: {required: [base64Encoded], properties: {base64Encoded: {type: string, format: byte}}}`
                # と返したので、そのとおりに入れ子で渡す。
                # バイナリ出力は Logic Apps では `{$content-type, $content}` になり、
                # `$content` が base64（2026-08-16 の初回実行で 147,604 文字が届くのを確認）。
                #
                # **このプロンプトは抽出しかしない。** 説明文は次の段で書く。
                "Extract_text": {
                    "type": "OpenApiConnection",
                    "runAfter": {"Get_file_content": ["Succeeded"]},
                    "inputs": {
                        "host": {
                            "apiId": _connector_id(DATAVERSE_CONNECTOR),
                            "connectionName": DATAVERSE_CONNECTOR_AI,
                            "operationId": "aibuilderpredict_customprompt",
                        },
                        "parameters": {
                            "recordId": ai_model_id,
                            # **base64 を渡してはいけない。バイナリを渡す。**
                            #
                            # `$content` は既に base64 文字列。それをそのまま
                            # `format: byte` のフィールドへ入れると、**コネクタが
                            # もう一度 base64 する**（二重符号化）。プロンプト側は
                            # 1回だけ復号するので、手元に残るのは base64 テキストで、
                            # zip として開けず `File is not a zip file` になる。
                            #
                            # 実行履歴のログがそれを名指しした:
                            #   source=input type=str size=147604 head=b'UEsD'
                            #   （147604 は base64 の長さ。復号後は 110703 のはず）
                            #
                            # `base64ToBinary` で一度バイナリに戻し、符号化は
                            # コネクタに1回だけやらせる。
                            f"item/requestv2/{PROMPT_INPUT_FILE}/base64Encoded": (
                                "@base64ToBinary(outputs('Get_file_content')?['body']?['$content'])"
                            ),
                            f"item/requestv2/{PROMPT_INPUT_FILENAME}": (
                                "@coalesce(outputs('Read_file_metadata')?['body/Name'],"
                                " triggerBody()?['text_1'])"
                            ),
                        },
                        "authentication": "@parameters('$authentication')",
                    },
                },
                # 抽出したテキストを読んで**説明文を書く**段。
                # ここを別プロンプトにしているのは、code interpreter の生成コードに
                # 文章を書かせると Python の文字列処理に化けたため（2026-08-16 実測）。
                # 抽出は決定的な処理なので一度固めれば動き続け、文章の質だけを
                # 独立して扱える。**指示文はどちらも UI でしか書けない**
                # （`find_text_prompt` の docstring に潰した経路を残してある）。
                "Write_description": {
                    "type": "OpenApiConnection",
                    "runAfter": {"Extract_text": ["Succeeded"]},
                    "inputs": {
                        "host": {
                            "apiId": _connector_id(DATAVERSE_CONNECTOR),
                            "connectionName": DATAVERSE_CONNECTOR_AI,
                            "operationId": "aibuilderpredict_customprompt",
                        },
                        "parameters": {
                            "recordId": text_model_id,
                            "item/requestv2/documentText": (
                                "@coalesce(outputs('Extract_text')"
                                "?['body/responsev2/predictionOutput/text'], '')"
                            ),
                            "item/requestv2/fileName": (
                                "@coalesce(outputs('Read_file_metadata')?['body/Name'],"
                                " triggerBody()?['text_1'])"
                            ),
                        },
                        "authentication": "@parameters('$authentication')",
                    },
                },
            },
        },
        "Respond": {
            "type": "Response",
            "kind": "PowerApp",
            # 失敗しても応答を返す。**失敗の仕方こそが知りたい情報**なので握り潰さない。
            # 分岐が丸ごと飛ばされる（メタデータが失敗）ことも、分岐の中で失敗する
            # （生成が転ぶ）こともあるので、Skipped と Failed の両方を受ける。
            "runAfter": {
                "Describe_if_within_limit": ["Succeeded", "Failed", "TimedOut", "Skipped"]
            },
            "inputs": {
                "statusCode": 200,
                "body": {
                    "status": "@{if(equals(outputs('Read_file_metadata')?['statusCode'], 200), 'succeeded', 'failed')}",
                    "detail": "@{string(coalesce(outputs('Read_file_metadata')?['body'], ''))}",
                    # 呼び出した本人の UPN。**取れなかったときは空**にする。
                    # 生のエラー本文をここへ落とすと、利用者のトーストに
                    # JSON がそのまま出る（2026-08-16 に実機で確認した粗さ）。
                    # 権限で弾かれた事実は status / detail が運ぶので、
                    # ここは身元だけを持たせる。
                    "actingAs": "@{string(coalesce(outputs('Probe_identity')?['body']?['LoginName'], outputs('Probe_identity')?['body']?['Email'], ''))}",
                    # 生成された説明文。**取れなかったときは空。**
                    # 出力形式は text なので `predictionOutput/text` に入る
                    # （`PredictionSchema` の output で確認。structuredOutput は無い）。
                    "description": (
                        "@{string(coalesce("
                        "outputs('Write_description')?['body/responsev2/predictionOutput/text'], ''))}"
                    ),
                    # **なぜ説明が無いのか**を UI が言えるようにする。空文字だけ返すと、
                    # 権限・サイズ・生成失敗が画面から区別できなくなる。
                    #
                    # **中身の取得失敗を `generation-failed` に混ぜない。**
                    # メタデータと中身は別の操作なので、メタデータが通って中身が
                    # 403 になることがある。そのとき Extract_text は飛ばされるので、
                    # 順番を工夫しないと「生成に失敗」と読めてしまう。
                    # ファイルは一度も読めていないのに、プロンプトを疑うことになる。
                    #
                    # 判定順が意味を持つ: サイズ超過で分岐ごと飛んだときも
                    # Get_file_content の出力は空なので、先に too-large を見る。
                    #
                    # **抽出の失敗と文章生成の失敗も混ぜない。** 別々のプロンプトなので、
                    # 直す対象が違う。一緒くたにすると、毎回どちらを疑うかの判断から
                    # やり直しになる（実際にそれで3往復した）。
                    "reason": (
                        "@{if(not(equals(outputs('Read_file_metadata')?['statusCode'], 200)), 'unreadable',"
                        f" if(greater(int(coalesce(outputs('Read_file_metadata')?['body/Size'], 0)), {MAX_FILE_BYTES}), 'too-large',"
                        " if(not(equals(outputs('Get_file_content')?['statusCode'], 200)), 'content-unreadable',"
                        " if(or(empty(coalesce(outputs('Extract_text')?['body/responsev2/predictionOutput/text'], '')),"
                        f" equals(trim(coalesce(outputs('Extract_text')?['body/responsev2/predictionOutput/text'], '')), '{EXTRACT_FAILED_MARKER}')),"
                        " 'extract-failed',"
                        " if(empty(coalesce(outputs('Write_description')?['body/responsev2/predictionOutput/text'], '')),"
                        " 'generation-failed', '')))))}"
                    ),
                },
                "schema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "title": "status",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                        },
                        "detail": {
                            "title": "detail",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                        },
                        "actingAs": {
                            "title": "actingAs",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                        },
                        "description": {
                            "title": "description",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                        },
                        "reason": {
                            "title": "reason",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                        },
                    },
                },
            },
        },
    }

    # **どのアクションも使わない接続参照は書かない。**
    # 素の `shared_commondataserviceforapps` を入れていたが、AI Builder の
    # アクションが名指しするのは `_1` の別名だけで、素の方は誰も使っていなかった。
    # プラットフォームは保存時にそれを落とす。**こちらが書いたものと保存されたものが
    # ずれる**ので、最初から書かない。
    connection_references = {
        # AI Builder のアクションが名指しする別名。
        DATAVERSE_CONNECTOR_AI: {
            "runtimeSource": "embedded",
            "connection": {
                "connectionReferenceLogicalName": dataverse_connection_reference
            },
            "api": {"name": DATAVERSE_CONNECTOR},
        },
        SHAREPOINT_CONNECTOR: {
            # ここが本体。embedded にすると所有者の資格で読む穴になる。
            #
            # **生の接続 ID ではなく接続参照で束ねる。** 生の ID は
            # 新しいデザイナーが警告するうえ、移送先で解決できずに壊れる。
            # 実行時に使われるのは呼び出した本人の接続で、ここで指すのは
            # **設計時の束ね先**でしかない。
            "runtimeSource": "invoker",
            "connection": {
                "connectionReferenceLogicalName": sharepoint_connection_reference
            },
            "api": {"name": SHAREPOINT_CONNECTOR},
        },
    }

    return json.dumps(
        {
            "properties": {
                "definition": _workflow_definition(actions, triggers),
                "connectionReferences": connection_references,
            },
            "schemaVersion": "1.0.0.0",
        },
        ensure_ascii=False,
    )


def find_existing_flow(flow_name: str) -> dict | None:
    existing = api_get(
        f"workflows?$filter=name eq '{_escape_odata_string(flow_name)}' and category eq 5"
        "&$select=workflowid,statecode&$orderby=createdon desc&$top=1"
    ).get("value", [])
    return existing[0] if existing else None


def find_sharepoint_connection_reference() -> str:
    """SharePoint の接続参照の論理名を引く。

    **生の接続 ID を焼き込まない。** 新しいデザイナーが
    「Uses a connection instead of a connection reference」と警告するのはここで、
    移送（別環境へのインポート）でも生の ID は解決できずに壊れる。

    **接続参照にしても invoker は維持できるはず**（Learn は「invoker 接続は
    エクスポートすると RuntimeSource が invoker」と書いており、
    エクスポート＝接続参照の世界）。ただし**そこは実行して確かめる**。
    `runtimeSource` の文字列が invoker でも、実行時に本人の資格で動く証明にはならない
    （登録の確認と実行の確認は別物）。応答の `actingAs` で見る。
    """
    refs = api_get(
        "connectionreferences?$filter=connectorid eq "
        f"'{_connector_id(SHAREPOINT_CONNECTOR)}'"
        "&$select=connectionreferencelogicalname,connectionid&$top=5"
    ).get("value", [])
    bound = [ref for ref in refs if ref.get("connectionid")]
    if not bound:
        raise RuntimeError(
            "SharePoint の接続参照が見つかりません。"
            "`npx power-apps add-flow` で作られるか、手で作成してください。"
        )
    return bound[0]["connectionreferencelogicalname"]


def find_dataverse_connection_reference() -> str:
    """既存フローが使っている Dataverse 接続参照の論理名を借りる。

    新しく作らない。**接続参照を増やすと移送のたびに紐付け直しが増える。**
    """
    refs = api_get(
        "connectionreferences?$filter=connectorid eq "
        f"'{_connector_id(DATAVERSE_CONNECTOR)}'"
        "&$select=connectionreferencelogicalname,connectionid&$top=5"
    ).get("value", [])
    bound = [r for r in refs if r.get("connectionid")]
    if not bound:
        raise RuntimeError(
            "Dataverse の接続参照が見つかりません。先に既存フローを配備してください。"
        )
    return bound[0]["connectionreferencelogicalname"]


def find_ai_prompt() -> str:
    """`ResourceDescription` プロンプトの model id を名前で引く。**作らない。**

    code interpreter 付きのプロンプトは `code`（生成された Python）と `signature`
    （プラットフォーム発行の整合性トークン。geography / cluster / key version が
    焼き込まれている）を持つ。**署名を手元で作れない**ので `AIModelPublish` では
    再現できない。Learn が「You must use the UI to create code interpreter enabled
    prompts」と書いているのは、この署名のことだと読める。

    無ければ**黙って別のものを使わず落とす**。text 専用のプロンプトを掴んで
    「動いているように見えて Office が読めない」が一番たちが悪い。
    """
    models = api_get(
        f"msdyn_aimodels?$filter=msdyn_name eq '{_escape_odata_string(AI_PROMPT_NAME)}'"
        "&$select=msdyn_aimodelid,statecode&$orderby=createdon desc&$top=1"
    ).get("value", [])
    if not models:
        raise RuntimeError(
            f"AI Builder プロンプト '{AI_PROMPT_NAME}' が見つかりません。\n"
            "AI Hub の UI で作成してください（code interpreter を ON、"
            "ドキュメント入力とテキスト入力を1つずつ、出力は Text）。\n"
            "このスクリプトでは作れません（署名を発行できないため）。"
        )
    model = models[0]
    if model.get("statecode") != 1:
        raise RuntimeError(
            f"'{AI_PROMPT_NAME}' が Active ではありません（statecode="
            f"{model.get('statecode')}）。公開してから配備してください。"
        )
    return model["msdyn_aimodelid"]


def find_text_prompt() -> str:
    """`ResourceDescriptionText` を名前で引き、**使える形になっているかを検める。**

    当初はここで作る／更新するつもりだった。**この環境では両方できない。**
    潰した経路を残しておく（同じ道を二度探さないため）。

    | 試したこと | 結果 |
    | --- | --- |
    | `PublishAIConfiguration` で新規公開 | ❌ 400 `Missing privilege definition: prvWritemsdyn_AIModel` |
    | `statecode` を直接 PATCH して公開済みに見せる | ❌ `Unexpected parameter(s) statecode, statuscode` |
    | `msdyn_customconfiguration` を直接 PATCH | ❌ `Unexpected parameter(s) msdyn_customconfiguration` |
    | 既存モデルへ `AIModelPublish` | ⚠ **200 が返るのに反映されない** |

    最後のものが一番たちが悪い。**成功したように見えて、保存されているのは
    UI で作ったときの空の指示文のまま**だった。ステータスコードを信じて
    「更新できた」と報告する寸前だった。中身を読み直して初めて分かった。

    したがって**指示文は UI でしか書けない**。ここでできるのは検査だけ。
    それでも検査には意味がある。**空のプロンプトのまま配線が通ってしまうと、
    説明文が静かに空で返る**（`generation-failed` としか分からない）。
    ここで落とせば、原因が名指しで出る。
    """
    models = api_get(
        f"msdyn_aimodels?$filter=msdyn_name eq '{_escape_odata_string(AI_TEXT_PROMPT_NAME)}'"
        "&$select=msdyn_aimodelid,statecode,_msdyn_activerunconfigurationid_value"
        "&$orderby=createdon desc&$top=1"
    ).get("value", [])

    if not models:
        raise RuntimeError(
            f"AI Builder プロンプト '{AI_TEXT_PROMPT_NAME}' が見つかりません。\n"
            f"{_text_prompt_setup_hint()}"
        )

    model = models[0]
    model_id = model["msdyn_aimodelid"]
    if model.get("statecode") != 1:
        raise RuntimeError(
            f"'{AI_TEXT_PROMPT_NAME}' が Active ではありません"
            f"（statecode={model.get('statecode')}）。AI Hub で保存し直してください。"
        )

    run_config_id = model.get("_msdyn_activerunconfigurationid_value")
    if not run_config_id:
        raise RuntimeError(
            f"'{AI_TEXT_PROMPT_NAME}' に有効な run configuration がありません"
            f"（model={model_id}）。作りかけで止まっている可能性があります。"
        )

    raw = api_get(
        f"msdyn_aiconfigurations({run_config_id})?$select=msdyn_customconfiguration"
    ).get("msdyn_customconfiguration")
    try:
        config = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"'{AI_TEXT_PROMPT_NAME}' の設定を読めませんでした: {exc}"
        ) from exc

    inputs = {item.get("id") for item in config.get("definitions", {}).get("inputs", [])}
    missing = {TEXT_INPUT_FILENAME, TEXT_INPUT_DOCUMENT} - inputs
    if missing:
        raise RuntimeError(
            f"'{AI_TEXT_PROMPT_NAME}' に入力 {sorted(missing)} がありません"
            f"（実際: {sorted(inputs)}）。\n{_text_prompt_setup_hint()}"
        )

    # **指示文が空のまま配線しない。** 入力変数だけ並んでいて地の文が無い状態でも
    # プロンプトは動いてしまい、意味を成さない出力が静かに返る。
    literal_length = sum(
        len((segment.get("text") or "").strip())
        for segment in config.get("prompt", [])
        if segment.get("type") == "literal"
    )
    if literal_length < 100:
        raise RuntimeError(
            f"'{AI_TEXT_PROMPT_NAME}' の指示文が空か短すぎます"
            f"（地の文 {literal_length} 文字）。\n{_text_prompt_setup_hint()}"
        )

    print(f"  指示文 OK（地の文 {literal_length} 文字 / 入力 {sorted(inputs)}）")
    print(f"  modelType: {config.get('modelParameters', {}).get('modelType')}")
    return model_id


def _text_prompt_setup_hint() -> str:
    return (
        "AI Hub の UI で用意してください（**指示文はスクリプトから書き込めません**）。\n"
        "  - code interpreter は OFF\n"
        f"  - テキスト入力を2つ: `{TEXT_INPUT_FILENAME}` と `{TEXT_INPUT_DOCUMENT}`\n"
        "  - 出力は Text\n"
        "  - 指示文は下記を貼る:\n\n"
        + "\n".join("    " + line for line in TEXT_PROMPT_INSTRUCTIONS.splitlines())
    )


def _write_debug(body: dict) -> Path:
    debug_path = ROOT / "scripts" / f"{FLOW_NAME}_debug.json"
    debug_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return debug_path


def create_flow(clientdata: str) -> str:
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    body = {
        "name": FLOW_NAME,
        "type": 1,
        "category": 5,
        "statecode": 0,
        "statuscode": 1,
        "primaryentity": "none",
        "clientdata": clientdata,
        "description": FLOW_DESCRIPTION,
    }
    response = session.post(f"{API}/workflows", json=body)
    if not response.ok:
        raise RuntimeError(
            f"{FLOW_NAME} の作成に失敗しました: {response.status_code}\n"
            f"{response.text[:2000]}\nDebug: {_write_debug(body)}"
        )
    workflow_id = response.headers.get("OData-EntityId", "").split("(")[-1].rstrip(")")
    _activate(session, workflow_id, body)
    return workflow_id


def update_flow(workflow_id: str, statecode: int, clientdata: str) -> str:
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    deactivated = False
    if statecode == 1:
        if session.patch(
            f"{API}/workflows({workflow_id})", json={"statecode": 0, "statuscode": 1}
        ).ok:
            deactivated = True
        else:
            print(f"  Warning: {FLOW_NAME} の無効化に失敗しました。active のまま更新を試みます。")
    body = {"clientdata": clientdata, "description": FLOW_DESCRIPTION}
    response = session.patch(f"{API}/workflows({workflow_id})", json=body)
    if not response.ok:
        raise RuntimeError(
            f"{FLOW_NAME} の更新に失敗しました: {response.status_code}\n"
            f"{response.text[:2000]}\nDebug: {_write_debug(body)}"
        )
    if statecode != 1 or deactivated:
        _activate(session, workflow_id, body)
    return workflow_id


def _activate(session: requests.Session, workflow_id: str, body: dict) -> None:
    response = session.patch(
        f"{API}/workflows({workflow_id})", json={"statecode": 1, "statuscode": 2}
    )
    if not response.ok:
        raise RuntimeError(
            f"{FLOW_NAME} の有効化に失敗しました: {response.status_code}\n"
            f"{response.text[:2000]}\nDebug: {_write_debug(body)}"
        )


def verify_runtime_source(workflow_id: str) -> None:
    """**設定したつもりで embedded のままが一番危ない。** 書いた後に読んで確かめる。

    SharePoint の1キーだけを見るのでは足りない。**キーの集合ごと固定する。**
    後からコネクタが1つ増えたとき、既定値のまま不変条件をすり抜けるのを防ぐ
    （増えたコネクタが外部を読むなら、それも invoker かどうかの判断が要る）。

    **束ね方（接続参照か生の接続か）も見る。** 2026-08-16 に、配備したあと
    保存されている clientdata が書き換わっているのを見つけた
    （デザイナーで開いた形跡があり、`modifiedon` が配備より後だった）。

        送った形   `_1` は connectionReferenceLogicalName / 素の Dataverse も同梱
        保存された形 `_1` は**生の接続 ID** / 素の Dataverse は**消えている**

    `runtimeSource` しか見ていなかったので**この書き換えを検知できなかった**。
    生の接続 ID は移送先で解決できず、新しいデザイナーも警告する。
    """
    expected = {DATAVERSE_CONNECTOR_AI, SHAREPOINT_CONNECTOR}

    record = api_get(f"workflows({workflow_id})?$select=clientdata")
    refs = json.loads(record["clientdata"])["properties"]["connectionReferences"]

    actual = set(refs)
    if actual != expected:
        raise RuntimeError(
            "接続参照のキーが想定と違います。\n"
            f"  想定: {sorted(expected)}\n"
            f"  実際: {sorted(actual)}\n"
            "増えたコネクタが外部を読むなら、invoker にすべきか判断してから通してください。"
        )

    if refs[SHAREPOINT_CONNECTOR].get("runtimeSource") != "invoker":
        raise RuntimeError(
            f"SharePoint 接続の runtimeSource が "
            f"'{refs[SHAREPOINT_CONNECTOR].get('runtimeSource')}' です。"
            "invoker でないと所有者の資格で読む穴になります。"
        )

    for connector in expected - {SHAREPOINT_CONNECTOR}:
        source = refs[connector].get("runtimeSource")
        if source != "embedded":
            raise RuntimeError(
                f"{connector} の runtimeSource が '{source}' です。"
                "申請レコードの読み書きは所有者の接続で行うので embedded が正しい。"
            )

    # **束ね方も固定する。** 生の接続 ID に落ちていたら移送で壊れる。
    raw_bound = [
        connector
        for connector in expected
        if "connectionReferenceLogicalName" not in refs[connector].get("connection", {})
    ]
    if raw_bound:
        raise RuntimeError(
            f"生の接続 ID で束ねられているコネクタがあります: {sorted(raw_bound)}\n"
            "接続参照で束ねてください（移送先で解決できず、"
            "新しいデザイナーも警告します）。"
        )

    print(f"  OK: {SHAREPOINT_CONNECTOR}.runtimeSource = invoker")
    for connector in sorted(expected - {SHAREPOINT_CONNECTOR}):
        print(f"  OK: {connector}.runtimeSource = embedded")
    for connector in sorted(expected):
        logical = refs[connector]["connection"]["connectionReferenceLogicalName"]
        print(f"  OK: {connector} は接続参照 {logical} で束ねている")


def main() -> None:
    if not DATAVERSE_URL:
        raise RuntimeError("DATAVERSE_URL が .env に設定されていません。")
    print("=== DecisionFlow resource description flow (stage 2: 説明文の生成) ===")
    print(f"Dataverse: {DATAVERSE_URL}")

    dataverse_ref = find_dataverse_connection_reference()
    print(f"Dataverse connection reference: {dataverse_ref}")

    ai_model_id = find_ai_prompt()
    print(f"AI Builder prompt (抽出・UI 製): {AI_PROMPT_NAME} ({ai_model_id})")

    print(f"AI Builder prompt (説明文・UI 製): {AI_TEXT_PROMPT_NAME}")
    text_model_id = find_text_prompt()
    print(f"  -> {text_model_id}")

    sharepoint_ref = find_sharepoint_connection_reference()
    print(f"SharePoint connection reference: {sharepoint_ref}")

    clientdata = build_clientdata(
        dataverse_ref, sharepoint_ref, ai_model_id, text_model_id
    )
    existing = find_existing_flow(FLOW_NAME)
    if existing:
        workflow_id = update_flow(
            existing["workflowid"], existing.get("statecode", 0), clientdata
        )
        print(f"Updated flow: {workflow_id}")
    else:
        workflow_id = create_flow(clientdata)
        print(f"Created flow: {workflow_id}")

    verify_runtime_source(workflow_id)
    print("\n次: **応答スキーマ（Respond の properties）を変えたときだけ**")
    print(f"    npx power-apps add-flow --flow-id {workflow_id}")
    print("    で生成物を作り直してから build → push する。")
    print("    アクションの中身だけを変えたなら、フローはこの時点で新しくなっている。")


if __name__ == "__main__":
    main()
