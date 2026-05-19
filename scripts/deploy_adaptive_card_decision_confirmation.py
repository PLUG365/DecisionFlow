from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL, api_get, get_session  # noqa: E402
from scripts.decision_confirmation_constants import validate_submit_payload  # noqa: E402

load_dotenv()

SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")
DATAVERSE_CONNECTOR = "shared_commondataserviceforapps"
ISSUE_DECISION_CARD_FLOW_NAME = "issue_decision_card"
CONFIRM_DECISION_FLOW_NAME = "confirm_decision"
API = f"{DATAVERSE_URL.rstrip('/')}/api/data/v9.2"


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


def _connref_logical_name(connector: str) -> str:
    return f"{PREFIX}_{connector}"


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


def _dataverse_host(operation_id: str) -> dict:
    return {
        "apiId": _connector_id(DATAVERSE_CONNECTOR),
        "connectionName": DATAVERSE_CONNECTOR,
        "operationId": operation_id,
    }


def _create_record_action(entity_set_name: str, item: dict, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": _dataverse_host("CreateRecord"),
            "parameters": {
                "entityName": entity_set_name,
                "item": item,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def _get_record_action(entity_set_name: str, record_id: str, select: str, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": _dataverse_host("GetItem"),
            "parameters": {
                "entityName": entity_set_name,
                "recordId": record_id,
                "$select": select,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def _list_records_action(entity_set_name: str, filter_query: str, select: str, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": _dataverse_host("ListRecords"),
            "parameters": {
                "entityName": entity_set_name,
                "$filter": filter_query,
                "$select": select,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def _update_record_action(entity_set_name: str, record_id: str, item: dict, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": _dataverse_host("UpdateRecord"),
            "parameters": {
                "entityName": entity_set_name,
                "recordId": record_id,
                "item": item,
            },
            "authentication": "@parameters('$authentication')",
        },
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


def _terminate_action(run_after: dict | None = None) -> dict:
    return {
        "type": "Terminate",
        "runAfter": run_after or {},
        "inputs": {"runStatus": "Succeeded"},
    }


CONFIRM_RESPONSE_PROPERTIES = {
    "status": "status",
    "applicationId": "applicationId",
    "decisionRecordId": "decisionRecordId",
    "decidedAt": "decidedAt",
    "message": "message",
}


def _confirm_response_body(status: str, message: str, decision_record_id: str = "", decided_at: str = "") -> dict:
    return {
        "status": status,
        "applicationId": "@triggerBody()?['applicationId']",
        "decisionRecordId": decision_record_id,
        "decidedAt": decided_at,
        "message": message,
    }


def _return_and_stop(action_name: str, body: dict) -> dict:
    return {
        action_name: _response_action(body, CONFIRM_RESPONSE_PROPERTIES),
        f"Stop_after_{action_name}": _terminate_action({action_name: ["Succeeded"]}),
    }


def _actor_card_filter(status: int) -> str:
    return (
        f"@if(empty(triggerBody()?['actorAadObjectId']), "
        f"concat('_{PREFIX}_applicationid_value eq ', triggerBody()?['applicationId'], "
        f"' and {PREFIX}_actorupn eq ''', triggerBody()?['actorUpn'], ''' and {PREFIX}_status eq {status}'), "
        f"concat('_{PREFIX}_applicationid_value eq ', triggerBody()?['applicationId'], "
        f"' and {PREFIX}_actoraadobjectid eq ''', triggerBody()?['actorAadObjectId'], ''' and {PREFIX}_status eq {status}'))"
    )


def adaptive_card_topic_validation_spike() -> dict:
    return {
        "cardSchemaVersion": "1.5",
        "submitAction": "Action.Submit",
        "checks": [
            "Generative Orchestration remains enabled for the agent.",
            "A dedicated Adaptive Card Topic is used for rendering and receiving decision confirmation submits.",
            "The topic calls the issue_decision_card Power Automate tool flow before card rendering.",
            "The topic calls the confirm_decision Power Automate tool flow after Action.Submit.",
            "Teams channel compatibility is validated with schema 1.5 and Action.Submit, not Action.Execute.",
        ],
    }


def succeeded_response(application_id: str, decision_record_id: str, decided_at: str) -> dict:
    return {
        "status": "succeeded",
        "applicationId": application_id,
        "decidedAt": decided_at,
        "decisionRecordId": decision_record_id,
        "message": "判断を確定しました。",
    }


def parse_submit_payload(payload: dict) -> dict:
    return validate_submit_payload(payload)


def build_issue_decision_card_clientdata(connection_refs: dict[str, str] | None = None) -> str:
    trigger = _skills_trigger(
        {
            "applicationId": _text_input("applicationId", "判断対象の ds_application ID"),
            "actorAadObjectId": _text_input("actorAadObjectId", "実行者の Entra object ID。取得できない場合は空でよい"),
            "actorUpn": _text_input("actorUpn", "実行者の UPN またはメールアドレス"),
        },
        ["applicationId", "actorUpn"],
    )
    actions = {
        "Compose_cardInstanceId": {
            "type": "Compose",
            "runAfter": {},
            "inputs": "@guid()",
        },
        "List_prior_issued_decisioncards": _list_records_action(
            f"{PREFIX}_decisioncards",
            _actor_card_filter(100000000),
            f"{PREFIX}_decisioncardid,{PREFIX}_cardinstanceid,{PREFIX}_status,{PREFIX}_actoraadobjectid,{PREFIX}_actorupn",
            {"Compose_cardInstanceId": ["Succeeded"]},
        ),
        "Supersede_prior_issued_decisioncards": {
            "type": "Foreach",
            "runAfter": {"List_prior_issued_decisioncards": ["Succeeded"]},
            "foreach": "@outputs('List_prior_issued_decisioncards')?['body/value']",
            "actions": {
                "Supersede_prior_issued_decisioncard": _update_record_action(
                    f"{PREFIX}_decisioncards",
                    "@items('Supersede_prior_issued_decisioncards')?['ds_decisioncardid']",
                    {
                        f"{PREFIX}_status": 100000002,
                        f"{PREFIX}_supersededat": "@utcNow()",
                    },
                )
            },
        },
        "Create_decisioncard": _create_record_action(
            f"{PREFIX}_decisioncards",
            {
                f"{PREFIX}_name": "@concat('判断カード - ', triggerBody()?['applicationId'])",
                f"{PREFIX}_cardinstanceid": "@outputs('Compose_cardInstanceId')",
                f"{PREFIX}_actoraadobjectid": "@triggerBody()?['actorAadObjectId']",
                f"{PREFIX}_actorupn": "@triggerBody()?['actorUpn']",
                f"{PREFIX}_status": 100000000,
                f"{PREFIX}_issuedat": "@utcNow()",
                f"{PREFIX}_applicationid@odata.bind": "@concat('/ds_applications(', triggerBody()?['applicationId'], ')')",
            },
            {"Supersede_prior_issued_decisioncards": ["Succeeded"]},
        ),
        "Return_card_context": _response_action(
            {
                "applicationId": "@triggerBody()?['applicationId']",
                "cardInstanceId": "@outputs('Compose_cardInstanceId')",
            },
            {"applicationId": "applicationId", "cardInstanceId": "cardInstanceId"},
            {"Create_decisioncard": ["Succeeded"]},
        ),
    }
    return _clientdata(_workflow_definition(actions, trigger), connection_refs)


def build_confirm_decision_clientdata(connection_refs: dict[str, str] | None = None) -> str:
    decided_at = "@utcNow()"
    trigger = _skills_trigger(
        {
            "applicationId": _text_input("applicationId", "判断対象の ds_application ID"),
            "decisionOption": _text_input("decisionOption", "選択された判断ラベル。承認、却下、差し戻しのいずれか"),
            "rationale": _text_input("rationale", "判断理由"),
            "cardInstanceId": _text_input("cardInstanceId", "issue_decision_card が返したカードインスタンス ID"),
            "actorAadObjectId": _text_input("actorAadObjectId", "実行者の Entra object ID。取得できない場合は空でよい"),
            "actorUpn": _text_input("actorUpn", "実行者の UPN またはメールアドレス"),
        },
        ["applicationId", "decisionOption", "rationale", "cardInstanceId", "actorUpn"],
    )
    success_actions = {
        "Create_decision": _create_record_action(
            f"{PREFIX}_decisions",
            {
                f"{PREFIX}_name": "@concat('判断 - ', triggerBody()?['applicationId'])",
                f"{PREFIX}_rationale": "@triggerBody()?['rationale']",
                f"{PREFIX}_decidedat": decided_at,
                f"{PREFIX}_applicationid@odata.bind": "@concat('/ds_applications(', triggerBody()?['applicationId'], ')')",
                f"{PREFIX}_deciderid@odata.bind": "@concat('/systemusers(', first(outputs('List_current_user')?['body/value'])?['systemuserid'], ')')",
                f"{PREFIX}_decisionoptionid@odata.bind": "@concat('/ds_decisionoptions(', first(outputs('Get_decision_option')?['body/value'])?['ds_decisionoptionid'], ')')",
            },
        ),
        "Consume_decisioncard": _update_record_action(
            f"{PREFIX}_decisioncards",
            "@first(outputs('List_current_issued_decisioncard')?['body/value'])?['ds_decisioncardid']",
            {
                f"{PREFIX}_status": 100000001,
                f"{PREFIX}_consumedat": decided_at,
            },
            {"Create_decision": ["Succeeded"]},
        ),
        "Return_succeeded": _response_action(
            _confirm_response_body(
                "succeeded",
                "判断を確定しました。",
                "@outputs('Create_decision')?['body/ds_decisionid']",
                decided_at,
            ),
            CONFIRM_RESPONSE_PROPERTIES,
            {"Consume_decisioncard": ["Succeeded"]},
        ),
    }
    actions = {
        "Parse_submit_payload": {
            "type": "Compose",
            "runAfter": {},
            "inputs": "@triggerBody()",
        },
        "List_current_user": _list_records_action(
            "systemusers",
            "@if(empty(triggerBody()?['actorAadObjectId']), concat('domainname eq ''', triggerBody()?['actorUpn'], ''''), concat('azureactivedirectoryobjectid eq ', triggerBody()?['actorAadObjectId']))",
            "systemuserid,domainname,internalemailaddress,azureactivedirectoryobjectid",
            {"Parse_submit_payload": ["Succeeded"]},
        ),
        "Validate_user_found": {
            "type": "If",
            "runAfter": {"List_current_user": ["Succeeded"]},
            "expression": {"greater": ["@length(outputs('List_current_user')?['body/value'])", 0]},
            "actions": {},
            "else": {
                "actions": _return_and_stop(
                    "Return_forbidden_user_not_found",
                    _confirm_response_body("forbidden", "ユーザーを確認できないため、判断を確定できません。"),
                )
            },
        },
        "Get_decision_option": _list_records_action(
            f"{PREFIX}_decisionoptions",
            f"@concat('{PREFIX}_name eq ''', triggerBody()?['decisionOption'], ''' and statecode eq 0 and statuscode eq 1')",
            f"{PREFIX}_decisionoptionid,{PREFIX}_name,statecode,statuscode",
            {"Validate_user_found": ["Succeeded"]},
        ),
        "Validate_decision_option_found": {
            "type": "If",
            "runAfter": {"Get_decision_option": ["Succeeded"]},
            "expression": {"greater": ["@length(outputs('Get_decision_option')?['body/value'])", 0]},
            "actions": {},
            "else": {
                "actions": _return_and_stop(
                    "Return_invalid_decision_option",
                    _confirm_response_body("invalid_target", "対象案件が無効または参照できません。"),
                )
            },
        },
        "Get_application": _get_record_action(
            f"{PREFIX}_applications",
            "@triggerBody()?['applicationId']",
            f"{PREFIX}_stage,{PREFIX}_submittedat,_{PREFIX}_deciderid_value",
            {"Validate_decision_option_found": ["Succeeded"]},
        ),
        "Validate_submitted_application": {
            "type": "If",
            "runAfter": {"Get_application": ["Succeeded"]},
            "expression": {"equals": [f"@outputs('Get_application')?['body/{PREFIX}_stage']", 100000001]},
            "actions": {},
            "else": {
                "actions": _return_and_stop(
                    "Return_invalid_application",
                    _confirm_response_body("invalid_target", "対象案件が無効または参照できません。"),
                )
            },
        },
        "Validate_actor_is_decider": {
            "type": "If",
            "runAfter": {"Validate_submitted_application": ["Succeeded"]},
            "expression": {
                "equals": [
                    f"@toLower(outputs('Get_application')?['body/_{PREFIX}_deciderid_value'])",
                    "@toLower(first(outputs('List_current_user')?['body/value'])?['systemuserid'])",
                ]
            },
            "actions": {},
            "else": {
                "actions": _return_and_stop(
                    "Return_forbidden_not_decider",
                    _confirm_response_body("forbidden", "この案件の判断者として割り当てられていないため、判断を確定できません。"),
                )
            },
        },
        "Validate_rationale_exists": {
            "type": "If",
            "runAfter": {"Validate_actor_is_decider": ["Succeeded"]},
            "expression": {"not": {"equals": ["@trim(triggerBody()?['rationale'])", ""]}},
            "actions": {},
            "else": {
                "actions": _return_and_stop(
                    "Return_invalid_empty_rationale",
                    _confirm_response_body("invalid_target", "判断理由を入力してください。"),
                )
            },
        },
        "List_current_issued_decisioncard": _list_records_action(
            f"{PREFIX}_decisioncards",
            _actor_card_filter(100000000),
            f"{PREFIX}_decisioncardid,{PREFIX}_cardinstanceid,{PREFIX}_status,{PREFIX}_actoraadobjectid,{PREFIX}_actorupn",
            {"Validate_rationale_exists": ["Succeeded"]},
        ),
        "Validate_current_issued_card": {
            "type": "If",
            "runAfter": {"List_current_issued_decisioncard": ["Succeeded"]},
            "expression": {
                "and": [
                    {"greater": ["@length(outputs('List_current_issued_decisioncard')?['body/value'])", 0]},
                    {
                        "equals": [
                            "@first(outputs('List_current_issued_decisioncard')?['body/value'])?['ds_cardinstanceid']",
                            "@triggerBody()?['cardInstanceId']",
                        ]
                    },
                ]
            },
            "actions": {},
            "else": {
                "actions": _return_and_stop(
                    "Return_already_processed_card",
                    _confirm_response_body("already_processed", "判断カードが無効、または既に使用済みです。"),
                )
            },
        },
        "List_existing_decisions": _list_records_action(
            f"{PREFIX}_decisions",
            f"@if(empty(outputs('Get_application')?['body/{PREFIX}_submittedat']), concat('_{PREFIX}_applicationid_value eq ', triggerBody()?['applicationId']), concat('_{PREFIX}_applicationid_value eq ', triggerBody()?['applicationId'], ' and {PREFIX}_decidedat ge ', outputs('Get_application')?['body/{PREFIX}_submittedat']))",
            f"{PREFIX}_decisionid,{PREFIX}_decidedat",
            {"Validate_current_issued_card": ["Succeeded"]},
        ),
        "First_write_wins_check": {
            "type": "If",
            "runAfter": {"List_existing_decisions": ["Succeeded"]},
            "expression": {"equals": ["@length(outputs('List_existing_decisions')?['body/value'])", 0]},
            "actions": success_actions,
            "else": {
                "actions": _return_and_stop(
                    "Return_already_processed",
                    _confirm_response_body("already_processed", "この案件は既に判断確定済みです。"),
                )
            },
        },
    }
    return _clientdata(_workflow_definition(actions, trigger), connection_refs)


def adaptive_card_tool_flow_definitions(connection_refs: dict[str, str] | None = None) -> dict[str, dict[str, str]]:
    return {
        ISSUE_DECISION_CARD_FLOW_NAME: {
            "name": ISSUE_DECISION_CARD_FLOW_NAME,
            "description": "Copilot Studio の判断確定カード表示前に ds_decisioncard を Issued として作成し、cardInstanceId を返す。",
            "clientdata": build_issue_decision_card_clientdata(connection_refs),
        },
        CONFIRM_DECISION_FLOW_NAME: {
            "name": CONFIRM_DECISION_FLOW_NAME,
            "description": "Copilot Studio の Adaptive Card submit を検証し、ds_decision を作成して ds_decisioncard を Consumed に更新する。",
            "clientdata": build_confirm_decision_clientdata(connection_refs),
        },
    }


def deploy_tool_flow(flow_name: str, description: str, clientdata: str) -> tuple[str, bool]:
    from scripts.deploy_notification_flows import _escape_odata_string, create_flow

    escaped_name = _escape_odata_string(flow_name)
    existing = api_get(
        f"workflows?$filter=name eq '{escaped_name}' and category eq 5&$select=workflowid,name,statecode,statuscode"
    ).get("value", [])
    if not existing:
        return create_flow(flow_name, description, clientdata)

    workflow_id = existing[0]["workflowid"]
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    print(f"  {flow_name}: 既存フローを更新します ({workflow_id})")
    if existing[0].get("statecode") == 1:
        deactivate = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 0, "statuscode": 1})
        if not deactivate.ok:
            print(f"  ⚠️ {flow_name}: 無効化失敗 ({deactivate.status_code})。clientdata 更新を続行します。")
            print(f"     {deactivate.text[:1000]}")

    update = session.patch(
        f"{API}/workflows({workflow_id})",
        json={"clientdata": clientdata, "description": description},
    )
    if not update.ok:
        raise RuntimeError(f"{flow_name} の更新に失敗しました ({update.status_code})。\n{update.text[:2000]}")

    activate = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 1, "statuscode": 2})
    if not activate.ok:
        print(f"  ⚠️ {flow_name}: 有効化失敗 ({activate.status_code})。Power Automate UI で手動有効化してください。")
        print(f"     {activate.text[:2000]}")
        return workflow_id, False
    print(f"  ✅ {flow_name}: 更新して有効化しました ({workflow_id})")
    return workflow_id, True


DeployFlow = Callable[[str, str, str], tuple[str, bool]]


def deploy_adaptive_card_tool_flows(deploy_flow_func: DeployFlow) -> dict[str, str]:
    deployed = {}
    for flow in adaptive_card_tool_flow_definitions().values():
        workflow_id, _active = deploy_flow_func(flow["name"], flow["description"], flow["clientdata"])
        deployed[flow["name"]] = workflow_id
    return deployed


def validate_deployment_prerequisites(
    *,
    dataverse_url: str,
    solution_name: str,
    prefix: str,
    connection_names: list[str],
    dataverse_connref: str | None = None,
) -> str:
    required_values = {
        "DATAVERSE_URL": dataverse_url,
        "SOLUTION_NAME": solution_name,
        "PUBLISHER_PREFIX": prefix,
    }
    missing = [name for name, value in required_values.items() if not str(value or "").strip()]
    if missing:
        raise RuntimeError(f"必須環境値が不足しています: {', '.join(missing)}")
    if not connection_names:
        raise RuntimeError(f"Dataverse connection が見つかりません: {DATAVERSE_CONNECTOR}")
    if dataverse_connref is not None and not dataverse_connref.strip():
        raise RuntimeError(f"Dataverse connection reference が見つかりません: {DATAVERSE_CONNECTOR}")
    return connection_names[0]


def main() -> int:
    from scripts.deploy_notification_flows import (
        DATAVERSE_CONNECTOR as NOTIFICATION_DATAVERSE_CONNECTOR,
        _read_environment_id,
        ensure_connection_reference,
        find_connections,
        start_deployed_flows,
    )

    print("=" * 72)
    print("DecisionFlow Adaptive Card decision confirmation deployment")
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

    print("\n=== Step 3: ツールフロー作成/更新 ===")
    deployed = {}
    all_active = True
    for flow in adaptive_card_tool_flow_definitions(connection_refs).values():
        workflow_id, active = deploy_tool_flow(flow["name"], flow["description"], flow["clientdata"])
        deployed[flow["name"]] = workflow_id
        all_active = all_active and active

    print("\n=== Step 4: Power Automate ランタイム start ===")
    all_started = start_deployed_flows(environment_id, deployed)

    print("\n=== Step 5: Copilot Studio 手動作業 ===")
    print("- Copilot Studio UI で issue_decision_card と confirm_decision をツールとして追加してください。")
    print("- 専用 Topic でカード表示前に issue_decision_card、submit 後に confirm_decision を呼びます。")
    if not all_active:
        print("\n  ⚠️ 一部フローの有効化に失敗しました。Power Automate UI で接続を修復してオンにしてください。")
    if not all_started:
        print("\n  ⚠️ 一部フローの start に失敗しました。Power Automate UI でフローを開き、保存またはオンにしてください。")
    print("\n✅ ツールフロー作成処理が完了しました")
    for flow_name, workflow_id in deployed.items():
        print(f"  {flow_name}: {workflow_id}")

    print("Validation spike:")
    for check in adaptive_card_topic_validation_spike()["checks"]:
        print(f"- {check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())