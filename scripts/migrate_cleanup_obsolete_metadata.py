import argparse
import os
import sys
import traceback

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auth_helper import (  # noqa: E402
    DATAVERSE_URL,
    api_delete,
    api_get,
    api_patch,
    get_session,
)

load_dotenv()

PREFIX = os.getenv("PUBLISHER_PREFIX", "").strip()
if not PREFIX:
    raise SystemExit("PUBLISHER_PREFIX must be set in .env")

APPLICATION_TABLE = f"{PREFIX}_application"
APPLICATION_RESOURCE_TABLE = f"{PREFIX}_applicationresource"
STAGE_ATTRIBUTE = f"{PREFIX}_stage"
SUBMITTED_STAGE = 100000001
OBSOLETE_STAGE_VALUES = [100000002, 100000003, 100000005]
OBSOLETE_RESOURCE_RELATIONSHIPS = [
    f"{PREFIX}_applicationresource_{PREFIX}_applicationresource_replacedfrom",
]
OBSOLETE_RESOURCE_COLUMNS = [
    f"{PREFIX}_type",
    f"{PREFIX}_attachment",
    f"{PREFIX}_status",
    f"{PREFIX}_version",
    f"{PREFIX}_replacedat",
    f"{PREFIX}_replacedfromid",
]


def entity_set(logical_name: str) -> str:
    meta = api_get(f"EntityDefinitions(LogicalName='{logical_name}')?$select=EntitySetName")
    return meta["EntitySetName"]


def attribute_exists(table: str, column: str) -> bool:
    try:
        api_get(
            f"EntityDefinitions(LogicalName='{table}')/Attributes(LogicalName='{column}')"
            "?$select=LogicalName"
        )
        return True
    except Exception:
        return False


def relationship_metadata_id(schema_name: str) -> str | None:
    try:
        rel = api_get(
            f"RelationshipDefinitions(SchemaName='{schema_name}')?$select=MetadataId,SchemaName"
        )
        return rel.get("MetadataId")
    except Exception:
        try:
            rels = api_get(
                "RelationshipDefinitions?"
                f"$filter=SchemaName eq '{schema_name}'&$select=MetadataId,SchemaName"
            )
            values = rels.get("value", [])
            return values[0].get("MetadataId") if values else None
        except Exception:
            return None


def publish_all(apply: bool, skip_publish: bool) -> None:
    if skip_publish:
        print("  Publish skipped (--skip-publish).")
        return
    if not apply:
        print("  DRY RUN: would call PublishAllXml")
        return
    url = f"{DATAVERSE_URL}/api/data/v9.2/PublishAllXml"
    response = get_session().post(url, json={}, timeout=180)
    if not response.ok:
        print(response.text, file=sys.stderr)
    response.raise_for_status()
    print("  Published")


def migrate_old_stage_records(apply: bool) -> None:
    print("\n=== Stage data migration ===")
    app_set = entity_set(APPLICATION_TABLE)
    filter_parts = [f"{STAGE_ATTRIBUTE} eq {value}" for value in OBSOLETE_STAGE_VALUES]
    rows = api_get(
        f"{app_set}?$select={PREFIX}_applicationid,{PREFIX}_name,{STAGE_ATTRIBUTE}"
        f"&$filter={' or '.join(filter_parts)}"
    ).get("value", [])
    if not rows:
        print("  No applications use obsolete stage values.")
        return
    print(f"  Found {len(rows)} applications with obsolete stage values.")
    for row in rows:
        app_id = row[f"{PREFIX}_applicationid"]
        name = row.get(f"{PREFIX}_name", app_id)
        old_stage = row.get(STAGE_ATTRIBUTE)
        if apply:
            api_patch(f"{app_set}({app_id})", {STAGE_ATTRIBUTE: SUBMITTED_STAGE})
            print(f"  Updated: {name} {old_stage} -> {SUBMITTED_STAGE}")
        else:
            print(f"  DRY RUN: would update {name} {old_stage} -> {SUBMITTED_STAGE}")


def delete_stage_options(apply: bool) -> None:
    print("\n=== Stage option cleanup ===")
    session = get_session()
    url = f"{DATAVERSE_URL}/api/data/v9.2/DeleteOptionValue"
    for value in OBSOLETE_STAGE_VALUES:
        payload = {
            "EntityLogicalName": APPLICATION_TABLE,
            "AttributeLogicalName": STAGE_ATTRIBUTE,
            "Value": value,
        }
        if not apply:
            print(f"  DRY RUN: would delete option {APPLICATION_TABLE}.{STAGE_ATTRIBUTE}={value}")
            continue
        response = session.post(url, json=payload)
        if response.status_code == 404 or "does not exist" in response.text.lower():
            print(f"  Option already absent: {value}")
            continue
        if not response.ok:
            print(response.text, file=sys.stderr)
        response.raise_for_status()
        print(f"  Deleted option: {value}")


def delete_relationships(apply: bool) -> None:
    print("\n=== Relationship cleanup ===")
    for schema_name in OBSOLETE_RESOURCE_RELATIONSHIPS:
        metadata_id = relationship_metadata_id(schema_name)
        if not metadata_id:
            print(f"  Relationship already absent: {schema_name}")
            continue
        if apply:
            api_delete(f"RelationshipDefinitions({metadata_id})")
            print(f"  Deleted relationship: {schema_name}")
        else:
            print(f"  DRY RUN: would delete relationship {schema_name}")


def delete_columns(apply: bool) -> None:
    print("\n=== Application resource column cleanup ===")
    for column in OBSOLETE_RESOURCE_COLUMNS:
        if not attribute_exists(APPLICATION_RESOURCE_TABLE, column):
            print(f"  Column already absent: {column}")
            continue
        if apply:
            api_delete(
                f"EntityDefinitions(LogicalName='{APPLICATION_RESOURCE_TABLE}')"
                f"/Attributes(LogicalName='{column}')"
            )
            print(f"  Deleted column: {column}")
        else:
            print(f"  DRY RUN: would delete column {APPLICATION_RESOURCE_TABLE}.{column}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean obsolete DecisionFlow Dataverse metadata. Defaults to dry-run."
    )
    parser.add_argument("--apply", action="store_true", help="Apply destructive metadata changes")
    parser.add_argument("--skip-publish", action="store_true", help="Skip PublishAllXml after changes")
    args = parser.parse_args()

    print("=" * 72)
    print("DecisionFlow obsolete metadata cleanup")
    print("=" * 72)
    print(f"Environment: {DATAVERSE_URL}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")

    migrate_old_stage_records(args.apply)
    delete_stage_options(args.apply)
    delete_relationships(args.apply)
    delete_columns(args.apply)
    print("\n=== Publish ===")
    publish_all(args.apply, args.skip_publish)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        if exc.response is not None:
            print(exc.response.text, file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        traceback.print_exc()
        raise SystemExit(1)