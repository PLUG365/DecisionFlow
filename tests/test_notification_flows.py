import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import deploy_notification_flows as flows  # noqa: E402


CONNECTION_REFS = {
    "shared_commondataserviceforapps": "ds_shared_commondataserviceforapps",
    "shared_office365": "ds_shared_office365",
}


def _clientdata(raw: str) -> dict:
    return json.loads(raw)


class NotificationFlowDefinitionTests(unittest.TestCase):
    def test_application_submitted_flow_uses_create_or_update_trigger_and_outlook_notifications(self):
        clientdata = _clientdata(flows.build_application_submitted_clientdata(CONNECTION_REFS, "ds"))
        definition = clientdata["properties"]["definition"]
        trigger = definition["triggers"]["When_application_created_or_updated"]

        self.assertEqual(trigger["type"], "OpenApiConnectionWebhook")
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/message"], 4)
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/entityname"], "ds_application")
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/filteringattributes"], "ds_stage,ds_submittedat")

        if_submitted = definition["actions"]["If_submitted"]
        self.assertEqual(if_submitted["expression"], {"equals": ["@triggerOutputs()?['body/ds_stage']", 100000001]})
        actions = if_submitted["actions"]
        self.assertEqual(actions["Get_decider"]["inputs"]["host"]["operationId"], "GetItem")
        self.assertEqual(actions["List_participants"]["inputs"]["host"]["operationId"], "ListRecords")
        self.assertEqual(actions["List_participants"]["inputs"]["parameters"]["$select"], "ds_participantid,_ds_userid_value")
        self.assertIn("Notify_participants", actions)
        self.assertEqual(
            actions["If_decider_has_email"]["actions"]["If_decider_has_email_send"]["inputs"]["host"]["operationId"],
            "SendEmailV2",
        )

    def test_decision_created_flow_notifies_applicant_and_participants(self):
        clientdata = _clientdata(flows.build_decision_created_clientdata(CONNECTION_REFS, "ds"))
        definition = clientdata["properties"]["definition"]
        trigger = definition["triggers"]["When_decision_created"]

        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/message"], 1)
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/entityname"], "ds_decision")
        actions = definition["actions"]
        self.assertEqual(actions["Get_application"]["inputs"]["parameters"]["entityName"], "ds_applications")
        self.assertEqual(actions["Get_decision_option"]["inputs"]["parameters"]["entityName"], "ds_decisionoptions")
        self.assertEqual(actions["Get_applicant"]["runAfter"], {"Get_application": ["Succeeded"]})
        self.assertEqual(actions["Get_decision_option"]["runAfter"], {"Get_applicant": ["Succeeded"]})
        self.assertEqual(actions["List_participants"]["runAfter"], {"Get_decision_option": ["Succeeded"]})
        self.assertIn("If_applicant_has_email", actions)
        self.assertEqual(actions["If_applicant_has_email"]["runAfter"], {"List_participants": ["Succeeded"]})
        self.assertIn("Notify_participants", actions)
        participant_get = actions["Notify_participants"]["actions"]["Get_participant_user"]
        self.assertEqual(
            actions["Notify_participants"]["runAfter"],
            {"If_applicant_has_email": ["Succeeded"]},
        )
        self.assertEqual(participant_get["inputs"]["parameters"]["recordId"], "@items('Notify_participants')?['_ds_userid_value']")

    def test_mention_created_flow_notifies_target_user(self):
        clientdata = _clientdata(flows.build_mention_created_clientdata(CONNECTION_REFS, "ds"))
        definition = clientdata["properties"]["definition"]
        trigger = definition["triggers"]["When_mention_created"]

        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/message"], 1)
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/entityname"], "ds_mention")
        if_unread = definition["actions"]["If_unread_mention"]
        self.assertEqual(if_unread["expression"], {"equals": ["@triggerOutputs()?['body/ds_isread']", False]})
        actions = if_unread["actions"]
        self.assertEqual(actions["Get_target_user"]["inputs"]["parameters"]["recordId"], "@triggerOutputs()?['body/_ds_targetuserid_value']")
        self.assertEqual(actions["Get_application"]["inputs"]["parameters"]["recordId"], "@outputs('Get_message')?['body/_ds_applicationid_value']")
        self.assertIn("If_target_has_email", actions)

    def test_stalled_reminder_flow_uses_submitted_at_not_modified_on(self):
        clientdata = _clientdata(flows.build_stalled_reminder_clientdata(CONNECTION_REFS, "ds"))
        definition = clientdata["properties"]["definition"]
        trigger = definition["triggers"]["Every_day_at_9am_jst"]

        self.assertEqual(trigger["type"], "Recurrence")
        self.assertEqual(trigger["recurrence"]["frequency"], "Day")
        self.assertEqual(trigger["recurrence"]["timeZone"], "Tokyo Standard Time")

        actions = definition["actions"]
        list_action = actions["List_submitted_applications"]
        self.assertEqual(list_action["inputs"]["parameters"]["entityName"], "ds_applications")
        self.assertEqual(list_action["inputs"]["parameters"]["$filter"], "ds_stage eq 100000001")
        self.assertIn("ds_submittedat", list_action["inputs"]["parameters"]["$select"])
        self.assertNotIn("modifiedon", list_action["inputs"]["parameters"]["$select"])

        foreach = actions["For_each_submitted_application"]
        condition = foreach["actions"]["If_stalled_and_has_decider"]
        condition_json = json.dumps(condition["expression"], ensure_ascii=False)
        self.assertIn("ds_submittedat", condition_json)
        self.assertIn("ds_duedate", condition_json)
        self.assertNotIn("modifiedon", condition_json)
        self.assertIn("Get_decider", condition["actions"])
        self.assertIn("If_decider_has_email", condition["actions"])

    def test_teams_action_is_optional_and_uses_supported_parameters(self):
        previous_enabled = flows.ENABLE_TEAMS
        previous_group = flows.TEAMS_GROUP_ID
        previous_channel = flows.TEAMS_CHANNEL_ID
        try:
            flows.ENABLE_TEAMS = True
            flows.TEAMS_GROUP_ID = "team-id"
            flows.TEAMS_CHANNEL_ID = "channel-id"
            refs = {**CONNECTION_REFS, "shared_teams": "ds_shared_teams"}
            clientdata = _clientdata(flows.build_decision_created_clientdata(refs, "ds"))
            action = clientdata["properties"]["definition"]["actions"]["Post_to_Teams_channel"]
            params = action["inputs"]["parameters"]

            self.assertEqual(action["inputs"]["host"]["operationId"], "PostMessageToConversation")
            self.assertEqual(action["runAfter"], {"Notify_participants": ["Succeeded"]})
            self.assertEqual(params["poster"], "Flow bot")
            self.assertEqual(params["location"], "Channel")
            self.assertEqual(params["body/recipient/groupId"], "team-id")
            self.assertEqual(params["body/recipient/channelId"], "channel-id")
            self.assertIn("body/messageBody", params)
            self.assertNotIn("body/subject", params)
        finally:
            flows.ENABLE_TEAMS = previous_enabled
            flows.TEAMS_GROUP_ID = previous_group
            flows.TEAMS_CHANNEL_ID = previous_channel

    def test_start_deployed_flows_calls_flow_management_start_endpoint(self):
        deployed = {
            "Application_OnSubmitted": "flow-application",
            "Decision_OnCreated": "flow-decision",
        }

        with patch.object(flows, "flow_api_call", return_value={}) as api_call:
            flows.start_deployed_flows("env-id", deployed)

        api_call.assert_any_call(
            "POST",
            "/providers/Microsoft.ProcessSimple/environments/env-id/flows/flow-application/start",
            {},
        )
        api_call.assert_any_call(
            "POST",
            "/providers/Microsoft.ProcessSimple/environments/env-id/flows/flow-decision/start",
            {},
        )
        self.assertEqual(api_call.call_count, 2)

    def test_get_existing_notification_flows_returns_flow_name_to_workflow_id_map(self):
        with patch.object(
            flows,
            "api_get",
            return_value={
                "value": [
                    {"name": "Application_OnSubmitted", "workflowid": "flow-application"},
                    {"name": "Decision_OnCreated", "workflowid": "flow-decision"},
                    {"name": "Mention_OnCreated", "workflowid": "flow-mention"},
                    {"name": "Application_StalledReminder", "workflowid": "flow-stalled"},
                ]
            },
        ) as api_get:
            existing = flows.get_existing_notification_flows()

        self.assertEqual(
            existing,
            {
                "Application_OnSubmitted": "flow-application",
                "Decision_OnCreated": "flow-decision",
                "Mention_OnCreated": "flow-mention",
                "Application_StalledReminder": "flow-stalled",
            },
        )
        query = api_get.call_args.args[0]
        self.assertIn("Application_OnSubmitted", query)
        self.assertIn("Decision_OnCreated", query)
        self.assertIn("Mention_OnCreated", query)
        self.assertIn("Application_StalledReminder", query)


if __name__ == "__main__":
    unittest.main()