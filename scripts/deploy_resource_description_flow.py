"""関連資料の説明文を自動生成するフロー（G13）を配備する。

**第1段: invoker 接続の疎通だけを通す骨。**

このフローの肝は「**誰の資格で SharePoint を読むか**」であり、そこだけが未知だった。
所有者の接続で読むと、利用者が URL を貼るだけで**管理者が読めるファイルを何でも読める**
穴になる（SharePoint は Dataverse の外なので `ds_*` ロールでは止められない）。

そこで SharePoint 接続だけ `runtimeSource: "invoker"` にする。Learn の
「Provided by run-only user … act as the run-only user and access the data that the user
has access to … RuntimeSource value of invoker」がこのフィールドに対応する。

**URL 解析と AI Builder によるテキスト抽出は第2段。** 先に骨を通すのは、
invoker が Code App から本当に効くか（SDK が APIM トークンヘッダーで接続を渡すか）が
実測しないと分からず、そこが崩れると設計全体を組み直すことになるため。

使い方（MinoDev2 へ向ける場合）:

    $env:PP_AUTH_RECORD_PATH="<scratch>/.auth_record_minodev2.json"
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
SHAREPOINT_CONNECTOR = "shared_sharepointonline"
FLOW_NAME = "ApplicationResource_DescribeLink"
FLOW_DESCRIPTION = (
    "Code Apps から関連資料の URL を受け取り、呼び出した本人の資格で SharePoint を"
    "読んで説明文を作る。SharePoint 接続は invoker（実行専用ユーザー提供）。"
)


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


def build_clientdata(dataverse_connection_reference: str) -> str:
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
                            "title": "resourceUrl",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                            "description": "説明文を作りたい関連資料の URL",
                        }
                    },
                    "required": ["text"],
                }
            },
        }
    }

    actions = {
        # 第1段では読み取りそのものは行わず、**誰として動いているか**だけを返す。
        # invoker が効いていれば呼び出した本人、効いていなければ接続所有者になる。
        "Who_am_I": {
            "type": "OpenApiConnection",
            "runAfter": {},
            "inputs": {
                "host": {
                    "apiId": _connector_id(SHAREPOINT_CONNECTOR),
                    "connectionName": SHAREPOINT_CONNECTOR,
                    "operationId": "GetMyProfile_V2",
                },
                "parameters": {"$select": "displayName,mail,userPrincipalName"},
                "authentication": "@parameters('$authentication')",
            },
        },
        "Respond": {
            "type": "Response",
            "kind": "PowerApp",
            "runAfter": {"Who_am_I": ["Succeeded", "Failed"]},
            "inputs": {
                "statusCode": 200,
                "body": {
                    "actingAs": "@{coalesce(outputs('Who_am_I')?['body/userPrincipalName'], outputs('Who_am_I')?['body/mail'], 'unknown')}",
                    "displayName": "@{coalesce(outputs('Who_am_I')?['body/displayName'], '')}",
                    "status": "@{if(equals(outputs('Who_am_I')?['statusCode'], 200), 'succeeded', 'failed')}",
                },
                "schema": {
                    "type": "object",
                    "properties": {
                        "actingAs": {
                            "title": "actingAs",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                        },
                        "displayName": {
                            "title": "displayName",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                        },
                        "status": {
                            "title": "status",
                            "type": "string",
                            "x-ms-content-hint": "TEXT",
                            "x-ms-dynamically-added": True,
                        },
                    },
                },
            },
        },
    }

    connection_references = {
        DATAVERSE_CONNECTOR: {
            "runtimeSource": "embedded",
            "connection": {
                "connectionReferenceLogicalName": dataverse_connection_reference
            },
            "api": {"name": DATAVERSE_CONNECTOR},
        },
        SHAREPOINT_CONNECTOR: {
            # ここが本体。embedded にすると所有者の資格で読む穴になる。
            "runtimeSource": "invoker",
            "connection": {},
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
    """**設定したつもりで embedded のままが一番危ない。** 書いた後に読んで確かめる。"""
    record = api_get(f"workflows({workflow_id})?$select=clientdata")
    refs = json.loads(record["clientdata"])["properties"]["connectionReferences"]
    source = refs.get(SHAREPOINT_CONNECTOR, {}).get("runtimeSource")
    if source != "invoker":
        raise RuntimeError(
            f"SharePoint 接続の runtimeSource が '{source}' です。"
            "invoker でないと所有者の資格で読む穴になります。"
        )
    print(f"  OK: {SHAREPOINT_CONNECTOR}.runtimeSource = invoker")
    print(f"  OK: {DATAVERSE_CONNECTOR}.runtimeSource = {refs[DATAVERSE_CONNECTOR]['runtimeSource']}")


def main() -> None:
    if not DATAVERSE_URL:
        raise RuntimeError("DATAVERSE_URL が .env に設定されていません。")
    print("=== DecisionFlow resource description flow (stage 1: invoker 疎通) ===")
    print(f"Dataverse: {DATAVERSE_URL}")

    dataverse_ref = find_dataverse_connection_reference()
    print(f"Dataverse connection reference: {dataverse_ref}")

    clientdata = build_clientdata(dataverse_ref)
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
    print("\n次: このフローを Code App のデータソースに追加して呼び、")
    print("    actingAs が『呼び出した本人』になるかを実機で確かめる。")


if __name__ == "__main__":
    main()
