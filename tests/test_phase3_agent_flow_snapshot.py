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


if __name__ == "__main__":
    unittest.main()
