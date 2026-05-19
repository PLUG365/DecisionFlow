import os
import sys
import time
import traceback
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auth_helper import (  # noqa: E402
    DATAVERSE_URL,
    api_get,
    api_post,
    get_session,
    retry_metadata,
)

load_dotenv()

SOLUTION_NAME = os.getenv("SOLUTION_NAME", "").strip()
PREFIX = os.getenv("PUBLISHER_PREFIX", "").strip()
SOLUTION_DISPLAY_NAME = os.getenv("SOLUTION_DISPLAY_NAME", "意思決定支援 (Decision Support)").strip()
PUBLISHER_UNIQUE_NAME = os.getenv("PUBLISHER_UNIQUE_NAME", f"{PREFIX}_publisher").strip()
PUBLISHER_DISPLAY_NAME = os.getenv("PUBLISHER_DISPLAY_NAME", "DecisionFlow Publisher").strip()
LANGUAGE_CODE = int(os.getenv("DATAVERSE_LANGUAGE_CODE", "1033"))

if not DATAVERSE_URL or not SOLUTION_NAME or not PREFIX:
    raise SystemExit("DATAVERSE_URL, SOLUTION_NAME, PUBLISHER_PREFIX must be set in .env")


def label(text: str) -> dict:
    return {"LocalizedLabels": [{"Label": text, "LanguageCode": LANGUAGE_CODE}]}


def save_env_value(key: str, value: str) -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updated = False
    for index, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[index] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def entity_set(logical_name: str) -> str:
    meta = api_get(f"EntityDefinitions(LogicalName='{logical_name}')?$select=EntitySetName")
    return meta["EntitySetName"]


def navprop_by_lookup_attr(from_logical: str, lookup_attr: str) -> str | None:
    rels = api_get(
        f"EntityDefinitions(LogicalName='{from_logical}')/ManyToOneRelationships"
        f"?$filter=ReferencingAttribute eq '{lookup_attr}'"
        "&$select=ReferencingEntityNavigationPropertyName"
    )
    values = rels.get("value", [])
    if not values:
        return None
    return values[0]["ReferencingEntityNavigationPropertyName"]


STAGE_OPTIONS = [
    (100000000, "Draft"),
    (100000001, "Submitted"),
    (100000004, "Decided"),
]

MESSAGE_KIND_OPTIONS = [
    (100000000, "Comment"),
    (100000001, "Question"),
    (100000002, "Answer"),
    (100000003, "System"),
]

PARTICIPANT_ROLE_OPTIONS = [
    (100000000, "Applicant"),
    (100000001, "Decider"),
    (100000003, "Contributor"),
]

DECISION_CARD_STATUS_OPTIONS = [
    (100000000, "Issued"),
    (100000001, "Consumed"),
    (100000002, "Superseded"),
    (100000003, "Expired"),
]

TABLES = [
    {
        "logical": f"{PREFIX}_category",
        "display": "カテゴリ",
        "plural": "カテゴリ",
        "description": "申請カテゴリのマスタ",
        "columns": [
            {"logical": f"{PREFIX}_description", "type": "Memo", "display": "説明", "maxLength": 2000},
            {"logical": f"{PREFIX}_template", "type": "Memo", "display": "推奨フォーマット", "maxLength": 4000},
            {"logical": f"{PREFIX}_sortorder", "type": "Integer", "display": "並び順", "minValue": 0, "maxValue": 1000},
        ],
    },
    {
        "logical": f"{PREFIX}_decisionoption",
        "display": "判断選択肢",
        "plural": "判断選択肢",
        "description": "判断結果の選択肢マスタ",
        "columns": [
            {"logical": f"{PREFIX}_description", "type": "Memo", "display": "説明", "maxLength": 2000},
            {"logical": f"{PREFIX}_sortorder", "type": "Integer", "display": "並び順", "minValue": 0, "maxValue": 1000},
        ],
    },
    {
        "logical": f"{PREFIX}_application",
        "display": "申請",
        "plural": "申請",
        "description": "意思決定を依頼する申請",
        "columns": [
            {"logical": f"{PREFIX}_body", "type": "Memo", "display": "申請本文", "maxLength": 20000},
            {"logical": f"{PREFIX}_stage", "type": "Picklist", "display": "ステージ", "options": STAGE_OPTIONS},
            {"logical": f"{PREFIX}_duedate", "type": "DateTime", "display": "希望期限", "format": "DateOnly"},
            {"logical": f"{PREFIX}_submittedat", "type": "DateTime", "display": "提出日時", "format": "DateAndTime"},
            {"logical": f"{PREFIX}_aiapplicationsummary", "type": "Memo", "display": "AI申請概要", "maxLength": 50000},
            {"logical": f"{PREFIX}_aiconversationsummary", "type": "Memo", "display": "AI会話概要", "maxLength": 50000},
            {"logical": f"{PREFIX}_aidecisionoptiontext", "type": "String", "display": "AI推奨判断", "maxLength": 200},
            {"logical": f"{PREFIX}_aidecisioncomment", "type": "Memo", "display": "AI判断コメント", "maxLength": 50000},
            {"logical": f"{PREFIX}_aidecisionbasis", "type": "Memo", "display": "AI判断根拠", "maxLength": 50000},
            {"logical": f"{PREFIX}_aidecisionupdatedat", "type": "DateTime", "display": "AI判断更新日時", "format": "DateAndTime"},
        ],
    },
    {
        "logical": f"{PREFIX}_message",
        "display": "メッセージ",
        "plural": "メッセージ",
        "description": "申請に紐づく会話スレッド",
        "columns": [
            {"logical": f"{PREFIX}_body", "type": "Memo", "display": "本文", "maxLength": 20000},
            {"logical": f"{PREFIX}_kind", "type": "Picklist", "display": "種別", "options": MESSAGE_KIND_OPTIONS},
        ],
    },
    {
        "logical": f"{PREFIX}_mention",
        "display": "メンション",
        "plural": "メンション",
        "description": "メッセージ内のメンション",
        "columns": [
            {"logical": f"{PREFIX}_isread", "type": "Boolean", "display": "既読", "true_label": "既読", "false_label": "未読"},
        ],
    },
    {
        "logical": f"{PREFIX}_participant",
        "display": "関係者",
        "plural": "関係者",
        "description": "申請ごとの関係者と役割",
        "columns": [
            {"logical": f"{PREFIX}_role", "type": "Picklist", "display": "役割", "options": PARTICIPANT_ROLE_OPTIONS},
            {"logical": f"{PREFIX}_addedat", "type": "DateTime", "display": "追加日時", "format": "DateAndTime"},
        ],
    },
    {
        "logical": f"{PREFIX}_decision",
        "display": "判断",
        "plural": "判断",
        "description": "申請に対する判断結果",
        "columns": [
            {"logical": f"{PREFIX}_rationale", "type": "Memo", "display": "判断理由", "maxLength": 20000},
            {"logical": f"{PREFIX}_decidedat", "type": "DateTime", "display": "判断日時", "format": "DateAndTime"},
        ],
    },
    {
        "logical": f"{PREFIX}_decisioncard",
        "display": "判断カード発行",
        "plural": "判断カード発行",
        "description": "Adaptive Card の発行・消費・再発行状態",
        "columns": [
            {"logical": f"{PREFIX}_cardinstanceid", "type": "String", "display": "カードインスタンスID", "maxLength": 200},
            {"logical": f"{PREFIX}_actoraadobjectid", "type": "String", "display": "実行者AADオブジェクトID", "maxLength": 100},
            {"logical": f"{PREFIX}_actorupn", "type": "String", "display": "実行者UPN", "maxLength": 320},
            {"logical": f"{PREFIX}_status", "type": "Picklist", "display": "状態", "options": DECISION_CARD_STATUS_OPTIONS},
            {"logical": f"{PREFIX}_issuedat", "type": "DateTime", "display": "発行日時", "format": "DateAndTime"},
            {"logical": f"{PREFIX}_consumedat", "type": "DateTime", "display": "消費日時", "format": "DateAndTime"},
            {"logical": f"{PREFIX}_supersededat", "type": "DateTime", "display": "失効日時", "format": "DateAndTime"},
        ],
    },
    {
        "logical": f"{PREFIX}_applicationresource",
        "display": "関連資料",
        "plural": "関連資料",
        "description": "申請に紐づく関連リンク",
        "columns": [
            {"logical": f"{PREFIX}_url", "type": "String", "display": "URL", "maxLength": 1000},
            {"logical": f"{PREFIX}_description", "type": "Memo", "display": "説明", "maxLength": 4000},
        ],
    },
]

# cascade_share=True を指定したリレーションは、関係者に申請が共有されたとき
# 子レコードも自動的に共有される（Cascade Share）。これにより関係者が他の関係者・
# 資料・コメント・判断・メンションを閲覧できる。
LOOKUPS = [
    {"schema": f"{PREFIX}_application_{PREFIX}_category", "referencing": f"{PREFIX}_application", "referenced": f"{PREFIX}_category", "lookup_attr": f"{PREFIX}_categoryid", "lookup_display": "カテゴリ"},
    {"schema": f"{PREFIX}_application_systemuser_decider", "referencing": f"{PREFIX}_application", "referenced": "systemuser", "lookup_attr": f"{PREFIX}_deciderid", "lookup_display": "判断者"},
    {"schema": f"{PREFIX}_message_{PREFIX}_application", "referencing": f"{PREFIX}_message", "referenced": f"{PREFIX}_application", "lookup_attr": f"{PREFIX}_applicationid", "lookup_display": "申請", "cascade_share": True},
    {"schema": f"{PREFIX}_message_{PREFIX}_message_parent", "referencing": f"{PREFIX}_message", "referenced": f"{PREFIX}_message", "lookup_attr": f"{PREFIX}_parentmessageid", "lookup_display": "親メッセージ"},
    {"schema": f"{PREFIX}_mention_{PREFIX}_message", "referencing": f"{PREFIX}_mention", "referenced": f"{PREFIX}_message", "lookup_attr": f"{PREFIX}_messageid", "lookup_display": "メッセージ", "cascade_share": True},
    {"schema": f"{PREFIX}_mention_systemuser_target", "referencing": f"{PREFIX}_mention", "referenced": "systemuser", "lookup_attr": f"{PREFIX}_targetuserid", "lookup_display": "対象ユーザー"},
    {"schema": f"{PREFIX}_participant_{PREFIX}_application", "referencing": f"{PREFIX}_participant", "referenced": f"{PREFIX}_application", "lookup_attr": f"{PREFIX}_applicationid", "lookup_display": "申請", "cascade_share": True},
    {"schema": f"{PREFIX}_participant_systemuser_user", "referencing": f"{PREFIX}_participant", "referenced": "systemuser", "lookup_attr": f"{PREFIX}_userid", "lookup_display": "ユーザー"},
    {"schema": f"{PREFIX}_participant_systemuser_addedby", "referencing": f"{PREFIX}_participant", "referenced": "systemuser", "lookup_attr": f"{PREFIX}_addedbyid", "lookup_display": "追加者"},
    {"schema": f"{PREFIX}_decision_{PREFIX}_application", "referencing": f"{PREFIX}_decision", "referenced": f"{PREFIX}_application", "lookup_attr": f"{PREFIX}_applicationid", "lookup_display": "申請", "cascade_share": True},
    {"schema": f"{PREFIX}_decision_systemuser_decider", "referencing": f"{PREFIX}_decision", "referenced": "systemuser", "lookup_attr": f"{PREFIX}_deciderid", "lookup_display": "判断者"},
    {"schema": f"{PREFIX}_decision_{PREFIX}_decisionoption", "referencing": f"{PREFIX}_decision", "referenced": f"{PREFIX}_decisionoption", "lookup_attr": f"{PREFIX}_decisionoptionid", "lookup_display": "判断結果"},
    {"schema": f"{PREFIX}_decisioncard_{PREFIX}_application", "referencing": f"{PREFIX}_decisioncard", "referenced": f"{PREFIX}_application", "lookup_attr": f"{PREFIX}_applicationid", "lookup_display": "申請", "cascade_share": True},
    {"schema": f"{PREFIX}_applicationresource_{PREFIX}_application", "referencing": f"{PREFIX}_applicationresource", "referenced": f"{PREFIX}_application", "lookup_attr": f"{PREFIX}_applicationid", "lookup_display": "申請", "cascade_share": True},
]


def ensure_publisher() -> str:
    print("\n=== Step 1: Publisher ===")
    pubs = api_get(f"publishers?$filter=customizationprefix eq '{PREFIX}'&$select=publisherid,friendlyname,uniquename")
    if pubs.get("value"):
        pub = pubs["value"][0]
        print(f"  Publisher exists: {pub.get('friendlyname')} ({pub.get('uniquename')})")
        return pub["publisherid"]

    print(f"  Creating publisher prefix '{PREFIX}'...")
    publisher_id = api_post("publishers", {
        "friendlyname": PUBLISHER_DISPLAY_NAME,
        "uniquename": PUBLISHER_UNIQUE_NAME,
        "customizationprefix": PREFIX,
        "customizationoptionvalueprefix": 10000,
    })
    save_env_value("PUBLISHER_UNIQUE_NAME", PUBLISHER_UNIQUE_NAME)
    save_env_value("PUBLISHER_DISPLAY_NAME", PUBLISHER_DISPLAY_NAME)
    print(f"  Publisher created: {PUBLISHER_DISPLAY_NAME}")
    return publisher_id or api_get(f"publishers?$filter=customizationprefix eq '{PREFIX}'&$select=publisherid")["value"][0]["publisherid"]


def ensure_solution() -> None:
    print("\n=== Step 2: Solution ===")
    existing = api_get(f"solutions?$filter=uniquename eq '{SOLUTION_NAME}'&$select=solutionid,friendlyname")
    if existing.get("value"):
        print(f"  Solution exists: {SOLUTION_NAME}")
        save_env_value("SOLUTION_DISPLAY_NAME", existing["value"][0].get("friendlyname", SOLUTION_DISPLAY_NAME))
        return

    publisher_id = ensure_publisher()
    print(f"  Creating solution '{SOLUTION_NAME}'...")
    api_post("solutions", {
        "uniquename": SOLUTION_NAME,
        "friendlyname": SOLUTION_DISPLAY_NAME,
        "version": "1.0.0.0",
        "publisherid@odata.bind": f"/publishers({publisher_id})",
    })
    save_env_value("SOLUTION_DISPLAY_NAME", SOLUTION_DISPLAY_NAME)
    print("  Solution created")


def table_exists(logical_name: str) -> bool:
    try:
        api_get(f"EntityDefinitions(LogicalName='{logical_name}')?$select=LogicalName")
        return True
    except Exception:
        return False


def column_exists(table: str, column: str) -> bool:
    try:
        api_get(f"EntityDefinitions(LogicalName='{table}')/Attributes(LogicalName='{column}')?$select=LogicalName")
        return True
    except Exception:
        return False


def column_body(column: dict) -> dict:
    body = {
        "SchemaName": column["logical"],
        "DisplayName": label(column["display"]),
        "RequiredLevel": {"Value": "None"},
    }
    col_type = column["type"]
    if col_type == "String":
        body.update({
            "@odata.type": "#Microsoft.Dynamics.CRM.StringAttributeMetadata",
            "FormatName": {"Value": "Text"},
            "MaxLength": column.get("maxLength", 200),
        })
    elif col_type == "Memo":
        body.update({
            "@odata.type": "#Microsoft.Dynamics.CRM.MemoAttributeMetadata",
            "Format": "Text",
            "MaxLength": column.get("maxLength", 2000),
        })
    elif col_type == "Integer":
        body.update({
            "@odata.type": "#Microsoft.Dynamics.CRM.IntegerAttributeMetadata",
            "MinValue": column.get("minValue", 0),
            "MaxValue": column.get("maxValue", 100000),
        })
    elif col_type == "DateTime":
        body.update({
            "@odata.type": "#Microsoft.Dynamics.CRM.DateTimeAttributeMetadata",
            "Format": column.get("format", "DateAndTime"),
        })
    elif col_type == "Picklist":
        body.update({
            "@odata.type": "#Microsoft.Dynamics.CRM.PicklistAttributeMetadata",
            "OptionSet": {
                "@odata.type": "#Microsoft.Dynamics.CRM.OptionSetMetadata",
                "IsGlobal": False,
                "OptionSetType": "Picklist",
                "Options": [{"Value": value, "Label": label(text)} for value, text in column["options"]],
            },
        })
    elif col_type == "Boolean":
        body.update({
            "@odata.type": "#Microsoft.Dynamics.CRM.BooleanAttributeMetadata",
            "OptionSet": {
                "@odata.type": "#Microsoft.Dynamics.CRM.BooleanOptionSetMetadata",
                "TrueOption": {"Value": 1, "Label": label(column.get("true_label", "はい"))},
                "FalseOption": {"Value": 0, "Label": label(column.get("false_label", "いいえ"))},
            },
        })
    elif col_type == "File":
        body.update({
            "@odata.type": "#Microsoft.Dynamics.CRM.FileAttributeMetadata",
            "MaxSizeInKB": column.get("maxSizeInKB", 32768),
        })
    else:
        raise ValueError(f"Unsupported column type: {col_type}")
    return body


def create_tables() -> None:
    print("\n=== Step 3: Tables and columns ===")
    for table in TABLES:
        logical = table["logical"]
        if not table_exists(logical):
            def create_table(t=table):
                body = {
                    "@odata.type": "#Microsoft.Dynamics.CRM.EntityMetadata",
                    "SchemaName": t["logical"],
                    "DisplayName": label(t["display"]),
                    "DisplayCollectionName": label(t["plural"]),
                    "Description": label(t["description"]),
                    "OwnershipType": "UserOwned",
                    "IsActivity": False,
                    "HasActivities": False,
                    "HasNotes": False,
                    "HasFeedback": False,
                    "PrimaryNameAttribute": f"{PREFIX}_name",
                    "Attributes": [
                        {
                            "@odata.type": "#Microsoft.Dynamics.CRM.StringAttributeMetadata",
                            "SchemaName": f"{PREFIX}_name",
                            "DisplayName": label("名前"),
                            "IsPrimaryName": True,
                            "RequiredLevel": {"Value": "ApplicationRequired"},
                            "FormatName": {"Value": "Text"},
                            "MaxLength": 200,
                        }
                    ],
                }
                api_post("EntityDefinitions", body, solution=SOLUTION_NAME)
                print(f"  Created table: {logical}")

            retry_metadata(create_table, f"table {logical}")
            time.sleep(8)
        else:
            print(f"  Table exists: {logical}")

        for column in table.get("columns", []):
            if column_exists(logical, column["logical"]):
                continue

            def add_column(t=logical, c=column):
                api_post(
                    f"EntityDefinitions(LogicalName='{t}')/Attributes",
                    column_body(c),
                    solution=SOLUTION_NAME,
                )
                print(f"    Added column: {c['logical']}")

            retry_metadata(add_column, f"column {logical}.{column['logical']}")
            time.sleep(3)


def lookup_exists(referencing: str, lookup_attr: str) -> bool:
    return navprop_by_lookup_attr(referencing, lookup_attr) is not None


def create_lookups() -> None:
    print("\n=== Step 4: Lookup relationships ===")
    for lookup in LOOKUPS:
        if lookup_exists(lookup["referencing"], lookup["lookup_attr"]):
            print(f"  Lookup exists: {lookup['lookup_attr']}")
            continue

        def create_lookup(l=lookup):
            body = {
                "@odata.type": "#Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata",
                "SchemaName": l["schema"],
                "ReferencedEntity": l["referenced"],
                "ReferencingEntity": l["referencing"],
                "Lookup": {
                    "SchemaName": l["lookup_attr"],
                    "DisplayName": label(l["lookup_display"]),
                    "RequiredLevel": {"Value": "None"},
                },
            }
            if l.get("cascade_share"):
                body["CascadeConfiguration"] = {
                    "Assign": "NoCascade",
                    "Delete": "RemoveLink",
                    "Merge": "NoCascade",
                    "Reparent": "NoCascade",
                    "Share": "Cascade",
                    "Unshare": "Cascade",
                    "RollupView": "NoCascade",
                }
            api_post("RelationshipDefinitions", body, solution=SOLUTION_NAME)
            print(f"  Created lookup: {l['lookup_attr']}")

        retry_metadata(create_lookup, f"lookup {lookup['schema']}")
        time.sleep(5)


def publish_all() -> None:
    print("\n=== Step 5: Publish ===")
    url = f"{DATAVERSE_URL}/api/data/v9.2/PublishAllXml"
    try:
        response = get_session().post(url, json={}, timeout=180)
        if not response.ok:
            print(response.text, file=sys.stderr)
        response.raise_for_status()
        print("  Published")
    except requests.exceptions.Timeout:
        print("  PublishAllXml timed out after 180 seconds; continuing with verification. Rerun the script later if metadata is not visible in Maker Portal.")


def ensure_solution_membership() -> None:
    print("\n=== Step 6: Solution membership ===")
    solution = api_get(f"solutions?$filter=uniquename eq '{SOLUTION_NAME}'&$select=solutionid")
    solution_id = solution["value"][0]["solutionid"]
    components = api_get(
        f"solutioncomponents?$filter=_solutionid_value eq {solution_id} and componenttype eq 1&$select=objectid"
    )
    existing_ids = {component["objectid"] for component in components.get("value", [])}
    for table in TABLES:
        logical = table["logical"]
        metadata_id = api_get(f"EntityDefinitions(LogicalName='{logical}')?$select=MetadataId")["MetadataId"]
        if metadata_id in existing_ids:
            print(f"  In solution: {logical}")
            continue
        api_post("AddSolutionComponent", {
            "ComponentId": metadata_id,
            "ComponentType": 1,
            "SolutionUniqueName": SOLUTION_NAME,
            "AddRequiredComponents": False,
            "DoNotIncludeSubcomponents": False,
        })
        print(f"  Added to solution: {logical}")


def find_by_name(entity_set_name: str, name: str) -> dict | None:
    rows = api_get(f"{entity_set_name}?$top=100").get("value", [])
    for row in rows:
        if row.get(f"{PREFIX}_name") == name:
            return row
    return None


def ensure_row(entity_set_name: str, name: str, body: dict) -> str:
    existing = find_by_name(entity_set_name, name)
    id_field = f"{entity_set_name[:-1]}id"
    if existing:
        for key, value in existing.items():
            if key.endswith("id"):
                return value
        if id_field in existing:
            return existing[id_field]
    created_id = api_post(entity_set_name, {f"{PREFIX}_name": name, **body})
    if not created_id:
        existing = find_by_name(entity_set_name, name)
        if existing:
            for key, value in existing.items():
                if key.endswith("id"):
                    return value
    return created_id or ""


def current_user_id() -> str:
    who = api_get("WhoAmI")
    return who["UserId"]


def create_demo_data() -> None:
    print("\n=== Step 7: Demo data ===")
    user_id = current_user_id()
    systemuser_set = entity_set("systemuser")
    category_set = entity_set(f"{PREFIX}_category")
    option_set = entity_set(f"{PREFIX}_decisionoption")
    application_set = entity_set(f"{PREFIX}_application")
    participant_set = entity_set(f"{PREFIX}_participant")
    message_set = entity_set(f"{PREFIX}_message")
    mention_set = entity_set(f"{PREFIX}_mention")
    decision_set = entity_set(f"{PREFIX}_decision")
    resource_set = entity_set(f"{PREFIX}_applicationresource")

    categories = [
        ("顧客案件", "顧客に関わる見積、契約、提案、例外対応など", "背景 / 顧客影響 / 判断してほしいこと / 期限 / 関連資料"),
        ("部内案件", "部内で判断が必要な施策や運用変更", "目的 / 対象範囲 / 選択肢 / 推奨案 / 懸念点"),
        ("課内案件", "課内の業務改善や進め方の判断", "現状 / 課題 / 提案 / 必要な判断 / 希望期限"),
        ("他部署案件", "他部署との調整や合意が必要な案件", "関係部署 / 依頼事項 / 影響範囲 / 期限 / 未解決事項"),
        ("事務処理", "定型的な承認・確認が必要な事務処理", "処理内容 / 根拠 / 期限 / 添付資料"),
    ]
    category_ids: dict[str, str] = {}
    for index, (name, description, template) in enumerate(categories, start=1):
        category_ids[name] = ensure_row(category_set, name, {
            f"{PREFIX}_description": description,
            f"{PREFIX}_template": template,
            f"{PREFIX}_sortorder": index,
        })
        print(f"  Category: {name}")

    decisions = [
        ("承認", "申請内容を承認する", 1),
        ("却下", "申請内容を却下する", 2),
        ("差し戻し", "追加情報や修正を求めて差し戻す", 3),
    ]
    decision_option_ids: dict[str, str] = {}
    for name, description, sort_order in decisions:
        decision_option_ids[name] = ensure_row(option_set, name, {
            f"{PREFIX}_description": description,
            f"{PREFIX}_sortorder": sort_order,
        })
        print(f"  Decision option: {name}")

    app_category_nav = navprop_by_lookup_attr(f"{PREFIX}_application", f"{PREFIX}_categoryid")
    app_decider_nav = navprop_by_lookup_attr(f"{PREFIX}_application", f"{PREFIX}_deciderid")
    participant_app_nav = navprop_by_lookup_attr(f"{PREFIX}_participant", f"{PREFIX}_applicationid")
    participant_user_nav = navprop_by_lookup_attr(f"{PREFIX}_participant", f"{PREFIX}_userid")
    participant_addedby_nav = navprop_by_lookup_attr(f"{PREFIX}_participant", f"{PREFIX}_addedbyid")
    message_app_nav = navprop_by_lookup_attr(f"{PREFIX}_message", f"{PREFIX}_applicationid")
    mention_message_nav = navprop_by_lookup_attr(f"{PREFIX}_mention", f"{PREFIX}_messageid")
    mention_target_nav = navprop_by_lookup_attr(f"{PREFIX}_mention", f"{PREFIX}_targetuserid")
    decision_app_nav = navprop_by_lookup_attr(f"{PREFIX}_decision", f"{PREFIX}_applicationid")
    decision_decider_nav = navprop_by_lookup_attr(f"{PREFIX}_decision", f"{PREFIX}_deciderid")
    decision_option_nav = navprop_by_lookup_attr(f"{PREFIX}_decision", f"{PREFIX}_decisionoptionid")
    resource_app_nav = navprop_by_lookup_attr(f"{PREFIX}_applicationresource", f"{PREFIX}_applicationid")

    now = datetime.now(UTC)
    applications = [
        {
            "name": "顧客案件: 見積条件の例外承認",
            "category": "顧客案件",
            "body": "重要顧客向けの提案で、通常条件から外れる支払条件を提示する必要があります。判断者には、収益影響と顧客関係の観点から承認可否を判断してほしいです。",
            "stage": 100000001,
            "due": (now + timedelta(days=5)).date().isoformat(),
        },
        {
            "name": "部内案件: ナレッジ共有会の定例化",
            "category": "部内案件",
            "body": "部内の暗黙知を減らすため、月1回のナレッジ共有会を定例化したいです。業務時間の確保と優先度について判断をお願いします。",
            "stage": 100000001,
            "due": (now + timedelta(days=10)).date().isoformat(),
        },
    ]

    for app in applications:
        body = {
            f"{PREFIX}_body": app["body"],
            f"{PREFIX}_stage": app["stage"],
            f"{PREFIX}_duedate": app["due"],
            f"{PREFIX}_submittedat": now.isoformat().replace("+00:00", "Z"),
            f"{PREFIX}_aiapplicationsummary": "申請の目的、背景、依頼内容を判断者向けに要約します。",
            f"{PREFIX}_aiconversationsummary": "提出時点では会話履歴はありません。",
            f"{PREFIX}_aidecisionoptiontext": "承認",
            f"{PREFIX}_aidecisioncomment": "デモ用のAI判断コメントです。実運用ではAI判断生成フローで更新されます。",
            f"{PREFIX}_aidecisionbasis": json.dumps({"risks": ["デモデータです。"], "similarCases": []}, ensure_ascii=False),
            f"{PREFIX}_aidecisionupdatedat": now.isoformat().replace("+00:00", "Z"),
        }
        if app_category_nav:
            body[f"{app_category_nav}@odata.bind"] = f"/{category_set}({category_ids[app['category']]})"
        if app_decider_nav:
            body[f"{app_decider_nav}@odata.bind"] = f"/{systemuser_set}({user_id})"
        app_id = ensure_row(application_set, app["name"], body)
        print(f"  Application: {app['name']}")

        if participant_app_nav and participant_user_nav:
            participant_body = {
                f"{PREFIX}_role": 100000000,
                f"{PREFIX}_addedat": now.isoformat().replace("+00:00", "Z"),
                f"{participant_app_nav}@odata.bind": f"/{application_set}({app_id})",
                f"{participant_user_nav}@odata.bind": f"/{systemuser_set}({user_id})",
            }
            if participant_addedby_nav:
                participant_body[f"{participant_addedby_nav}@odata.bind"] = f"/{systemuser_set}({user_id})"
            ensure_row(participant_set, f"{app['name']} - 申請者", participant_body)

        if message_app_nav:
            message_id = ensure_row(message_set, f"{app['name']} - 初期コメント", {
                f"{PREFIX}_body": "申請を作成しました。関連資料もあわせて確認してください。",
                f"{PREFIX}_kind": 100000000,
                f"{message_app_nav}@odata.bind": f"/{application_set}({app_id})",
            })
            if mention_message_nav and mention_target_nav:
                ensure_row(mention_set, f"{app['name']} - 判断者メンション", {
                    f"{PREFIX}_isread": False,
                    f"{mention_message_nav}@odata.bind": f"/{message_set}({message_id})",
                    f"{mention_target_nav}@odata.bind": f"/{systemuser_set}({user_id})",
                })

        if app["name"].startswith("顧客案件") and decision_app_nav and decision_decider_nav and decision_option_nav:
            ensure_row(decision_set, f"{app['name']} - 承認判断", {
                f"{PREFIX}_rationale": "デモ判断です。収益影響は限定的で、顧客関係の維持を優先できると判断しました。",
                f"{PREFIX}_decidedat": now.isoformat().replace("+00:00", "Z"),
                f"{decision_app_nav}@odata.bind": f"/{application_set}({app_id})",
                f"{decision_decider_nav}@odata.bind": f"/{systemuser_set}({user_id})",
                f"{decision_option_nav}@odata.bind": f"/{option_set}({decision_option_ids['承認']})",
            })

        if resource_app_nav:
            ensure_row(resource_set, f"{app['name']} - 関連資料リンク", {
                f"{PREFIX}_url": "https://example.com/decisionflow/sample-resource",
                f"{PREFIX}_description": "デモ用の関連資料リンクです。実運用ではSharePointやTeamsのリンクを登録します。",
                f"{resource_app_nav}@odata.bind": f"/{application_set}({app_id})",
            })


def verify_tables() -> None:
    print("\n=== Step 8: Verification ===")
    for table in TABLES:
        logical = table["logical"]
        set_name = entity_set(logical)
        rows = api_get(f"{set_name}?$top=1&$select={PREFIX}_name").get("value", [])
        print(f"  OK: {logical} ({set_name}) rows_sample={len(rows)}")


def main() -> int:
    print("=" * 72)
    print("DecisionFlow Dataverse setup")
    print("=" * 72)
    print(f"Environment: {DATAVERSE_URL}")
    print(f"Solution: {SOLUTION_NAME}")
    print(f"Prefix: {PREFIX}")

    ensure_publisher()
    ensure_solution()
    create_tables()
    create_lookups()
    publish_all()
    ensure_solution_membership()
    create_demo_data()
    verify_tables()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}")
        traceback.print_exc()
        raise SystemExit(1)
