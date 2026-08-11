import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = (
    ROOT
    / "artifacts"
    / "agent-flows"
    / "DecisionFlow_Phase3_AgentNode_Harness"
    / "flowagent.snapshot.json"
)
SOLUTION_EXPORT = SNAPSHOT.with_name("solution-export.workflow.json")
DECISION_OUTPUT_SCHEMA = SNAPSHOT.with_name("decision-output.schema.json")


class Phase3AgentFlowSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        cls.action = cls.snapshot["definition"]["actions"]["Run_an_agent"]

    def test_snapshot_is_non_running_draft(self) -> None:
        self.assertEqual(self.snapshot["state"], "Stopped")
        self.assertEqual(self.snapshot["componentState"], "Draft")

    def test_agent_action_is_read_only_benchmark_configuration(self) -> None:
        inputs = self.action["inputs"]
        self.assertEqual(inputs["host"]["operationId"], "InvokeAgent")
        self.assertEqual(inputs["parameters"]["body/agentId"], "ds_DecisionFlowAssistant")
        self.assertFalse(inputs["parameters"]["body/isHitlEscalationEnabled"])
        self.assertIn("Do not call tools or write data", inputs["parameters"]["body/prompt"])

    def test_snapshot_contains_no_runtime_secret_or_trigger_url(self) -> None:
        serialized = json.dumps(self.snapshot).lower()
        for forbidden in ("flowtriggeruri", "sig=", "access_token", "refresh_token"):
            self.assertNotIn(forbidden, serialized)

    def test_solution_export_contains_reproducible_agent_action(self) -> None:
        exported = json.loads(SOLUTION_EXPORT.read_text(encoding="utf-8"))
        properties = exported["properties"]
        definition = properties["definition"]
        action = definition["actions"]["Run_an_agent"]
        self.assertEqual(action["inputs"]["host"]["operationId"], "InvokeAgent")
        self.assertEqual(
            action["inputs"]["parameters"]["body/agentId"],
            "ds_DecisionFlowAssistant",
        )
        parameters = action["inputs"]["parameters"]
        output_schema = parameters["body/outputSchema"]
        expected_schema = json.loads(DECISION_OUTPUT_SCHEMA.read_text(encoding="utf-8"))
        self.assertIn("読み取り専用ベンチマーク", parameters["body/prompt"])
        self.assertEqual(output_schema, expected_schema)
        self.assertEqual(
            properties["connectionReferences"]["shared_agentnode"]["connection"]
            ["connectionReferenceLogicalName"],
            "new_sharedagentnode_c6fa5",
        )
        self.assertEqual(
            properties["connectionReferences"]["shared_commondataserviceforapps"]
            ["connection"]["connectionReferenceLogicalName"],
            "ds_shared_commondataserviceforapps",
        )

        serialized = json.dumps(exported).lower()
        for forbidden in ("flowtriggeruri", "sig=", "access_token", "refresh_token"):
            self.assertNotIn(forbidden, serialized)

    def test_solution_export_uses_power_apps_v2_and_reads_application(self) -> None:
        exported = json.loads(SOLUTION_EXPORT.read_text(encoding="utf-8"))
        definition = exported["properties"]["definition"]
        trigger = definition["triggers"]["manual"]
        self.assertEqual(trigger["kind"], "PowerAppV2")
        trigger_schema = trigger["inputs"]["schema"]
        expected = {
            "text": "applicationId",
            "text_1": "resources",
            "text_2": "conversation",
            "text_3": "similarCases",
            "text_4": "decisionOptions",
            "text_5": "categoryRegulation",
        }

        self.assertEqual(trigger_schema["required"], list(expected))
        self.assertEqual(
            {name: spec["title"] for name, spec in trigger_schema["properties"].items()},
            expected,
        )

        actions = definition["actions"]
        get_application = actions["Get_application"]
        self.assertEqual(
            get_application["inputs"]["host"]["operationId"],
            "GetItem",
        )
        self.assertEqual(
            get_application["inputs"]["parameters"],
            {
                "entityName": "ds_applications",
                "recordId": "@triggerBody()?['text']",
                "$select": (
                    "ds_applicationid,ds_name,ds_body,ds_stage,ds_duedate,"
                    "ds_submittedat,_ds_categoryid_value"
                ),
            },
        )

        agent = actions["Run_an_agent"]
        self.assertEqual(agent["runAfter"], {"Get_application": ["SUCCEEDED"]})
        prompt = agent["inputs"]["parameters"]["body/prompt"]
        for expression in (
            "@{outputs('Get_application')?['body/ds_name']}",
            "@{coalesce(outputs('Get_application')?['body/ds_body'], '')}",
            "@{outputs('Get_application')?['body/ds_stage']}",
            "@{coalesce(outputs('Get_application')?['body/ds_duedate'], '未設定')}",
        ):
            self.assertIn(expression, prompt)
        self.assertNotIn("@{triggerBody()?['text']}\n", prompt)
        for name in list(expected)[1:]:
            self.assertIn(f"@{{triggerBody()?['{name}']}}", prompt)

    def test_solution_export_contains_no_dataverse_write_action(self) -> None:
        exported = json.loads(SOLUTION_EXPORT.read_text(encoding="utf-8"))
        actions = exported["properties"]["definition"]["actions"]
        forbidden_prefixes = ("create", "update", "delete", "upsert", "relate")
        for action in actions.values():
            operation_id = action.get("inputs", {}).get("host", {}).get(
                "operationId", ""
            )
            self.assertFalse(operation_id.lower().startswith(forbidden_prefixes))


if __name__ == "__main__":
    unittest.main()
