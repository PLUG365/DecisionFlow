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

        condition_json = json.dumps(if_submitted["expression"], ensure_ascii=False)
        self.assertIn("ds_stage", condition_json)
        self.assertNotIn("ds_aidecisionupdatedat", trigger["inputs"]["parameters"]["subscriptionRequest/filteringattributes"])
        actions = if_submitted["actions"]
        self.assertEqual(actions["Get_decider"]["inputs"]["host"]["operationId"], "GetItem")
        self.assertEqual(actions["List_participants"]["inputs"]["host"]["operationId"], "ListRecords")
        self.assertEqual(actions["List_participants"]["inputs"]["parameters"]["$select"], "ds_participantid,_ds_userid_value")
        self.assertIn("Notify_participants", actions)
        self.assertEqual(
            actions["If_decider_has_email"]["actions"]["If_decider_has_email_send"]["inputs"]["host"]["operationId"],
            "SendEmailV2",
        )

    def test_application_submitted_participant_notifications_skip_decider(self):
        clientdata = _clientdata(flows.build_application_submitted_clientdata(CONNECTION_REFS, "ds"))
        actions = clientdata["properties"]["definition"]["actions"]["If_submitted"]["actions"]
        notify_participants = actions["Notify_participants"]["actions"]

        self.assertIn("If_participant_is_not_decider", notify_participants)
        skip_decider = notify_participants["If_participant_is_not_decider"]
        condition_json = json.dumps(skip_decider["expression"], ensure_ascii=False)
        self.assertIn("items('Notify_participants')?['_ds_userid_value']", condition_json)
        self.assertIn("triggerOutputs()?['body/_ds_deciderid_value']", condition_json)
        self.assertIn("toLower(coalesce", condition_json)
        self.assertIn("not", condition_json)
        self.assertIn("Get_participant_user", skip_decider["actions"])
        self.assertIn("If_participant_has_email", skip_decider["actions"])

    def test_application_submitted_email_resolves_deeplink_from_solution_environment_variable(self):
        previous_app_url = flows.DECISIONFLOW_APP_BASE_URL
        previous_app_id = flows.COPILOT_TEAMS_APP_ID
        try:
            flows.DECISIONFLOW_APP_BASE_URL = "https://apps.powerapps.com/play/decisionflow"
            flows.COPILOT_TEAMS_APP_ID = ""
            clientdata = _clientdata(flows.build_application_submitted_clientdata(CONNECTION_REFS, "ds"))
            actions = clientdata["properties"]["definition"]["actions"]["If_submitted"]["actions"]
            body = actions["If_decider_has_email"]["actions"]["If_decider_has_email_send"]["inputs"]["parameters"]["emailMessage/Body"]

            self.assertIn("申請を開く", body)
            self.assertIn("Get_DecisionFlow_App_Base_Url", body)
            self.assertIn("?deepLink=%2Fapplications%2F", body)
            self.assertIn("triggerOutputs()?['body/ds_applicationid']", body)
            self.assertNotIn("https://apps.powerapps.com/play/decisionflow", body)
            self.assertIn("teams.microsoft.com/l/chat/0/0", body)
            self.assertIn("Get_Copilot_Teams_App_Id", body)
            self.assertIn("List_DecisionFlow_App_Base_Url_Definition", actions)
            self.assertIn("Get_DecisionFlow_App_Base_Url", actions)
            self.assertIn("ds_DecisionFlowAppBaseUrl", json.dumps(actions["List_DecisionFlow_App_Base_Url_Definition"], ensure_ascii=False))
        finally:
            flows.DECISIONFLOW_APP_BASE_URL = previous_app_url
            flows.COPILOT_TEAMS_APP_ID = previous_app_id

    def test_application_submitted_email_keeps_runtime_deeplink_when_base_url_unset(self):
        previous_app_url = flows.DECISIONFLOW_APP_BASE_URL
        previous_app_id = flows.COPILOT_TEAMS_APP_ID
        try:
            flows.DECISIONFLOW_APP_BASE_URL = ""
            flows.COPILOT_TEAMS_APP_ID = ""
            clientdata = _clientdata(flows.build_application_submitted_clientdata(CONNECTION_REFS, "ds"))
            body = clientdata["properties"]["definition"]["actions"]["If_submitted"]["actions"]["If_decider_has_email"]["actions"]["If_decider_has_email_send"]["inputs"]["parameters"]["emailMessage/Body"]

            self.assertIn("申請を開く", body)
            self.assertIn("Get_DecisionFlow_App_Base_Url", body)
        finally:
            flows.DECISIONFLOW_APP_BASE_URL = previous_app_url
            flows.COPILOT_TEAMS_APP_ID = previous_app_id

    def test_stalled_reminder_email_resolves_deeplink_from_solution_environment_variable(self):
        previous_app_url = flows.DECISIONFLOW_APP_BASE_URL
        previous_app_id = flows.COPILOT_TEAMS_APP_ID
        try:
            flows.DECISIONFLOW_APP_BASE_URL = "https://apps.powerapps.com/play/decisionflow"
            flows.COPILOT_TEAMS_APP_ID = ""
            clientdata = _clientdata(flows.build_stalled_reminder_clientdata(CONNECTION_REFS, "ds"))
            condition = clientdata["properties"]["definition"]["actions"]["For_each_submitted_application"]["actions"]["If_stalled_and_has_decider"]
            body = condition["actions"]["If_decider_has_email"]["actions"]["If_decider_has_email_send"]["inputs"]["parameters"]["emailMessage/Body"]

            self.assertIn("申請を開く", body)
            self.assertIn("Get_DecisionFlow_App_Base_Url", body)
            self.assertNotIn("https://apps.powerapps.com/play/decisionflow", body)
            self.assertIn("ds_applicationid", body)
        finally:
            flows.DECISIONFLOW_APP_BASE_URL = previous_app_url
            flows.COPILOT_TEAMS_APP_ID = previous_app_id

    def test_decision_and_mention_emails_include_deeplink_when_base_url_set(self):
        previous_app_url = flows.DECISIONFLOW_APP_BASE_URL
        try:
            flows.DECISIONFLOW_APP_BASE_URL = "https://apps.powerapps.com/play/decisionflow"
            decision_clientdata = _clientdata(flows.build_decision_created_clientdata(CONNECTION_REFS, "ds"))
            mention_clientdata = _clientdata(flows.build_mention_created_clientdata(CONNECTION_REFS, "ds"))
            decision_body = decision_clientdata["properties"]["definition"]["actions"]["If_applicant_has_email"]["actions"]["If_applicant_has_email_send"]["inputs"]["parameters"]["emailMessage/Body"]
            mention_body = mention_clientdata["properties"]["definition"]["actions"]["If_unread_mention"]["actions"]["If_target_has_email"]["actions"]["If_target_has_email_send"]["inputs"]["parameters"]["emailMessage/Body"]

            self.assertIn("申請を開く", decision_body)
            self.assertIn("Get_DecisionFlow_App_Base_Url", decision_body)
            self.assertNotIn("https://apps.powerapps.com/play/decisionflow", decision_body)
            self.assertIn("triggerOutputs()?['body/_ds_applicationid_value']", decision_body)

            self.assertIn("申請を開く", mention_body)
            self.assertIn("Get_DecisionFlow_App_Base_Url", mention_body)
            self.assertNotIn("https://apps.powerapps.com/play/decisionflow", mention_body)
            self.assertIn("outputs('Get_message')?['body/_ds_applicationid_value']", mention_body)
        finally:
            flows.DECISIONFLOW_APP_BASE_URL = previous_app_url

    def test_decision_and_mention_emails_keep_runtime_deeplink_when_base_url_unset(self):
        previous_app_url = flows.DECISIONFLOW_APP_BASE_URL
        try:
            flows.DECISIONFLOW_APP_BASE_URL = ""
            decision_clientdata = _clientdata(flows.build_decision_created_clientdata(CONNECTION_REFS, "ds"))
            mention_clientdata = _clientdata(flows.build_mention_created_clientdata(CONNECTION_REFS, "ds"))
            decision_body = decision_clientdata["properties"]["definition"]["actions"]["If_applicant_has_email"]["actions"]["If_applicant_has_email_send"]["inputs"]["parameters"]["emailMessage/Body"]
            mention_body = mention_clientdata["properties"]["definition"]["actions"]["If_unread_mention"]["actions"]["If_target_has_email"]["actions"]["If_target_has_email_send"]["inputs"]["parameters"]["emailMessage/Body"]

            self.assertIn("申請を開く", decision_body)
            self.assertIn("申請を開く", mention_body)
            self.assertIn("Get_DecisionFlow_App_Base_Url", decision_body)
            self.assertIn("Get_DecisionFlow_App_Base_Url", mention_body)
        finally:
            flows.DECISIONFLOW_APP_BASE_URL = previous_app_url

    def test_application_submitted_email_resolves_copilot_deep_link_from_solution_environment_variable(self):
        previous_app_id = flows.COPILOT_TEAMS_APP_ID
        previous_app_url = flows.DECISIONFLOW_APP_BASE_URL
        try:
            flows.COPILOT_TEAMS_APP_ID = "bot-app-id"
            flows.DECISIONFLOW_APP_BASE_URL = "https://apps.powerapps.com/play/decisionflow"
            clientdata = _clientdata(flows.build_application_submitted_clientdata(CONNECTION_REFS, "ds"))
            actions = clientdata["properties"]["definition"]["actions"]["If_submitted"]["actions"]
            body = actions["If_decider_has_email"]["actions"]["If_decider_has_email_send"]["inputs"]["parameters"]["emailMessage/Body"]

            self.assertIn("teams.microsoft.com/l/chat/0/0", body)
            self.assertIn("Get_Copilot_Teams_App_Id", body)
            self.assertIn("startsWith(outputs('Get_Copilot_Teams_App_Id'),'28:')", body)
            self.assertIn("encodeUriComponent", body)
            self.assertNotIn("bot-app-id", body)
            self.assertNotIn("https://apps.powerapps.com/play/decisionflow", body)
            self.assertIn("List_Copilot_Teams_App_Id_Definition", actions)
            self.assertIn("ds_CopilotTeamsAppId", json.dumps(actions["List_Copilot_Teams_App_Id_Definition"], ensure_ascii=False))
        finally:
            flows.COPILOT_TEAMS_APP_ID = previous_app_id
            flows.DECISIONFLOW_APP_BASE_URL = previous_app_url

    def test_decision_created_flow_notifies_applicant_and_participants(self):
        clientdata = _clientdata(flows.build_decision_created_clientdata(CONNECTION_REFS, "ds"))
        definition = clientdata["properties"]["definition"]
        trigger = definition["triggers"]["When_decision_created"]

        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/message"], 1)
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/entityname"], "ds_decision")
        actions = definition["actions"]
        self.assertEqual(actions["Get_application"]["inputs"]["parameters"]["entityName"], "ds_applications")
        self.assertIn("ds_stage", actions["Get_application"]["inputs"]["parameters"]["$select"])
        self.assertEqual(actions["Get_decision_option"]["inputs"]["parameters"]["entityName"], "ds_decisionoptions")
        self.assertEqual(actions["Get_applicant"]["runAfter"], {"Get_application": ["Succeeded"]})
        self.assertEqual(actions["Get_decision_option"]["runAfter"], {"Get_applicant": ["Succeeded"]})
        self.assertEqual(actions["List_participants"]["runAfter"], {"Clear_submitted_at_if_returned_to_draft": ["Succeeded"]})
        self.assertIn("If_applicant_has_email", actions)
        self.assertEqual(
            actions["If_applicant_has_email"]["runAfter"],
            {"Grant_decision_access_to_participants": ["Succeeded"], "Get_DecisionFlow_App_Base_Url": ["Succeeded"]},
        )
        self.assertIn("Notify_participants", actions)
        participant_get = actions["Notify_participants"]["actions"]["Get_participant_user"]
        self.assertEqual(
            actions["Notify_participants"]["runAfter"],
            {"If_applicant_has_email": ["Succeeded"], "Get_DecisionFlow_App_Base_Url": ["Succeeded"]},
        )
        self.assertEqual(participant_get["inputs"]["parameters"]["recordId"], "@items('Notify_participants')?['_ds_userid_value']")

    def test_decision_created_flow_grants_decision_read_access_to_applicant_and_participants(self):
        clientdata = _clientdata(flows.build_decision_created_clientdata(CONNECTION_REFS, "ds"))
        actions = clientdata["properties"]["definition"]["actions"]

        applicant_payload = actions["Build_grant_decision_access_to_applicant_payload"]
        self.assertEqual(applicant_payload["type"], "Compose")
        self.assertEqual(applicant_payload["runAfter"], {"List_participants": ["Succeeded"]})
        applicant_item = applicant_payload["inputs"]
        self.assertEqual(applicant_item["Target"]["@@odata.type"], "Microsoft.Dynamics.CRM.ds_decision")
        self.assertEqual(applicant_item["Target"]["ds_decisionid"], "@triggerOutputs()?['body/ds_decisionid']")
        self.assertEqual(applicant_item["PrincipalAccess"]["Principal"]["systemuserid"], "@outputs('Get_application')?['body/_createdby_value']")
        self.assertEqual(applicant_item["PrincipalAccess"]["AccessMask"], "ReadAccess")

        grant_applicant = actions["Grant_decision_access_to_applicant"]
        self.assertEqual(grant_applicant["runAfter"], {"Build_grant_decision_access_to_applicant_payload": ["Succeeded"]})
        self.assertEqual(grant_applicant["inputs"]["host"]["operationId"], "PerformUnboundAction")
        self.assertEqual(grant_applicant["inputs"]["parameters"]["actionName"], "GrantAccess")

        participant_loop = actions["Grant_decision_access_to_participants"]
        self.assertEqual(participant_loop["type"], "Foreach")
        self.assertEqual(participant_loop["runAfter"], {"Grant_decision_access_to_applicant": ["Succeeded"]})
        participant_actions = participant_loop["actions"]
        participant_payload = participant_actions["Build_grant_decision_access_to_participant_payload"]
        self.assertEqual(participant_payload["inputs"]["PrincipalAccess"]["Principal"]["systemuserid"], "@items('Grant_decision_access_to_participants')?['_ds_userid_value']")
        self.assertEqual(participant_payload["inputs"]["PrincipalAccess"]["AccessMask"], "ReadAccess")
        self.assertEqual(participant_actions["Grant_decision_access_to_participant"]["inputs"]["parameters"]["actionName"], "GrantAccess")

        self.assertEqual(actions["If_applicant_has_email"]["runAfter"], {"Grant_decision_access_to_participants": ["Succeeded"], "Get_DecisionFlow_App_Base_Url": ["Succeeded"]})

    def test_decision_created_flow_reconciles_application_stage_before_notifications(self):
        clientdata = _clientdata(flows.build_decision_created_clientdata(CONNECTION_REFS, "ds"))
        actions = clientdata["properties"]["definition"]["actions"]

        self.assertIn("Derive_next_application_stage", actions)
        self.assertIn("If_application_stage_needs_update", actions)
        self.assertIn("Clear_submitted_at_if_returned_to_draft", actions)

        derive_stage = actions["Derive_next_application_stage"]
        self.assertEqual(derive_stage["type"], "Compose")
        derive_json = json.dumps(derive_stage["inputs"], ensure_ascii=False)
        self.assertIn("Get_decision_option", derive_json)
        self.assertIn("差し戻し", derive_json)
        self.assertIn("100000000", derive_json)
        self.assertIn("100000004", derive_json)

        reconcile_condition = actions["If_application_stage_needs_update"]
        self.assertEqual(reconcile_condition["runAfter"], {"Derive_next_application_stage": ["Succeeded"]})
        condition_json = json.dumps(reconcile_condition["expression"], ensure_ascii=False)
        self.assertIn("Get_application", condition_json)
        self.assertIn("ds_stage", condition_json)
        self.assertIn("Derive_next_application_stage", condition_json)

        update_stage = reconcile_condition["actions"]["Update_application_stage"]
        self.assertEqual(update_stage["inputs"]["host"]["operationId"], "UpdateRecord")
        self.assertEqual(update_stage["inputs"]["parameters"]["entityName"], "ds_applications")
        self.assertEqual(update_stage["inputs"]["parameters"]["recordId"], "@triggerOutputs()?['body/_ds_applicationid_value']")
        self.assertEqual(update_stage["inputs"]["parameters"]["item"]["ds_stage"], "@outputs('Derive_next_application_stage')")

        clear_submitted_at = actions["Clear_submitted_at_if_returned_to_draft"]
        self.assertEqual(clear_submitted_at["runAfter"], {"If_application_stage_needs_update": ["Succeeded"]})
        clear_json = json.dumps(clear_submitted_at, ensure_ascii=False)
        self.assertIn("100000000", clear_json)
        self.assertIn("ds_submittedat", clear_json)

        self.assertEqual(actions["List_participants"]["runAfter"], {"Clear_submitted_at_if_returned_to_draft": ["Succeeded"]})
        self.assertEqual(
            actions["If_applicant_has_email"]["runAfter"],
            {"Grant_decision_access_to_participants": ["Succeeded"], "Get_DecisionFlow_App_Base_Url": ["Succeeded"]},
        )

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

    def test_stalled_reminder_email_resolves_copilot_deep_link_from_solution_environment_variable(self):
        previous_app_id = flows.COPILOT_TEAMS_APP_ID
        try:
            flows.COPILOT_TEAMS_APP_ID = "28:already-prefixed"
            clientdata = _clientdata(flows.build_stalled_reminder_clientdata(CONNECTION_REFS, "ds"))
            condition = clientdata["properties"]["definition"]["actions"]["For_each_submitted_application"]["actions"]["If_stalled_and_has_decider"]
            body = condition["actions"]["If_decider_has_email"]["actions"]["If_decider_has_email_send"]["inputs"]["parameters"]["emailMessage/Body"]

            self.assertIn("teams.microsoft.com/l/chat/0/0", body)
            self.assertIn("Get_Copilot_Teams_App_Id", body)
            self.assertNotIn("28:already-prefixed", body)
            self.assertIn("推奨判断と判断コメントドラフト", body)
        finally:
            flows.COPILOT_TEAMS_APP_ID = previous_app_id

    def test_ensure_notification_environment_variables_upserts_solution_environment_definitions(self):
        existing = {"value": [{"environmentvariabledefinitionid": "existing-app-url"}]}
        created_response = unittest.mock.Mock(ok=True, headers={"OData-EntityId": "environmentvariabledefinitions(created-copilot-id)"})
        session = unittest.mock.Mock()
        session.headers = {}
        session.post.return_value = created_response

        with patch.object(flows, "api_get", side_effect=[existing, {"value": []}]) as api_get, patch.object(flows, "get_session", return_value=session):
            flows.ensure_notification_environment_variables("ds")

        self.assertEqual(api_get.call_count, 2)
        self.assertIn("ds_DecisionFlowAppBaseUrl", api_get.call_args_list[0].args[0])
        self.assertIn("ds_CopilotTeamsAppId", api_get.call_args_list[1].args[0])
        self.assertEqual(session.post.call_count, 1)
        body = session.post.call_args.kwargs["json"]
        self.assertEqual(body["schemaname"], "ds_CopilotTeamsAppId")
        self.assertEqual(body["type"], 100000000)

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

    def test_find_connections_prefers_oauth_connection_from_admin_scope(self):
        stale_connection = {
            "name": "stale-dataverse-connection",
            "properties": {
                "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                "statuses": [{"status": "Connected"}],
                "connectionParametersSet": {"values": {}},
                "createdTime": "2026-05-04T00:00:00Z",
            },
        }
        oauth_connection = {
            "name": "oauth-dataverse-connection",
            "properties": {
                "apiId": "/providers/Microsoft.PowerApps/apis/shared_commondataserviceforapps",
                "statuses": [{"status": "Connected"}],
                "connectionParametersSet": {"values": {"token:grantType": {"value": "code"}}},
                "createdTime": "2026-05-03T00:00:00Z",
            },
        }
        outlook_connection = {
            "name": "outlook-connection",
            "properties": {
                "apiId": "/providers/Microsoft.PowerApps/apis/shared_office365",
                "statuses": [{"status": "Connected"}],
                "connectionParametersSet": {"values": {}},
            },
        }

        with patch.object(
            flows,
            "_powerapps_get",
            return_value={"value": [stale_connection, oauth_connection, outlook_connection]},
        ):
            names = flows.find_connections("env-id", "shared_commondataserviceforapps")

        self.assertEqual(names[0], "oauth-dataverse-connection")
        self.assertNotIn("outlook-connection", names)


if __name__ == "__main__":
    unittest.main()
