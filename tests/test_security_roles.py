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


def _fake_tables() -> list[dict[str, str]]:
    return [
        {"logical_name": name, "schema_name": name}
        for name in roles.TABLE_LOGICAL_NAMES
    ]


def _fake_privilege_map() -> dict[str, dict[str, str]]:
    """`prv<Verb><Table>` の privilegeid が引けた状態を模す。"""
    return {
        table["logical_name"]: {
            verb: f"prv{verb}{table['logical_name']}" for verb in roles.TABLE_VERBS
        }
        for table in _fake_tables()
    }


class RolePrivilegeCompositionTest(unittest.TestCase):
    """
    ロールは DecisionFlow の11テーブル分だけを持ち、環境の `Basic User` を取り込まない。

    取り込むと移送元のベースラインを他テナントへ持ち込むことになり、深度の可否が
    環境で違う権限（`prvDeleteUserSettings` など）でソリューション import が落ちる。
    詳細は docs/UX_ROADMAP.md「ALM の実測ブロッカー」。
    """

    def _built(self, role_name: str) -> dict[str, str]:
        role_def = roles.role_by_name(role_name)
        built = roles.build_role_privileges(
            role_def, _fake_tables(), _fake_privilege_map()
        )
        return {item["PrivilegeId"]: item["Depth"] for item in built}

    def test_roles_carry_no_privileges_outside_the_decisionflow_tables(self):
        allowed = {
            f"prv{verb}{name}"
            for name in roles.TABLE_LOGICAL_NAMES
            for verb in roles.TABLE_VERBS
        }
        for role_name in ["ds_Applicant", "ds_Decider", "ds_Admin"]:
            with self.subTest(role=role_name):
                self.assertTrue(
                    set(self._built(role_name)).issubset(allowed),
                    "DecisionFlow のテーブル以外の権限が混ざっている",
                )

    def test_built_privileges_match_the_declared_depths_exactly(self):
        """変更前後で 11テーブル×verb の深度が一致することの担保。"""
        for role_name in ["ds_Applicant", "ds_Decider", "ds_Admin"]:
            role_def = roles.role_by_name(role_name)
            built = self._built(role_name)
            for name in roles.TABLE_LOGICAL_NAMES:
                declared = roles.privileges_for_table(role_def, name)
                for verb in roles.TABLE_VERBS:
                    privilege_id = f"prv{verb}{name}"
                    with self.subTest(role=role_name, table=name, verb=verb):
                        if declared[verb] is None:
                            self.assertNotIn(privilege_id, built)
                        else:
                            self.assertEqual(built[privilege_id], declared[verb])

    def test_applicant_gets_no_delegation_privileges_at_all(self):
        built = self._built("ds_Applicant")
        for name in ["ds_delegationrequest", "ds_delegationhistory"]:
            for verb in roles.TABLE_VERBS:
                with self.subTest(table=name, verb=verb):
                    self.assertNotIn(f"prv{verb}{name}", built)

    def test_a_table_whose_privilege_id_is_missing_is_skipped(self):
        privilege_map = _fake_privilege_map()
        privilege_map["ds_application"] = {}

        built = roles.build_role_privileges(
            roles.role_by_name("ds_Admin"), _fake_tables(), privilege_map
        )
        privilege_ids = {item["PrivilegeId"] for item in built}

        self.assertNotIn("prvReadds_application", privilege_ids)
        self.assertIn("prvReadds_message", privilege_ids)

    def test_privilege_count_stays_small_enough_for_one_batch(self):
        """
        `set_role_privileges` は先頭だけ ReplacePrivilegesRole で以降は Add。
        1バッチに収まる限り、途中失敗で「一部だけ入ったロール」は生じない。
        """
        for role_name in ["ds_Applicant", "ds_Decider", "ds_Admin"]:
            with self.subTest(role=role_name):
                self.assertLessEqual(len(self._built(role_name)), roles.PRIVILEGE_BATCH_SIZE)

    def test_the_basic_user_baseline_is_no_longer_read(self):
        self.assertFalse(
            hasattr(roles, "get_basic_user_privileges"),
            "ベースライン取り込みが残っている",
        )


if __name__ == "__main__":
    unittest.main()

