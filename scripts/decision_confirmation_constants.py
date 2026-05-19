ALLOWED_DECISION_OPTION_LABELS = ("承認", "却下", "差し戻し")

CARD_STATUS_ISSUED = 100000000
CARD_STATUS_CONSUMED = 100000001
CARD_STATUS_SUPERSEDED = 100000002
CARD_STATUS_EXPIRED = 100000003

RESPONSE_SUCCEEDED = "succeeded"
RESPONSE_ALREADY_PROCESSED = "already_processed"
RESPONSE_FORBIDDEN = "forbidden"
RESPONSE_INVALID_TARGET = "invalid_target"

DRAFT_STAGE = 100000000
SUBMITTED_STAGE = 100000001
DECIDED_STAGE = 100000004


def require_trimmed(field_name: str, value: str | None) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        raise ValueError(f"{field_name} is required")
    return trimmed


def validate_decision_option_label(label: str | None) -> str:
    trimmed = require_trimmed("decisionOptionLabel", label)
    if trimmed not in ALLOWED_DECISION_OPTION_LABELS:
        raise ValueError(f"Unsupported decision option label: {trimmed}")
    return trimmed


def validate_submit_payload(payload: dict) -> dict:
    actor = payload.get("actor") or {}
    return {
        "applicationId": require_trimmed("applicationId", payload.get("applicationId")),
        "decisionOption": validate_decision_option_label(payload.get("decisionOption")),
        "rationale": require_trimmed("rationale", payload.get("rationale")),
        "cardInstanceId": require_trimmed("cardInstanceId", payload.get("cardInstanceId")),
        "actor": {
            "aadObjectId": require_trimmed("actor.aadObjectId", actor.get("aadObjectId")),
            "upn": require_trimmed("actor.upn", actor.get("upn")),
        },
    }