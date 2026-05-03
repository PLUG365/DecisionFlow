import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import deploy_ai_decision as ai_decision  # noqa: E402
import migrate_cleanup_old_ai_summary as old_ai_summary_cleanup  # noqa: E402
import setup_dataverse as setup_dataverse  # noqa: E402


class AiDecisionDataverseMetadataTests(unittest.TestCase):
    def test_application_table_defines_ai_decision_columns(self):
        application_table = next(
            table
            for table in setup_dataverse.TABLES
            if table["logical"] == "ds_application"
        )
        columns = {column["logical"]: column for column in application_table["columns"]}

        self.assertEqual(columns["ds_aiapplicationsummary"]["type"], "Memo")
        self.assertEqual(columns["ds_aiconversationsummary"]["type"], "Memo")
        self.assertEqual(columns["ds_aidecisionoptiontext"]["type"], "String")
        self.assertEqual(columns["ds_aidecisioncomment"]["type"], "Memo")
        self.assertEqual(columns["ds_aidecisionbasis"]["type"], "Memo")
        self.assertEqual(columns["ds_aidecisionupdatedat"]["type"], "DateTime")

    def test_application_table_does_not_define_legacy_ai_summary_columns(self):
        application_table = next(
            table
            for table in setup_dataverse.TABLES
            if table["logical"] == "ds_application"
        )
        columns = {column["logical"] for column in application_table["columns"]}

        self.assertNotIn("ds_aisummary", columns)
        self.assertNotIn("ds_summaryupdatedat", columns)

    def test_message_kind_options_do_not_include_legacy_ai_summary(self):
        values = {value for value, _label in setup_dataverse.MESSAGE_KIND_OPTIONS}
        labels = {label for _value, label in setup_dataverse.MESSAGE_KIND_OPTIONS}

        self.assertNotIn(100000004, values)
        self.assertNotIn("AISummary", labels)

    def test_old_ai_summary_cleanup_targets_legacy_metadata(self):
        self.assertEqual(
            old_ai_summary_cleanup.OBSOLETE_APPLICATION_COLUMNS,
            ["ds_aisummary", "ds_summaryupdatedat"],
        )
        self.assertEqual(old_ai_summary_cleanup.OBSOLETE_MESSAGE_KIND_VALUE, 100000004)


class AiDecisionPromptDefinitionTests(unittest.TestCase):
    def test_prompt_outputs_application_and_conversation_summary(self):
        output = ai_decision.AI_OUTPUT_DEFINITION
        properties = output["jsonSchema"]["properties"]

        self.assertIn("applicationSummary", properties)
        self.assertIn("conversationSummary", properties)
        self.assertIn("recommendedOption", properties)
        self.assertIn("comment", properties)
        self.assertIn("risks", properties)
        self.assertIn("similarCases", properties)

    def test_flow_uses_powerapp_v2_trigger_and_ai_builder_action(self):
        clientdata = json.loads(
            ai_decision.build_ai_decision_flow_clientdata(
                {"shared_commondataserviceforapps": "ds_shared_commondataserviceforapps"},
                "model-id",
                "ds",
            )
        )
        definition = clientdata["properties"]["definition"]

        self.assertEqual(definition["triggers"]["manual"]["kind"], "PowerAppV2")
        trigger_schema = definition["triggers"]["manual"]["inputs"]["schema"]
        self.assertEqual(trigger_schema["properties"]["text"]["title"], "applicationId")

        run_ai = definition["actions"]["Run_AI_Prompt"]
        self.assertEqual(run_ai["inputs"]["host"]["operationId"], "aibuilderpredict_customprompt")
        self.assertEqual(run_ai["inputs"]["parameters"]["recordId"], "model-id")
        self.assertIn("item/requestv2/application", run_ai["inputs"]["parameters"])

        similar = definition["actions"]["List_similar_applications"]
        self.assertEqual(similar["inputs"]["parameters"]["$top"], 30)
        self.assertIn("_ds_categoryid_value", similar["inputs"]["parameters"]["$filter"])
        self.assertNotIn("ds_body", similar["inputs"]["parameters"]["$select"])
        self.assertIn("ds_aiapplicationsummary", similar["inputs"]["parameters"]["$select"])

        recent = definition["actions"]["List_recent_decided_applications"]
        self.assertEqual(recent["inputs"]["parameters"]["$top"], 10)
        self.assertNotIn("ds_body", recent["inputs"]["parameters"]["$select"])

        prompt_inputs = definition["actions"]["Build_prompt_inputs"]
        self.assertIn("同一カテゴリ候補", prompt_inputs["inputs"]["similarCases"])
        self.assertIn("補助候補", prompt_inputs["inputs"]["similarCases"])

        update = definition["actions"]["Update_application_ai_decision"]
        item = update["inputs"]["parameters"]["item"]
        self.assertIn("ds_aiapplicationsummary", item)
        self.assertIn("ds_aiconversationsummary", item)
        self.assertIn("ds_aidecisionoptiontext", item)
        self.assertIn("ds_aidecisioncomment", item)
        self.assertIn("ds_aidecisionbasis", item)
        self.assertIn("ds_aidecisionupdatedat", item)


if __name__ == "__main__":
    unittest.main()