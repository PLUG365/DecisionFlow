from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL  # noqa: E402

load_dotenv()

SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")
DATAVERSE_CONNECTOR = "shared_commondataserviceforapps"
APPLICATION_LINK_FLOW_NAME = "Get_ApplicationDetailUrl"
APPLICATION_LINK_FLOW_DESCRIPTION = (
    "Copilot Studio エージェントが申請詳細リンクを案内するときに呼び出すツールフロー。"
    "ソリューション環境変数 ds_DecisionFlowAppBaseUrl を実行時に解決し、"
    "applicationId を deepLink パラメータとして付加した完全 URL を返す。"
    "環境変数が未設定の場合は空文字列を返し、エージェントはリンクなしで誘導する。"
)
API = f"{DATAVERSE_URL.rstrip('/')}/api/data/v9.2" if DATAVERSE_URL else ""


def _connector_id(connector: str) -> str:
    return f"/providers/Microsoft.PowerApps/apis/{connector}"


def _connref_logical_name(connector: str) -> str:
    return f"{PREFIX}_{connector}"


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


def _clientdata(definition: dict, connection_reference_logical_names: dict[str, str] | None = None) -> str:
    connection_reference_logical_names = connection_reference_logical_names or {
        DATAVERSE_CONNECTOR: _connref_logical_name(DATAVERSE_CONNECTOR)
    }
    return json.dumps(
        {
            "properties": {
                "definition": definition,
                "connectionReferences": {
                    connector: {
                        "runtimeSource": "embedded",
                        "connection": {
                            "connectionReferenceLogicalName": logical_name,
                        },
                        "api": {"name": connector},
                    }
                    for connector, logical_name in connection_reference_logical_names.items()
                },
            },
            "schemaVersion": "1.0.0.0",
        },
        ensure_ascii=False,
    )


def _text_input(title: str, description: str) -> dict:
    return {
        "title": title,
        "type": "string",
        "x-ms-content-hint": "TEXT",
        "x-ms-dynamically-added": True,
        "description": description,
    }


def _skills_trigger(properties: dict[str, dict], required: list[str]) -> dict:
    return {
        "manual": {
            "type": "Request",
            "kind": "Skills",
            "inputs": {
                "schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            },
        }
    }


def _response_schema(properties: dict[str, str]) -> dict:
    return {
        "type": "object",
        "properties": {
            name: {
                "title": title,
                "type": "string",
                "x-ms-dynamically-added": True,
            }
            for name, title in properties.items()
        },
    }


def _response_action(body: dict, response_properties: dict[str, str], run_after: dict | None = None) -> dict:
    return {
        "type": "Response",
        "kind": "Skills",
        "runAfter": run_after or {},
        "inputs": {
            "statusCode": 200,
            "body": body,
            "schema": _response_schema(response_properties),
        },
    }


APP_BASE_URL_ENV_LABEL = "DecisionFlow_App_Base_Url"
APPLICATION_URL_RESPONSE_PROPERTIES = {"applicationUrl": "applicationUrl"}


def build_application_link_flow_clientdata(
    connection_refs: dict[str, str] | None = None,
    prefix: str = PREFIX,
) -> str:
    """Build the Power Automate clientdata JSON for the application link tool flow."""

    from scripts.deploy_notification_flows import (
        APP_BASE_URL_ENVVAR_SUFFIX,
        _environment_variable_schema_name,
        _runtime_environment_variable_actions,
    )

    trigger = _skills_trigger(
        {
            "applicationId": _text_input(
                "applicationId",
                "申請詳細リンクを生成する対象 ds_application の GUID。",
            ),
        },
        ["applicationId"],
    )

    env_actions = _runtime_environment_variable_actions(
        _environment_variable_schema_name(prefix, APP_BASE_URL_ENVVAR_SUFFIX),
        APP_BASE_URL_ENV_LABEL,
    )

    application_url_expression = (
        f"@if(equals(outputs('Get_{APP_BASE_URL_ENV_LABEL}'),''),"
        "'',"
        f"concat(outputs('Get_{APP_BASE_URL_ENV_LABEL}'),"
        "'?deepLink=%2Fapplications%2F',"
        "triggerBody()?['applicationId']))"
    )

    actions = {
        **env_actions,
        "Compose_ApplicationUrl": {
            "type": "Compose",
            "runAfter": {f"Get_{APP_BASE_URL_ENV_LABEL}": ["Succeeded"]},
            "inputs": application_url_expression,
        },
        "Return_application_url": _response_action(
            {"applicationUrl": "@outputs('Compose_ApplicationUrl')"},
            APPLICATION_URL_RESPONSE_PROPERTIES,
            {"Compose_ApplicationUrl": ["Succeeded"]},
        ),
    }

    return _clientdata(_workflow_definition(actions, trigger), connection_refs)


def application_link_flow_definition(connection_refs: dict[str, str] | None = None) -> dict[str, str]:
    return {
        "name": APPLICATION_LINK_FLOW_NAME,
        "description": APPLICATION_LINK_FLOW_DESCRIPTION,
        "clientdata": build_application_link_flow_clientdata(connection_refs),
    }


DeployFlow = Callable[[str, str, str], tuple[str, bool]]


def deploy_application_link_flow(deploy_flow_func: DeployFlow, connection_refs: dict[str, str] | None = None) -> tuple[str, bool]:
    flow = application_link_flow_definition(connection_refs)
    return deploy_flow_func(flow["name"], flow["description"], flow["clientdata"])


def main() -> int:
    from scripts.deploy_adaptive_card_decision_confirmation import (
        deploy_tool_flow,
        validate_deployment_prerequisites,
    )
    from scripts.deploy_notification_flows import (
        DATAVERSE_CONNECTOR as NOTIFICATION_DATAVERSE_CONNECTOR,
        _read_environment_id,
        ensure_connection_reference,
        ensure_notification_environment_variables,
        find_connections,
        start_deployed_flows,
    )

    if not DATAVERSE_URL:
        raise RuntimeError("DATAVERSE_URL が .env に設定されていません。")

    print("=" * 72)
    print("DecisionFlow Application detail link tool flow deployment")
    print("=" * 72)
    print(f"Environment: {DATAVERSE_URL}")
    print(f"Solution: {SOLUTION_NAME}")
    print(f"Prefix: {PREFIX}")

    print("\n=== Step 1: 接続検索 ===")
    environment_id = _read_environment_id()
    connection_names = find_connections(environment_id, NOTIFICATION_DATAVERSE_CONNECTOR)
    connection_name = validate_deployment_prerequisites(
        dataverse_url=DATAVERSE_URL,
        solution_name=SOLUTION_NAME,
        prefix=PREFIX,
        connection_names=connection_names,
    )
    print(f"  {DATAVERSE_CONNECTOR}: {connection_name}")

    print("\n=== Step 2: 接続参照作成/更新 ===")
    dataverse_connref = ensure_connection_reference(
        NOTIFICATION_DATAVERSE_CONNECTOR,
        connection_name,
        "DecisionFlow Dataverse connection",
    )
    validate_deployment_prerequisites(
        dataverse_url=DATAVERSE_URL,
        solution_name=SOLUTION_NAME,
        prefix=PREFIX,
        connection_names=connection_names,
        dataverse_connref=dataverse_connref,
    )
    connection_refs = {DATAVERSE_CONNECTOR: dataverse_connref}

    print("\n=== Step 3: 環境変数定義作成/確認 ===")
    ensure_notification_environment_variables(PREFIX)

    print("\n=== Step 4: ツールフロー作成/更新 ===")
    flow = application_link_flow_definition(connection_refs)
    workflow_id, active = deploy_tool_flow(flow["name"], flow["description"], flow["clientdata"])
    deployed = {flow["name"]: workflow_id}

    print("\n=== Step 5: Power Automate ランタイム start ===")
    all_started = start_deployed_flows(environment_id, deployed)

    print("\n=== Step 6: Copilot Studio 手動作業 ===")
    print(f"- Copilot Studio UI で {APPLICATION_LINK_FLOW_NAME} をエージェントツールとして追加してください。")
    print("- Instructions の「申請詳細リンク」セクションに従い、申請を案内するときにこのツールを呼ぶ運用にします。")
    if not active:
        print("\n  ⚠️ ツールフローの有効化に失敗しました。Power Automate UI で接続を修復してオンにしてください。")
    if not all_started:
        print("\n  ⚠️ ツールフローの start に失敗しました。Power Automate UI でフローを開き、保存またはオンにしてください。")
    print("\n✅ ツールフロー作成処理が完了しました")
    print(f"  {APPLICATION_LINK_FLOW_NAME}: {workflow_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
