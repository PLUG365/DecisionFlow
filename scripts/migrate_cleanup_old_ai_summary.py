import argparse
import json
import os
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auth_helper import (  # noqa: E402
    DATAVERSE_URL,
    api_delete,
    api_get,
    get_session,
)

load_dotenv()

PREFIX = os.getenv("PUBLISHER_PREFIX", "").strip()
if not PREFIX:
    raise SystemExit("PUBLISHER_PREFIX must be set in .env")

APPLICATION_TABLE = f"{PREFIX}_application"
APPLICATION_SET = f"{PREFIX}_applications"
MESSAGE_TABLE = f"{PREFIX}_message"
MESSAGE_SET = f"{PREFIX}_messages"
MESSAGE_KIND_ATTRIBUTE = f"{PREFIX}_kind"
OBSOLETE_APPLICATION_COLUMNS = [
    f"{PREFIX}_aisummary",
    f"{PREFIX}_summaryupdatedat",
]
OBSOLETE_MESSAGE_KIND_VALUE = 100000004


def attribute_exists(table: str, column: str) -> bool:
    try:
        api_get(
            f"EntityDefinitions(LogicalName='{table}')/Attributes(LogicalName='{column}')"
            "?$select=LogicalName"
        )
        return True
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return False
        raise


def count_rows(path: str) -> int:
    data = api_get(f"{path}&$top=1&$count=true")
    count = data.get("@odata.count")
    return int(count) if count is not None else len(data.get("value", []))


def option_exists() -> bool:
    attr = api_get(
        f"EntityDefinitions(LogicalName='{MESSAGE_TABLE}')"
        f"/Attributes(LogicalName='{MESSAGE_KIND_ATTRIBUTE}')"
        "/Microsoft.Dynamics.CRM.PicklistAttributeMetadata"
        "?$select=LogicalName&$expand=OptionSet($select=Options)"
    )
    values = [option.get("Value") for option in attr.get("OptionSet", {}).get("Options", [])]
    return OBSOLETE_MESSAGE_KIND_VALUE in values


def collect_backup_rows(existing_columns: list[str]) -> list[dict]:
    select = ",".join([f"{PREFIX}_applicationid", f"{PREFIX}_name", *existing_columns])
    filter_expr = " or ".join(f"{column} ne null" for column in existing_columns)
    rows = api_get(
        f"{APPLICATION_SET}?$select={select}"
        f"&$filter={filter_expr}"
    ).get("value", [])
    return [
        {
            "id": row.get(f"{PREFIX}_applicationid"),
            "name": row.get(f"{PREFIX}_name"),
            OBSOLETE_APPLICATION_COLUMNS[0]: row.get(OBSOLETE_APPLICATION_COLUMNS[0]),
            OBSOLETE_APPLICATION_COLUMNS[1]: row.get(OBSOLETE_APPLICATION_COLUMNS[1]),
        }
        for row in rows
    ]


def write_backup(rows: list[dict]) -> Path | None:
    if not rows:
        return None
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = Path(__file__).resolve().parents[1] / "artifacts" / "migrations"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"old_ai_summary_backup_{timestamp}.json"
    backup_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return backup_path


def delete_message_kind_option(apply: bool) -> None:
    print("\n=== Message kind option cleanup ===")
    old_messages = count_rows(
        f"{MESSAGE_SET}?$select={PREFIX}_messageid"
        f"&$filter={MESSAGE_KIND_ATTRIBUTE} eq {OBSOLETE_MESSAGE_KIND_VALUE}"
    )
    if old_messages:
        raise RuntimeError(
            f"Cannot delete AISummary option while {old_messages} messages still use it."
        )
    print("  No messages use AISummary kind.")

    if not option_exists():
        print(f"  Option already absent: {OBSOLETE_MESSAGE_KIND_VALUE}")
        return

    payload = {
        "EntityLogicalName": MESSAGE_TABLE,
        "AttributeLogicalName": MESSAGE_KIND_ATTRIBUTE,
        "Value": OBSOLETE_MESSAGE_KIND_VALUE,
    }
    if not apply:
        print(
            f"  DRY RUN: would delete option "
            f"{MESSAGE_TABLE}.{MESSAGE_KIND_ATTRIBUTE}={OBSOLETE_MESSAGE_KIND_VALUE}"
        )
        return

    response = get_session().post(f"{DATAVERSE_URL}/api/data/v9.2/DeleteOptionValue", json=payload)
    if response.status_code == 404 or "does not exist" in response.text.lower():
        print(f"  Option already absent: {OBSOLETE_MESSAGE_KIND_VALUE}")
        return
    if not response.ok:
        print(response.text, file=sys.stderr)
    response.raise_for_status()
    print(f"  Deleted option: {OBSOLETE_MESSAGE_KIND_VALUE}")


def delete_application_columns(apply: bool) -> None:
    print("\n=== Application legacy AI summary column cleanup ===")
    existing_columns = [
        column
        for column in OBSOLETE_APPLICATION_COLUMNS
        if attribute_exists(APPLICATION_TABLE, column)
    ]
    if not existing_columns:
        print("  Legacy AI summary columns already absent.")
        return

    backup_rows = collect_backup_rows(existing_columns)
    if backup_rows:
        print(f"  Found {len(backup_rows)} applications with legacy AI summary values.")
        if apply:
            backup_path = write_backup(backup_rows)
            print(f"  Backup written: {backup_path}")
        else:
            print("  DRY RUN: would back up legacy AI summary values before deleting columns.")
    else:
        print("  No legacy AI summary values found.")

    for column in OBSOLETE_APPLICATION_COLUMNS:
        if column not in existing_columns:
            print(f"  Column already absent: {column}")
            continue
        if apply:
            api_delete(
                f"EntityDefinitions(LogicalName='{APPLICATION_TABLE}')"
                f"/Attributes(LogicalName='{column}')"
            )
            print(f"  Deleted column: {column}")
        else:
            print(f"  DRY RUN: would delete column {APPLICATION_TABLE}.{column}")


def publish_all(apply: bool, skip_publish: bool) -> None:
    print("\n=== Publish ===")
    if skip_publish:
        print("  Publish skipped (--skip-publish).")
        return
    if not apply:
        print("  DRY RUN: would call PublishAllXml")
        return
    response = get_session().post(f"{DATAVERSE_URL}/api/data/v9.2/PublishAllXml", json={}, timeout=180)
    if not response.ok:
        print(response.text, file=sys.stderr)
    response.raise_for_status()
    print("  Published")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean obsolete DecisionFlow AI summary metadata. Defaults to dry-run."
    )
    parser.add_argument("--apply", action="store_true", help="Apply destructive metadata changes")
    parser.add_argument("--skip-publish", action="store_true", help="Skip PublishAllXml after changes")
    args = parser.parse_args()

    print("=" * 72)
    print("DecisionFlow old AI summary cleanup")
    print("=" * 72)
    print(f"Environment: {DATAVERSE_URL}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")

    delete_message_kind_option(args.apply)
    delete_application_columns(args.apply)
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