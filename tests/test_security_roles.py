import unittest

from scripts import setup_dataverse as schema
from scripts import setup_security_roles as roles


class SecurityRoleDefinitionsTest(unittest.TestCase):
    def test_delegation_schema_has_separate_request_and_append_only_history_tables(self):
        tables = {table["logical"]: table for table in schema.TABLES}
        self.assertIn("ds_delegationrequest", tables)
        self.assertIn("ds_delegationhistory", tables)

        request_columns = {column["logical"] for column in tables["ds_delegationrequest"]["columns"]}
        history_columns = {column["logical"] for column in tables["ds_delegationhistory"]["columns"]}
        self.assertEqual(request_columns, {"ds_status", "ds_processedat", "ds_resultmessage"})
        self.assertEqual(history_columns, {"ds_result", "ds_detail", "ds_processedat"})

        lookups = {(item["referencing"], item["lookup_attr"]) for item in schema.LOOKUPS}
        self.assertIn(("ds_delegationrequest", "ds_applicationid"), lookups)
        self.assertIn(("ds_delegationrequest", "ds_requesteddeciderid"), lookups)
        self.assertIn(("ds_delegationrequest", "ds_previousdeciderid"), lookups)
        self.assertIn(("ds_delegationhistory", "ds_delegationrequestid"), lookups)
        self.assertIn(("ds_delegationhistory", "ds_actorid"), lookups)
        self.assertIn(("ds_delegationhistory", "ds_previousdeciderid"), lookups)
        self.assertIn(("ds_delegationhistory", "ds_newdeciderid"), lookups)

        request_application = next(
            item for item in schema.LOOKUPS
            if item["referencing"] == "ds_delegationrequest" and item["lookup_attr"] == "ds_applicationid"
        )
        request_decider = next(
            item for item in schema.LOOKUPS
            if item["referencing"] == "ds_delegationrequest" and item["lookup_attr"] == "ds_requesteddeciderid"
        )
        self.assertEqual(request_application["required_level"], "ApplicationRequired")
        self.assertEqual(request_decider["required_level"], "ApplicationRequired")

    def test_defines_decisionflow_roles(self):
        role_names = {role["name"] for role in roles.ROLE_DEFINITIONS}
        self.assertEqual(role_names, {"ds_Applicant", "ds_Decider", "ds_Admin"})

    def test_master_tables_are_readable_and_appendto_for_applicant(self):
        applicant = roles.role_by_name("ds_Applicant")
        for table in ["ds_category", "ds_decisionoption"]:
            privileges = roles.privileges_for_table(applicant, table)
            self.assertEqual(privileges["Read"], "Global")
            self.assertEqual(privileges["AppendTo"], "Global")
            self.assertIsNone(privileges["Create"])
            self.assertIsNone(privileges["Write"])
            self.assertIsNone(privileges["Delete"])

    def test_applicant_can_delete_own_application_without_global_access(self):
        applicant = roles.role_by_name("ds_Applicant")
        privileges = roles.privileges_for_table(applicant, "ds_application")
        self.assertEqual(privileges["Create"], "Basic")
        self.assertEqual(privileges["Read"], "Basic")
        self.assertEqual(privileges["Write"], "Basic")
        self.assertEqual(privileges["Delete"], "Basic")

    def test_decider_can_read_all_decision_context(self):
        decider = roles.role_by_name("ds_Decider")
        for table in ["ds_application", "ds_message", "ds_applicationresource", "ds_participant"]:
            self.assertEqual(roles.privileges_for_table(decider, table)["Read"], "Global")
        participant = roles.privileges_for_table(decider, "ds_participant")
        self.assertEqual(participant["Delete"], "Basic")
        decision = roles.privileges_for_table(decider, "ds_decision")
        self.assertEqual(decision["Create"], "Basic")
        self.assertEqual(decision["Read"], "Global")
        self.assertEqual(decision["Write"], "Basic")

    def test_decider_can_write_categories_for_regulation_management(self):
        decider = roles.role_by_name("ds_Decider")
        privileges = roles.privileges_for_table(decider, "ds_category")

        self.assertEqual(privileges["Read"], "Global")
        self.assertEqual(privileges["Write"], "Global")
        self.assertEqual(privileges["AppendTo"], "Global")
        self.assertIsNone(privileges["Delete"])

    def test_admin_has_global_full_access(self):
        admin = roles.role_by_name("ds_Admin")
        privileges = roles.privileges_for_table(admin, "ds_application")
        for verb in roles.TABLE_VERBS:
            self.assertEqual(privileges[verb], "Global")

    def test_only_decider_can_create_delegation_requests_and_cannot_change_them(self):
        applicant = roles.role_by_name("ds_Applicant")
        decider = roles.role_by_name("ds_Decider")

        applicant_request = roles.privileges_for_table(applicant, "ds_delegationrequest")
        self.assertTrue(all(value is None for value in applicant_request.values()))

        request = roles.privileges_for_table(decider, "ds_delegationrequest")
        self.assertEqual(request["Create"], "Basic")
        self.assertEqual(request["Read"], "Basic")
        self.assertEqual(request["Append"], "Basic")
        self.assertIsNone(request["Write"])
        self.assertIsNone(request["Delete"])
        self.assertIsNone(request["Assign"])
        self.assertIsNone(request["Share"])

    def test_delegation_history_is_read_only_for_deciders_and_hidden_from_applicants(self):
        applicant = roles.role_by_name("ds_Applicant")
        decider = roles.role_by_name("ds_Decider")

        applicant_history = roles.privileges_for_table(applicant, "ds_delegationhistory")
        self.assertTrue(all(value is None for value in applicant_history.values()))

        history = roles.privileges_for_table(decider, "ds_delegationhistory")
        self.assertEqual(history["Read"], "Global")
        for verb in ["Create", "Write", "Delete", "Append", "Assign", "Share"]:
            self.assertIsNone(history[verb])

    def test_decider_group_team_is_manual(self):
        steps = roles.decider_group_team_manual_steps()
        joined = "\n".join(steps)
        self.assertIn("DecisionFlow-Deciders", joined)
        self.assertIn("ds_Decider", joined)
        self.assertIn("Power Platform admin center", joined)


if __name__ == "__main__":
    unittest.main()

