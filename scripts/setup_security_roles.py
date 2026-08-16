import os
import sys
import time
import traceback
from typing import Any

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auth_helper import api_get, api_patch, api_post  # noqa: E402

load_dotenv()

SOLUTION_NAME = os.getenv("SOLUTION_NAME", "").strip()
PREFIX = os.getenv("PUBLISHER_PREFIX", "").strip()
DECIDER_GROUP_NAME = os.getenv("DECIDER_GROUP_NAME", "DecisionFlow-Deciders").strip()

if not SOLUTION_NAME or not PREFIX:
    raise SystemExit("SOLUTION_NAME and PUBLISHER_PREFIX must be set in .env")

TABLE_VERBS = ["Create", "Read", "Write", "Delete", "Append", "AppendTo", "Assign", "Share"]

# ReplacePrivilegesRole / AddPrivilegesRole の1回あたりの上限。
# 11テーブル×8動詞=88 が上限なので、実際には常に1バッチで収まる。
PRIVILEGE_BATCH_SIZE = 100

TABLE_LOGICAL_NAMES = [
    f"{PREFIX}_category",
    f"{PREFIX}_decisionoption",
    f"{PREFIX}_application",
    f"{PREFIX}_message",
    f"{PREFIX}_mention",
    f"{PREFIX}_participant",
    f"{PREFIX}_decision",
    f"{PREFIX}_decisioncard",
    f"{PREFIX}_applicationresource",
    f"{PREFIX}_delegationrequest",
    f"{PREFIX}_delegationhistory",
]


def table_defaults(**overrides: str | None) -> dict[str, str | None]:
    values: dict[str, str | None] = {verb: None for verb in TABLE_VERBS}
    values.update(overrides)
    return values


MASTER_READ_ONLY = table_defaults(Read="Global", AppendTo="Global")

APPLICANT_OWNED = table_defaults(
    Create="Basic",
    Read="Basic",
    Write="Basic",
    Delete="Basic",
    Append="Basic",
    AppendTo="Basic",
    Share="Basic",
)

# 関係者追加時にメンションを target ユーザー所有として作成するため、Assign 権限が必要。
MENTION_WRITABLE = table_defaults(
    Create="Basic",
    Read="Basic",
    Write="Basic",
    Append="Basic",
    AppendTo="Basic",
    Share="Basic",
    Assign="Basic",
)

APPLICANT_READ_OWNED = table_defaults(Read="Basic", AppendTo="Basic")

NO_ACCESS = table_defaults()

DELEGATION_REQUEST_CREATE_ONLY = table_defaults(
    Create="Basic",
    Read="Basic",
    Append="Basic",
)

DELEGATION_HISTORY_READ_ONLY = table_defaults(Read="Global")

DECIDER_CONTEXT_READ = table_defaults(Read="Global", AppendTo="Global")

DECIDER_CATEGORY_REGULATION_WRITE = table_defaults(
    Read="Global",
    Write="Global",
    AppendTo="Global",
)

DECIDER_OWNED_WRITE = table_defaults(
    Create="Basic",
    Read="Basic",
    Write="Basic",
    Append="Basic",
    AppendTo="Basic",
    Share="Basic",
)

DECISION_CARD_ASSIGNED_ACTOR = table_defaults(
    Create="Basic",
    Read="Basic",
    Write="Basic",
    Append="Basic",
    AppendTo="Basic",
    Share="Basic",
)

ADMIN_FULL = table_defaults(**{verb: "Global" for verb in TABLE_VERBS})

ROLE_DEFINITIONS = [
    {
        "name": "ds_Applicant",
        "description": "DecisionFlow applicant role. Users can create and update their own applications and related conversation records.",
        "table_privileges": {
            "*": APPLICANT_OWNED,
            f"{PREFIX}_category": MASTER_READ_ONLY,
            f"{PREFIX}_decisionoption": MASTER_READ_ONLY,
            f"{PREFIX}_decision": APPLICANT_READ_OWNED,
            f"{PREFIX}_decisioncard": APPLICANT_READ_OWNED,
            f"{PREFIX}_mention": MENTION_WRITABLE,
            f"{PREFIX}_delegationrequest": NO_ACCESS,
            f"{PREFIX}_delegationhistory": NO_ACCESS,
        },
    },
    {
        "name": "ds_Decider",
        "description": "DecisionFlow decider role. Deciders can read all decision context and create their own decisions and discussion records.",
        "table_privileges": {
            "*": DECIDER_CONTEXT_READ,
            f"{PREFIX}_category": DECIDER_CATEGORY_REGULATION_WRITE,
            f"{PREFIX}_decisionoption": MASTER_READ_ONLY,
            f"{PREFIX}_message": DECIDER_OWNED_WRITE | {"Read": "Global"},
            f"{PREFIX}_mention": MENTION_WRITABLE | {"Read": "Global"},
            f"{PREFIX}_participant": table_defaults(Create="Basic", Read="Global", Write="Basic", Delete="Basic", Append="Basic", AppendTo="Global", Share="Basic"),
            f"{PREFIX}_decision": DECIDER_OWNED_WRITE | {"Read": "Global"},
            f"{PREFIX}_decisioncard": DECISION_CARD_ASSIGNED_ACTOR,
            f"{PREFIX}_delegationrequest": DELEGATION_REQUEST_CREATE_ONLY,
            f"{PREFIX}_delegationhistory": DELEGATION_HISTORY_READ_ONLY,
        },
    },
    {
        "name": "ds_Admin",
        "description": "DecisionFlow administrator role. Full access to all DecisionFlow tables.",
        "table_privileges": {"*": ADMIN_FULL},
    },
]


def role_by_name(name: str) -> dict[str, Any]:
    for role in ROLE_DEFINITIONS:
        if role["name"] == name:
            return role
    raise KeyError(name)


def privileges_for_table(role_def: dict[str, Any], table_logical_name: str) -> dict[str, str | None]:
    table_privileges = role_def.get("table_privileges", {})
    values = dict(table_privileges.get("*", table_defaults()))
    values.update(table_privileges.get(table_logical_name, {}))
    return values


def get_root_business_unit() -> str:
    print("\n=== Step 1: Root business unit ===")
    result = api_get("businessunits?$filter=parentbusinessunitid eq null&$select=businessunitid,name")
    values = result.get("value", [])
    if not values:
        raise RuntimeError("Root business unit was not found")
    root_bu = values[0]
    print(f"  Root BU: {root_bu.get('name')}")
    return root_bu["businessunitid"]


def get_solution_id() -> str:
    result = api_get(f"solutions?$filter=uniquename eq '{SOLUTION_NAME}'&$select=solutionid")
    values = result.get("value", [])
    if not values:
        raise RuntimeError(f"Solution '{SOLUTION_NAME}' was not found")
    return values[0]["solutionid"]


def get_table_metadata() -> list[dict[str, Any]]:
    print("\n=== Step 2: DecisionFlow table metadata ===")
    tables: list[dict[str, Any]] = []
    for logical_name in TABLE_LOGICAL_NAMES:
        meta = api_get(
            f"EntityDefinitions(LogicalName='{logical_name}')?"
            "$select=LogicalName,SchemaName,MetadataId"
        )
        tables.append(
            {
                "logical_name": meta["LogicalName"],
                "schema_name": meta["SchemaName"],
                "metadata_id": meta["MetadataId"],
            }
        )
        print(f"  {meta['LogicalName']} ({meta['SchemaName']})")
    return tables


def find_privilege(name: str) -> str | None:
    escaped = name.replace("'", "''")
    result = api_get(f"privileges?$filter=name eq '{escaped}'&$select=privilegeid,name")
    values = result.get("value", [])
    if not values:
        return None
    return values[0]["privilegeid"]


def get_table_privileges(tables: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    print("\n=== Step 3: Table privilege IDs ===")
    privilege_map: dict[str, dict[str, str]] = {}
    for table in tables:
        logical_name = table["logical_name"]
        schema_name = table["schema_name"]
        privilege_map[logical_name] = {}
        for verb in TABLE_VERBS:
            privilege_id = find_privilege(f"prv{verb}{schema_name}") or find_privilege(f"prv{verb}{logical_name}")
            if privilege_id:
                privilege_map[logical_name][verb] = privilege_id
        print(f"  {logical_name}: {len(privilege_map[logical_name])}/{len(TABLE_VERBS)}")
    return privilege_map


def ensure_role(role_def: dict[str, Any], root_bu_id: str) -> str:
    role_name = role_def["name"]
    escaped = role_name.replace("'", "''")
    existing = api_get(
        f"roles?$filter=name eq '{escaped}' and _businessunitid_value eq {root_bu_id}"
        "&$select=roleid,name,description"
    )
    body = {
        "name": role_name,
        "description": role_def.get("description", ""),
        "businessunitid@odata.bind": f"/businessunits({root_bu_id})",
    }
    if existing.get("value"):
        role_id = existing["value"][0]["roleid"]
        api_patch(f"roles({role_id})", {"description": role_def.get("description", "")})
        print(f"  Role exists: {role_name}")
        return role_id

    role_id = api_post("roles", body, solution=SOLUTION_NAME)
    if not role_id:
        refetch = api_get(
            f"roles?$filter=name eq '{escaped}' and _businessunitid_value eq {root_bu_id}"
            "&$select=roleid"
        )
        if not refetch.get("value"):
            raise RuntimeError(f"Role '{role_name}' was created but could not be refetched")
        role_id = refetch["value"][0]["roleid"]
    time.sleep(2)
    print(f"  Created role: {role_name}")
    return role_id


def build_role_privileges(
    role_def: dict[str, Any],
    tables: list[dict[str, Any]],
    privilege_map: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """
    ロールは **DecisionFlow の11テーブル分だけ**を持つ。基盤権限は取り込まない。

    以前はこの環境の `Basic User` を丸ごとコピーして土台にしていた。そのせいでロールが
    1634件に膨れ、**移送元のベースラインを他テナントへ持ち込む**状態になっていた。
    深度の可否は環境で違うことがあり（`prvDeleteUserSettings` は MinoruEnv では Basic 可、
    MinoDev2 では不可）、2026-08-12 のソリューション import が実際にこれで失敗した。

    利用者は `Basic User` を別途保有して基盤権限を得る（Dataverse のロールは加算式）。
    **このロールだけを割り当てても、アプリは動かない。** 詳細は
    開発メモ（非公開）「ALM の実測ブロッカー」と、その下の境界表。
    """
    privileges: dict[str, dict[str, str]] = {}
    unresolved: list[str] = []

    for table in tables:
        logical_name = table["logical_name"]
        table_privileges = privileges_for_table(role_def, logical_name)
        table_privilege_ids = privilege_map.get(logical_name, {})
        for verb in TABLE_VERBS:
            depth = table_privileges.get(verb)
            if depth is None:
                # 深度なし = このロールに与えない。土台が空なので消す対象は存在しない。
                continue
            privilege_id = table_privilege_ids.get(verb)
            if not privilege_id:
                unresolved.append(f"prv{verb}{logical_name}")
                continue
            privileges[privilege_id] = {"PrivilegeId": privilege_id, "Depth": depth}

    if unresolved:
        # 黙って飛ばすと ReplacePrivilegesRole は全置換なので、**権限が縮んだロールが
        # エラーなしで出来上がる**。テーブル発行直後のメタデータ遅延などで privilege_map が
        # 欠けたまま流れる経路があるため、ここで止める。
        raise RuntimeError(
            f"{role_def['name']}: 付与すべき権限の privilege ID を解決できなかった: "
            + ", ".join(sorted(unresolved))
        )

    return list(privileges.values())


def set_role_privileges(role_id: str, role_def: dict[str, Any], privileges: list[dict[str, str]]) -> None:
    """
    先頭バッチだけ `ReplacePrivilegesRole`、以降は `AddPrivilegesRole`。
    **1バッチに収まる限り、途中失敗で「一部だけ入ったロール」は生じない。**
    ベースラインを取り込まなくなったので11テーブル分だけになり、収まる前提。
    収まらなくなったらテストが落ちる（`tests/test_security_roles.py`）。
    """
    if not privileges:
        # 空だと range() が1度も回らず、API を呼ばないまま「成功」で次のロールへ進む。
        # 既存ロールは古い権限（旧ベースライン含む）を保ったまま残るので、黙って通さない。
        raise RuntimeError(
            f"{role_def['name']}: 付与する権限が0件。privilege ID の解決に失敗している可能性がある"
        )

    print(f"\n  Setting privileges: {role_def['name']} ({len(privileges)} total)")
    batch_size = PRIVILEGE_BATCH_SIZE
    for index in range(0, len(privileges), batch_size):
        batch = privileges[index : index + batch_size]
        action = "ReplacePrivilegesRole" if index == 0 else "AddPrivilegesRole"
        api_post(
            f"roles({role_id})/Microsoft.Dynamics.CRM.{action}",
            {"Privileges": batch},
        )
        print(f"    Batch {index // batch_size + 1}: {action} {len(batch)} privileges")


def ensure_solution_membership(role_ids: list[tuple[str, str]]) -> None:
    print("\n=== Step 5: Solution membership ===")
    for role_id, role_name in role_ids:
        try:
            api_post(
                "AddSolutionComponent",
                {
                    "ComponentId": role_id,
                    "ComponentType": 20,
                    "SolutionUniqueName": SOLUTION_NAME,
                    "AddRequiredComponents": False,
                    "DoNotIncludeSubcomponents": False,
                },
            )
            print(f"  Added/verified: {role_name}")
        except requests.HTTPError as exc:
            text = exc.response.text if exc.response is not None else str(exc)
            if "already" in text.lower() or "0x8004f016" in text:
                print(f"  Already in solution: {role_name}")
            else:
                raise


def verify_solution_membership(role_ids: list[tuple[str, str]]) -> None:
    solution_id = get_solution_id()
    components = api_get(
        f"solutioncomponents?$filter=_solutionid_value eq {solution_id} and componenttype eq 20"
        "&$select=objectid"
    )
    object_ids = {component["objectid"].lower() for component in components.get("value", [])}
    for role_id, role_name in role_ids:
        status = "OK" if role_id.lower() in object_ids else "MISSING"
        print(f"  {status}: {role_name}")


def decider_group_team_manual_steps() -> list[str]:
    return [
        f"Create or confirm the Microsoft 365 group / Teams team named '{DECIDER_GROUP_NAME}'.",
        "Open Power Platform admin center > Environments > this environment > Settings > Users + permissions > Teams.",
        f"Create a Dataverse group team linked to the '{DECIDER_GROUP_NAME}' Microsoft 365 group.",
        "Use membership type 'Members and guests' unless your tenant policy requires a narrower setting.",
        "Open the created Dataverse group team and assign the 'ds_Decider' security role.",
        "Add decider users to the Microsoft 365 group / Teams team; Dataverse membership sync will handle access.",
    ]


def print_decider_group_team_manual_steps(role_ids: list[tuple[str, str]]) -> None:
    print("\n=== Step 6: Decider group team ===")
    decider_role_id = next((role_id for role_id, role_name in role_ids if role_name == "ds_Decider"), "")
    if not decider_role_id:
        print("  Skipped: ds_Decider role ID was not found")
        return
    print("  Manual step. This script does not create or link Microsoft 365 / Dataverse group teams.")
    print(f"  ds_Decider role ID: {decider_role_id}")
    for index, step in enumerate(decider_group_team_manual_steps(), start=1):
        print(f"  {index}. {step}")


def main() -> int:
    print("=" * 72)
    print("DecisionFlow security role setup")
    print("=" * 72)
    print(f"Solution: {SOLUTION_NAME}")
    print(f"Prefix: {PREFIX}")

    root_bu_id = get_root_business_unit()
    tables = get_table_metadata()
    privilege_map = get_table_privileges(tables)

    print("\n=== Step 4: Roles and privileges ===")
    print("  基盤権限は取り込まない。利用者は Basic User を別途保有すること。")
    role_ids: list[tuple[str, str]] = []
    for role_def in ROLE_DEFINITIONS:
        role_id = ensure_role(role_def, root_bu_id)
        role_privileges = build_role_privileges(role_def, tables, privilege_map)
        set_role_privileges(role_id, role_def, role_privileges)
        role_ids.append((role_id, role_def["name"]))

    ensure_solution_membership(role_ids)
    print("\n=== Step 5b: Solution membership verification ===")
    verify_solution_membership(role_ids)
    print_decider_group_team_manual_steps(role_ids)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}")
        traceback.print_exc()
        raise SystemExit(1)
