from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL, api_get, flow_api_call, get_session, get_token  # noqa: E402

load_dotenv()

API = f"{DATAVERSE_URL}/api/data/v9.2"
POWERAPPS_API = "https://api.powerapps.com"
SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")

DATAVERSE_CONNECTOR = "shared_commondataserviceforapps"
OUTLOOK_CONNECTOR = "shared_office365"
TEAMS_CONNECTOR = "shared_teams"

SUBMITTED_STAGE = 100000001

APPLICATION_SUBMITTED_FLOW_NAME = "Application_OnSubmitted"
DECISION_CREATED_FLOW_NAME = "Decision_OnCreated"
MENTION_CREATED_FLOW_NAME = "Mention_OnCreated"
STALLED_REMINDER_FLOW_NAME = "Application_StalledReminder"
OBSOLETE_NOTIFICATION_FLOW_NAMES = ["Application_OnCreatedSubmitted"]
NOTIFICATION_FLOW_NAMES = [
    APPLICATION_SUBMITTED_FLOW_NAME,
    DECISION_CREATED_FLOW_NAME,
    MENTION_CREATED_FLOW_NAME,
    STALLED_REMINDER_FLOW_NAME,
]

TEAMS_GROUP_ID = os.environ.get("TEAMS_NOTIFICATION_GROUP_ID", "").strip()
TEAMS_CHANNEL_ID = os.environ.get("TEAMS_NOTIFICATION_CHANNEL_ID", "").strip()
ENABLE_TEAMS = bool(TEAMS_GROUP_ID and TEAMS_CHANNEL_ID)
COPILOT_TEAMS_APP_ID = os.environ.get("COPILOT_TEAMS_APP_ID", "").strip()
DECISIONFLOW_APP_BASE_URL = os.environ.get("DECISIONFLOW_APP_BASE_URL", "").strip().rstrip("/")


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


def _clientdata(definition: dict, connection_reference_logical_names: dict[str, str]) -> str:
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


def _escape_odata_string(value: str) -> str:
    return value.replace("'", "''")


def _safe_debug_name(flow_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", flow_name)


def _dataverse_trigger(name: str, message: int, entity_name: str, filtering_attributes: str | None = None) -> dict:
    parameters = {
        "subscriptionRequest/message": message,
        "subscriptionRequest/entityname": entity_name,
        "subscriptionRequest/scope": 4,
        "subscriptionRequest/runas": 3,
    }
    if filtering_attributes:
        parameters["subscriptionRequest/filteringattributes"] = filtering_attributes
    return {
        name: {
            "type": "OpenApiConnectionWebhook",
            "inputs": {
                "host": {
                    "apiId": _connector_id(DATAVERSE_CONNECTOR),
                    "connectionName": DATAVERSE_CONNECTOR,
                    "operationId": "SubscribeWebhookTrigger",
                },
                "parameters": parameters,
                "authentication": "@parameters('$authentication')",
            },
        }
    }


def _recurrence_trigger() -> dict:
    return {
        "Every_day_at_9am_jst": {
            "type": "Recurrence",
            "recurrence": {
                "frequency": "Day",
                "interval": 1,
                "timeZone": "Tokyo Standard Time",
                "schedule": {
                    "hours": [9],
                    "minutes": [0],
                },
            },
        }
    }


def _get_record_action(entity_set_name: str, record_id: str, select: str, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": {
                "apiId": _connector_id(DATAVERSE_CONNECTOR),
                "connectionName": DATAVERSE_CONNECTOR,
                "operationId": "GetItem",
            },
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
            "host": {
                "apiId": _connector_id(DATAVERSE_CONNECTOR),
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


def _update_record_action(entity_set_name: str, record_id: str, item: dict, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": {
                "apiId": _connector_id(DATAVERSE_CONNECTOR),
                "connectionName": DATAVERSE_CONNECTOR,
                "operationId": "UpdateRecord",
            },
            "parameters": {
                "entityName": entity_set_name,
                "recordId": record_id,
                "item": item,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def _compose_action(inputs: str | dict, run_after: dict | None = None) -> dict:
    return {"type": "Compose", "runAfter": run_after or {}, "inputs": inputs}


def _send_email_action(to: str, subject: str, body: str, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": {
                "apiId": _connector_id(OUTLOOK_CONNECTOR),
                "connectionName": OUTLOOK_CONNECTOR,
                "operationId": "SendEmailV2",
            },
            "parameters": {
                "emailMessage/To": to,
                "emailMessage/Subject": subject,
                "emailMessage/Body": body,
                "emailMessage/Importance": "Normal",
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def _send_email_if_present(action_name: str, email_expression: str, subject: str, body: str, run_after: dict | None = None) -> dict:
    return {
        action_name: {
            "type": "If",
            "runAfter": run_after or {},
            "expression": {
                "not": {"equals": [f"@coalesce({email_expression},'')", ""]}
            },
            "actions": {
                f"{action_name}_send": _send_email_action(
                    f"@{email_expression}",
                    subject,
                    body,
                )
            },
            "else": {"actions": {}},
        }
    }


def _post_teams_action(message_body: str, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": {
                "apiId": _connector_id(TEAMS_CONNECTOR),
                "connectionName": TEAMS_CONNECTOR,
                "operationId": "PostMessageToConversation",
            },
            "parameters": {
                "poster": "Flow bot",
                "location": "Channel",
                "body/recipient/groupId": TEAMS_GROUP_ID,
                "body/recipient/channelId": TEAMS_CHANNEL_ID,
                "body/messageBody": message_body,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def _html(title: str, lines: list[str]) -> str:
    content = "".join(f"<p>{line}</p>" for line in lines)
    return (
        "<html><body>"
        f"<h2>{title}</h2>"
        f"{content}"
        "<p>DecisionFlow</p>"
        "</body></html>"
    )


def _teams_bot_user_id(app_id: str) -> str:
    if app_id.startswith("T_"):
        raise RuntimeError("COPILOT_TEAMS_APP_ID には titleId ではなく botChannelRegistrationAppId を設定してください。")
    return app_id if app_id.startswith("28:") else f"28:{app_id}"


def _app_link_lines(application_id_expression: str) -> list[str]:
    if not DECISIONFLOW_APP_BASE_URL:
        return []
    href = (
        "@{concat('"
        f"{DECISIONFLOW_APP_BASE_URL}?deepLink=%2Fapplications%2F"
        "', "
        f"{application_id_expression}"
        ")}"
    )
    return [f"申請を開く: <a href=\"{href}\">申請詳細ページ</a>"]


def _assistant_link_lines(title_expression: str, application_id_expression: str | None = None) -> list[str]:
    if not COPILOT_TEAMS_APP_ID:
        return []

    message_args = [
        "'申請「'",
        title_expression,
        "'」について、概要・関連資料・過去類似案件・推奨判断と判断コメントドラフトを教えてください。'",
    ]
    if DECISIONFLOW_APP_BASE_URL and application_id_expression:
        message_args.extend([
            "' Code Apps URL: '",
            f"concat('{DECISIONFLOW_APP_BASE_URL}/applications/', {application_id_expression})",
        ])

    message_expression = f"concat({', '.join(message_args)})"
    href = (
        "@{concat('https://teams.microsoft.com/l/chat/0/0?users="
        f"{_teams_bot_user_id(COPILOT_TEAMS_APP_ID)}"
        "&message=', encodeUriComponent("
        f"{message_expression}"
        "))}"
    )
    return [
        "AIアシスタント: "
        f"<a href=\"{href}\">申請について相談する</a>",
    ]


def _participant_email_foreach(subject: str, body: str, run_after: dict, prefix: str = PREFIX) -> dict:
    return {
        "Notify_participants": {
            "type": "Foreach",
            "runAfter": run_after,
            "foreach": "@outputs('List_participants')?['body/value']",
            "actions": {
                "Get_participant_user": _get_record_action(
                    "systemusers",
                    f"@items('Notify_participants')?['_{prefix}_userid_value']",
                    "internalemailaddress,fullname",
                ),
                **_send_email_if_present(
                    "If_participant_has_email",
                    "outputs('Get_participant_user')?['body/internalemailaddress']",
                    subject,
                    body,
                    {"Get_participant_user": ["Succeeded"]},
                ),
            },
        }
    }


def build_application_submitted_clientdata(connection_refs: dict[str, str], prefix: str = PREFIX) -> str:
    subject = "@{concat('【DecisionFlow】申請が提出されました: ', triggerOutputs()?['body/ds_name'])}"
    body = _html(
        "申請が提出されました",
        [
            "申請: @{triggerOutputs()?['body/ds_name']}",
            "希望期限: @{coalesce(triggerOutputs()?['body/ds_duedate'],'未設定')}",
            "本文: @{coalesce(triggerOutputs()?['body/ds_body'],'')}",
            *_app_link_lines("triggerOutputs()?['body/ds_applicationid']"),
            *_assistant_link_lines("triggerOutputs()?['body/ds_name']", "triggerOutputs()?['body/ds_applicationid']"),
        ],
    )
    teams_body = "@{concat('<b>申請が提出されました</b><br>申請: ', triggerOutputs()?['body/ds_name'])}"
    actions = {
        "If_submitted": {
            "type": "If",
            "expression": {"equals": [f"@triggerOutputs()?['body/{prefix}_stage']", SUBMITTED_STAGE]},
            "actions": {
                "Get_decider": _get_record_action(
                    "systemusers",
                    f"@triggerOutputs()?['body/_{prefix}_deciderid_value']",
                    "internalemailaddress,fullname",
                ),
                "List_participants": _list_records_action(
                    f"{prefix}_participants",
                    f"_{prefix}_applicationid_value eq @{{triggerOutputs()?['body/{prefix}_applicationid']}}",
                    f"{prefix}_participantid,_{prefix}_userid_value",
                ),
                **_send_email_if_present(
                    "If_decider_has_email",
                    "outputs('Get_decider')?['body/internalemailaddress']",
                    subject,
                    body,
                    {"Get_decider": ["Succeeded"]},
                ),
                **_participant_email_foreach(subject, body, {"List_participants": ["Succeeded"]}, prefix),
            },
            "else": {"actions": {}},
        }
    }
    if ENABLE_TEAMS:
        actions["If_submitted"]["actions"]["Post_to_Teams_channel"] = _post_teams_action(teams_body)
    triggers = _dataverse_trigger(
        "When_application_created_or_updated",
        4,
        f"{prefix}_application",
        f"{prefix}_stage,{prefix}_submittedat",
    )
    return _clientdata(_workflow_definition(actions=actions, triggers=triggers), connection_refs)


def build_decision_created_clientdata(connection_refs: dict[str, str], prefix: str = PREFIX) -> str:
    subject = "@{concat('【DecisionFlow】判断が確定しました: ', outputs('Get_application')?['body/ds_name'])}"
    body = _html(
        "判断が確定しました",
        [
            "申請: @{outputs('Get_application')?['body/ds_name']}",
            "判断: @{outputs('Get_decision_option')?['body/ds_name']}",
            "理由: @{coalesce(triggerOutputs()?['body/ds_rationale'],'')}",
            *_app_link_lines(f"triggerOutputs()?['body/_{prefix}_applicationid_value']"),
        ],
    )
    teams_body = "@{concat('<b>判断が確定しました</b><br>申請: ', outputs('Get_application')?['body/ds_name'], '<br>判断: ', outputs('Get_decision_option')?['body/ds_name'])}"
    actions = {
        "Get_application": _get_record_action(
            f"{prefix}_applications",
            f"@triggerOutputs()?['body/_{prefix}_applicationid_value']",
            f"{prefix}_name,{prefix}_body,{prefix}_stage,_createdby_value",
        ),
        "Get_applicant": _get_record_action(
            "systemusers",
            "@outputs('Get_application')?['body/_createdby_value']",
            "internalemailaddress,fullname",
            {"Get_application": ["Succeeded"]},
        ),
        "Get_decision_option": _get_record_action(
            f"{prefix}_decisionoptions",
            f"@triggerOutputs()?['body/_{prefix}_decisionoptionid_value']",
            f"{prefix}_name",
            {"Get_applicant": ["Succeeded"]},
        ),
        "Derive_next_application_stage": _compose_action(
            f"@if(equals(outputs('Get_decision_option')?['body/{prefix}_name'],'差し戻し'),100000000,100000004)",
            {"Get_decision_option": ["Succeeded"]},
        ),
        "If_application_stage_needs_update": {
            "type": "If",
            "runAfter": {"Derive_next_application_stage": ["Succeeded"]},
            "expression": {
                "not": {
                    "equals": [
                        f"@outputs('Get_application')?['body/{prefix}_stage']",
                        "@outputs('Derive_next_application_stage')",
                    ]
                }
            },
            "actions": {
                "Update_application_stage": _update_record_action(
                    f"{prefix}_applications",
                    f"@triggerOutputs()?['body/_{prefix}_applicationid_value']",
                    {f"{prefix}_stage": "@outputs('Derive_next_application_stage')"},
                )
            },
            "else": {"actions": {}},
        },
        "Clear_submitted_at_if_returned_to_draft": {
            "type": "If",
            "runAfter": {"If_application_stage_needs_update": ["Succeeded"]},
            "expression": {"equals": ["@outputs('Derive_next_application_stage')", 100000000]},
            "actions": {
                "Clear_submitted_at": _update_record_action(
                    f"{prefix}_applications",
                    f"@triggerOutputs()?['body/_{prefix}_applicationid_value']",
                    {f"{prefix}_submittedat": None},
                ),
            },
            "else": {"actions": {}},
        },
        "List_participants": _list_records_action(
            f"{prefix}_participants",
            f"_{prefix}_applicationid_value eq @{{triggerOutputs()?['body/_{prefix}_applicationid_value']}}",
            f"{prefix}_participantid,_{prefix}_userid_value",
            {"Clear_submitted_at_if_returned_to_draft": ["Succeeded"]},
        ),
        **_send_email_if_present(
            "If_applicant_has_email",
            "outputs('Get_applicant')?['body/internalemailaddress']",
            subject,
            body,
            {"List_participants": ["Succeeded"]},
        ),
        **_participant_email_foreach(
            subject,
            body,
            {"If_applicant_has_email": ["Succeeded"]},
            prefix,
        ),
    }
    if ENABLE_TEAMS:
        actions["Post_to_Teams_channel"] = _post_teams_action(
            teams_body,
            {"Notify_participants": ["Succeeded"]},
        )
    triggers = _dataverse_trigger("When_decision_created", 1, f"{prefix}_decision")
    return _clientdata(_workflow_definition(actions=actions, triggers=triggers), connection_refs)


def build_mention_created_clientdata(connection_refs: dict[str, str], prefix: str = PREFIX) -> str:
    subject = "@{concat('【DecisionFlow】メンションされました: ', outputs('Get_application')?['body/ds_name'])}"
    body = _html(
        "メンションされました",
        [
            "申請: @{outputs('Get_application')?['body/ds_name']}",
            "メッセージ: @{outputs('Get_message')?['body/ds_body']}",
            *_app_link_lines(f"outputs('Get_message')?['body/_{prefix}_applicationid_value']"),
        ],
    )
    teams_body = "@{concat('<b>メンション通知</b><br>申請: ', outputs('Get_application')?['body/ds_name'], '<br>メッセージ: ', outputs('Get_message')?['body/ds_body'])}"
    actions = {
        "If_unread_mention": {
            "type": "If",
            "expression": {"equals": [f"@triggerOutputs()?['body/{prefix}_isread']", False]},
            "actions": {
                "Get_target_user": _get_record_action(
                    "systemusers",
                    f"@triggerOutputs()?['body/_{prefix}_targetuserid_value']",
                    "internalemailaddress,fullname",
                ),
                "Get_message": _get_record_action(
                    f"{prefix}_messages",
                    f"@triggerOutputs()?['body/_{prefix}_messageid_value']",
                    f"{prefix}_body,_{prefix}_applicationid_value",
                ),
                "Get_application": _get_record_action(
                    f"{prefix}_applications",
                    f"@outputs('Get_message')?['body/_{prefix}_applicationid_value']",
                    f"{prefix}_name,{prefix}_body",
                    {"Get_message": ["Succeeded"]},
                ),
                **_send_email_if_present(
                    "If_target_has_email",
                    "outputs('Get_target_user')?['body/internalemailaddress']",
                    subject,
                    body,
                    {"Get_target_user": ["Succeeded"], "Get_application": ["Succeeded"]},
                ),
            },
            "else": {"actions": {}},
        }
    }
    if ENABLE_TEAMS:
        actions["If_unread_mention"]["actions"]["Post_to_Teams_channel"] = _post_teams_action(
            teams_body,
            {"Get_application": ["Succeeded"]},
        )
    triggers = _dataverse_trigger("When_mention_created", 1, f"{prefix}_mention")
    return _clientdata(_workflow_definition(actions=actions, triggers=triggers), connection_refs)


def build_stalled_reminder_clientdata(connection_refs: dict[str, str], prefix: str = PREFIX) -> str:
    foreach_name = "For_each_submitted_application"
    subject = f"@{{concat('【DecisionFlow】判断待ちリマインド: ', items('{foreach_name}')?['{prefix}_name'])}}"
    body = _html(
        "判断待ちの申請があります",
        [
            f"申請: @{{items('{foreach_name}')?['{prefix}_name']}}",
            f"希望期限: @{{coalesce(items('{foreach_name}')?['{prefix}_duedate'],'未設定')}}",
            f"提出日時: @{{coalesce(items('{foreach_name}')?['{prefix}_submittedat'],'未設定')}}",
            f"本文: @{{coalesce(items('{foreach_name}')?['{prefix}_body'],'')}}",
            "停滞条件: 希望期限超過、または提出日時から3日以上経過しています。",
            *_app_link_lines(f"items('{foreach_name}')?['{prefix}_applicationid']"),
            *_assistant_link_lines(f"items('{foreach_name}')?['{prefix}_name']", f"items('{foreach_name}')?['{prefix}_applicationid']"),
        ],
    )
    teams_body = f"@{{concat('<b>判断待ちリマインド</b><br>申請: ', items('{foreach_name}')?['{prefix}_name'])}}"
    stalled_expression = {
        "and": [
            {"not": {"equals": [f"@items('{foreach_name}')?['_{prefix}_deciderid_value']", None]}},
            {
                "or": [
                    {
                        "and": [
                            {"not": {"equals": [f"@items('{foreach_name}')?['{prefix}_duedate']", None]}},
                            {
                                "less": [
                                    f"@items('{foreach_name}')?['{prefix}_duedate']",
                                    "@formatDateTime(convertTimeZone(utcNow(),'UTC','Tokyo Standard Time'),'yyyy-MM-dd')",
                                ]
                            },
                        ]
                    },
                    {
                        "and": [
                            {"not": {"equals": [f"@items('{foreach_name}')?['{prefix}_submittedat']", None]}},
                            {
                                "lessOrEquals": [
                                    f"@ticks(items('{foreach_name}')?['{prefix}_submittedat'])",
                                    "@ticks(addDays(utcNow(), -3))",
                                ]
                            },
                        ]
                    },
                ]
            },
        ]
    }
    actions = {
        "List_submitted_applications": _list_records_action(
            f"{prefix}_applications",
            f"{prefix}_stage eq {SUBMITTED_STAGE}",
            f"{prefix}_applicationid,{prefix}_name,{prefix}_body,{prefix}_stage,{prefix}_duedate,{prefix}_submittedat,_{prefix}_deciderid_value",
        ),
        foreach_name: {
            "type": "Foreach",
            "runAfter": {"List_submitted_applications": ["Succeeded"]},
            "foreach": "@outputs('List_submitted_applications')?['body/value']",
            "actions": {
                "If_stalled_and_has_decider": {
                    "type": "If",
                    "expression": stalled_expression,
                    "actions": {
                        "Get_decider": _get_record_action(
                            "systemusers",
                            f"@items('{foreach_name}')?['_{prefix}_deciderid_value']",
                            "internalemailaddress,fullname",
                        ),
                        **_send_email_if_present(
                            "If_decider_has_email",
                            "outputs('Get_decider')?['body/internalemailaddress']",
                            subject,
                            body,
                            {"Get_decider": ["Succeeded"]},
                        ),
                    },
                    "else": {"actions": {}},
                }
            },
        },
    }
    if ENABLE_TEAMS:
        actions[foreach_name]["actions"]["If_stalled_and_has_decider"]["actions"]["Post_to_Teams_channel"] = _post_teams_action(
            teams_body,
            {"If_decider_has_email": ["Succeeded"]},
        )
    return _clientdata(_workflow_definition(actions=actions, triggers=_recurrence_trigger()), connection_refs)


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
    return (1 if _status_is_connected(connection) else 0, 1 if has_oauth_grant else 0, connection.get("properties", {}).get("createdTime") or "")


def _connection_env_candidates(connector: str) -> list[str]:
    env_names = {
        DATAVERSE_CONNECTOR: ["DATAVERSE_CONN", "FALLBACK_CONN_DATAVERSE"],
        OUTLOOK_CONNECTOR: ["OUTLOOK_CONN", "FALLBACK_CONN_OUTLOOK"],
        TEAMS_CONNECTOR: ["TEAMS_CONN", "FALLBACK_CONN_TEAMS"],
    }.get(connector, [])
    return [os.environ.get(name, "").strip() for name in env_names if os.environ.get(name, "").strip()]


def find_connections(environment_id: str, connector: str) -> list[str]:
    env_candidates = _connection_env_candidates(connector)
    if env_candidates:
        print(f"  {connector}: .env の接続 ID を優先します")
        return list(dict.fromkeys(env_candidates))

    encoded_env = quote(environment_id, safe="")
    urls = [
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/scopes/admin/environments/{encoded_env}/connections"
        "?api-version=2016-11-01",
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/scopes/admin/environments/{encoded_env}/apis/{connector}/connections"
        "?api-version=2016-11-01",
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/apis/{connector}/connections"
        f"?$filter=environment eq '{environment_id}'&api-version=2016-11-01",
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/environments/{encoded_env}/apis/{connector}/connections"
        "?api-version=2016-11-01",
    ]
    candidates: list[dict] = []
    for url in urls:
        try:
            candidates.extend(
                candidate
                for candidate in _powerapps_get(url).get("value", [])
                if _connection_connector_name(candidate) == connector
            )
        except RuntimeError as exc:
            print(f"  {connector}: 接続検索エンドポイントをスキップ: {exc}")
    connected = [candidate for candidate in candidates if _status_is_connected(candidate)]
    ordered = sorted(connected or candidates, key=_connection_auth_score, reverse=True)
    names = [candidate.get("name") or candidate.get("properties", {}).get("connectionName") for candidate in ordered]
    names = [name for name in names if name]
    if not names:
        raise RuntimeError(f"{connector} 接続が見つかりません。Power Automate の接続ページで接続を作成してください。")
    return list(dict.fromkeys(names))


def ensure_connection_reference(connector: str, connection_name: str, display_name: str) -> str:
    logical_name = _connref_logical_name(connector)
    escaped = _escape_odata_string(logical_name)
    connector_id = _connector_id(connector)
    existing = api_get(
        "connectionreferences?"
        f"$filter=connectionreferencelogicalname eq '{escaped}'"
        "&$select=connectionreferenceid,connectionreferencelogicalname,connectionid,connectorid"
    ).get("value", [])
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    if existing:
        ref = existing[0]
        patch_body = {}
        if ref.get("connectionid") != connection_name:
            patch_body["connectionid"] = connection_name
        if ref.get("connectorid") != connector_id:
            patch_body["connectorid"] = connector_id
        if patch_body:
            response = session.patch(f"{API}/connectionreferences({ref['connectionreferenceid']})", json=patch_body)
            response.raise_for_status()
            print(f"  接続参照を更新しました: {logical_name}")
        else:
            print(f"  接続参照は既存です: {logical_name}")
        return logical_name
    body = {
        "connectionreferencelogicalname": logical_name,
        "connectionreferencedisplayname": display_name,
        "connectorid": connector_id,
        "connectionid": connection_name,
    }
    response = session.post(f"{API}/connectionreferences", json=body)
    if not response.ok:
        raise RuntimeError(f"接続参照の作成に失敗しました ({response.status_code})。\n{response.text[:800]}")
    print(f"  接続参照を作成しました: {logical_name}")
    return logical_name


def delete_existing_flow(flow_name: str) -> None:
    escaped_name = _escape_odata_string(flow_name)
    existing = api_get(
        f"workflows?$filter=name eq '{escaped_name}' and category eq 5&$select=workflowid,name,statecode"
    ).get("value", [])
    if not existing:
        print(f"  {flow_name}: 既存フローなし")
        return
    session = get_session()
    for flow in existing:
        workflow_id = flow["workflowid"]
        print(f"  {flow_name}: 既存フローを再作成します ({workflow_id})")
        if flow.get("statecode") == 1:
            response = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 0, "statuscode": 1})
            if not response.ok:
                print(f"    無効化失敗: {response.status_code} {response.text[:250]}")
        response = session.delete(f"{API}/workflows({workflow_id})")
        response.raise_for_status()


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
        raise RuntimeError(f"{flow_name} の作成に失敗しました ({response.status_code})。Debug: {debug_path}\n{response.text[:1000]}")
    location = response.headers.get("OData-EntityId", "")
    if "(" not in location:
        raise RuntimeError(f"{flow_name} の Workflow ID を取得できませんでした。")
    workflow_id = location.split("(")[-1].rstrip(")")
    activate = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 1, "statuscode": 2})
    if not activate.ok:
        print(f"  ⚠️ {flow_name}: 有効化失敗 ({activate.status_code})。Power Automate UI で手動有効化してください。")
        print(f"     {activate.text[:2000]}")
        return workflow_id, False
    print(f"  ✅ {flow_name}: 作成して有効化しました ({workflow_id})")
    return workflow_id, True


def deploy_flow(flow_name: str, description: str, clientdata: str) -> tuple[str, bool]:
    delete_existing_flow(flow_name)
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


def get_existing_notification_flows() -> dict[str, str]:
    names_filter = " or ".join(
        f"name eq '{_escape_odata_string(name)}'" for name in NOTIFICATION_FLOW_NAMES
    )
    result = api_get(
        "workflows?"
        f"$filter=({names_filter}) and category eq 5"
        "&$select=workflowid,name,statecode,statuscode"
    )
    return {flow["name"]: flow["workflowid"] for flow in result.get("value", [])}


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy or start DecisionFlow notification flows.")
    parser.add_argument(
        "--start-existing",
        action="store_true",
        help="Do not recreate flows; only call Flow API /start for existing notification flows.",
    )
    args = parser.parse_args()

    if not DATAVERSE_URL:
        raise RuntimeError("DATAVERSE_URL が .env に設定されていません。")
    print("=" * 72)
    print("DecisionFlow notification flows")
    print(f"Solution: {SOLUTION_NAME}")
    print(f"Prefix: {PREFIX}")
    print(f"Teams channel enabled: {ENABLE_TEAMS}")
    print("=" * 72)

    environment_id = _read_environment_id()
    if args.start_existing:
        print("\n=== Start existing notification flows ===")
        existing = get_existing_notification_flows()
        if not existing:
            raise RuntimeError("既存の通知フローが見つかりません。")
        started = start_deployed_flows(environment_id, existing)
        if not started:
            raise RuntimeError("一部の通知フローの /start に失敗しました。")
        print("\n✅ 既存通知フローの start が完了しました")
        for flow_name, workflow_id in existing.items():
            print(f"  {flow_name}: {workflow_id}")
        return

    connectors = [DATAVERSE_CONNECTOR, OUTLOOK_CONNECTOR]
    if ENABLE_TEAMS:
        connectors.append(TEAMS_CONNECTOR)

    print("\n=== Step 1: 接続検索 ===")
    connection_names = {connector: find_connections(environment_id, connector)[0] for connector in connectors}
    for connector, connection_name in connection_names.items():
        print(f"  {connector}: {connection_name}")

    print("\n=== Step 2: 接続参照作成/更新 ===")
    connection_refs = {
        DATAVERSE_CONNECTOR: ensure_connection_reference(DATAVERSE_CONNECTOR, connection_names[DATAVERSE_CONNECTOR], "DecisionFlow Dataverse connection"),
        OUTLOOK_CONNECTOR: ensure_connection_reference(OUTLOOK_CONNECTOR, connection_names[OUTLOOK_CONNECTOR], "DecisionFlow Outlook connection"),
    }
    if ENABLE_TEAMS:
        connection_refs[TEAMS_CONNECTOR] = ensure_connection_reference(TEAMS_CONNECTOR, connection_names[TEAMS_CONNECTOR], "DecisionFlow Teams connection")

    print("\n=== Step 3: 廃止フロー削除 ===")
    for flow_name in OBSOLETE_NOTIFICATION_FLOW_NAMES:
        delete_existing_flow(flow_name)

    print("\n=== Step 4: フロー作成/更新 ===")
    flows = {
        APPLICATION_SUBMITTED_FLOW_NAME: (
            "ds_application 作成または更新時にステージが Submitted の場合、判断者・関係者へメール通知する。Teams チャネル設定がある場合はチャネルにも投稿する。",
            build_application_submitted_clientdata(connection_refs, PREFIX),
        ),
        DECISION_CREATED_FLOW_NAME: (
            "ds_decision 作成時に申請者・関係者へ判断結果をメール通知する。Teams チャネル設定がある場合はチャネルにも投稿する。",
            build_decision_created_clientdata(connection_refs, PREFIX),
        ),
        MENTION_CREATED_FLOW_NAME: (
            "ds_mention 作成時に対象ユーザーへメール通知する。Teams チャネル設定がある場合はチャネルにも投稿する。",
            build_mention_created_clientdata(connection_refs, PREFIX),
        ),
        STALLED_REMINDER_FLOW_NAME: (
            "毎日 9:00 JST に Submitted のまま希望期限超過または提出から3日以上経過した申請を判断者へメール通知する。Teams チャネル設定がある場合はチャネルにも投稿する。",
            build_stalled_reminder_clientdata(connection_refs, PREFIX),
        ),
    }
    deployed: dict[str, str] = {}
    all_active = True
    for flow_name, (description, clientdata) in flows.items():
        workflow_id, active = deploy_flow(flow_name, description, clientdata)
        deployed[flow_name] = workflow_id
        all_active = all_active and active

    print("\n=== Step 5: Power Automate ランタイム start ===")
    all_started = start_deployed_flows(environment_id, deployed)

    print("\n=== Step 6: 確認 ===")
    for flow_name, workflow_id in get_existing_notification_flows().items():
        flow = api_get(f"workflows({workflow_id})?$select=workflowid,name,statecode,statuscode")
        state = "有効" if flow.get("statecode") == 1 else "無効"
        print(f"  {flow_name}: {state} ({workflow_id})")
    if not all_active:
        print("\n  ⚠️ 一部フローの有効化に失敗しました。Power Automate UI で接続を修復してオンにしてください。")
    if not all_started:
        print("\n  ⚠️ 一部フローの start に失敗しました。Power Automate UI でフローを開き、保存またはオンにしてください。")
    print("\n✅ 完了")
    for flow_name, workflow_id in deployed.items():
        print(f"  {flow_name}: {workflow_id}")


if __name__ == "__main__":
    main()