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

    # 共有リンクは `text_1` に `u!…`（base64url 符号化した共有 URL）で入ってくる。
    # **トリガーの引数を増やしていない。** `text_1` は元々「ファイルの指し方」で、
    # パスかトークンかの違いでしかない。増やすと生成物の作り直しが要る。
    # 式の中に埋める形（`@` 無し）と、単独で評価する形（`@` 付き）の2つが要る。
    sharing_test = "startsWith(coalesce(triggerBody()?['text_1'], ''), 'u!')"
    is_sharing_link = f"@{sharing_test}"

    # 共有リンクとパス形式で**入口だけが違い、その先は同じ**。
    # 名前・サイズ・中身が取れれば、抽出も説明文も分岐しない。
    # 分岐を下流まで引きずると、`reason` の判定が組み合わせ爆発する。
    share = "body('Read_share')"
    file_size = (
        f"int(coalesce({share}?['size'],"
        " outputs('Read_file_metadata')?['body/Size'], 0))"
    )
    file_name = (
        f"coalesce({share}?['name'],"
        " outputs('Read_file_metadata')?['body/Name'], triggerBody()?['text_1'])"
    )
    # バイナリ出力は Logic Apps では `{$content-type, $content}`。`$content` が base64。
    content_base64 = (
        "coalesce(outputs('Get_share_content')?['body']?['$content'],"
        " outputs('Get_file_content')?['body']?['$content'])"
    )
    source_ok = (
        "or(equals(outputs('Read_share')?['statusCode'], 200),"
        " equals(outputs('Read_file_metadata')?['statusCode'], 200))"
    )

    def sharepoint_http(uri: str, run_after: dict | None = None) -> dict:
        """SharePoint の REST を本人の資格で叩く。

        **`Prefer` ヘッダーを付けない。** `redeemSharingLink` を送ると
        共有リンクを引き換えて恒久的なアクセス権を与えてしまう。
        """
        return {
            "type": "OpenApiConnection",
            "runAfter": run_after or {},
            "inputs": {
                "host": {
                    "apiId": _connector_id(SHAREPOINT_CONNECTOR),
                    "connectionName": SHAREPOINT_CONNECTOR,
                    "operationId": "HttpRequest",
                },
                "parameters": {
                    "dataset": "@{triggerBody()?['text']}",
                    "parameters/method": "GET",
                    "parameters/uri": uri,
                    "parameters/headers": {"accept": "application/json"},
                },
                "authentication": "@parameters('$authentication')",
            },
        }

    def sharepoint_file(operation_id: str, run_after: dict | None = None) -> dict:
        return {
            "type": "OpenApiConnection",
            "runAfter": run_after or {},
            "inputs": {
                "host": {
                    "apiId": _connector_id(SHAREPOINT_CONNECTOR),
                    "connectionName": SHAREPOINT_CONNECTOR,
                    "operationId": operation_id,
                },
                "parameters": {
                    "dataset": "@{triggerBody()?['text']}",
                    "path": "@{triggerBody()?['text_1']}",
                },
                "authentication": "@parameters('$authentication')",
            },
        }

    actions = {
        # **身元を推測せず、名乗らせる。**
        # `_api/web/currentUser` は「この接続が誰として動いているか」を直接返す。
        # invoker が効いていれば呼び出した本人、効いていなければ接続所有者（管理者）。
        "Probe_identity": sharepoint_http("_api/web/currentUser"),
        # ここが入口の分岐。**共有リンクは Graph 互換の `shares` で解決する。**
        #
        # `_api/v2.0/shares/{u!…}/driveItem` は SharePoint コネクタ越しに 200 を返し、
        # `name` / `size` / `@content.downloadUrl` を持って戻る（2026-08-16 実測）。
        # **パスを組み立て直す必要が無い**ので、`_layouts` 形式の webUrl を
        # 解析するような脆い処理を入れずに済む。
        #
        # 解決は invoker の資格で行われるので、**本人が未受諾のリンクはここで失敗する。
        # それが正しい挙動**（フローが権限を与える装置になってはいけない）。
        "Read_source": {
            "type": "If",
            "runAfter": {"Probe_identity": ["Succeeded", "Failed", "TimedOut"]},
            "expression": {"equals": [is_sharing_link, True]},
            "actions": {
                "Read_share": sharepoint_http(
                    "_api/v2.0/shares/@{triggerBody()?['text_1']}/driveItem"
                ),
            },
            "else": {
                "actions": {
                    "Read_file_metadata": sharepoint_file("GetFileMetadataByPath"),
                }
            },
        },
        # **中身を取りに行く前に**サイズで止める。25 MB を超えるとプロンプト側で
        # 失敗するが、そこまで行くと理由の分からない失敗になる。
        "Describe_if_within_limit": {
            "type": "If",
            "runAfter": {"Read_source": ["Succeeded", "Failed", "TimedOut"]},
            "expression": {
                "and": [
                    {"equals": [f"@{source_ok}", True]},
                    {"lessOrEquals": [f"@{file_size}", MAX_FILE_BYTES]},
                ]
            },
            "actions": {
                # 中身の取り方も入口ごとに違う。ここから先は同じ。
                "Fetch_content": {
                    "type": "If",
                    "runAfter": {},
                    "expression": {"equals": [is_sharing_link, True]},
                    "actions": {
                        # **`downloadUrlNoAuth` を使う。** 認証トークン付きの
                        # `downloadUrl` ではなく、呼び出し側の資格で解決される方。
                        # サイト相対にして invoker の接続で取りに行く。
                        "Get_share_content": sharepoint_http(
                            "@{replace(body('Read_share')?['@content.downloadUrlNoAuth'],"
                            " concat(triggerBody()?['text'], '/'), '')}"
                        ),
                    },
                    "else": {
                        "actions": {
                            "Get_file_content": sharepoint_file("GetFileContentByPath"),
                        }
                    },
                },
                # ファイルを**そのまま**プロンプトへ渡す。OCR も PDF 変換も挟まない。
                #
                # 値の形は推測していない。`PredictionSchema` が
                # `File: {required: [base64Encoded], …}` と返したのでそのとおり入れ子で渡す。
                #
                # **base64 を渡してはいけない。バイナリを渡す。** `$content` は既に
                # base64 文字列で、`format: byte` のフィールドへ直接入れると
                # コネクタがもう一度 base64 する（二重符号化）。プロンプト側は1回しか
                # 復号しないので `File is not a zip file` になる（2026-08-16 実測）。
                "Extract_text": {
                    "type": "OpenApiConnection",
                    "runAfter": {"Fetch_content": ["Succeeded"]},
                    "inputs": {
                        "host": {
                            "apiId": _connector_id(DATAVERSE_CONNECTOR),
                            "connectionName": DATAVERSE_CONNECTOR_AI,
                            "operationId": "aibuilderpredict_customprompt",
                        },
                        "parameters": {
                            "recordId": ai_model_id,
                            f"item/requestv2/{PROMPT_INPUT_FILE}/base64Encoded": (
                                f"@base64ToBinary({content_base64})"
                            ),
                            f"item/requestv2/{PROMPT_INPUT_FILENAME}": f"@{file_name}",
                        },
                        "authentication": "@parameters('$authentication')",
                    },
                },
                # 抽出したテキストを読んで**説明文を書く**段。
                # 別プロンプトなのは、code interpreter の生成コードに文章を書かせると
                # Python の文字列処理に化けるため（2026-08-16 実測）。抽出側は
                # モデルを呼んでおらず、クレジットも 0。**文章を書けるのはこちらだけ。**
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
                            f"item/requestv2/{TEXT_INPUT_DOCUMENT}": (
                                "@coalesce(outputs('Extract_text')"
                                "?['body/responsev2/predictionOutput/text'], '')"
                            ),
                            f"item/requestv2/{TEXT_INPUT_FILENAME}": f"@{file_name}",
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
            "runAfter": {
                "Describe_if_within_limit": ["Succeeded", "Failed", "TimedOut", "Skipped"]
            },
            "inputs": {
                "statusCode": 200,
                "body": {
                    "status": f"@{{if({source_ok}, 'succeeded', 'failed')}}",
                    # 診断用。パス形式ならメタデータ本体、共有リンクならファイル名。
                    "detail": (
                        "@{string(coalesce(outputs('Read_file_metadata')?['body'], "
                        + share
                        + "?['name'], ''))}"
                    ),
                    # 呼び出した本人の UPN。**取れなかったときは空**にする。
                    # 生のエラー本文をここへ落とすと利用者のトーストに JSON が出る。
                    "actingAs": "@{string(coalesce(outputs('Probe_identity')?['body']?['LoginName'], outputs('Probe_identity')?['body']?['Email'], ''))}",
                    # 出力形式は text なので `predictionOutput/text` に入る。
                    "description": (
                        "@{string(coalesce("
                        "outputs('Write_description')?['body/responsev2/predictionOutput/text'], ''))}"
                    ),
                    # **なぜ説明が無いのか**を UI が言えるようにする。
                    #
                    # 判定順が意味を持つ。**共有リンクを最初に見る**のは、
                    # 解決できなかった共有リンクが「ファイルが見つかりません」
                    # （＝パスが違う）に化けると、利用者に URL の打ち直しをさせるから。
                    # 原因が違う。
                    #
                    # 抽出の失敗と文章生成の失敗も分ける。別のプロンプトなので
                    # 直す対象が違う（一緒くたにして実際に3往復した）。
                    "reason": (
                        f"@{{if(and({sharing_test},"
                        " not(equals(outputs('Read_share')?['statusCode'], 200))),"
                        " 'sharing-link-unresolved',"
                        f" if(not({source_ok}), 'unreadable',"
                        f" if(greater({file_size}, {MAX_FILE_BYTES}), 'too-large',"
                        f" if(empty({content_base64}), 'content-unreadable',"
                        " if(or(empty(coalesce(outputs('Extract_text')?['body/responsev2/predictionOutput/text'], '')),"
                        f" equals(trim(coalesce(outputs('Extract_text')?['body/responsev2/predictionOutput/text'], '')), '{EXTRACT_FAILED_MARKER}')),"
                        " 'extract-failed',"
                        " if(empty(coalesce(outputs('Write_description')?['body/responsev2/predictionOutput/text'], '')),"
                        " 'generation-failed', ''))))))}"
                    ),
                },
                "schema": {
                    "type": "object",
                    "properties": {
                        name: {
                            "title": name,
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                        }
                        for name in ("status", "detail", "actingAs", "description", "reason")
                    },
                },
            },
        },
    }


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


def _prompt_setup_hint(
    name: str, *, code_interpreter: bool, inputs: str, instructions: str
) -> str:
    """UI で何をすればよいかを、**貼れる形**で出す。

    **指示文をこのスクリプトから書き込むことはできない。** ここでできるのは
    「正本を持っておいて、必要なときに表示する」ことだけ。
    """
    return (
        f"AI Hub の UI で用意してください（**指示文はスクリプトから書き込めません**）。\n"
        f"  - 名前: {name}\n"
        f"  - code interpreter: {'ON' if code_interpreter else 'OFF'}\n"
        f"  - 入力: {inputs}\n"
        "  - 出力: Text\n"
        "  - 指示文は下記を貼る（`〔…〕` の位置に入力変数を差し込む）:\n\n"
        + "\n".join("    " + line for line in instructions.splitlines())
    )


def _require_prompt(
    name: str,
    *,
    expected_inputs: set[str],
    instructions: str,
    code_interpreter: bool,
    inputs_label: str,
) -> str:
    """プロンプトを名前で引き、**使える形になっているかを検める。作らない。**

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

    **したがって作成も編集も UI でしかできない。ここでできるのは検査だけ。**
    それでも検査には意味がある。**形が違っても配線は通ってしまい、実行時に
    静かに失敗する**（説明が空で返り、画面には `extract-failed` としか出ない）。
    ここで落とせば、原因が名指しで出て、貼るべき指示文もその場に出る。
    """
    hint = _prompt_setup_hint(
        name,
        code_interpreter=code_interpreter,
        inputs=inputs_label,
        instructions=instructions,
    )

    models = api_get(
        f"msdyn_aimodels?$filter=msdyn_name eq '{_escape_odata_string(name)}'"
        "&$select=msdyn_aimodelid,statecode,_msdyn_activerunconfigurationid_value"
        "&$orderby=createdon desc&$top=1"
    ).get("value", [])
    if not models:
        raise RuntimeError(f"AI Builder プロンプト '{name}' が見つかりません。\n{hint}")

    model = models[0]
    model_id = model["msdyn_aimodelid"]
    if model.get("statecode") != 1:
        raise RuntimeError(
            f"'{name}' が Active ではありません（statecode={model.get('statecode')}）。"
            "AI Hub で保存し直してください。"
        )

    run_config_id = model.get("_msdyn_activerunconfigurationid_value")
    if not run_config_id:
        raise RuntimeError(
            f"'{name}' に有効な run configuration がありません（model={model_id}）。"
            "作りかけで止まっている可能性があります。"
        )

    raw = api_get(
        f"msdyn_aiconfigurations({run_config_id})?$select=msdyn_customconfiguration"
    ).get("msdyn_customconfiguration")
    try:
        config = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"'{name}' の設定を読めませんでした: {exc}") from exc

    actual_inputs = {
        item.get("id") for item in config.get("definitions", {}).get("inputs", [])
    }
    missing = expected_inputs - actual_inputs
    if missing:
        raise RuntimeError(
            f"'{name}' に入力 {sorted(missing)} がありません"
            f"（実際: {sorted(actual_inputs)}）。\n{hint}"
        )

    # **code interpreter の入れ忘れは実行時まで見えない。**
    # Office ファイルはこれが無いとドキュメント入力として扱われない。
    # 保存された設定では `settings.runtime` が `codeinterpreter` になる（実測）。
    runtime = (config.get("settings") or {}).get("runtime")
    if code_interpreter and runtime != "codeinterpreter":
        raise RuntimeError(
            f"'{name}' で code interpreter が有効になっていません"
            f"（settings.runtime = {runtime!r}）。\n"
            "Office ファイルを読むには必須です（プロンプト設定の「…」→ 設定）。\n"
            f"{hint}"
        )
    if not code_interpreter and runtime == "codeinterpreter":
        raise RuntimeError(
            f"'{name}' で code interpreter が有効になっています。**OFF にしてください。**\n"
            "有効にすると生成コードの戻り値がそのまま出力になり、"
            "**モデルが文章を書く段が消えます**（2026-08-16 実測）。"
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
            f"'{name}' の指示文が空か短すぎます（地の文 {literal_length} 文字）。\n{hint}"
        )

    print(
        f"  {name}: 指示文 OK（地の文 {literal_length} 文字 / 入力 {sorted(actual_inputs)}"
        f" / runtime={runtime!r} / modelType="
        f"{(config.get('modelParameters') or {}).get('modelType')}）"
    )
    return model_id


def find_ai_prompt() -> str:
    """抽出プロンプト。**code interpreter が要る**（Office をドキュメント入力にするため）。"""
    return _require_prompt(
        AI_PROMPT_NAME,
        expected_inputs={PROMPT_INPUT_FILE, PROMPT_INPUT_FILENAME},
        instructions=EXTRACT_PROMPT_INSTRUCTIONS,
        code_interpreter=True,
        inputs_label=(
            f"`{PROMPT_INPUT_FILE}`（画像またはドキュメント） / "
            f"`{PROMPT_INPUT_FILENAME}`（テキスト）"
        ),
    )


def find_text_prompt() -> str:
    """説明文プロンプト。**code interpreter は入れない**（入れるとモデルが黙る）。"""
    return _require_prompt(
        AI_TEXT_PROMPT_NAME,
        expected_inputs={TEXT_INPUT_FILENAME, TEXT_INPUT_DOCUMENT},
        instructions=TEXT_PROMPT_INSTRUCTIONS,
        code_interpreter=False,
        inputs_label=f"`{TEXT_INPUT_FILENAME}` / `{TEXT_INPUT_DOCUMENT}`（どちらもテキスト）",
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

    # **リンクの引き換えをしていないこと。**
    # Graph の `shares` は `Prefer: redeemSharingLink` で恒久的なアクセス権を
    # 与えられる。それを送ると「本人が既に読めるものだけ」という前提が崩れ、
    # **URL を貼っただけで権限が付く**装置になる（第1段で塞いだ穴と同じ形）。
    # 未受諾のリンクは解決に失敗してよい。**失敗が正しい挙動。**
    if "redeem" in record["clientdata"].lower():
        raise RuntimeError(
            "clientdata に 'redeem' が含まれています。"
            "共有リンクの引き換え（Prefer: redeemSharingLink）は行いません。"
            "未受諾のリンクは解決に失敗するのが正しい挙動です。"
        )

    print(f"  OK: {SHAREPOINT_CONNECTOR}.runtimeSource = invoker")
    for connector in sorted(expected - {SHAREPOINT_CONNECTOR}):
        print(f"  OK: {connector}.runtimeSource = embedded")
    print("  OK: リンクの引き換え（redeem）は行っていない")
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

    # **プロンプト2本はどちらも UI で作る。** ここでは検査だけを行う
    # （`_require_prompt` の docstring に、潰した書き込み経路を残してある）。
    print("AI Builder プロンプト（UI 製・ここでは検査のみ）:")
    ai_model_id = find_ai_prompt()
    text_model_id = find_text_prompt()

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
