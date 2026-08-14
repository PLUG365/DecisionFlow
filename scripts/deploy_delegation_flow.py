from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL, api_get, get_session  # noqa: E402
from scripts.agent_flow_common import create_record_action  # noqa: E402
from scripts.deploy_notification_flows import (  # noqa: E402
    DATAVERSE_CONNECTOR,
    OUTLOOK_CONNECTOR,
    _clientdata,
    _dataverse_trigger,
    _get_record_action,
    _html,
    _list_records_action,
    _read_environment_id,
    _send_email_if_present,
    _update_record_action,
    ensure_connection_reference,
    find_connections,
    start_deployed_flows,
)

load_dotenv()

API = f"{DATAVERSE_URL}/api/data/v9.2"
SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")
DECIDER_GROUP_NAME = os.environ.get("DECIDER_GROUP_NAME", "DecisionFlow-Deciders")

FLOW_NAME = "Application_DelegationRequest_OnCreated"
PENDING = 100000000
PROCESSED = 100000001
REJECTED = 100000002
HISTORY_SUCCEEDED = 100000000
HISTORY_REJECTED = 100000001
SUBMITTED = 100000001


def _update_only_record_action(
    entity_set_name: str,
    record_id: str,
    item: dict,
    run_after: dict | None = None,
) -> dict:
    action = _update_record_action(entity_set_name, record_id, item, run_after)
    action["inputs"]["host"]["operationId"] = "UpdateOnlyRecord"
    return action


def _strip_explicit_authentication(value):
    if isinstance(value, dict):
        return {
            key: _strip_explicit_authentication(item)
            for key, item in value.items()
            if key != "authentication"
        }
    if isinstance(value, list):
        return [_strip_explicit_authentication(item) for item in value]
    return value


def _history_item(prefix: str, result: int, detail: str, include_previous_decider: bool = True) -> dict:
    request_id = "triggerOutputs()?['body/{0}_delegationrequestid']".format(prefix)
    application_id = "triggerOutputs()?['body/_{0}_applicationid_value']".format(prefix)
    actor_id = "triggerOutputs()?['body/_createdby_value']"
    previous_decider_id = "outputs('Get_application')?['body/_{0}_deciderid_value']".format(prefix)
    new_decider_id = "triggerOutputs()?['body/_{0}_requesteddeciderid_value']".format(prefix)
    item = {
        f"{prefix}_name": "@concat('担当変更 - ', outputs('Get_application')?['body/{0}_name'])".format(prefix),
        f"{prefix}_result": result,
        f"{prefix}_detail": detail,
        f"{prefix}_processedat": "@utcNow()",
        f"{prefix}_delegationrequestid@odata.bind": "@concat('/{0}_delegationrequests(', {1}, ')')".format(prefix, request_id),
        f"{prefix}_applicationid@odata.bind": "@concat('/{0}_applications(', {1}, ')')".format(prefix, application_id),
        f"{prefix}_actorid@odata.bind": "@concat('/systemusers(', {0}, ')')".format(actor_id),
        f"{prefix}_newdeciderid@odata.bind": "@concat('/systemusers(', {0}, ')')".format(new_decider_id),
    }
    if include_previous_decider:
        item[f"{prefix}_previousdeciderid@odata.bind"] = "@concat('/systemusers(', {0}, ')')".format(previous_decider_id)
    return item


def build_delegation_flow_clientdata(
    connection_refs: dict[str, str] | None = None,
    prefix: str = PREFIX,
) -> str:
    connection_refs = connection_refs or {
        DATAVERSE_CONNECTOR: f"{prefix}_{DATAVERSE_CONNECTOR}",
        OUTLOOK_CONNECTOR: f"{prefix}_{OUTLOOK_CONNECTOR}",
    }
    trigger = _dataverse_trigger("When_delegation_request_created", 1, f"{prefix}_delegationrequest")
    trigger["When_delegation_request_created"]["runtimeConfiguration"] = {"concurrency": {"runs": 1}}

    application_id = f"@triggerOutputs()?['body/_{prefix}_applicationid_value']"
    requested_decider_id = f"@triggerOutputs()?['body/_{prefix}_requesteddeciderid_value']"
    actor_id = "@triggerOutputs()?['body/_createdby_value']"
    request_id = f"@triggerOutputs()?['body/{prefix}_delegationrequestid']"
    previous_decider_id = f"outputs('Get_application')?['body/_{prefix}_deciderid_value']"

    valid_expression = {
        "and": [
            {"equals": [f"@triggerOutputs()?['body/{prefix}_status']", PENDING]},
            {"equals": [f"@outputs('Get_application')?['body/{prefix}_stage']", SUBMITTED]},
            {"not": {"equals": [f"@coalesce({previous_decider_id},'')", ""]}},
            {
                "not": {
                    "equals": [
                        f"@toLower(coalesce({previous_decider_id},''))",
                        f"@toLower(coalesce(triggerOutputs()?['body/_{prefix}_requesteddeciderid_value'],''))",
                    ]
                }
            },
            {
                "or": [
                    {
                        "equals": [
                            f"@toLower(coalesce({previous_decider_id},''))",
                            "@toLower(coalesce(triggerOutputs()?['body/_createdby_value'],''))",
                        ]
                    },
                    {"greater": ["@length(outputs('List_actor_admin_role')?['body/value'])", 0]},
                ]
            },
            {"greater": ["@length(outputs('List_valid_requested_decider')?['body/value'])", 0]},
        ]
    }

    success_detail = "担当判断者を変更しました。"
    rejected_detail = "担当変更を実行できませんでした。申請状態、現在の担当者、変更先の判断者資格を確認してください。"
    subject = f"@{{concat('【DecisionFlow】判断担当者変更: ', outputs('Get_application')?['body/{prefix}_name'])}}"
    body = _html(
        "判断担当者が変更されました",
        [
            f"申請: @{{outputs('Get_application')?['body/{prefix}_name']}}",
            "変更前: @{outputs('Get_previous_decider')?['body/fullname']}",
            "変更後: @{outputs('Get_requested_decider')?['body/fullname']}",
            "実行者: @{outputs('Get_actor')?['body/fullname']}",
        ],
    )

    update_request_success = _update_only_record_action(
        f"{prefix}_delegationrequests",
        request_id,
        {
            f"{prefix}_status": PROCESSED,
            f"{prefix}_processedat": "@utcNow()",
            f"{prefix}_resultmessage": success_detail,
            f"{prefix}_previousdeciderid@odata.bind": f"@concat('/systemusers(', {previous_decider_id}, ')')",
        },
        {"Update_application_decider": ["Succeeded"]},
    )
    create_success_history = create_record_action(
        f"{prefix}_delegationhistories",
        _history_item(prefix, HISTORY_SUCCEEDED, success_detail),
        {"Update_request_processed": ["Succeeded"]},
    )
    update_request_rejected = _update_only_record_action(
        f"{prefix}_delegationrequests",
        request_id,
        {
            f"{prefix}_status": REJECTED,
            f"{prefix}_processedat": "@utcNow()",
            f"{prefix}_resultmessage": rejected_detail,
        },
    )
    # 変更前担当が空のまま bind すると `@concat('/systemusers(', '', ')')` が
    # `/systemusers()` になり、**拒否履歴の作成ごと落ちる**。
    # ただし空になり得るのは1ケースだけである。`If_request_is_authorized_and_valid` の
    # runAfter は `Get_application` を含む全アクションの Succeeded を要求するので、
    # else へ来た時点で申請は取れている。空なのは条件3が偽のとき＝担当未割当だけ。
    # そこだけ bind を落とし、**担当が実在した拒否では証跡を残す**。
    rejected_history_gate = {
        "If_previous_decider_is_known": {
            "type": "If",
            "runAfter": {"Update_request_rejected": ["Succeeded"]},
            "expression": {"not": {"equals": [f"@coalesce({previous_decider_id},'')", ""]}},
            "actions": {
                "Create_rejected_history": create_record_action(
                    f"{prefix}_delegationhistories",
                    _history_item(prefix, HISTORY_REJECTED, rejected_detail),
                ),
            },
            "else": {
                "actions": {
                    "Create_rejected_history_without_previous": create_record_action(
                        f"{prefix}_delegationhistories",
                        _history_item(
                            prefix,
                            HISTORY_REJECTED,
                            rejected_detail,
                            include_previous_decider=False,
                        ),
                    ),
                }
            },
        }
    }

    actions = {
        "Get_application": _get_record_action(
            f"{prefix}_applications",
            application_id,
            f"{prefix}_applicationid,{prefix}_name,{prefix}_stage,_{prefix}_deciderid_value,_createdby_value",
        ),
        "Get_requested_decider": _get_record_action(
            "systemusers",
            requested_decider_id,
            "systemuserid,fullname,internalemailaddress,isdisabled",
        ),
        "Get_actor": _get_record_action(
            "systemusers",
            actor_id,
            "systemuserid,fullname,internalemailaddress",
        ),
        "List_actor_admin_role": _list_records_action(
            "systemusers",
            "@concat('systemuserid eq ', triggerOutputs()?['body/_createdby_value'], "
            "' and systemuserroles_association/any(r:r/name eq ''ds_Admin'')')",
            "systemuserid",
        ),
        "List_valid_requested_decider": _list_records_action(
            "systemusers",
            "@concat('systemuserid eq ', triggerOutputs()?['body/_{0}_requesteddeciderid_value'], "
            "' and isdisabled eq false and teammembership_association/any(t:t/name eq ''{1}'' )')".format(prefix, DECIDER_GROUP_NAME),
            "systemuserid",
        ),
        "If_request_is_authorized_and_valid": {
            "type": "If",
            "runAfter": {
                "Get_application": ["Succeeded"],
                "Get_requested_decider": ["Succeeded"],
                "Get_actor": ["Succeeded"],
                "List_actor_admin_role": ["Succeeded"],
                "List_valid_requested_decider": ["Succeeded"],
            },
            "expression": valid_expression,
            "actions": {
                "Get_previous_decider": _get_record_action(
                    "systemusers",
                    f"@{previous_decider_id}",
                    "systemuserid,fullname,internalemailaddress",
                ),
                "Get_applicant": _get_record_action(
                    "systemusers",
                    f"@outputs('Get_application')?['body/_createdby_value']",
                    "systemuserid,fullname,internalemailaddress",
                ),
                "Update_application_decider": _update_only_record_action(
                    f"{prefix}_applications",
                    application_id,
                    {
                        f"{prefix}_deciderid@odata.bind": f"@concat('/systemusers(', triggerOutputs()?['body/_{prefix}_requesteddeciderid_value'], ')')"
                    },
                    {"Get_previous_decider": ["Succeeded"], "Get_applicant": ["Succeeded"]},
                ),
                "Update_request_processed": update_request_success,
                "Create_success_history": create_success_history,
                **_send_email_if_present(
                    "If_new_decider_has_email",
                    "outputs('Get_requested_decider')?['body/internalemailaddress']",
                    subject,
                    body,
                    {"Create_success_history": ["Succeeded"]},
                ),
                **_send_email_if_present(
                    "If_previous_decider_has_email",
                    "outputs('Get_previous_decider')?['body/internalemailaddress']",
                    subject,
                    body,
                    {"If_new_decider_has_email": ["Succeeded"]},
                ),
                **_send_email_if_present(
                    "If_applicant_has_email",
                    "outputs('Get_applicant')?['body/internalemailaddress']",
                    subject,
                    body,
                    {"If_previous_decider_has_email": ["Succeeded"]},
                ),
            },
            "else": {
                "actions": {
                    "Update_request_rejected": update_request_rejected,
                    **rejected_history_gate,
                }
            },
        },
    }
    definition = _strip_explicit_authentication(_workflow_definition(actions, trigger))
    return _clientdata(definition, connection_refs)


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


def deploy_flow(clientdata: str, activate: bool = False) -> tuple[str, bool]:
    existing = api_get(
        f"workflows?$filter=name eq '{FLOW_NAME}' and category eq 5&$select=workflowid,statecode,statuscode"
    ).get("value", [])
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    body = {
        "name": FLOW_NAME,
        "type": 1,
        "category": 5,
        "primaryentity": "none",
        "clientdata": clientdata,
        "description": "担当変更要求のcreatedbyを実行者として検証し、Submitted申請の判断者を変更して専用履歴へ追記する。",
    }
    if existing:
        workflow_id = existing[0]["workflowid"]
        if existing[0].get("statecode") == 1:
            response = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 0, "statuscode": 1})
            response.raise_for_status()
        response = session.patch(f"{API}/workflows({workflow_id})", json=body)
        response.raise_for_status()
    else:
        body.update({"statecode": 0, "statuscode": 1})
        response = session.post(f"{API}/workflows", json=body)
        response.raise_for_status()
        location = response.headers.get("OData-EntityId", "")
        workflow_id = location.split("(")[-1].rstrip(")")
    if not activate:
        return workflow_id, False
    response = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 1, "statuscode": 2})
    response.raise_for_status()
    return workflow_id, True


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy the DecisionFlow delegation request flow.")
    parser.add_argument("--activate", action="store_true", help="Activate and start the validated flow after deployment.")
    args = parser.parse_args()

    environment_id = _read_environment_id()
    connection_names = {
        DATAVERSE_CONNECTOR: find_connections(environment_id, DATAVERSE_CONNECTOR)[0],
        OUTLOOK_CONNECTOR: find_connections(environment_id, OUTLOOK_CONNECTOR)[0],
    }
    connection_refs = {
        DATAVERSE_CONNECTOR: ensure_connection_reference(
            DATAVERSE_CONNECTOR,
            connection_names[DATAVERSE_CONNECTOR],
            "DecisionFlow Dataverse connection",
        ),
        OUTLOOK_CONNECTOR: ensure_connection_reference(
            OUTLOOK_CONNECTOR,
            connection_names[OUTLOOK_CONNECTOR],
            "DecisionFlow Outlook connection",
        ),
    }
    workflow_id, active = deploy_flow(build_delegation_flow_clientdata(connection_refs), args.activate)
    if active:
        start_deployed_flows(environment_id, {FLOW_NAME: workflow_id})
    print(json.dumps({"flow": FLOW_NAME, "workflowId": workflow_id, "active": active}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
