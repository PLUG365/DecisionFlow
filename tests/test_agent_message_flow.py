import json
import unittest

from scripts import deploy_agent_message_flow as message_flow


def find_action(actions: dict, name: str) -> dict:
    if name in actions:
        return actions[name]
    for action in actions.values():
        nested = action.get("actions")
        if isinstance(nested, dict):
            try:
                return find_action(nested, name)
            except AssertionError:
                pass
        else_actions = action.get("else", {}).get("actions") if isinstance(action.get("else"), dict) else None
        if isinstance(else_actions, dict):
            try:
                return find_action(else_actions, name)
            except AssertionError:
                pass
    raise AssertionError(f"Action '{name}' was not found.")


def flatten_actions(actions: dict) -> list[dict]:
    flattened = []
    for action in actions.values():
        flattened.append(action)
        nested = action.get("actions")
        if isinstance(nested, dict):
            flattened.extend(flatten_actions(nested))
        else_actions = action.get("else", {}).get("actions") if isinstance(action.get("else"), dict) else None
        if isinstance(else_actions, dict):
            flattened.extend(flatten_actions(else_actions))
    return flattened


class AgentMessageFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        clientdata = json.loads(message_flow.build_post_application_message_clientdata())
        self.definition = clientdata["properties"]["definition"]
        self.actions = self.definition["actions"]

    def test_trigger_takes_actor_identity_and_requires_upn(self):
        trigger = self.definition["triggers"]["manual"]
        self.assertEqual(trigger["type"], "Request")
        self.assertEqual(trigger["kind"], "Skills")

        schema = trigger["inputs"]["schema"]
        self.assertEqual(
            set(schema["properties"]),
            {"applicationId", "body", "actorAadObjectId", "actorUpn"},
        )
        # 実行者を指定せずに投稿できてはいけない。
        self.assertIn("actorUpn", schema["required"])
        self.assertIn("applicationId", schema["required"])
        self.assertIn("body", schema["required"])

    def test_actor_is_resolved_from_directory_not_from_free_text(self):
        # 実行者は systemuser を Entra object ID か domainname で引いて解決する。
        # 会話本文から名前を推測して書き込む経路を作らない。
        actor_filter = find_action(self.actions, "List_current_user")["inputs"]["parameters"]["$filter"]
        self.assertIn("azureactivedirectoryobjectid", actor_filter)
        self.assertIn("domainname", actor_filter)
        self.assertIn("actorAadObjectId", actor_filter)
        self.assertIn("actorUpn", actor_filter)

    def test_every_gate_runs_before_the_write(self):
        create = find_action(self.actions, "Create_message")
        self.assertEqual(create["inputs"]["host"]["operationId"], "CreateRecord")
        self.assertEqual(create["runAfter"], {"Validate_actor_is_participant": ["Succeeded"]})

        expected_chain = {
            "Validate_user_found": "List_current_user",
            "Validate_body_exists": "Validate_user_found",
            "List_application": "Validate_body_exists",
            "Validate_application_found": "List_application",
            "List_actor_participation": "Validate_application_found",
            "Validate_actor_is_participant": "List_actor_participation",
        }
        for action_name, predecessor in expected_chain.items():
            action = find_action(self.actions, action_name)
            self.assertEqual(
                action["runAfter"],
                {predecessor: ["Succeeded"]},
                f"{action_name} must run after {predecessor}.",
            )

    def test_participation_accepts_participant_decider_or_creator(self):
        gate = find_action(self.actions, "Validate_actor_is_participant")
        self.assertEqual(gate["type"], "If")
        conditions = json.dumps(gate["expression"], ensure_ascii=False)

        self.assertIn("List_actor_participation", conditions)
        self.assertIn("_ds_deciderid_value", conditions)
        self.assertIn("_createdby_value", conditions)

    def test_each_gate_returns_and_stops_instead_of_falling_through(self):
        for gate_name, stop_action in {
            "Validate_user_found": "Return_forbidden_user_not_found",
            "Validate_body_exists": "Return_invalid_empty_body",
            "Validate_application_found": "Return_invalid_application",
            "Validate_actor_is_participant": "Return_forbidden_not_participant",
        }.items():
            gate = find_action(self.actions, gate_name)
            else_actions = gate["else"]["actions"]
            self.assertIn(stop_action, else_actions, f"{gate_name} must return a failure response.")
            self.assertIn(
                f"Stop_after_{stop_action}",
                else_actions,
                f"{gate_name} must terminate after returning.",
            )

    def test_message_is_written_as_a_comment_bound_to_the_application(self):
        item = find_action(self.actions, "Create_message")["inputs"]["parameters"]["item"]
        self.assertEqual(item["ds_kind"], message_flow.MESSAGE_KIND_COMMENT)
        self.assertIn("trim(triggerBody()?['body'])", item["ds_body"])
        self.assertIn("ds_applications(", item["ds_applicationid@odata.bind"])
        self.assertIn(str(message_flow.MESSAGE_NAME_MAX_LENGTH), item["ds_name"])

    def test_flow_writes_only_to_messages(self):
        # 書き込み境界（docs/AGENT_WRITE_BOUNDARY.md）で禁止している対象へ書き込まない。
        # ds_participants は関係者チェックのために「読む」ので、読み取りは許容する。
        write_operations = {"CreateRecord", "UpdateRecord", "DeleteRecord"}
        written_entities = set()
        for action in flatten_actions(self.actions):
            host = action.get("inputs", {}).get("host", {})
            if host.get("operationId") in write_operations:
                written_entities.add(action["inputs"]["parameters"]["entityName"])

        self.assertEqual(written_entities, {"ds_messages"})


if __name__ == "__main__":
    unittest.main()
