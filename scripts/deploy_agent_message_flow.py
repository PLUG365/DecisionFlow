"""DecisionFlow Assistant が申請の会話へ投稿するための agent flow をデプロイする。

`docs/AGENT_WRITE_BOUNDARY.md` の「許可する操作」のうち、会話への投稿
（`ds_message` の作成）を実装する。低リスクの書き込みから始める方針に沿う。

**重要**: agent flow は接続参照の identity で実行される。誰の操作として扱うかは
トリガー引数 `actorAadObjectId` / `actorUpn` が決めるため、Copilot Studio 側では
必ず認証済みユーザー変数（System.User.Id / System.User.PrincipalName）から渡すこと。
会話本文やモデルの推論から組み立ててはならない。

ゲート:
1. 実行者が systemuser として解決できる
2. 本文が空でない
3. 申請が存在する
4. 実行者がその申請の関係者である（ds_participant / 判断者 / 作成者のいずれか）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.agent_flow_common import (  # noqa: E402
    PREFIX,
    actor_lookup_filter,
    clientdata,
    create_record_action,
    list_records_action,
    response_action,
    return_and_stop,
    skills_trigger,
    text_input,
    workflow_definition,
)

load_dotenv()

SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
POST_MESSAGE_FLOW_NAME = "post_application_message"
POST_MESSAGE_FLOW_DESCRIPTION = (
    "DecisionFlow Assistant が申請の会話へコメントを投稿する。実行者が申請の関係者である場合のみ許可する。"
)

MESSAGE_KIND_COMMENT = 100000000
MESSAGE_NAME_MAX_LENGTH = 80

MESSAGE_RESPONSE_PROPERTIES = {
    "status": "status",
    "applicationId": "applicationId",
    "messageId": "messageId",
    "message": "message",
}

_ACTOR_ID = "first(outputs('List_current_user')?['body/value'])?['systemuserid']"
_APPLICATION = "first(outputs('List_application')?['body/value'])"
_TRIMMED_BODY = "trim(triggerBody()?['body'])"


def _response_body(status: str, message: str, message_id: str = "") -> dict:
    return {
        "status": status,
        "applicationId": "@triggerBody()?['applicationId']",
        "messageId": message_id,
        "message": message,
    }


def _stop(action_name: str, status: str, message: str) -> dict:
    return return_and_stop(action_name, _response_body(status, message), MESSAGE_RESPONSE_PROPERTIES)


def build_post_application_message_clientdata() -> str:
    triggers = skills_trigger(
        {
            "applicationId": text_input("applicationId", "投稿先の申請 ID"),
            "body": text_input("body", "投稿する本文"),
            "actorAadObjectId": text_input(
                "actorAadObjectId",
                "実行者の Entra object ID。Copilot Studio の認証済みユーザー変数から渡す。取得できない場合は空でよい",
            ),
            "actorUpn": text_input(
                "actorUpn",
                "実行者の UPN。Copilot Studio の認証済みユーザー変数から渡す",
            ),
        },
        ["applicationId", "body", "actorUpn"],
    )

    actions = {
        "List_current_user": list_records_action(
            "systemusers",
            actor_lookup_filter(),
            "systemuserid,domainname,internalemailaddress,azureactivedirectoryobjectid",
        ),
        "Validate_user_found": {
            "type": "If",
            "runAfter": {"List_current_user": ["Succeeded"]},
            "expression": {"greater": ["@length(outputs('List_current_user')?['body/value'])", 0]},
            "actions": {},
            "else": {
                "actions": _stop(
                    "Return_forbidden_user_not_found",
                    "forbidden",
                    "ユーザーを確認できないため、会話に投稿できません。",
                )
            },
        },
        "Validate_body_exists": {
            "type": "If",
            "runAfter": {"Validate_user_found": ["Succeeded"]},
            "expression": {"not": {"equals": [f"@{_TRIMMED_BODY}", ""]}},
            "actions": {},
            "else": {
                "actions": _stop(
                    "Return_invalid_empty_body",
                    "invalid_target",
                    "投稿する本文が空です。",
                )
            },
        },
        "List_application": list_records_action(
            f"{PREFIX}_applications",
            f"@concat('{PREFIX}_applicationid eq ', triggerBody()?['applicationId'])",
            f"{PREFIX}_applicationid,{PREFIX}_name,_{PREFIX}_deciderid_value,_createdby_value",
            {"Validate_body_exists": ["Succeeded"]},
        ),
        "Validate_application_found": {
            "type": "If",
            "runAfter": {"List_application": ["Succeeded"]},
            "expression": {"greater": ["@length(outputs('List_application')?['body/value'])", 0]},
            "actions": {},
            "else": {
                "actions": _stop(
                    "Return_invalid_application",
                    "invalid_target",
                    "対象の申請が見つかりません。",
                )
            },
        },
        "List_actor_participation": list_records_action(
            f"{PREFIX}_participants",
            (
                f"@concat('_{PREFIX}_applicationid_value eq ', triggerBody()?['applicationId'], "
                f"' and _{PREFIX}_userid_value eq ', {_ACTOR_ID})"
            ),
            f"{PREFIX}_participantid",
            {"Validate_application_found": ["Succeeded"]},
        ),
        # 関係者テーブルに加えて判断者と作成者も許可する。申請作成時に
        # ds_participant が自動登録される設計だが、既存データには揃っていない行がある。
        "Validate_actor_is_participant": {
            "type": "If",
            "runAfter": {"List_actor_participation": ["Succeeded"]},
            "expression": {
                "or": [
                    {"greater": ["@length(outputs('List_actor_participation')?['body/value'])", 0]},
                    {
                        "equals": [
                            f"@toLower(coalesce({_APPLICATION}?['_{PREFIX}_deciderid_value'], ''))",
                            f"@toLower({_ACTOR_ID})",
                        ]
                    },
                    {
                        "equals": [
                            f"@toLower(coalesce({_APPLICATION}?['_createdby_value'], ''))",
                            f"@toLower({_ACTOR_ID})",
                        ]
                    },
                ]
            },
            "actions": {},
            "else": {
                "actions": _stop(
                    "Return_forbidden_not_participant",
                    "forbidden",
                    "この申請の関係者ではないため、会話に投稿できません。",
                )
            },
        },
        "Create_message": create_record_action(
            f"{PREFIX}_messages",
            {
                f"{PREFIX}_name": (
                    f"@if(greater(length({_TRIMMED_BODY}), {MESSAGE_NAME_MAX_LENGTH}), "
                    f"substring({_TRIMMED_BODY}, 0, {MESSAGE_NAME_MAX_LENGTH}), {_TRIMMED_BODY})"
                ),
                f"{PREFIX}_body": f"@{_TRIMMED_BODY}",
                f"{PREFIX}_kind": MESSAGE_KIND_COMMENT,
                f"{PREFIX}_applicationid@odata.bind": (
                    f"@concat('/{PREFIX}_applications(', triggerBody()?['applicationId'], ')')"
                ),
            },
            {"Validate_actor_is_participant": ["Succeeded"]},
        ),
        "Return_succeeded": response_action(
            _response_body(
                "succeeded",
                "会話に投稿しました。",
                f"@outputs('Create_message')?['body/{PREFIX}_messageid']",
            ),
            MESSAGE_RESPONSE_PROPERTIES,
            {"Create_message": ["Succeeded"]},
        ),
    }

    return clientdata(workflow_definition(actions, triggers))


def main() -> int:
    from scripts.deploy_adaptive_card_decision_confirmation import deploy_tool_flow

    print("=== DecisionFlow エージェント会話投稿フローのデプロイ ===")
    workflow_id, active = deploy_tool_flow(
        POST_MESSAGE_FLOW_NAME,
        POST_MESSAGE_FLOW_DESCRIPTION,
        build_post_application_message_clientdata(),
    )
    print(f"Flow: {POST_MESSAGE_FLOW_NAME} ({workflow_id}) active={active}")
    print()
    print("=== Copilot Studio 側の反映 ===")
    print(f"- {POST_MESSAGE_FLOW_NAME} をツールとして追加しないでください。追加すると生成")
    print("  オーケストレーションが専用トピックを迂回して直接呼び、実行者をモデルが埋めます。")
    print("- 専用トピック（会話へ投稿）が flowId 直指定で呼びます。ツール登録は不要です。")
    print("- actorAadObjectId には System.User.Id、actorUpn には System.User.PrincipalName を渡すこと。")
    print("- 会話本文やモデルの推論から実行者を組み立ててはいけません（docs/AGENT_WRITE_BOUNDARY.md）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
