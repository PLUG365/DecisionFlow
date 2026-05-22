from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL, api_get, flow_api_call, get_session, get_token  # noqa: E402


API = f"{DATAVERSE_URL}/api/data/v9.2"
POWERAPPS_API = "https://api.powerapps.com"
SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")
DATAVERSE_CONNECTOR = "shared_commondataserviceforapps"
DATAVERSE_CONNECTOR_ID = f"/providers/Microsoft.PowerApps/apis/{DATAVERSE_CONNECTOR}"
DATAVERSE_CONNREF_LOGICAL_NAME = f"{PREFIX}_{DATAVERSE_CONNECTOR}"

GRANT_FLOW_NAME = "Participant_OnCreated_GrantAccess"
REVOKE_FLOW_NAME = "Participant_PreDelete_RevokeAccess"


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


def _clientdata(definition: dict, connection_reference_logical_name: str) -> str:
    return json.dumps(
        {
            "properties": {
                "definition": definition,
                "connectionReferences": {
                    DATAVERSE_CONNECTOR: {
                        "runtimeSource": "embedded",
                        "connection": {
                            "connectionReferenceLogicalName": connection_reference_logical_name,
                        },
                        "api": {"name": DATAVERSE_CONNECTOR},
                    }
                },
            },
            "schemaVersion": "1.0.0.0",
        },
        ensure_ascii=False,
    )


def _compose_action(inputs: dict, run_after: dict | None = None) -> dict:
    return {
        "type": "Compose",
        "runAfter": run_after or {},
        "inputs": inputs,
    }


def _dataverse_action(action_name: str, item: dict | str, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": {
                    "apiId": DATAVERSE_CONNECTOR_ID,
                    "connectionName": DATAVERSE_CONNECTOR,
                    "operationId": "PerformUnboundAction",
            },
            "parameters": {
                "actionName": action_name,
                "item": item,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def _list_records_action(entity_set_name: str, filter_query: str, select: str, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": {
                "apiId": DATAVERSE_CONNECTOR_ID,
                "connectionName": DATAVERSE_CONNECTOR,
                "operationId": "ListRecords",
            },
            "parameters": {
                "entityName": entity_set_name,
                "$filter": filter_query,
                "$select": select,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def build_grant_flow_clientdata(
    prefix: str = PREFIX,
    connection_reference_logical_name: str = DATAVERSE_CONNREF_LOGICAL_NAME,
) -> str:
    global PREFIX
    previous_prefix = PREFIX
    PREFIX = prefix
    try:
        triggers = {
            "When_participant_created": {
                "type": "OpenApiConnectionWebhook",
                "inputs": {
                    "host": {
                        "apiId": DATAVERSE_CONNECTOR_ID,
                        "connectionName": DATAVERSE_CONNECTOR,
                        "operationId": "SubscribeWebhookTrigger",
                    },
                    "parameters": {
                        "subscriptionRequest/message": 1,
                        "subscriptionRequest/entityname": f"{prefix}_participant",
                        "subscriptionRequest/scope": 4,
                        "subscriptionRequest/runas": 3,
                    },
                    "authentication": "@parameters('$authentication')",
                },
            }
        }
        grant_payload_action = "Build_grant_access_payload"
        actions = {
            grant_payload_action: _compose_action(
                {
                    "Target": {
                        "@@odata.type": f"Microsoft.Dynamics.CRM.{prefix}_application",
                        f"{prefix}_applicationid": f"@triggerOutputs()?['body/_{prefix}_applicationid_value']",
                    },
                    "PrincipalAccess": {
                        "Principal": {
                            "@@odata.type": "Microsoft.Dynamics.CRM.systemuser",
                            "systemuserid": f"@triggerOutputs()?['body/_{prefix}_userid_value']",
                        },
                        "AccessMask": "ReadAccess,AppendToAccess",
                    }
                },
            ),
            "Grant_application_access": _dataverse_action(
                "GrantAccess",
                f"@outputs('{grant_payload_action}')",
                {grant_payload_action: ["Succeeded"]},
            )
        }
        return _clientdata(_workflow_definition(actions=actions, triggers=triggers), connection_reference_logical_name)
    finally:
        PREFIX = previous_prefix


def _powerapp_text_input(title: str, description: str) -> dict:
    return {
        "title": title,
        "type": "string",
        "x-ms-content-hint": "TEXT",
        "x-ms-dynamically-added": True,
        "description": description,
    }


def _response_text_output(title: str) -> dict:
    return {
        "title": title,
        "type": "string",
        "x-ms-content-hint": "TEXT",
        "x-ms-dynamically-added": True,
    }


def build_revoke_flow_clientdata(
    prefix: str = PREFIX,
    connection_reference_logical_name: str = DATAVERSE_CONNREF_LOGICAL_NAME,
) -> str:
    global PREFIX
    previous_prefix = PREFIX
    PREFIX = prefix
    try:
        triggers = {
            "manual": {
                "type": "Request",
                "kind": "PowerAppV2",
                "inputs": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "text": _powerapp_text_input("participantId", "削除対象の関係者 ID"),
                            "text_1": _powerapp_text_input("applicationId", "共有解除対象の申請 ID"),
                            "text_2": _powerapp_text_input("userId", "共有解除対象の systemuser ID"),
                        },
                        "required": ["text", "text_1", "text_2"],
                    }
                },
            }
        }
        revoke_payload_action = "Build_revoke_access_payload"
        actions = {
            revoke_payload_action: _compose_action(
                {
                    "Target": {
                        "@@odata.type": f"Microsoft.Dynamics.CRM.{prefix}_application",
                        f"{prefix}_applicationid": "@triggerBody()?['text_1']",
                    },
                    "Revokee": {
                        "@@odata.type": "Microsoft.Dynamics.CRM.systemuser",
                        "systemuserid": "@triggerBody()?['text_2']",
                    }
                },
            ),
            "Revoke_application_access": _dataverse_action(
                "RevokeAccess",
                f"@outputs('{revoke_payload_action}')",
                {revoke_payload_action: ["Succeeded"]},
            ),
            "List_application_decisions": _list_records_action(
                f"{prefix}_decisions",
                f"_{prefix}_applicationid_value eq @{{triggerBody()?['text_1']}}",
                f"{prefix}_decisionid",
                {"Revoke_application_access": ["Succeeded"]},
            ),
            "Revoke_decision_access": {
                "type": "Foreach",
                "runAfter": {"List_application_decisions": ["Succeeded"]},
                "foreach": "@outputs('List_application_decisions')?['body/value']",
                "actions": {
                    "Build_revoke_decision_access_payload": _compose_action(
                        {
                            "Target": {
                                "@@odata.type": f"Microsoft.Dynamics.CRM.{prefix}_decision",
                                f"{prefix}_decisionid": "@items('Revoke_decision_access')?['ds_decisionid']",
                            },
                            "Revokee": {
                                "@@odata.type": "Microsoft.Dynamics.CRM.systemuser",
                                "systemuserid": "@triggerBody()?['text_2']",
                            },
                        },
                    ),
                    "Revoke_single_decision_access": _dataverse_action(
                        "RevokeAccess",
                        "@outputs('Build_revoke_decision_access_payload')",
                        {"Build_revoke_decision_access_payload": ["Succeeded"]},
                    ),
                },
            },
            "Respond_success": {
                "type": "Response",
                "kind": "PowerApp",
                "runAfter": {"Revoke_decision_access": ["Succeeded"]},
                "inputs": {
                    "statusCode": 200,
                    "body": {
                        "ok": "true",
                        "participantid": "@{triggerBody()?['text']}",
                        "message": "Access revoked.",
                    },
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ok": _response_text_output("ok"),
                            "participantid": _response_text_output("participantid"),
                            "message": _response_text_output("message"),
                        },
                        "additionalProperties": {},
                    },
                },
            },
            "Respond_failure": {
                "type": "Response",
                "kind": "PowerApp",
                "runAfter": {"Revoke_application_access": ["Failed", "TimedOut"]},
                "inputs": {
                    "statusCode": 200,
                    "body": {
                        "ok": "false",
                        "participantid": "@{triggerBody()?['text']}",
                        "message": "@{coalesce(outputs('Revoke_application_access')?['body/error/message'],'Access revoke failed.')}",
                    },
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ok": _response_text_output("ok"),
                            "participantid": _response_text_output("participantid"),
                            "message": _response_text_output("message"),
                        },
                        "additionalProperties": {},
                    },
                },
            },
        }
        return _clientdata(_workflow_definition(actions=actions, triggers=triggers), connection_reference_logical_name)
    finally:
        PREFIX = previous_prefix


def _escape_odata_string(value: str) -> str:
    return value.replace("'", "''")


def _safe_debug_name(flow_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", flow_name)


def _read_environment_id() -> str:
    config_path = ROOT / "power.config.json"
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        env_id = data.get("environmentId")
        if env_id:
            return env_id

    envs = flow_api_call("GET", "/providers/Microsoft.ProcessSimple/environments")
    for env in envs.get("value", []):
        linked = env.get("properties", {}).get("linkedEnvironmentMetadata", {})
        if (linked.get("instanceUrl") or "").rstrip("/").lower() == DATAVERSE_URL.lower():
            return env["name"]
    raise RuntimeError("環境 ID を解決できませんでした。power.config.json または DATAVERSE_URL を確認してください。")


def _powerapps_get(url: str) -> dict:
    token = get_token(scope="https://service.powerapps.com/.default")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    last_error = ""
    for attempt in range(3):
        response = requests.get(url, headers=headers, timeout=120)
        if response.ok:
            return response.json()
        last_error = response.text[:500]
        if response.status_code in {429, 500, 502, 503, 504}:
            wait = 15 * (attempt + 1)
            print(f"  接続検索が一時失敗しました。{wait} 秒後に再試行します ({attempt + 1}/3)")
            time.sleep(wait)
            continue
        break
    raise RuntimeError(f"PowerApps API の接続検索に失敗しました: {last_error}")


def _status_is_connected(connection: dict) -> bool:
    statuses = connection.get("properties", {}).get("statuses", [])
    return any(status.get("status", "").lower() == "connected" for status in statuses)


def _connection_connector_name(connection: dict) -> str:
    return (connection.get("properties", {}).get("apiId") or "").rstrip("/").split("/")[-1]


def _connection_auth_score(connection: dict) -> tuple[int, int, str]:
    values = connection.get("properties", {}).get("connectionParametersSet", {}).get("values", {})
    has_oauth_grant = "token:grantType" in values
    return (
        1 if _status_is_connected(connection) else 0,
        1 if has_oauth_grant else 0,
        connection.get("properties", {}).get("createdTime") or "",
    )


def find_dataverse_connections(environment_id: str) -> list[str]:
    encoded_env = quote(environment_id, safe="")
    urls = [
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/scopes/admin/environments/{encoded_env}/connections"
        "?api-version=2016-11-01",
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/scopes/admin/environments/{encoded_env}/apis/{DATAVERSE_CONNECTOR}/connections"
        "?api-version=2016-11-01",
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/apis/{DATAVERSE_CONNECTOR}/connections"
        f"?$filter=environment eq '{environment_id}'&api-version=2016-11-01",
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/environments/{encoded_env}/apis/{DATAVERSE_CONNECTOR}/connections"
        "?api-version=2016-11-01",
    ]
    candidates: list[dict] = []
    for url in urls:
        try:
            candidates.extend(
                candidate
                for candidate in _powerapps_get(url).get("value", [])
                if _connection_connector_name(candidate) == DATAVERSE_CONNECTOR
            )
        except RuntimeError as exc:
            print(f"  接続検索エンドポイントをスキップ: {exc}")

    if not candidates:
        raise RuntimeError(
            "Dataverse 接続が見つかりません。Power Automate の接続ページで Dataverse 接続を作成してから再実行してください。"
        )

    connected = [candidate for candidate in candidates if _status_is_connected(candidate)]
    ordered = sorted(connected or candidates, key=_connection_auth_score, reverse=True)
    connection_names = [
        candidate.get("name") or candidate.get("properties", {}).get("connectionName") for candidate in ordered
    ]
    connection_names = [name for name in connection_names if name]
    if not connection_names:
        raise RuntimeError("Dataverse 接続 ID を取得できませんでした。")
    if not connected:
        print("  ⚠️ Connected 状態の Dataverse 接続が見つからないため、最初の接続を使用します。")
    return list(dict.fromkeys(connection_names))


def find_dataverse_connection(environment_id: str) -> str:
    return find_dataverse_connections(environment_id)[0]


def ensure_connection_reference(connection_name: str) -> str:
    logical_name = DATAVERSE_CONNREF_LOGICAL_NAME
    display_name = "DecisionFlow Dataverse connection"
    escaped = _escape_odata_string(logical_name)
    existing = api_get(
        "connectionreferences?"
        f"$filter=connectionreferencelogicalname eq '{escaped}'"
        "&$select=connectionreferenceid,connectionreferencelogicalname,connectionid,connectorid"
    ).get("value", [])

    if existing:
        ref = existing[0]
        ref_id = ref["connectionreferenceid"]
        patch_body = {}
        if ref.get("connectionid") != connection_name:
            patch_body["connectionid"] = connection_name
        if ref.get("connectorid") != DATAVERSE_CONNECTOR_ID:
            patch_body["connectorid"] = DATAVERSE_CONNECTOR_ID
        if patch_body:
            session = get_session()
            session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
            response = session.patch(f"{API}/connectionreferences({ref_id})", json=patch_body)
            response.raise_for_status()
            print(f"  接続参照を更新しました: {logical_name}")
        else:
            print(f"  接続参照は既存です: {logical_name}")
        return logical_name

    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    body = {
        "connectionreferencelogicalname": logical_name,
        "connectionreferencedisplayname": display_name,
        "connectorid": DATAVERSE_CONNECTOR_ID,
        "connectionid": connection_name,
    }
    response = session.post(f"{API}/connectionreferences", json=body)
    if not response.ok:
        raise RuntimeError(f"接続参照の作成に失敗しました ({response.status_code})。\n{response.text[:800]}")
    print(f"  接続参照を作成しました: {logical_name}")
    return logical_name


def delete_existing_flow(flow_name: str) -> str | None:
    escaped_name = _escape_odata_string(flow_name)
    existing = api_get(
        f"workflows?$filter=name eq '{escaped_name}' and category eq 5&$select=workflowid,name,statecode"
    ).get("value", [])
    if not existing:
        print(f"  {flow_name}: 既存フローなし")
        return None

    session = get_session()
    reusable_workflow_id: str | None = None
    for flow in existing:
        workflow_id = flow["workflowid"]
        print(f"  {flow_name}: 既存フローを再作成します ({workflow_id})")
        if flow.get("statecode") == 1:
            response = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 0, "statuscode": 1})
            if not response.ok:
                print(f"    無効化失敗: {response.status_code} {response.text[:250]}")
        response = session.delete(f"{API}/workflows({workflow_id})")
        if response.ok:
            continue
        if response.status_code == 400 and "referenced by" in response.text:
            print(f"    削除不可の参照があるため既存フローを更新します: {workflow_id}")
            reusable_workflow_id = workflow_id
            continue
        response.raise_for_status()
    return reusable_workflow_id


def create_flow(flow_name: str, description: str, clientdata: str) -> tuple[str, bool]:
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    body = {
        "name": flow_name,
        "type": 1,
        "category": 5,
        "statecode": 0,
        "statuscode": 1,
        "primaryentity": "none",
        "clientdata": clientdata,
        "description": description,
    }
    response = session.post(f"{API}/workflows", json=body)
    if not response.ok:
        debug_path = ROOT / "scripts" / f"{_safe_debug_name(flow_name)}_debug.json"
        debug_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"{flow_name} の作成に失敗しました ({response.status_code})。Debug: {debug_path}\n{response.text[:800]}")

    location = response.headers.get("OData-EntityId", "")
    if "(" not in location:
        raise RuntimeError(f"{flow_name} の Workflow ID を取得できませんでした。")
    workflow_id = location.split("(")[-1].rstrip(")")

    activate = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 1, "statuscode": 2})
    if not activate.ok:
        print(f"  ⚠️ {flow_name}: 有効化失敗 ({activate.status_code})。Power Automate UI で手動有効化してください。")
        print(f"     {activate.text[:2000]}")
        return workflow_id, False
    else:
        print(f"  ✅ {flow_name}: 作成して有効化しました ({workflow_id})")
    return workflow_id, True


def update_flow(workflow_id: str, flow_name: str, description: str, clientdata: str) -> tuple[str, bool]:
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    body = {
        "name": flow_name,
        "type": 1,
        "category": 5,
        "statecode": 0,
        "statuscode": 1,
        "primaryentity": "none",
        "clientdata": clientdata,
        "description": description,
    }
    response = session.patch(f"{API}/workflows({workflow_id})", json=body)
    if not response.ok:
        debug_path = ROOT / "scripts" / f"{_safe_debug_name(flow_name)}_debug.json"
        debug_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"{flow_name} の更新に失敗しました ({response.status_code})。Debug: {debug_path}\n{response.text[:800]}")

    activate = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 1, "statuscode": 2})
    if not activate.ok:
        print(f"  ⚠️ {flow_name}: 更新後の有効化失敗 ({activate.status_code})。Power Automate UI で手動有効化してください。")
        print(f"     {activate.text[:2000]}")
        return workflow_id, False
    print(f"  ✅ {flow_name}: 既存フローを更新して有効化しました ({workflow_id})")
    return workflow_id, True


def deploy_flow(flow_name: str, description: str, clientdata: str) -> tuple[str, bool]:
    reusable_workflow_id = delete_existing_flow(flow_name)
    if reusable_workflow_id:
        return update_flow(reusable_workflow_id, flow_name, description, clientdata)
    return create_flow(flow_name, description, clientdata)


def start_deployed_flows(environment_id: str, deployed: dict[str, str]) -> bool:
    all_started = True
    for flow_name, workflow_id in deployed.items():
        try:
            flow_api_call(
                "POST",
                f"/providers/Microsoft.ProcessSimple/environments/{environment_id}/flows/{workflow_id}/start",
                {},
            )
            print(f"  ✅ {flow_name}: Flow API start を実行しました")
        except Exception as exc:
            all_started = False
            print(f"  ⚠️ {flow_name}: Flow API start に失敗しました: {exc}")
    return all_started


def deploy_access_flows(connection_reference_logical_name: str) -> tuple[dict[str, str], bool]:
    grant_id, grant_active = deploy_flow(
        GRANT_FLOW_NAME,
        "ds_participant 作成時に対象ユーザーへ ds_application の Read/AppendTo 共有権限を付与する。",
        build_grant_flow_clientdata(PREFIX, connection_reference_logical_name),
    )
    revoke_id, revoke_active = deploy_flow(
        REVOKE_FLOW_NAME,
        "Code Apps の関係者削除前に対象ユーザーから ds_application の共有権限を解除し、結果を返す。",
        build_revoke_flow_clientdata(PREFIX, connection_reference_logical_name),
    )
    return {GRANT_FLOW_NAME: grant_id, REVOKE_FLOW_NAME: revoke_id}, grant_active and revoke_active


def main() -> None:
    if not DATAVERSE_URL:
        raise RuntimeError("DATAVERSE_URL が .env に設定されていません。")

    print("=" * 64)
    print("DecisionFlow access-control flows")
    print(f"Solution: {SOLUTION_NAME}")
    print(f"Prefix: {PREFIX}")
    print("=" * 64)

    environment_id = _read_environment_id()
    print("\n=== Step 1: Dataverse 接続検索 ===")
    forced_connection = os.environ.get("DATAVERSE_CONN", "").strip()
    connection_names = [forced_connection] if forced_connection else find_dataverse_connections(environment_id)
    print(f"  ✅ Dataverse 接続候補を確認しました ({len(connection_names)} 件)")

    print("\n=== Step 2: 接続参照作成/更新 ===")

    deployed_ids: dict[str, str] = {}
    activated = False
    for index, connection_name in enumerate(connection_names, start=1):
        print(f"\n--- Dataverse 接続候補 {index}/{len(connection_names)} で試行 ---")
        connection_reference_logical_name = ensure_connection_reference(connection_name)

        print("\n=== Step 3: フロー作成/更新 ===")
        deployed_ids, activated = deploy_access_flows(connection_reference_logical_name)
        if activated:
            break

    if not activated:
        print("\n  ⚠️ すべての接続候補で有効化に失敗しました。")
        print("     Power Automate UI でフローを開き、接続を修復してオンにしてください。")

    print("\n=== Step 4: Power Automate ランタイム start ===")
    started = start_deployed_flows(environment_id, deployed_ids)
    if not started:
        print("\n  ⚠️ 一部フローの start に失敗しました。Power Automate UI でフローを開き、保存またはオンにしてください。")

    print("\n=== Step 5: 確認 ===")
    result = api_get(
        "workflows?"
        f"$filter=(name eq '{_escape_odata_string(GRANT_FLOW_NAME)}' or name eq '{_escape_odata_string(REVOKE_FLOW_NAME)}') and category eq 5"
        "&$select=workflowid,name,statecode,statuscode"
    )
    for flow in result.get("value", []):
        state = "有効" if flow.get("statecode") == 1 else "無効"
        print(f"  {flow['name']}: {state} ({flow['workflowid']})")

    print("\n✅ 完了")
    print(f"  {GRANT_FLOW_NAME}: {deployed_ids.get(GRANT_FLOW_NAME)}")
    print(f"  {REVOKE_FLOW_NAME}: {deployed_ids.get(REVOKE_FLOW_NAME)}")
    print("  次に Code Apps へ Revoke フローを add-flow で追加してください。")


if __name__ == "__main__":
    main()