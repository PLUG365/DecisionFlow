"""Copilot Studio の agent flow（Skills トリガー）を組み立てる共通ヘルパー。

`deploy_adaptive_card_decision_confirmation.py` から抽出した。フローを追加する
たびに同じ定義を書き写さないための置き場であり、挙動は抽出前と同じである。

書き込み系のフローを足す前に `docs/AGENT_WRITE_BOUNDARY.md` を読むこと。
特に、実行者の識別子（actorAadObjectId / actorUpn）は Copilot Studio の
認証済みユーザー変数からのみ渡す。agent flow は接続参照の identity で実行される
ため、この引数が「誰の操作として扱うか」を決めてしまう。
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

load_dotenv()

PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")
DATAVERSE_CONNECTOR = "shared_commondataserviceforapps"


def connector_id(connector: str) -> str:
    return f"/providers/Microsoft.PowerApps/apis/{connector}"


def connref_logical_name(connector: str) -> str:
    return f"{PREFIX}_{connector}"


def workflow_definition(actions: dict, triggers: dict) -> dict:
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


def clientdata(definition: dict, connection_reference_logical_names: dict[str, str] | None = None) -> str:
    connection_reference_logical_names = connection_reference_logical_names or {
        DATAVERSE_CONNECTOR: connref_logical_name(DATAVERSE_CONNECTOR)
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


def text_input(title: str, description: str) -> dict:
    return {
        "title": title,
        "type": "string",
        "x-ms-content-hint": "TEXT",
        "x-ms-dynamically-added": True,
        "description": description,
    }


def skills_trigger(properties: dict[str, dict], required: list[str]) -> dict:
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


def dataverse_host(operation_id: str) -> dict:
    return {
        "apiId": connector_id(DATAVERSE_CONNECTOR),
        "connectionName": DATAVERSE_CONNECTOR,
        "operationId": operation_id,
    }


def create_record_action(entity_set_name: str, item: dict, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": dataverse_host("CreateRecord"),
            "parameters": {
                "entityName": entity_set_name,
                "item": item,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def get_record_action(entity_set_name: str, record_id: str, select: str, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": dataverse_host("GetItem"),
            "parameters": {
                "entityName": entity_set_name,
                "recordId": record_id,
                "$select": select,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def list_records_action(entity_set_name: str, filter_query: str, select: str, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": dataverse_host("ListRecords"),
            "parameters": {
                "entityName": entity_set_name,
                "$filter": filter_query,
                "$select": select,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def update_record_action(entity_set_name: str, record_id: str, item: dict, run_after: dict | None = None) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": dataverse_host("UpdateRecord"),
            "parameters": {
                "entityName": entity_set_name,
                "recordId": record_id,
                "item": item,
            },
            "authentication": "@parameters('$authentication')",
        },
    }


def response_schema(properties: dict[str, str]) -> dict:
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


def response_action(body: dict, response_properties: dict[str, str], run_after: dict | None = None) -> dict:
    return {
        "type": "Response",
        "kind": "Skills",
        "runAfter": run_after or {},
        "inputs": {
            "statusCode": 200,
            "body": body,
            "schema": response_schema(response_properties),
        },
    }


def terminate_action(run_after: dict | None = None) -> dict:
    return {
        "type": "Terminate",
        "runAfter": run_after or {},
        "inputs": {"runStatus": "Succeeded"},
    }


def actor_lookup_filter() -> str:
    """actorAadObjectId があればそれで、無ければ actorUpn で systemuser を引く。

    どちらも Copilot Studio の認証済みユーザー変数から渡すこと。
    """
    return (
        "@if(empty(triggerBody()?['actorAadObjectId']), "
        "concat('domainname eq ''', triggerBody()?['actorUpn'], ''''), "
        "concat('azureactivedirectoryobjectid eq ', triggerBody()?['actorAadObjectId']))"
    )


def return_and_stop(action_name: str, body: dict, response_properties: dict[str, str]) -> dict:
    """検証に落ちたときに応答を返して打ち切る else ブランチを作る。"""
    return {
        action_name: response_action(body, response_properties),
        f"Stop_after_{action_name}": terminate_action({action_name: ["Succeeded"]}),
    }
