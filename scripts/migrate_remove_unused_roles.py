"""
ds_participant.ds_role Choice から CoDecider(100000002), Observer(100000004) を削除する。
既存レコードがあれば Contributor(100000003 = 関係者) に変換してから削除する。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import api_get, api_patch, api_post  # noqa: E402

PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")
SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")

ROLE_ATTR = f"{PREFIX}_role"
ROLE_TABLE = f"{PREFIX}_participant"
ENTITY_SET = f"{PREFIX}_participants"
ID_ATTR = f"{PREFIX}_participantid"
CONTRIBUTOR_VALUE = 100000003
TARGET_VALUES = [100000002, 100000004]  # CoDecider, Observer
TARGET_LABELS = {100000002: "CoDecider", 100000004: "Observer"}


def find_records(value: int) -> list[dict]:
    result = api_get(
        f"{ENTITY_SET}?$select={ID_ATTR}&$filter={ROLE_ATTR} eq {value}"
    )
    return result.get("value", [])


def convert_to_contributor(records: list[dict]) -> None:
    for record in records:
        record_id = record[ID_ATTR]
        api_patch(f"{ENTITY_SET}({record_id})", {ROLE_ATTR: CONTRIBUTOR_VALUE})


def delete_choice_option(value: int) -> None:
    body = {
        "AttributeLogicalName": ROLE_ATTR,
        "EntityLogicalName": ROLE_TABLE,
        "Value": value,
        "SolutionUniqueName": SOLUTION_NAME,
    }
    api_post("DeleteOptionValue", body, solution=SOLUTION_NAME)


def main() -> None:
    print("=" * 64)
    print(f"Remove unused {ROLE_ATTR} Choice options")
    print("=" * 64)

    print("\n=== Step 1: 既存レコードを Contributor に変換 ===")
    for value in TARGET_VALUES:
        label = TARGET_LABELS[value]
        records = find_records(value)
        if not records:
            print(f"  {label}({value}): 該当レコードなし")
            continue
        print(f"  {label}({value}): {len(records)} 件を Contributor({CONTRIBUTOR_VALUE}) に変換")
        convert_to_contributor(records)
        print(f"  ✅ {label}: 変換完了")

    print("\n=== Step 2: Choice 値削除 ===")
    for value in TARGET_VALUES:
        try:
            delete_choice_option(value)
            print(f"  ✅ {TARGET_LABELS[value]}({value}) を削除しました")
        except Exception as exc:
            print(f"  ⚠️ {TARGET_LABELS[value]}({value}) の削除に失敗: {exc}")

    print("\n✅ 完了")


if __name__ == "__main__":
    main()
