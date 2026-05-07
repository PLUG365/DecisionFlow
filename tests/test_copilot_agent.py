import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import deploy_copilot_agent as agent  # noqa: E402


class CopilotAgentDefinitionTests(unittest.TestCase):
    def test_extract_bot_id_accepts_guid_or_copilot_url(self):
        guid = "11111111-2222-3333-4444-555555555555"
        self.assertEqual(agent.extract_bot_id(guid), guid)
        self.assertEqual(agent.extract_bot_id(f"https://copilotstudio.microsoft.com/foo/bots/{guid}/overview"), guid)
        self.assertIsNone(agent.extract_bot_id("not-a-bot-id"))

    def test_gpt_yaml_uses_pva_double_newline_format_and_preserves_ai_settings(self):
        yaml_text = agent.build_gpt_yaml("kind: Old\n\naISettings:\n  model:\n    modelNameHint: Sonnet46\n")

        self.assertIn("kind: GptComponentMetadata\n\n", yaml_text)
        self.assertIn("displayName: DecisionFlow Assistant\n\n", yaml_text)
        self.assertIn("instructions: |-\n", yaml_text)
        self.assertIn("conversationStarters:\n\n", yaml_text)
        self.assertIn("aISettings:\n  model:\n    modelNameHint: Sonnet46", yaml_text)
        self.assertIn("判断待ち一覧", yaml_text)

    def test_conversation_start_contains_greeting_and_quick_replies(self):
        yaml_text = agent.build_conversation_start_yaml("id: sendMessage_existing")

        self.assertIn("id: sendMessage_existing", yaml_text)
        self.assertIn("DecisionFlow Assistant", yaml_text)
        self.assertIn("判断待ちの申請を一覧で教えて", yaml_text)
        self.assertIn("\n\n", yaml_text)

    def test_gpt_instructions_includes_app_url_section_when_set(self):
        previous = agent.DECISIONFLOW_APP_BASE_URL
        try:
            agent.DECISIONFLOW_APP_BASE_URL = "https://apps.powerapps.com/play/decisionflow"
            yaml_text = agent.build_gpt_yaml("")

            self.assertIn("申請詳細リンク", yaml_text)
            self.assertIn("https://apps.powerapps.com/play/decisionflow?deepLink=%2Fapplications%2F", yaml_text)
        finally:
            agent.DECISIONFLOW_APP_BASE_URL = previous

    def test_gpt_instructions_have_no_curly_brace_placeholders(self):
        """Copilot Studio は `{name}` を式ノードとして解釈し ContentValidationError になる。"""
        previous = agent.DECISIONFLOW_APP_BASE_URL
        try:
            agent.DECISIONFLOW_APP_BASE_URL = "https://apps.powerapps.com/play/decisionflow"
            instructions = agent.build_gpt_instructions()

            import re
            placeholders = re.findall(r"\{[A-Za-z_][A-Za-z0-9_.]*\}", instructions)
            self.assertEqual(
                placeholders,
                [],
                f"Curly-brace placeholders {placeholders} would be parsed as Power Fx expressions by Copilot Studio.",
            )
        finally:
            agent.DECISIONFLOW_APP_BASE_URL = previous

    def test_gpt_instructions_omits_app_url_section_when_unset(self):
        previous = agent.DECISIONFLOW_APP_BASE_URL
        try:
            agent.DECISIONFLOW_APP_BASE_URL = ""
            yaml_text = agent.build_gpt_yaml("")

            self.assertNotIn("申請詳細リンク", yaml_text)
        finally:
            agent.DECISIONFLOW_APP_BASE_URL = previous

    def test_deep_merge_preserves_existing_config(self):
        merged = agent.deep_merge(
            {"aISettings": {"model": {"modelNameHint": "Sonnet46"}}, "gPTSettings": {"defaultSchemaName": "abc"}},
            {"aISettings": {"optInUseLatestModels": False}},
        )

        self.assertEqual(merged["aISettings"]["model"]["modelNameHint"], "Sonnet46")
        self.assertFalse(merged["aISettings"]["optInUseLatestModels"])
        self.assertEqual(merged["gPTSettings"]["defaultSchemaName"], "abc")


if __name__ == "__main__":
    unittest.main()
