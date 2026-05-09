"""
ds_application から子テーブル(ds_participant, ds_message, ds_decision, ds_applicationresource)
へのリレーションシップで Share カスケードを Cascade に変更する。
これにより、申請レコードが共有されたとき子レコードも自動的に共有される。
ds_mention は ds_message 経由で連鎖する。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL, api_get, get_session  # noqa: E402

PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")
SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")

# (schema_name, 説明)
RELATIONSHIPS = [
    (f"{PREFIX}_participant_{PREFIX}_application", "ds_application -> ds_participant"),
    (f"{PREFIX}_message_{PREFIX}_application", "ds_application -> ds_message"),
    (f"{PREFIX}_decision_{PREFIX}_application", "ds_application -> ds_decision"),
    (f"{PREFIX}_applicationresource_{PREFIX}_application", "ds_application -> ds_applicationresource"),
    (f"{PREFIX}_mention_{PREFIX}_message", "ds_message -> ds_mention (連鎖用)"),
]


def get_relationship(schema: str) -> dict:
    return api_get(f"RelationshipDefinitions(SchemaName='{schema}')")


def update_cascade_share(schema: str) -> None:
    rel = get_relationship(schema)
    body = {k: v for k, v in rel.items() if not k.startswith("@odata.")}
    body["@odata.type"] = "#Microsoft.Dynamics.CRM.OneToManyRelationshipMetadata"
    cascade = body.get("CascadeConfiguration") or {}
    cascade["Share"] = "Cascade"
    cascade["Unshare"] = "Cascade"
    body["CascadeConfiguration"] = cascade

    url = f"{DATAVERSE_URL}/api/data/v9.2/RelationshipDefinitions(SchemaName='{schema}')"
    session = get_session()
    session.headers["MSCRM.MergeLabels"] = "true"
    resp = session.put(url, json=body)
    if not resp.ok:
        raise RuntimeError(f"{resp.status_code}: {resp.text[:500]}")


def main() -> None:
    print("=" * 64)
    print("Migrate: cascade Share to child relationships")
    print("=" * 64)

    for schema, desc in RELATIONSHIPS:
        try:
            rel = get_relationship(schema)
            current = (rel.get("CascadeConfiguration") or {}).get("Share")
            print(f"\n  {desc}")
            print(f"    schema: {schema}")
            print(f"    現在の Share: {current}")
            if current == "Cascade":
                print("    既に Cascade です。スキップ")
                continue
            update_cascade_share(schema)
            print("    ✅ Share=Cascade, Unshare=Cascade に更新しました")
        except Exception as exc:
            print(f"  ⚠️ {schema} の更新に失敗: {exc}")

    print("\n✅ 完了")
    print("\n注意: 既に作成済みの申請レコードと既に追加済みの関係者については")
    print("Grant フローを再実行する必要があります。Code Apps で関係者を一度削除→再追加するか")
    print("Power Automate UI で Participant_OnCreated_GrantAccess を手動実行してください。")


if __name__ == "__main__":
    main()
