from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL, api_delete, api_get, api_patch, api_post, flow_api_call, get_session, get_token  # noqa: E402

load_dotenv()

API = f"{DATAVERSE_URL}/api/data/v9.2"
POWERAPPS_API = "https://api.powerapps.com"
SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")
DATAVERSE_CONNECTOR = "shared_commondataserviceforapps"
DATAVERSE_CONNECTOR_AI = "shared_commondataserviceforapps_1"
AI_PROMPT_NAME = "DecisionRecommendation"
AI_FLOW_NAME = "Application_GenerateAiDecision"
GPT_PROMPT_TEMPLATE_ID = "edfdb190-3791-45d8-9a6c-8f90a37c278a"

PROMPT_SEGMENTS = [
    {
        "type": "literal",
        "text": """
あなたは企業内の意思決定支援アシスタントです。以下の情報を読み、判断者が最終判断を行うための推奨案を作成してください。

制約:
- 判断選択肢は、入力された判断選択肢の名称から最も近いものを1つ選ぶ。
- 申請概要は3〜5文で、判断者が論点を素早く把握できる粒度にする。
- 会話概要は会話履歴がある場合だけ論点、追加確認、合意事項を要約する。会話履歴がない場合は「提出時点では会話履歴はありません。」と返す。
- 類似案件が少ない、または確度が低い場合はその旨を similarCases または risks に明記する。
- カテゴリ別レギュレーションが入力されている場合は、充足状況、懸念、追加確認事項を comment または risks に含める。
- カテゴリ別レギュレーションが未設定の場合は、その旨を comment または risks に明記し、通常のAI判断を継続する。
- 出力は指定 JSON スキーマに厳密に従う。

申請情報:
""".strip(),
    },
    {"type": "inputVariable", "id": "application"},
    {"type": "literal", "text": "\n\n関連資料:\n"},
    {"type": "inputVariable", "id": "resources"},
    {"type": "literal", "text": "\n\n会話履歴:\n"},
    {"type": "inputVariable", "id": "conversation"},
    {"type": "literal", "text": "\n\n過去類似案件:\n"},
    {"type": "inputVariable", "id": "similarCases"},
    {"type": "literal", "text": "\n\n判断選択肢:\n"},
    {"type": "inputVariable", "id": "decisionOptions"},
    {"type": "literal", "text": "\n\nカテゴリ別レギュレーション:\n"},
    {"type": "inputVariable", "id": "categoryRegulation"},
]

AI_INPUT_DEFINITIONS = [
    {"id": "application", "text": "application", "type": "text", "quickTestValue": "タイトル: 顧客案件: 見積条件の例外承認\n本文: 重要顧客向けの提案で通常条件から外れる支払条件を提示したい。"},
    {"id": "resources", "text": "resources", "type": "text", "quickTestValue": "見積条件資料: https://example.com"},
    {"id": "conversation", "text": "conversation", "type": "text", "quickTestValue": "提出時点では会話履歴はありません。"},
    {"id": "similarCases", "text": "similarCases", "type": "text", "quickTestValue": "顧客案件: 前回の例外承認 / 判断: 承認 / 理由: 顧客影響が大きい"},
    {"id": "decisionOptions", "text": "decisionOptions", "type": "text", "quickTestValue": "承認\n却下\n差し戻し"},
    {"id": "categoryRegulation", "text": "categoryRegulation", "type": "text", "quickTestValue": "例外条件は収益影響、顧客影響、回収条件を確認する。"},
]

AI_OUTPUT_DEFINITION = {
    "formats": ["json"],
    "jsonSchema": {
        "type": "object",
        "properties": {
            "applicationSummary": {"type": "string"},
            "conversationSummary": {"type": "string"},
            "recommendedOption": {"type": "string"},
            "comment": {"type": "string"},
            "risks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "detail": {"type": "string"},
                    },
                },
            },
            "similarCases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "decision": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
            },
        },
    },
    "jsonExamples": [
        {
            "applicationSummary": "重要顧客向け提案で、通常条件から外れる支払条件の提示可否を判断する申請です。顧客関係維持と収益影響のバランスが主な論点です。希望期限までに判断者の承認可否を確定する必要があります。",
            "conversationSummary": "提出時点では会話履歴はありません。",
            "recommendedOption": "承認",
            "comment": "顧客関係への影響が大きく、提示条件の例外は限定的であるため承認を推奨します。収益影響の上限と回収条件は資料で再確認してください。",
            "risks": [{"category": "収益影響", "detail": "収益影響の試算が更新されていない場合は追加確認が必要です。"}],
            "similarCases": [{"title": "顧客案件: 見積条件の例外承認", "decision": "承認", "reason": "重要顧客維持と例外条件の範囲が類似しています。"}],
        }
    ],
}

CUSTOM_CONFIG = {
    "version": "GptDynamicPrompt-2",
    "prompt": PROMPT_SEGMENTS,
    "definitions": {"inputs": AI_INPUT_DEFINITIONS, "formulas": [], "data": [], "output": AI_OUTPUT_DEFINITION},
    "modelParameters": {"modelType": "gpt-41-mini", "gptParameters": {"temperature": 0}},
    "settings": {"recordRetrievalLimit": 30, "shouldPreserveRecordLinks": None, "runtime": None},
    "code": "",
    "signature": "",
}


def delete_ai_prompt_model(model_id: str) -> None:
    try:
        api_patch(
            f"msdyn_aimodels({model_id})",
            {"msdyn_name": AI_PROMPT_NAME, "statecode": 0, "statuscode": 0},
        )
    except Exception as exc:
        print(f"  Warning: AI Builder model の Draft 戻しをスキップしました: {exc}")

    configs = api_get(
        f"msdyn_aiconfigurations?$filter=_msdyn_aimodelid_value eq '{model_id}'"
        "&$select=msdyn_aiconfigurationid&$orderby=createdon desc"
    )
    for config in configs.get("value", []):
        config_id = config["msdyn_aiconfigurationid"]
        try:
            api_delete(f"msdyn_aiconfigurations({config_id})")
            print(f"  Deleted AI Builder config: {config_id}")
        except Exception as exc:
            print(f"  Warning: AI Builder config 削除をスキップしました ({config_id}): {exc}")

    try:
        api_delete(f"msdyn_aimodels({model_id})")
        print(f"  Deleted AI Builder model: {model_id}")
    except Exception as exc:
        archive_name = f"{AI_PROMPT_NAME}_Archived_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        try:
            session = get_session()
            response = session.patch(f"{API}/msdyn_aimodels({model_id})", json={"msdyn_name": archive_name})
            response.raise_for_status()
            print(f"  Archived AI Builder model: {archive_name}")
        except Exception as rename_exc:
            raise RuntimeError(f"既存 AI Builder model の退避に失敗しました: {exc}; rename: {rename_exc}") from rename_exc


def _connector_id(connector: str = DATAVERSE_CONNECTOR) -> str:
    return f"/providers/Microsoft.PowerApps/apis/{connector}"


def _connref_logical_name() -> str:
    return f"{PREFIX}_{DATAVERSE_CONNECTOR}"


def _escape_odata_string(value: str) -> str:
    return value.replace("'", "''")


def _safe_debug_name(flow_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", flow_name)


def _workflow_definition(actions: dict, triggers: dict) -> dict:
    return {
        "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {"$authentication": {"defaultValue": {}, "type": "SecureObject"}, "$connections": {"defaultValue": {}, "type": "Object"}},
        "triggers": triggers,
        "actions": actions,
    }


def _clientdata(definition: dict, connection_refs: dict[str, str]) -> str:
    refs = {
        connector: {
            "runtimeSource": "embedded",
            "connection": {"connectionReferenceLogicalName": logical_name},
            "api": {"name": DATAVERSE_CONNECTOR},
        }
        for connector, logical_name in connection_refs.items()
    }
    refs.setdefault(
        DATAVERSE_CONNECTOR_AI,
        {
            "runtimeSource": "embedded",
            "connection": {"connectionReferenceLogicalName": connection_refs[DATAVERSE_CONNECTOR]},
            "api": {"name": DATAVERSE_CONNECTOR},
        },
    )
    return json.dumps({"properties": {"definition": definition, "connectionReferences": refs}, "schemaVersion": "1.0.0.0"}, ensure_ascii=False)


def _powerapp_text_input(title: str, description: str) -> dict:
    return {"title": title, "type": "string", "x-ms-content-hint": "TEXT", "x-ms-dynamically-added": True, "description": description}


def _response_text_output(title: str) -> dict:
    return {"title": title, "type": "string", "x-ms-content-hint": "TEXT", "x-ms-dynamically-added": True}


def _openapi_action(operation_id: str, parameters: dict, run_after: dict | None = None, connection_name: str = DATAVERSE_CONNECTOR) -> dict:
    return {
        "type": "OpenApiConnection",
        "runAfter": run_after or {},
        "inputs": {
            "host": {"apiId": _connector_id(), "connectionName": connection_name, "operationId": operation_id},
            "parameters": parameters,
            "authentication": "@parameters('$authentication')",
        },
    }


def build_ai_decision_flow_clientdata(connection_refs: dict[str, str], model_id: str, prefix: str = PREFIX) -> str:
    def ai_output(path: str) -> str:
        return f"outputs('Run_AI_Prompt')?['body/responsev2/predictionOutput/structuredOutput/{path}']"

    triggers = {
        "manual": {
            "type": "Request",
            "kind": "PowerAppV2",
            "inputs": {"schema": {"type": "object", "properties": {"text": _powerapp_text_input("applicationId", "AI 判断を生成する申請 ID")}, "required": ["text"]}},
        }
    }
    actions = {
        "Get_application": _openapi_action("GetItem", {"entityName": f"{prefix}_applications", "recordId": "@triggerBody()?['text']", "$select": f"{prefix}_applicationid,{prefix}_name,{prefix}_body,{prefix}_stage,{prefix}_duedate,{prefix}_submittedat,_{prefix}_categoryid_value"}),
        "List_category_regulation": _openapi_action("ListRecords", {"entityName": f"{prefix}_categories", "$filter": f"{prefix}_categoryid eq @{{coalesce(outputs('Get_application')?['body/_{prefix}_categoryid_value'], '00000000-0000-0000-0000-000000000000')}}", "$select": f"{prefix}_categoryid,{prefix}_name,{prefix}_regulationtext", "$top": 1}, {"Get_application": ["Succeeded"]}),
        "List_messages": _openapi_action("ListRecords", {"entityName": f"{prefix}_messages", "$filter": f"_{prefix}_applicationid_value eq @{{triggerBody()?['text']}}", "$select": f"{prefix}_body,createdon", "$orderby": "createdon asc"}, {"List_category_regulation": ["Succeeded"]}),
        "List_resources": _openapi_action("ListRecords", {"entityName": f"{prefix}_applicationresources", "$filter": f"_{prefix}_applicationid_value eq @{{triggerBody()?['text']}}", "$select": f"{prefix}_name,{prefix}_url,{prefix}_description"}, {"List_messages": ["Succeeded"]}),
        "List_decision_options": _openapi_action("ListRecords", {"entityName": f"{prefix}_decisionoptions", "$select": f"{prefix}_name,{prefix}_description", "$orderby": f"{prefix}_sortorder asc"}, {"List_resources": ["Succeeded"]}),
        "List_similar_applications": _openapi_action("ListRecords", {"entityName": f"{prefix}_applications", "$filter": f"{prefix}_applicationid ne @{{triggerBody()?['text']}} and {prefix}_stage eq 100000004 and _{prefix}_categoryid_value eq @{{coalesce(outputs('Get_application')?['body/_{prefix}_categoryid_value'], '00000000-0000-0000-0000-000000000000')}}", "$select": f"{prefix}_applicationid,{prefix}_name,{prefix}_aiapplicationsummary,{prefix}_aidecisionoptiontext,{prefix}_aidecisioncomment,{prefix}_aidecisionupdatedat", "$top": 30, "$orderby": f"{prefix}_aidecisionupdatedat desc"}, {"List_decision_options": ["Succeeded"]}),
        "List_recent_decided_applications": _openapi_action("ListRecords", {"entityName": f"{prefix}_applications", "$filter": f"{prefix}_applicationid ne @{{triggerBody()?['text']}} and {prefix}_stage eq 100000004", "$select": f"{prefix}_applicationid,{prefix}_name,{prefix}_aiapplicationsummary,{prefix}_aidecisionoptiontext,{prefix}_aidecisioncomment,{prefix}_aidecisionupdatedat", "$top": 10, "$orderby": f"{prefix}_aidecisionupdatedat desc"}, {"List_similar_applications": ["Succeeded"]}),
        "Build_prompt_inputs": {
            "type": "Compose",
            "runAfter": {"List_recent_decided_applications": ["Succeeded"]},
            "inputs": {
                "application": f"@{{concat('利用文脈: ', if(equals(outputs('Get_application')?['body/{prefix}_stage'], 100000001), '判断者向け判断支援', '申請者向け提出前確認'), '\\nタイトル: ', outputs('Get_application')?['body/{prefix}_name'], '\\n本文: ', coalesce(outputs('Get_application')?['body/{prefix}_body'], ''), '\\n希望期限: ', coalesce(outputs('Get_application')?['body/{prefix}_duedate'], '未設定'))}}",
                "resources": "@string(outputs('List_resources')?['body/value'])",
                "conversation": "@if(empty(outputs('List_messages')?['body/value']), '提出時点では会話履歴はありません。', string(outputs('List_messages')?['body/value']))",
                "similarCases": "@concat('同一カテゴリ候補: ', if(empty(outputs('List_similar_applications')?['body/value']), 'なし', string(outputs('List_similar_applications')?['body/value'])), '\n補助候補（直近判断済み）: ', if(empty(outputs('List_recent_decided_applications')?['body/value']), 'なし', string(outputs('List_recent_decided_applications')?['body/value'])))",
                "decisionOptions": "@string(outputs('List_decision_options')?['body/value'])",
                "categoryRegulation": f"@if(or(empty(outputs('List_category_regulation')?['body/value']), empty(first(outputs('List_category_regulation')?['body/value'])?['{prefix}_regulationtext'])), 'カテゴリ固有のレギュレーションは未設定です。通常のAI判断を継続してください。', concat('カテゴリ別レギュレーション: ', first(outputs('List_category_regulation')?['body/value'])?['{prefix}_regulationtext']))",
            },
        },
        "Run_AI_Prompt": _openapi_action(
            "aibuilderpredict_customprompt",
            {
                "recordId": model_id,
                "item/requestv2/application": "@outputs('Build_prompt_inputs')?['application']",
                "item/requestv2/resources": "@outputs('Build_prompt_inputs')?['resources']",
                "item/requestv2/conversation": "@outputs('Build_prompt_inputs')?['conversation']",
                "item/requestv2/similarCases": "@outputs('Build_prompt_inputs')?['similarCases']",
                "item/requestv2/decisionOptions": "@outputs('Build_prompt_inputs')?['decisionOptions']",
                "item/requestv2/categoryRegulation": "@outputs('Build_prompt_inputs')?['categoryRegulation']",
            },
            {"Build_prompt_inputs": ["Succeeded"]},
            DATAVERSE_CONNECTOR_AI,
        ),
        "Build_basis_json": {
            "type": "Compose",
            "runAfter": {"Run_AI_Prompt": ["Succeeded"]},
            "inputs": f"@string(json(concat('{{\"risks\":', string(coalesce({ai_output('risks')}, {ai_output('recommendation/risks')}, json('[]'))), ',\"similarCases\":', string(coalesce({ai_output('similarCases')}, {ai_output('recommendation/similarCases')}, json('[]'))), ',\"regulationContext\":{{\"considered\":', if(startsWith(outputs('Build_prompt_inputs')?['categoryRegulation'], 'カテゴリ別レギュレーション:'), 'true', 'false'), ',\"audience\":\"', if(equals(outputs('Get_application')?['body/{prefix}_stage'], 100000001), 'deciderReview', 'applicantPreSubmit'), '\",\"message\":\"', if(startsWith(outputs('Build_prompt_inputs')?['categoryRegulation'], 'カテゴリ別レギュレーション:'), 'カテゴリ別レギュレーションを考慮しました。', 'カテゴリ固有のレギュレーションは未設定です。'), '\"}}}}')))",
        },
        "Update_application_ai_decision": _openapi_action(
            "UpdateRecord",
            {
                "entityName": f"{prefix}_applications",
                "recordId": "@triggerBody()?['text']",
                "item": {
                    f"{prefix}_aiapplicationsummary": f"@coalesce({ai_output('applicationSummary')}, {ai_output('recommendation/applicationSummary')})",
                    f"{prefix}_aiconversationsummary": f"@coalesce({ai_output('conversationSummary')}, {ai_output('recommendation/conversationSummary')})",
                    f"{prefix}_aidecisionoptiontext": f"@coalesce({ai_output('recommendedOption')}, {ai_output('recommendation/recommendedOption')}, {ai_output('recommendedDecision')}, {ai_output('recommendation/recommendedDecision')}, {ai_output('suggestedDecision')}, {ai_output('recommendation/suggestedDecision')})",
                    f"{prefix}_aidecisioncomment": f"@coalesce({ai_output('comment')}, {ai_output('recommendation/comment')}, {ai_output('recommendationReason')}, {ai_output('recommendation/recommendationReason')})",
                    f"{prefix}_aidecisionbasis": "@outputs('Build_basis_json')",
                    f"{prefix}_aidecisionupdatedat": "@utcNow()",
                },
            },
            {"Build_basis_json": ["Succeeded"]},
        ),
        "Respond_success": {"type": "Response", "kind": "PowerApp", "runAfter": {"Update_application_ai_decision": ["Succeeded"]}, "inputs": {"statusCode": 200, "body": {"ok": "true", "applicationid": "@{triggerBody()?['text']}", "message": "AI decision generated."}, "schema": {"type": "object", "properties": {"ok": _response_text_output("ok"), "applicationid": _response_text_output("applicationid"), "message": _response_text_output("message")}, "additionalProperties": {}}}},
        "Respond_failure": {"type": "Response", "kind": "PowerApp", "runAfter": {"Run_AI_Prompt": ["Failed", "TimedOut"], "Update_application_ai_decision": ["Failed", "TimedOut"]}, "inputs": {"statusCode": 200, "body": {"ok": "false", "applicationid": "@{triggerBody()?['text']}", "message": "AI decision generation failed."}, "schema": {"type": "object", "properties": {"ok": _response_text_output("ok"), "applicationid": _response_text_output("applicationid"), "message": _response_text_output("message")}, "additionalProperties": {}}}},
    }
    return _clientdata(_workflow_definition(actions=actions, triggers=triggers), connection_refs)


def _read_environment_id() -> str:
    config_path = ROOT / "power.config.json"
    if config_path.exists():
        data = json.loads(config_path.read_text(encoding="utf-8"))
        if data.get("environmentId"):
            return data["environmentId"]
    envs = flow_api_call("GET", "/providers/Microsoft.ProcessSimple/environments")
    for env in envs.get("value", []):
        linked = env.get("properties", {}).get("linkedEnvironmentMetadata", {})
        if (linked.get("instanceUrl") or "").rstrip("/").lower() == DATAVERSE_URL.lower():
            return env["name"]
    raise RuntimeError("環境 ID を解決できませんでした。")


def find_dataverse_connections(environment_id: str) -> list[str]:
    forced = os.environ.get("DATAVERSE_CONN", "").strip() or os.environ.get("FALLBACK_CONN_DATAVERSE", "").strip()
    if forced:
        return [forced]
    encoded_env = quote(environment_id, safe="")
    token = get_token(scope="https://service.powerapps.com/.default")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    urls = [
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/apis/{DATAVERSE_CONNECTOR}/connections?$filter=environment eq '{environment_id}'&api-version=2016-11-01",
        f"{POWERAPPS_API}/providers/Microsoft.PowerApps/environments/{encoded_env}/apis/{DATAVERSE_CONNECTOR}/connections?api-version=2016-11-01",
    ]
    names: list[str] = []
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=120)
            response.raise_for_status()
            for connection in response.json().get("value", []):
                name = connection.get("name") or connection.get("properties", {}).get("connectionName")
                if name:
                    names.append(name)
        except Exception as exc:
            print(f"  接続検索をスキップ: {exc}")
    unique_names = list(dict.fromkeys(names))
    if not unique_names:
        raise RuntimeError("Dataverse 接続が見つかりません。")
    return unique_names


def find_dataverse_connection(environment_id: str) -> str:
    return find_dataverse_connections(environment_id)[0]


def ensure_connection_reference(connection_name: str) -> str:
    logical_name = _connref_logical_name()
    existing = api_get(f"connectionreferences?$filter=connectionreferencelogicalname eq '{logical_name}'&$select=connectionreferenceid").get("value", [])
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    body = {"connectionid": connection_name, "connectorid": _connector_id()}
    if existing:
        session.patch(f"{API}/connectionreferences({existing[0]['connectionreferenceid']})", json=body).raise_for_status()
        return logical_name
    body.update({"connectionreferencelogicalname": logical_name, "connectionreferencedisplayname": "DecisionFlow Dataverse connection"})
    session.post(f"{API}/connectionreferences", json=body).raise_for_status()
    return logical_name


def deploy_ai_prompt() -> str:
    existing = api_get(f"msdyn_aimodels?$filter=msdyn_name eq '{AI_PROMPT_NAME}'&$select=msdyn_aimodelid,_msdyn_activerunconfigurationid_value").get("value", [])
    custom_config_str = json.dumps(CUSTOM_CONFIG, ensure_ascii=False)
    if existing and existing[0].get("_msdyn_activerunconfigurationid_value"):
        model_id = existing[0]["msdyn_aimodelid"]
        run_config_id = existing[0].get("_msdyn_activerunconfigurationid_value")
        if run_config_id:
            current_config = api_get(
                f"msdyn_aiconfigurations({run_config_id})?$select=msdyn_customconfiguration"
            ).get("msdyn_customconfiguration")
            try:
                if json.loads(current_config or "{}") == CUSTOM_CONFIG:
                    return model_id
            except json.JSONDecodeError:
                pass
            session = get_session()
            patch_response = session.patch(
                f"{API}/msdyn_aiconfigurations({run_config_id})",
                json={"msdyn_customconfiguration": custom_config_str},
            )
            if not patch_response.ok:
                print(
                    "  Warning: 既存 AI Builder run configuration の直接更新に失敗しました "
                    f"({patch_response.status_code})"
                )
                delete_ai_prompt_model(model_id)
            else:
                return model_id
        else:
            delete_ai_prompt_model(model_id)
    model_id = api_post("msdyn_aimodels", {"msdyn_name": AI_PROMPT_NAME, "msdyn_TemplateId@odata.bind": f"/msdyn_aitemplates({GPT_PROMPT_TEMPLATE_ID})", "msdyn_sharewithorganizationoncreate": False}, solution=SOLUTION_NAME)
    now_str = datetime.now(timezone.utc).strftime("%m/%d/%Y %I:%M:%S %p")
    training_id = api_post("msdyn_aiconfigurations", {"msdyn_AIModelId@odata.bind": f"/msdyn_aimodels({model_id})", "msdyn_type": 190690000, "msdyn_name": f"{model_id}_Training_{now_str}"}, solution=SOLUTION_NAME)
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "OData-MaxVersion": "4.0", "OData-Version": "4.0", "Accept": "application/json", "Content-Type": "application/json; charset=utf-8"}
    requests.post(f"{DATAVERSE_URL}/api/data/v9.2/AIModelPublish", headers=headers, json={"TemplateId": GPT_PROMPT_TEMPLATE_ID, "ModelId": model_id, "RunConfigurationId": training_id, "ModelName": AI_PROMPT_NAME, "CustomConfiguration": custom_config_str, "RunConfiguration": custom_config_str}).raise_for_status()
    time.sleep(2)
    configs = api_get(f"msdyn_aiconfigurations?$filter=_msdyn_aimodelid_value eq '{model_id}' and msdyn_type eq 190690000 and statecode eq 2&$select=msdyn_aiconfigurationid&$top=1&$orderby=createdon desc")
    published_training_id = configs.get("value", [{}])[0].get("msdyn_aiconfigurationid", training_id)
    run_id = api_post("msdyn_aiconfigurations", {"msdyn_AIModelId@odata.bind": f"/msdyn_aimodels({model_id})", "msdyn_type": 190690001, "msdyn_name": f"{model_id}_Run_{now_str}", "msdyn_customconfiguration": custom_config_str, "msdyn_TrainedModelAIConfigurationPareId@odata.bind": f"/msdyn_aiconfigurations({published_training_id})"}, solution=SOLUTION_NAME)
    requests.post(f"{DATAVERSE_URL}/api/data/v9.2/msdyn_aiconfigurations({run_id})/Microsoft.Dynamics.CRM.PublishAIConfiguration", headers=headers, json={"version": "1.0"}).raise_for_status()
    return model_id or ""


def find_existing_flow(flow_name: str) -> dict | None:
    existing = api_get(
        f"workflows?$filter=name eq '{_escape_odata_string(flow_name)}' and category eq 5"
        "&$select=workflowid,statecode&$orderby=createdon desc&$top=1"
    ).get("value", [])
    return existing[0] if existing else None


def activate_flow(session: requests.Session, workflow_id: str, body: dict) -> None:
    activate_response = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 1, "statuscode": 2})
    if not activate_response.ok:
        debug_path = ROOT / "scripts" / f"{_safe_debug_name(AI_FLOW_NAME)}_debug.json"
        debug_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(
            f"{AI_FLOW_NAME} の有効化に失敗しました: {activate_response.status_code}\n"
            f"{activate_response.text[:2000]}\nDebug: {debug_path}"
        )


def create_flow(clientdata: str) -> str:
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    body = {"name": AI_FLOW_NAME, "type": 1, "category": 5, "statecode": 0, "statuscode": 1, "primaryentity": "none", "clientdata": clientdata, "description": "Code Apps から申請 ID を受け取り AI 判断を生成して ds_application に保存する。"}
    response = session.post(f"{API}/workflows", json=body)
    if not response.ok:
        debug_path = ROOT / "scripts" / f"{_safe_debug_name(AI_FLOW_NAME)}_debug.json"
        debug_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"{AI_FLOW_NAME} の作成に失敗しました: {response.status_code}\n{response.text[:1000]}\nDebug: {debug_path}")
    workflow_id = response.headers.get("OData-EntityId", "").split("(")[-1].rstrip(")")
    activate_flow(session, workflow_id, body)
    return workflow_id


def update_flow(workflow_id: str, statecode: int, clientdata: str) -> str:
    session = get_session()
    session.headers["MSCRM.SolutionUniqueName"] = SOLUTION_NAME
    deactivated = False
    if statecode == 1:
        deactivate_response = session.patch(f"{API}/workflows({workflow_id})", json={"statecode": 0, "statuscode": 1})
        if not deactivate_response.ok:
            print(
                f"  Warning: {AI_FLOW_NAME} の無効化に失敗しました。"
                "active のまま clientdata 更新を試行します。"
            )
        else:
            deactivated = True
    body = {"clientdata": clientdata, "description": "Code Apps から申請 ID を受け取り AI 判断を生成して ds_application に保存する。"}
    update_response = session.patch(f"{API}/workflows({workflow_id})", json=body)
    if not update_response.ok:
        debug_path = ROOT / "scripts" / f"{_safe_debug_name(AI_FLOW_NAME)}_debug.json"
        debug_path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(
            f"{AI_FLOW_NAME} の更新に失敗しました: {update_response.status_code}\n"
            f"{update_response.text[:2000]}\nDebug: {debug_path}"
        )
    if statecode != 1 or deactivated:
        activate_flow(session, workflow_id, body)
    return workflow_id


def deploy_flow(model_id: str, connection_reference: str) -> str:
    clientdata = build_ai_decision_flow_clientdata({DATAVERSE_CONNECTOR: connection_reference}, model_id, PREFIX)
    existing = find_existing_flow(AI_FLOW_NAME)
    if existing:
        workflow_id = update_flow(existing["workflowid"], existing.get("statecode", 0), clientdata)
    else:
        workflow_id = create_flow(clientdata)
    environment_id = _read_environment_id()
    flow_api_call("POST", f"/providers/Microsoft.ProcessSimple/environments/{environment_id}/flows/{workflow_id}/start", {})
    return workflow_id


def main() -> None:
    if not DATAVERSE_URL:
        raise RuntimeError("DATAVERSE_URL が .env に設定されていません。")
    print("=== DecisionFlow AI decision deployment ===")
    model_id = deploy_ai_prompt()
    print(f"AI Builder model: {model_id}")
    environment_id = _read_environment_id()
    connection_names = find_dataverse_connections(environment_id)
    last_error: Exception | None = None
    workflow_id = ""
    for index, connection_name in enumerate(connection_names, start=1):
        try:
            print(f"Dataverse connection candidate {index}/{len(connection_names)}: {connection_name}")
            connection_reference = ensure_connection_reference(connection_name)
            workflow_id = deploy_flow(model_id, connection_reference)
            break
        except Exception as exc:
            last_error = exc
            print(f"  Warning: 接続候補 {connection_name} でフロー更新に失敗しました: {exc}")
    if not workflow_id:
        raise RuntimeError("すべての Dataverse 接続候補で AI 判断フローのデプロイに失敗しました。") from last_error
    print(f"Flow: {AI_FLOW_NAME} ({workflow_id})")
    print("Next: npx power-apps add-flow --flow-id " + workflow_id)


if __name__ == "__main__":
    main()