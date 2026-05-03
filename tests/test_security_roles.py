import unittest

from scripts import setup_security_roles as roles


class SecurityRoleDefinitionsTest(unittest.TestCase):
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
        self.assertEqual(decision["Read"], "Basic")
        self.assertEqual(decision["Write"], "Basic")

    def test_admin_has_global_full_access(self):
        admin = roles.role_by_name("ds_Admin")
        privileges = roles.privileges_for_table(admin, "ds_application")
        for verb in roles.TABLE_VERBS:
            self.assertEqual(privileges[verb], "Global")

    def test_decider_group_team_is_manual(self):
        steps = roles.decider_group_team_manual_steps()
        joined = "\n".join(steps)
        self.assertIn("DecisionFlow-Deciders", joined)
        self.assertIn("ds_Decider", joined)
        self.assertIn("Power Platform admin center", joined)


if __name__ == "__main__":
    unittest.main()

