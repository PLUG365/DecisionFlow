import os
import sys
from urllib.parse import quote

from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auth_helper import api_get  # noqa: E402

load_dotenv()

SOLUTION_NAME = os.getenv("SOLUTION_NAME", "").strip()
PREFIX = os.getenv("PUBLISHER_PREFIX", "").strip()

TABLE_LOGICAL_NAMES = [
    f"{PREFIX}_category",
    f"{PREFIX}_decisionoption",
    f"{PREFIX}_application",
    f"{PREFIX}_message",
    f"{PREFIX}_mention",
    f"{PREFIX}_participant",
    f"{PREFIX}_decision",
    f"{PREFIX}_applicationresource",
]


def require_env() -> None:
    missing = [
        name
        for name in ["DATAVERSE_URL", "TENANT_ID", "SOLUTION_NAME", "PUBLISHER_PREFIX"]
        if not os.getenv(name, "").strip()
    ]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")


def print_publishers() -> None:
    print("\n=== Publishers ===")
    publishers = api_get(
        "publishers?"
        "$filter=customizationprefix ne 'none'&"
        "$select=friendlyname,uniquename,customizationprefix&"
        "$orderby=friendlyname"
    )
    for publisher in publishers.get("value", []):
        print(
            f"- {publisher.get('customizationprefix')} | "
            f"{publisher.get('friendlyname')} ({publisher.get('uniquename')})"
        )


def check_solution_collision() -> bool:
    print("\n=== Solution Collision ===")
    escaped = SOLUTION_NAME.replace("'", "''")
    result = api_get(
        f"solutions?$filter=uniquename eq '{escaped}'&$select=solutionid,friendlyname,uniquename"
    )
    values = result.get("value", [])
    if not values:
        print(f"OK: solution '{SOLUTION_NAME}' does not exist yet.")
        return False
    for solution in values:
        print(
            "FOUND: "
            f"{solution.get('friendlyname')} ({solution.get('uniquename')}) "
            f"solutionid={solution.get('solutionid')}"
        )
    return True


def check_table_collisions() -> list[str]:
    print("\n=== Table Collisions ===")
    found: list[str] = []
    for logical_name in TABLE_LOGICAL_NAMES:
        encoded = quote(logical_name, safe="")
        try:
            entity = api_get(
                f"EntityDefinitions(LogicalName='{encoded}')?"
                "$select=LogicalName,SchemaName,DisplayName"
            )
        except Exception:
            print(f"OK: {logical_name} does not exist yet.")
            continue
        label = ""
        display = entity.get("DisplayName", {})
        labels = display.get("LocalizedLabels", []) if isinstance(display, dict) else []
        if labels:
            label = labels[0].get("Label", "")
        print(f"FOUND: {entity.get('LogicalName')} ({entity.get('SchemaName')}) {label}")
        found.append(logical_name)
    return found


def main() -> int:
    require_env()
    print_publishers()
    solution_exists = check_solution_collision()
    table_collisions = check_table_collisions()

    print("\n=== Summary ===")
    if solution_exists or table_collisions:
        print("Collision detected. Review before proceeding to setup_dataverse.py.")
        return 2
    print("No solution/table collisions detected for the planned DecisionFlow schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
