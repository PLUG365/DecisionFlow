import importlib
import json
import unittest


class ApplicationLinkFlowDefinitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = importlib.import_module("scripts.deploy_application_link_flow")
        self.clientdata = json.loads(self.module.build_application_link_flow_clientdata())
        self.definition = self.clientdata["properties"]["definition"]
        self.actions = self.definition["actions"]
        self.trigger = self.definition["triggers"]["manual"]

    def test_trigger_is_skills_with_required_application_id_input(self):
        self.assertEqual(self.trigger["type"], "Request")
        self.assertEqual(self.trigger["kind"], "Skills")

        properties = self.trigger["inputs"]["schema"]["properties"]
        self.assertEqual(set(properties), {"applicationId"})
        self.assertEqual(self.trigger["inputs"]["schema"]["required"], ["applicationId"])
        self.assertEqual(properties["applicationId"]["type"], "string")

    def test_resolves_app_base_url_environment_variable_at_runtime(self):
        definition_action = self.actions["List_DecisionFlow_App_Base_Url_Definition"]
        self.assertEqual(definition_action["inputs"]["host"]["operationId"], "ListRecords")
        self.assertEqual(definition_action["inputs"]["parameters"]["entityName"], "environmentvariabledefinitions")
        self.assertIn("ds_DecisionFlowAppBaseUrl", definition_action["inputs"]["parameters"]["$filter"])

        value_action = self.actions["List_DecisionFlow_App_Base_Url_Value"]
        self.assertEqual(value_action["inputs"]["parameters"]["entityName"], "environmentvariablevalues")
        self.assertIn(
            "List_DecisionFlow_App_Base_Url_Definition",
            value_action["inputs"]["parameters"]["$filter"],
        )

        compose_value = self.actions["Get_DecisionFlow_App_Base_Url"]
        self.assertEqual(compose_value["type"], "Compose")
        self.assertIn("coalesce", compose_value["inputs"])
        self.assertIn("defaultvalue", compose_value["inputs"])

    def test_compose_application_url_returns_empty_when_base_url_unset(self):
        compose_url = self.actions["Compose_ApplicationUrl"]
        self.assertEqual(compose_url["type"], "Compose")
        expression = compose_url["inputs"]
        self.assertIn("if(equals(outputs('Get_DecisionFlow_App_Base_Url'),'')", expression)
        self.assertIn("?deepLink=%2Fapplications%2F", expression)
        self.assertIn("triggerBody()?['applicationId']", expression)
        self.assertEqual(compose_url["runAfter"], {"Get_DecisionFlow_App_Base_Url": ["Succeeded"]})

    def test_response_returns_application_url_string(self):
        response = self.actions["Return_application_url"]
        self.assertEqual(response["type"], "Response")
        self.assertEqual(response["kind"], "Skills")
        self.assertEqual(response["runAfter"], {"Compose_ApplicationUrl": ["Succeeded"]})
        self.assertEqual(set(response["inputs"]["body"]), {"applicationUrl"})
        self.assertEqual(response["inputs"]["body"]["applicationUrl"], "@outputs('Compose_ApplicationUrl')")
        self.assertEqual(set(response["inputs"]["schema"]["properties"]), {"applicationUrl"})
        self.assertEqual(response["inputs"]["schema"]["properties"]["applicationUrl"]["type"], "string")

    def test_does_not_hardcode_environment_specific_app_url(self):
        actions_json = json.dumps(self.actions, ensure_ascii=False)
        self.assertNotIn("apps.powerapps.com/play", actions_json)

    def test_module_exposes_flow_metadata(self):
        self.assertEqual(self.module.APPLICATION_LINK_FLOW_NAME, "Get_ApplicationDetailUrl")
        self.assertIn("ds_DecisionFlowAppBaseUrl", self.module.APPLICATION_LINK_FLOW_DESCRIPTION)
        flow = self.module.application_link_flow_definition()
        self.assertEqual(flow["name"], "Get_ApplicationDetailUrl")
        self.assertTrue(flow["description"])
        self.assertTrue(flow["clientdata"])

    def test_clientdata_uses_dataverse_connection_reference(self):
        connection_refs = self.clientdata["properties"]["connectionReferences"]
        self.assertIn("shared_commondataserviceforapps", connection_refs)
        self.assertEqual(
            connection_refs["shared_commondataserviceforapps"]["connection"]["connectionReferenceLogicalName"],
            "ds_shared_commondataserviceforapps",
        )

    def test_deploy_application_link_flow_invokes_passed_deploy_function(self):
        captured: dict = {}

        def fake_deploy(name: str, description: str, clientdata: str) -> tuple[str, bool]:
            captured["name"] = name
            captured["description"] = description
            captured["clientdata"] = clientdata
            return ("workflow-id-123", True)

        workflow_id, active = self.module.deploy_application_link_flow(fake_deploy)
        self.assertEqual(workflow_id, "workflow-id-123")
        self.assertTrue(active)
        self.assertEqual(captured["name"], "Get_ApplicationDetailUrl")
        self.assertIn("ds_DecisionFlowAppBaseUrl", captured["description"])
        parsed = json.loads(captured["clientdata"])
        self.assertIn("Compose_ApplicationUrl", parsed["properties"]["definition"]["actions"])


if __name__ == "__main__":
    unittest.main()
