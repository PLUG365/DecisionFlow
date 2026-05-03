import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from deploy_access_flows import (  # noqa: E402
    build_grant_flow_clientdata,
    build_revoke_flow_clientdata,
    start_deployed_flows,
)


def _clientdata(raw: str) -> dict:
    return json.loads(raw)


class AccessFlowDefinitionTests(unittest.TestCase):
    def test_flow_uses_solution_connection_reference_not_embedded_connection(self):
        clientdata = _clientdata(build_grant_flow_clientdata("ds", "ds_shared_commondataserviceforapps"))
        connection_ref = clientdata["properties"]["connectionReferences"]["shared_commondataserviceforapps"]

        self.assertEqual(connection_ref["runtimeSource"], "embedded")
        self.assertEqual(
            connection_ref["connection"]["connectionReferenceLogicalName"],
            "ds_shared_commondataserviceforapps",
        )
        self.assertEqual(connection_ref["api"]["name"], "shared_commondataserviceforapps")
        self.assertNotIn("source", connection_ref)
        self.assertNotIn("connectionName", connection_ref)

    def test_grant_flow_uses_dataverse_create_webhook_and_grant_access_action(self):
        clientdata = _clientdata(build_grant_flow_clientdata("ds", "ds_shared_commondataserviceforapps"))
        definition = clientdata["properties"]["definition"]

        trigger = definition["triggers"]["When_participant_created"]
        self.assertEqual(trigger["type"], "OpenApiConnectionWebhook")
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/message"], 1)
        self.assertEqual(trigger["inputs"]["parameters"]["subscriptionRequest/entityname"], "ds_participant")

        payload_action = definition["actions"]["Build_grant_access_payload"]
        self.assertEqual(payload_action["type"], "Compose")
        item = payload_action["inputs"]
        self.assertEqual(item["Target"]["@@odata.type"], "Microsoft.Dynamics.CRM.ds_application")
        self.assertEqual(item["Target"]["ds_applicationid"], "@triggerOutputs()?['body/_ds_applicationid_value']")
        self.assertEqual(item["PrincipalAccess"]["Principal"]["@@odata.type"], "Microsoft.Dynamics.CRM.systemuser")
        self.assertEqual(item["PrincipalAccess"]["Principal"]["systemuserid"], "@triggerOutputs()?['body/_ds_userid_value']")
        access_mask = item["PrincipalAccess"]["AccessMask"]
        self.assertIn("ReadAccess", access_mask)
        self.assertIn("AppendToAccess", access_mask)

        grant_action = definition["actions"]["Grant_application_access"]
        self.assertEqual(grant_action["runAfter"], {"Build_grant_access_payload": ["Succeeded"]})
        self.assertEqual(grant_action["inputs"]["host"]["operationId"], "PerformUnboundAction")
        self.assertTrue(grant_action["inputs"]["parameters"]["actionName"].endswith("GrantAccess"))
        self.assertEqual(grant_action["inputs"]["parameters"]["item"], "@outputs('Build_grant_access_payload')")

    def test_revoke_flow_uses_powerapp_v2_inputs_and_response_schema(self):
        clientdata = _clientdata(build_revoke_flow_clientdata("ds", "ds_shared_commondataserviceforapps"))
        definition = clientdata["properties"]["definition"]

        trigger = definition["triggers"]["manual"]
        self.assertEqual(trigger["kind"], "PowerAppV2")

        schema = trigger["inputs"]["schema"]
        self.assertEqual(schema["required"], ["text", "text_1", "text_2"])
        self.assertEqual(schema["properties"]["text"]["title"], "participantId")
        self.assertEqual(schema["properties"]["text_1"]["title"], "applicationId")
        self.assertEqual(schema["properties"]["text_2"]["title"], "userId")
        self.assertEqual(schema["properties"]["text_2"]["x-ms-content-hint"], "TEXT")
        self.assertIs(schema["properties"]["text_2"]["x-ms-dynamically-added"], True)

        payload_action = definition["actions"]["Build_revoke_access_payload"]
        self.assertEqual(payload_action["type"], "Compose")
        item = payload_action["inputs"]
        self.assertEqual(
            item["Target"]["ds_applicationid"],
            "@triggerBody()?['text_1']",
        )
        self.assertEqual(item["Revokee"]["@@odata.type"], "Microsoft.Dynamics.CRM.systemuser")
        self.assertEqual(item["Revokee"]["systemuserid"], "@triggerBody()?['text_2']")

        revoke_action = definition["actions"]["Revoke_application_access"]
        self.assertEqual(revoke_action["runAfter"], {"Build_revoke_access_payload": ["Succeeded"]})
        self.assertEqual(revoke_action["inputs"]["host"]["operationId"], "PerformUnboundAction")
        self.assertTrue(revoke_action["inputs"]["parameters"]["actionName"].endswith("RevokeAccess"))
        self.assertEqual(revoke_action["inputs"]["parameters"]["item"], "@outputs('Build_revoke_access_payload')")

        response = definition["actions"]["Respond_success"]
        response_schema = response["inputs"]["schema"]
        self.assertEqual(response["kind"], "PowerApp")
        self.assertEqual(response_schema["properties"]["ok"]["x-ms-content-hint"], "TEXT")
        self.assertEqual(response_schema["additionalProperties"], {})

    def test_start_deployed_flows_calls_flow_management_start_endpoint(self):
        deployed = {
            "Participant_OnCreated_GrantAccess": "flow-grant",
            "Participant_PreDelete_RevokeAccess": "flow-revoke",
        }

        with patch("deploy_access_flows.flow_api_call", return_value={}) as api_call:
            start_deployed_flows("env-id", deployed)

        api_call.assert_any_call(
            "POST",
            "/providers/Microsoft.ProcessSimple/environments/env-id/flows/flow-grant/start",
            {},
        )
        api_call.assert_any_call(
            "POST",
            "/providers/Microsoft.ProcessSimple/environments/env-id/flows/flow-revoke/start",
            {},
        )
        self.assertEqual(api_call.call_count, 2)