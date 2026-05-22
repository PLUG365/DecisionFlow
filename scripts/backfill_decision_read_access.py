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


def build_decision_grant_payload(prefix: str, decision_id: str, systemuser_id: str) -> dict:
    return {
        "Target": {
            "@odata.type": f"Microsoft.Dynamics.CRM.{prefix}_decision",
            f"{prefix}_decisionid": decision_id,
        },
        "PrincipalAccess": {
            "Principal": {
                "@odata.type": "Microsoft.Dynamics.CRM.systemuser",
                "systemuserid": systemuser_id,
            },
            "AccessMask": "ReadAccess",
        },
    }


def _normalize_guid(value: str | None) -> str | None:
    trimmed = (value or "").strip()
    return trimmed.lower() if trimmed else None


def _grant_decision_read_access(decision_id: str, systemuser_id: str) -> bool:
    session = get_session()
    response = session.post(
        f"{API}/GrantAccess",
        json=build_decision_grant_payload(PREFIX, decision_id, systemuser_id),
    )
    if response.ok:
        return True

    message = response.text[:500]
    print(f"    ⚠️ GrantAccess failed decision={decision_id} user={systemuser_id}: {response.status_code} {message}")
    return False


def _get_application_applicant_id(application_id: str) -> str | None:
    application = api_get(f"{PREFIX}_applications({application_id})?$select=_createdby_value")
    return _normalize_guid(application.get("_createdby_value"))


def _get_application_participant_user_ids(application_id: str) -> list[str]:
    participants = api_get(
        f"{PREFIX}_participants?"
        f"$filter=_{PREFIX}_applicationid_value eq {application_id}"
        f"&$select=_{PREFIX}_userid_value"
    ).get("value", [])
    user_ids = []
    for participant in participants:
        user_id = _normalize_guid(participant.get(f"_{PREFIX}_userid_value"))
        if user_id:
            user_ids.append(user_id)
    return user_ids


def backfill_decision_read_access() -> tuple[int, int]:
    decisions = api_get(
        f"{PREFIX}_decisions?"
        f"$select={PREFIX}_decisionid,_{PREFIX}_applicationid_value"
        "&$orderby=createdon asc"
    ).get("value", [])
    print(f"対象判断レコード: {len(decisions)} 件")

    grant_attempts = 0
    grant_successes = 0
    for decision in decisions:
        decision_id = decision.get(f"{PREFIX}_decisionid")
        application_id = decision.get(f"_{PREFIX}_applicationid_value")
        if not decision_id or not application_id:
            continue

        target_user_ids = {
            user_id
            for user_id in [
                _get_application_applicant_id(application_id),
                *_get_application_participant_user_ids(application_id),
            ]
            if user_id
        }
        print(f"  decision={decision_id} application={application_id} users={len(target_user_ids)}")
        for user_id in sorted(target_user_ids):
            grant_attempts += 1
            if _grant_decision_read_access(decision_id, user_id):
                grant_successes += 1

    return grant_attempts, grant_successes


def main() -> None:
    print("=" * 72)
    print("Backfill ds_decision ReadAccess for applicants and participants")
    print(f"Prefix: {PREFIX}")
    print("=" * 72)
    attempts, successes = backfill_decision_read_access()
    print(f"\nDone. GrantAccess success: {successes}/{attempts}")
    if attempts != successes:
        raise RuntimeError("一部の ds_decision ReadAccess 付与に失敗しました。")


if __name__ == "__main__":
    main()