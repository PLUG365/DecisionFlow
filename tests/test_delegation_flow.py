import json
import unittest

from scripts import deploy_delegation_flow as flow


def definition() -> dict:
    return json.loads(flow.build_delegation_flow_clientdata())["properties"]["definition"]


class DelegationFlowDefinitionTests(unittest.TestCase):
    def test_trigger_is_serialized_create_only_webhook(self):
        trigger = definition()["triggers"]["When_delegation_request_created"]
        self.assertEqual(trigger["type"], "OpenApiConnectionWebhook")
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/message"], 1)
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/entityname"], "ds_delegationrequest")
        self.assertEqual(trigger["runtimeConfiguration"], {"concurrency": {"runs": 1}})

    def test_actor_comes_only_from_dataverse_createdby(self):
        raw = json.dumps(definition(), ensure_ascii=False)
        self.assertIn("triggerOutputs()?['body/_createdby_value']", raw)
        self.assertNotIn("actorUpn", raw)
        self.assertNotIn("actorAadObjectId", raw)

    def test_validation_checks_stage_current_decider_admin_and_target_group(self):
        actions = definition()["actions"]
        condition = actions["If_request_is_authorized_and_valid"]
        raw = json.dumps(condition["expression"], ensure_ascii=False)
        self.assertIn("ds_stage", raw)
        self.assertIn("_ds_deciderid_value", raw)
        self.assertIn("List_actor_admin_role", raw)
        self.assertIn("List_valid_requested_decider", raw)
        self.assertIn("100000001", raw)

        admin_filter = actions["List_actor_admin_role"]["inputs"]["parameters"]["$filter"]
        target_filter = actions["List_valid_requested_decider"]["inputs"]["parameters"]["$filter"]
        self.assertIn("ds_Admin", admin_filter)
        self.assertIn("DecisionFlow-Deciders", target_filter)
        self.assertIn("isdisabled eq false", target_filter)

    def test_success_updates_one_decider_then_writes_history_and_notifies(self):
        success = definition()["actions"]["If_request_is_authorized_and_valid"]["actions"]
        update = success["Update_application_decider"]
        self.assertEqual(update["inputs"]["parameters"]["entityName"], "ds_applications")
        self.assertEqual(update["inputs"]["host"]["operationId"], "UpdateOnlyRecord")
        self.assertEqual(
            set(update["inputs"]["parameters"]["item"]),
            {"ds_deciderid@odata.bind"},
        )
        history = success["Create_success_history"]
        self.assertEqual(history["inputs"]["parameters"]["entityName"], "ds_delegationhistories")
        item = history["inputs"]["parameters"]["item"]
        self.assertEqual(item["ds_result"], flow.HISTORY_SUCCEEDED)
        self.assertIn("ds_actorid@odata.bind", item)
        self.assertIn("ds_previousdeciderid@odata.bind", item)
        self.assertIn("ds_newdeciderid@odata.bind", item)
        self.assertIn("If_new_decider_has_email", success)
        self.assertIn("If_previous_decider_has_email", success)
        self.assertIn("If_applicant_has_email", success)

    def test_rejected_request_is_recorded_without_changing_application(self):
        rejected = definition()["actions"]["If_request_is_authorized_and_valid"]["else"]["actions"]
        self.assertNotIn("Update_application_decider", rejected)
        self.assertEqual(
            rejected["Update_request_rejected"]["inputs"]["parameters"]["item"]["ds_status"],
            flow.REJECTED,
        )
        self.assertEqual(
            rejected["Update_request_rejected"]["inputs"]["host"]["operationId"],
            "UpdateOnlyRecord",
        )
        self.assertNotIn(
            "ds_previousdeciderid@odata.bind",
            rejected["Update_request_rejected"]["inputs"]["parameters"]["item"],
        )
        self.assertEqual(
            rejected["Create_rejected_history"]["inputs"]["parameters"]["item"]["ds_result"],
            flow.HISTORY_REJECTED,
        )
        self.assertNotIn(
            "ds_previousdeciderid@odata.bind",
            rejected["Create_rejected_history"]["inputs"]["parameters"]["item"],
        )

    def test_connection_references_are_solution_embedded(self):
        clientdata = json.loads(flow.build_delegation_flow_clientdata())
        refs = clientdata["properties"]["connectionReferences"]
        self.assertEqual(refs["shared_commondataserviceforapps"]["runtimeSource"], "embedded")
        self.assertEqual(refs["shared_office365"]["runtimeSource"], "embedded")

    def test_definition_relies_on_save_time_authentication_injection(self):
        raw = json.dumps(definition(), ensure_ascii=False)
        self.assertNotIn('"authentication"', raw)


if __name__ == "__main__":
    unittest.main()
