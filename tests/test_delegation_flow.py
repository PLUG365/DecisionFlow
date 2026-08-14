import json
import unittest

from scripts import deploy_delegation_flow as flow


def definition() -> dict:
    return json.loads(flow.build_delegation_flow_clientdata())["properties"]["definition"]


def _walk(node):
    """入れ子になった action を全部たどる。トップレベルの key だけ見ると内側を見落とす。"""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def _connectors(node) -> set[str]:
    return {
        host["connectionName"]
        for item in _walk(node)
        if isinstance(host := item.get("host"), dict) and "connectionName" in host
    }


def _written_entities(node) -> set[str]:
    return {
        params["entityName"]
        for item in _walk(node)
        if isinstance(params := item.get("parameters"), dict) and "entityName" in params
    }


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
        # 要求行 `ds_delegationrequest` 側は今回のスコープ外。据え置き。
        self.assertNotIn(
            "ds_previousdeciderid@odata.bind",
            rejected["Update_request_rejected"]["inputs"]["parameters"]["item"],
        )

    def test_rejected_history_keeps_previous_decider_only_when_it_is_known(self):
        """変更前担当が空のときだけ bind を落とす。空でないなら証跡に残す。

        空のまま `@concat('/systemusers(', '', ')')` を書くと bind が壊れ、
        拒否履歴の作成ごと失敗する。だからといって常に落とすと、
        **担当が実在した拒否**（実測4件はすべてこれ）の証跡まで捨てることになる。
        """
        outer = definition()["actions"]["If_request_is_authorized_and_valid"]
        gate = outer["else"]["actions"]["If_previous_decider_is_known"]
        self.assertEqual(gate["type"], "If")
        self.assertEqual(gate["runAfter"], {"Update_request_rejected": ["Succeeded"]})

        # ゲート式は検証条件そのものでなければならない。文字列の出現を見るだけだと
        # `not` を外して反転させても緑のまま通る（監査で実証された）。
        # 6条件のいずれかと**構造ごと一致**することを要求して、向きの取り違えを塞ぐ。
        self.assertIn(gate["expression"], outer["expression"]["and"])
        self.assertIn("_ds_deciderid_value", json.dumps(gate["expression"], ensure_ascii=False))
        self.assertIn("not", gate["expression"])

        known = gate["actions"]["Create_rejected_history"]["inputs"]["parameters"]["item"]
        unknown = gate["else"]["actions"]["Create_rejected_history_without_previous"]["inputs"]["parameters"]["item"]
        self.assertIn("ds_previousdeciderid@odata.bind", known)
        self.assertNotIn("ds_previousdeciderid@odata.bind", unknown)
        # 評価時点の不変条件: 履歴作成時に取り直さず、条件判定に使ったのと同じ出力を使う。
        self.assertIn("outputs('Get_application')", known["ds_previousdeciderid@odata.bind"])
        for item in (known, unknown):
            self.assertEqual(item["ds_result"], flow.HISTORY_REJECTED)
            self.assertIn("ds_actorid@odata.bind", item)
            self.assertIn("ds_newdeciderid@odata.bind", item)

    def test_rejected_branch_never_reassigns_or_notifies(self):
        """実測4件が担保していた不変条件。分岐を組み替えても壊さない。

        2026-08-12 の拒否4件は「申請の担当は不変・メール送信なし」で通っている。
        else 分岐に担当更新やメール送信が紛れ込めば、ここが落ちる。
        """
        rejected = definition()["actions"]["If_request_is_authorized_and_valid"]["else"]
        raw = json.dumps(rejected, ensure_ascii=False)
        # else が入れ子になったので、トップレベルの key だけを見ると内側をすり抜ける。
        self.assertNotIn("Update_application_decider", raw)
        self.assertNotIn("ds_deciderid@odata.bind", raw)

        # 「メールを送らない」を `SendEmailV2` という1文字列で見ると、v1 や Teams 投稿が
        # すり抜ける。**使ってよいコネクタは Dataverse だけ**という形で覆う。
        self.assertEqual(_connectors(rejected), {"shared_commondataserviceforapps"})
        # 申請テーブルへ書く action が1つも無いこと（bind 文字列ではなく操作対象で見る）。
        self.assertNotIn("ds_applications", _written_entities(rejected))

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
