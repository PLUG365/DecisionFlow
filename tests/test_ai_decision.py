import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

AGENT_OUTPUT_SCHEMA = json.loads(
    (
        ROOT
        / "artifacts"
        / "agent-flows"
        / "DecisionFlow_Phase3_AgentNode_Harness"
        / "decision-output.schema.json"
    ).read_text(encoding="utf-8")
)

import deploy_ai_decision as ai_decision  # noqa: E402
import migrate_cleanup_old_ai_summary as old_ai_summary_cleanup  # noqa: E402
import setup_dataverse as setup_dataverse  # noqa: E402


class AiDecisionDataverseMetadataTests(unittest.TestCase):
    def test_category_table_defines_regulation_text_column(self):
        category_table = next(
            table
            for table in setup_dataverse.TABLES
            if table["logical"] == "ds_category"
        )
        columns = {column["logical"]: column for column in category_table["columns"]}

        self.assertEqual(columns["ds_regulationtext"]["type"], "Memo")
        self.assertEqual(columns["ds_regulationtext"]["display"], "レギュレーション")
        self.assertGreaterEqual(columns["ds_regulationtext"]["maxLength"], 50000)

    def test_decision_table_snapshots_ai_suggestion(self):
        decision_table = next(
            table
            for table in setup_dataverse.TABLES
            if table["logical"] == "ds_decision"
        )
        columns = {column["logical"]: column for column in decision_table["columns"]}

        # ds_application.ds_aidecisionoptiontext は AI 再生成で上書きされるため、
        # 判断時点の推奨を ds_decision 側へ控えないと採否率を後から測れない。
        self.assertEqual(columns["ds_aisuggestionatdecision"]["type"], "String")
        self.assertEqual(columns["ds_aisuggestionatdecision"]["display"], "判断時のAI推奨")

    def test_prompt_forbids_inventing_past_decision_reasons(self):
        constraints = "".join(
            segment["text"]
            for segment in ai_decision.PROMPT_SEGMENTS
            if segment["type"] == "literal"
        )

        self.assertIn("原文のまま引用", constraints)
        self.assertIn("推測した理由を書いてはならない", constraints)

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

        risks = properties["risks"]
        self.assertEqual(risks["type"], "array")
        self.assertEqual(risks["items"]["type"], "object")
        self.assertIn("category", risks["items"]["properties"])
        self.assertIn("detail", risks["items"]["properties"])

        example_risk = output["jsonExamples"][0]["risks"][0]
        self.assertIsInstance(example_risk, dict)
        self.assertIn("detail", example_risk)

    def test_agent_output_schema_matches_ai_builder_contract_and_is_strict(self):
        ai_properties = ai_decision.AI_OUTPUT_DEFINITION["jsonSchema"]["properties"]
        agent_properties = AGENT_OUTPUT_SCHEMA["properties"]

        self.assertEqual(set(agent_properties), set(ai_properties))
        self.assertEqual(set(AGENT_OUTPUT_SCHEMA["required"]), set(ai_properties))
        self.assertFalse(AGENT_OUTPUT_SCHEMA["additionalProperties"])

        for collection, required_fields in (
            ("risks", {"category", "detail"}),
            ("similarCases", {"title", "decision", "reason"}),
        ):
            agent_items = agent_properties[collection]["items"]
            ai_items = ai_properties[collection]["items"]
            self.assertEqual(
                set(agent_items["properties"]),
                set(ai_items["properties"]),
            )
            self.assertEqual(set(agent_items["required"]), required_fields)
            self.assertFalse(agent_items["additionalProperties"])

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
        self.assertIn("item/requestv2/categoryRegulation", run_ai["inputs"]["parameters"])

        category_regulation = definition["actions"]["List_category_regulation"]
        self.assertEqual(category_regulation["inputs"]["host"]["operationId"], "ListRecords")
        self.assertEqual(category_regulation["inputs"]["parameters"]["entityName"], "ds_categories")
        self.assertIn("ds_regulationtext", category_regulation["inputs"]["parameters"]["$select"])

        # 類似案件には申請本文そのものを渡す。AI 生成列は「AI が過去に出した推奨」
        # であって人が下した判断ではないため、類似案件の根拠にしてはいけない。
        similar = definition["actions"]["List_similar_applications"]
        self.assertEqual(similar["inputs"]["parameters"]["$top"], 30)
        self.assertIn("_ds_categoryid_value", similar["inputs"]["parameters"]["$filter"])
        self.assertIn("ds_body", similar["inputs"]["parameters"]["$select"])
        self.assertNotIn("ds_aiapplicationsummary", similar["inputs"]["parameters"]["$select"])
        self.assertNotIn("ds_aidecisionoptiontext", similar["inputs"]["parameters"]["$select"])

        # 実際の判断結果と理由は ds_decision にしかないので、そこから取得する。
        recent = definition["actions"]["List_recent_decisions"]
        self.assertEqual(recent["inputs"]["parameters"]["entityName"], "ds_decisions")
        self.assertIn("ds_rationale", recent["inputs"]["parameters"]["$select"])
        self.assertIn("ds_decidedat", recent["inputs"]["parameters"]["$select"])
        self.assertIn("ds_decisionoptionid(", recent["inputs"]["parameters"]["$expand"])
        self.assertIn("ds_applicationid(", recent["inputs"]["parameters"]["$expand"])
        self.assertNotIn("List_recent_decided_applications", definition["actions"])

        prompt_inputs = definition["actions"]["Build_prompt_inputs"]
        self.assertIn("同一カテゴリの過去申請", prompt_inputs["inputs"]["similarCases"])
        self.assertIn("過去の判断", prompt_inputs["inputs"]["similarCases"])
        self.assertIn("ds_rationale", prompt_inputs["inputs"]["similarCases"])
        self.assertIn("categoryRegulation", prompt_inputs["inputs"])
        self.assertIn("レギュレーション", prompt_inputs["inputs"]["categoryRegulation"])
        self.assertIn("利用文脈", prompt_inputs["inputs"]["application"])

        basis_json = definition["actions"]["Build_basis_json"]["inputs"]
        self.assertIn("json('[]')", basis_json)
        self.assertNotIn("createArray()", basis_json)
        self.assertIn("structuredOutput/recommendation/risks", basis_json)
        self.assertIn("structuredOutput/recommendation/similarCases", basis_json)
        self.assertIn("regulationContext", basis_json)
        self.assertIn("audience", basis_json)

        update = definition["actions"]["Update_application_ai_decision"]
        item = update["inputs"]["parameters"]["item"]
        self.assertIn("ds_aiapplicationsummary", item)
        self.assertIn("ds_aiconversationsummary", item)
        self.assertIn("ds_aidecisionoptiontext", item)
        self.assertIn("ds_aidecisioncomment", item)
        self.assertIn("ds_aidecisionbasis", item)
        self.assertIn("ds_aidecisionupdatedat", item)
        self.assertIn("structuredOutput/recommendation/applicationSummary", item["ds_aiapplicationsummary"])
        self.assertIn("structuredOutput/recommendation/recommendedDecision", item["ds_aidecisionoptiontext"])
        self.assertIn("structuredOutput/recommendation/suggestedDecision", item["ds_aidecisionoptiontext"])
        self.assertIn("structuredOutput/recommendation/recommendationReason", item["ds_aidecisioncomment"])

    def test_flow_does_not_create_regulation_history_or_snapshot_fields(self):
        application_table = next(
            table
            for table in setup_dataverse.TABLES
            if table["logical"] == "ds_application"
        )
        columns = {column["logical"] for column in application_table["columns"]}

        self.assertNotIn("ds_regulationhistory", columns)
        self.assertNotIn("ds_regulationsnapshot", columns)
        self.assertNotIn("ds_regulationtextsnapshot", columns)

    def test_default_categories_include_regulation_text_seed(self):
        categories = setup_dataverse.DEFAULT_CATEGORIES

        self.assertEqual(len(categories), 5)
        self.assertEqual(categories[0][0], "顧客案件")
        self.assertIn("顧客影響", categories[0][3])
        for category in categories:
            self.assertTrue(category[3].strip())
            self.assertIn("確認", category[3])


if __name__ == "__main__":
    unittest.main()
