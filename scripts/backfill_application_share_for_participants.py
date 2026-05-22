from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL, api_get, get_session  # noqa: E402

load_dotenv()

PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")
API = f"{DATAVERSE_URL.rstrip('/')}/api/data/v9.2"


def build_application_grant_payload(prefix: str, application_id: str, systemuser_id: str) -> dict:
    return {
        "Target": {
            "@odata.type": f"Microsoft.Dynamics.CRM.{prefix}_application",
            f"{prefix}_applicationid": application_id,
        },
        "PrincipalAccess": {
            "Principal": {
                "@odata.type": "Microsoft.Dynamics.CRM.systemuser",
                "systemuserid": systemuser_id,
            },
            "AccessMask": "ReadAccess,AppendToAccess",
        },
    }


def _normalize_guid(value: str | None) -> str | None:
    trimmed = (value or "").strip()
    return trimmed.lower() if trimmed else None


def _grant_application_access(application_id: str, systemuser_id: str) -> bool:
    session = get_session()
    response = session.post(
        f"{API}/GrantAccess",
        json=build_application_grant_payload(PREFIX, application_id, systemuser_id),
    )
    if response.ok:
        return True
    print(
        f"    ⚠️ GrantAccess failed application={application_id} user={systemuser_id}: "
        f"{response.status_code} {response.text[:500]}"
    )
    return False


def backfill_application_share_for_participants() -> tuple[int, int]:
    participants = api_get(
        f"{PREFIX}_participants?"
        f"$select={PREFIX}_participantid,_{PREFIX}_applicationid_value,_{PREFIX}_userid_value"
        "&$orderby=createdon asc"
    ).get("value", [])

    pairs: set[tuple[str, str]] = set()
    for participant in participants:
        application_id = _normalize_guid(participant.get(f"_{PREFIX}_applicationid_value"))
        user_id = _normalize_guid(participant.get(f"_{PREFIX}_userid_value"))
        if application_id and user_id:
            pairs.add((application_id, user_id))

    print(f"対象 application/user 共有: {len(pairs)} 件")
    attempts = 0
    successes = 0
    for application_id, user_id in sorted(pairs):
        attempts += 1
        print(f"  application={application_id} user={user_id}")
        if _grant_application_access(application_id, user_id):
            successes += 1
    return attempts, successes


def main() -> None:
    print("=" * 72)
    print("Backfill ds_application share for participants")
    print(f"Prefix: {PREFIX}")
    print("=" * 72)
    attempts, successes = backfill_application_share_for_participants()
    print(f"\nDone. GrantAccess success: {successes}/{attempts}")
    if attempts != successes:
        raise RuntimeError("一部の ds_application 共有再付与に失敗しました。")


if __name__ == "__main__":
    main()