import importlib.util
import json
import unittest
from pathlib import Path

from scripts import setup_dataverse
from scripts import setup_security_roles


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "adaptive_card_decision_confirmation.json"
COPILOT_DIR = ROOT / "copilot" / "DecisionFlowAssistant"
DECISION_TOPIC_PATH = COPILOT_DIR / "topics" / "zdI.mcs.yml"


def table_by_logical(logical_name: str) -> dict:
    for table in setup_dataverse.TABLES:
        if table["logical"] == logical_name:
            return table
    raise AssertionError(f"Table not found: {logical_name}")


def find_action(actions: dict, name: str) -> dict:
    if name in actions:
        return actions[name]
    for action in actions.values():
        nested = action.get("actions")
        if isinstance(nested, dict):
            try:
                return find_action(nested, name)
            except AssertionError:
                pass
        else_actions = action.get("else", {}).get("actions") if isinstance(action.get("else"), dict) else None
        if isinstance(else_actions, dict):
            try:
                return find_action(else_actions, name)
            except AssertionError:
                pass
    raise AssertionError(f"Action not found: {name}")


def _flatten_topic_steps(steps: list) -> list[dict]:
    """トピック YAML のアクションを、ConditionGroup の中身まで含めて平らにする。"""
    flat = []
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        flat.append(step)
        for condition in step.get("conditions") or []:
            flat.extend(_flatten_topic_steps(condition.get("actions")))
        flat.extend(_flatten_topic_steps(step.get("elseActions")))
        flat.extend(_flatten_topic_steps(step.get("actions")))
    return flat


def flatten_actions(actions: dict) -> list[dict]:
    flattened = []
    for action in actions.values():
        flattened.append(action)
        nested = action.get("actions")
        if isinstance(nested, dict):
            flattened.extend(flatten_actions(nested))
        else_actions = action.get("else", {}).get("actions") if isinstance(action.get("else"), dict) else None
        if isinstance(else_actions, dict):
            flattened.extend(flatten_actions(else_actions))
    return flattened


class AdaptiveCardDecisionConfirmationFoundationTests(unittest.TestCase):
    def test_contract_fixture_uses_schema_15_action_submit_and_required_payload_fields(self):
        self.assertTrue(FIXTURE_PATH.exists(), "contract fixture is missing")
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(fixture["$schema"], "http://adaptivecards.io/schemas/adaptive-card.json")
        self.assertEqual(fixture["type"], "AdaptiveCard")
        self.assertEqual(fixture["version"], "1.5")

        submit_actions = [action for action in fixture.get("actions", []) if action.get("type") == "Action.Submit"]
        self.assertEqual(len(submit_actions), 1)
        submit_data = submit_actions[0]["data"]
        for field in ["action", "applicationId", "cardInstanceId"]:
            self.assertIn(field, submit_data)
        self.assertEqual(submit_data["action"], "confirm_decision")

        body_json = json.dumps(fixture.get("body", []), ensure_ascii=False)
        self.assertIn("decisionOption", body_json)
        self.assertIn("rationale", body_json)
        self.assertNotIn("Action.Execute", json.dumps(fixture, ensure_ascii=False))
        choice_set = next(item for item in fixture["body"] if item.get("id") == "decisionOption")
        self.assertEqual({choice["value"] for choice in choice_set["choices"]}, {"承認", "却下", "差し戻し"})
        self.assertNotIn("approvalDecisionOption", body_json)

    def test_decision_topic_guards_empty_adaptive_card_outputs_before_confirm_flow(self):
        """検査対象は push される topics/zdI.mcs.yml。

        以前は specs/ 配下のテンプレートを読んでいたが、正本が YAML へ移った時点で
        テンプレートはデプロイされない写しになっていた。実際に両者は
        `=Or(IsBlank(a), IsBlank(b))` と `=IsBlank(a) || IsBlank(b)` に分岐しており、
        テストは緑のまま「もう使われていないファイル」を守っていた。
        """
        self.assertTrue(DECISION_TOPIC_PATH.exists(), "decision topic YAML is missing")
        topic_yaml = DECISION_TOPIC_PATH.read_text(encoding="utf-8")

        self.assertNotIn("id: askApplicationId", topic_yaml)
        self.assertIn("id: validateApplicationContext", topic_yaml)
        self.assertIn("=IsBlank(Topic.applicationId)", topic_yaml)
        self.assertIn("inputType:", topic_yaml)
        self.assertIn("applicationId:", topic_yaml)
        self.assertIn('actionSubmitId: "confirmDecisionSubmitId"', topic_yaml)
        self.assertIn("id: validateAdaptiveCardOutput", topic_yaml)
        self.assertIn("=IsBlank(Topic.decisionOption) || IsBlank(Topic.rationale)", topic_yaml)
        self.assertLess(
            topic_yaml.index("id: validateAdaptiveCardOutput"),
            topic_yaml.index("flowId: f8502159-9153-f111-a824-3833c5de99c8"),
        )
        self.assertIn("decisionOption: =Topic.decisionOption", topic_yaml)

    def test_decision_topic_binds_the_actor_from_authenticated_user_variables(self):
        # actorUpn / actorAadObjectId がモデルの出力から埋まると、他人の名前で
        # 判断が確定される。Validate_actor_is_decider は渡された実行者を見るだけなので、
        # 作文された実行者がそのまま判断者として通る。
        topic_yaml = DECISION_TOPIC_PATH.read_text(encoding="utf-8")

        self.assertIn("variable: Topic.actorUpn", topic_yaml)
        self.assertIn("value: =System.User.PrincipalName", topic_yaml)
        self.assertIn("variable: Topic.actorAadObjectId", topic_yaml)
        self.assertIn("value: =System.User.Id", topic_yaml)

        inputs = topic_yaml.split("inputType:", 1)[1]
        self.assertNotIn("actorUpn", inputs)
        self.assertNotIn("actorAadObjectId", inputs)

    def test_decision_flows_are_not_registered_as_agent_tools(self):
        """ツール登録があると、生成オーケストレーションがトピックを迂回して直接呼ぶ。

        2026-08-08 に post_application_message で実測済み。判断確定はさらに悪く、
        issue_decision_card も登録されていると「作文した実行者でカードを発行し、
        同じ実行者で確定する」で6段目（Validate_current_issued_card）も通る。
        2本とも外して初めてトピックが唯一の入口になる。
        """
        for flow_name in ("issue_decision_card", "confirm_decision"):
            action_yaml = COPILOT_DIR / "actions" / f"{flow_name}.mcs.yml"
            self.assertFalse(
                action_yaml.exists(),
                f"{flow_name} をツール登録すると、判断確定トピックの実行者束縛が迂回される。",
            )

    def test_decision_topic_invokes_both_flows_by_flow_id(self):
        # ツール登録を外しても InvokeFlowAction は flowId 直指定で動く。
        topic_yaml = DECISION_TOPIC_PATH.read_text(encoding="utf-8")

        self.assertIn("flowId: c37ed747-9153-f111-a824-3833c5de99c8", topic_yaml)  # issue_decision_card
        self.assertIn("flowId: f8502159-9153-f111-a824-3833c5de99c8", topic_yaml)  # confirm_decision
        self.assertIn("actorAadObjectId: =Topic.actorAadObjectId", topic_yaml)
        self.assertIn("actorUpn: =Topic.actorUpn", topic_yaml)

    def test_ds_decisioncard_table_schema_is_declared(self):
        table = table_by_logical("ds_decisioncard")
        self.assertEqual(table["display"], "判断カード発行")
        columns = {column["logical"]: column for column in table["columns"]}

        self.assertEqual(columns["ds_cardinstanceid"]["type"], "String")
        self.assertEqual(columns["ds_actoraadobjectid"]["type"], "String")
        self.assertEqual(columns["ds_actorupn"]["type"], "String")
        self.assertEqual(columns["ds_issuedat"]["type"], "DateTime")
        self.assertEqual(columns["ds_consumedat"]["type"], "DateTime")
        self.assertEqual(columns["ds_supersededat"]["type"], "DateTime")

        status_options = columns["ds_status"]["options"]
        self.assertEqual(
            status_options,
            [
                (100000000, "Issued"),
                (100000001, "Consumed"),
                (100000002, "Superseded"),
                (100000003, "Expired"),
            ],
        )

    def test_ds_decisioncard_application_lookup_is_declared_with_cascade_share(self):
        matches = [
            lookup
            for lookup in setup_dataverse.LOOKUPS
            if lookup["referencing"] == "ds_decisioncard" and lookup["referenced"] == "ds_application"
        ]
        self.assertEqual(len(matches), 1)
        lookup = matches[0]
        self.assertEqual(lookup["lookup_attr"], "ds_applicationid")
        self.assertEqual(lookup["lookup_display"], "申請")
        self.assertTrue(lookup["cascade_share"])

    def test_security_roles_include_ds_decisioncard_privileges(self):
        self.assertIn("ds_decisioncard", setup_security_roles.TABLE_LOGICAL_NAMES)

        applicant = setup_security_roles.role_by_name("ds_Applicant")
        decider = setup_security_roles.role_by_name("ds_Decider")
        admin = setup_security_roles.role_by_name("ds_Admin")

        applicant_privileges = setup_security_roles.privileges_for_table(applicant, "ds_decisioncard")
        self.assertEqual(applicant_privileges["Read"], "Basic")
        self.assertIsNone(applicant_privileges["Create"])
        self.assertIsNone(applicant_privileges["Write"])

        decider_privileges = setup_security_roles.privileges_for_table(decider, "ds_decisioncard")
        self.assertEqual(decider_privileges["Create"], "Basic")
        self.assertEqual(decider_privileges["Read"], "Basic")
        self.assertEqual(decider_privileges["Write"], "Basic")
        self.assertEqual(decider_privileges["Append"], "Basic")
        self.assertEqual(decider_privileges["AppendTo"], "Basic")

        admin_privileges = setup_security_roles.privileges_for_table(admin, "ds_decisioncard")
        for verb in setup_security_roles.TABLE_VERBS:
            self.assertEqual(admin_privileges[verb], "Global")

    def test_shared_constants_module_defines_card_and_response_contract(self):
        spec = importlib.util.find_spec("scripts.decision_confirmation_constants")
        self.assertIsNotNone(spec, "scripts.decision_confirmation_constants is missing")
        constants = importlib.import_module("scripts.decision_confirmation_constants")

        self.assertEqual(constants.ALLOWED_DECISION_OPTION_LABELS, ("承認", "却下", "差し戻し"))
        self.assertEqual(constants.CARD_STATUS_ISSUED, 100000000)
        self.assertEqual(constants.CARD_STATUS_CONSUMED, 100000001)
        self.assertEqual(constants.CARD_STATUS_SUPERSEDED, 100000002)
        self.assertEqual(constants.CARD_STATUS_EXPIRED, 100000003)
        self.assertEqual(constants.RESPONSE_SUCCEEDED, "succeeded")
        self.assertEqual(constants.RESPONSE_ALREADY_PROCESSED, "already_processed")
        self.assertEqual(constants.RESPONSE_FORBIDDEN, "forbidden")
        self.assertEqual(constants.RESPONSE_INVALID_TARGET, "invalid_target")
        self.assertEqual(constants.SUBMITTED_STAGE, 100000001)
        self.assertEqual(constants.DRAFT_STAGE, 100000000)
        self.assertEqual(constants.DECIDED_STAGE, 100000004)

    def test_shared_validation_helpers_trim_and_require_submit_payload_values(self):
        constants = importlib.import_module("scripts.decision_confirmation_constants")

        self.assertEqual(constants.require_trimmed("rationale", "  判断します  "), "判断します")
        with self.assertRaises(ValueError):
            constants.require_trimmed("rationale", "   ")
        with self.assertRaises(ValueError):
            constants.require_trimmed("actor.upn", None)

        constants.validate_decision_option_label("承認")
        constants.validate_decision_option_label("却下")
        constants.validate_decision_option_label("差し戻し")
        with self.assertRaises(ValueError):
            constants.validate_decision_option_label("条件付き承認")

        payload = constants.validate_submit_payload(
            {
                "applicationId": " application-1 ",
                "decisionOption": " 承認 ",
                "rationale": " 承認します ",
                "cardInstanceId": " card-1 ",
                "actor": {
                    "aadObjectId": " aad-1 ",
                    "upn": " decider@example.com ",
                },
            }
        )
        self.assertEqual(payload["applicationId"], "application-1")
        self.assertEqual(payload["actor"]["upn"], "decider@example.com")

    def test_shared_validation_helpers_reject_missing_or_invalid_submit_values(self):
        constants = importlib.import_module("scripts.decision_confirmation_constants")

        valid_payload = {
            "applicationId": "application-1",
            "decisionOption": "承認",
            "rationale": "承認します",
            "cardInstanceId": "card-1",
            "actor": {"aadObjectId": "aad-1", "upn": "decider@example.com"},
        }

        for field in ["applicationId", "decisionOption", "rationale", "cardInstanceId"]:
            payload = dict(valid_payload)
            payload[field] = " "
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    constants.validate_submit_payload(payload)

        with self.assertRaises(ValueError):
            constants.validate_submit_payload({**valid_payload, "decisionOption": "条件付き承認"})
        with self.assertRaises(ValueError):
            constants.validate_submit_payload({**valid_payload, "actor": {"aadObjectId": "", "upn": ""}})

    def test_deployment_script_exposes_copilot_topic_validation_spike(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        spike = deploy.adaptive_card_topic_validation_spike()
        joined = "\n".join(spike["checks"])

        self.assertEqual(spike["cardSchemaVersion"], "1.5")
        self.assertEqual(spike["submitAction"], "Action.Submit")
        self.assertIn("Generative Orchestration", joined)
        self.assertIn("dedicated Adaptive Card Topic", joined)
        self.assertIn("Power Automate tool flow", joined)
        self.assertIn("Teams", joined)

    def test_valid_confirm_decision_contract_returns_succeeded_response(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        response = deploy.succeeded_response(
            application_id="application-1",
            decision_record_id="decision-1",
            decided_at="2026-01-02T03:04:05Z",
        )

        self.assertEqual(response["status"], "succeeded")
        self.assertEqual(response["applicationId"], "application-1")
        self.assertEqual(response["decisionRecordId"], "decision-1")
        self.assertEqual(response["decidedAt"], "2026-01-02T03:04:05Z")
        self.assertEqual(response["message"], "判断を確定しました。")

    def test_confirm_flow_creates_decision_consumes_card_and_never_updates_application(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_confirm_decision_clientdata())
        actions = clientdata["properties"]["definition"]["actions"]

        create_decision = find_action(actions, "Create_decision")
        self.assertEqual(create_decision["inputs"]["host"]["operationId"], "CreateRecord")
        self.assertEqual(create_decision["inputs"]["parameters"]["entityName"], "ds_decisions")
        decision_item = create_decision["inputs"]["parameters"]["item"]
        self.assertIn("ds_rationale", decision_item)
        self.assertIn("ds_applicationid@odata.bind", decision_item)
        self.assertIn("ds_decisionoptionid@odata.bind", decision_item)
        # Adaptive Card 経由の判断も AI 推奨を控える。Code Apps 側だけに入れると
        # 判断経路によって採否記録に穴が空く。
        self.assertIn("ds_aisuggestionatdecision", decision_item)
        self.assertIn(
            "ds_aidecisionoptiontext",
            decision_item["ds_aisuggestionatdecision"],
        )
        get_application = find_action(actions, "Get_application")
        self.assertIn(
            "ds_aidecisionoptiontext",
            get_application["inputs"]["parameters"]["$select"],
        )

        consume_card = find_action(actions, "Consume_decisioncard")
        self.assertEqual(consume_card["inputs"]["host"]["operationId"], "UpdateRecord")
        self.assertEqual(consume_card["inputs"]["parameters"]["entityName"], "ds_decisioncards")
        self.assertEqual(consume_card["inputs"]["parameters"]["item"]["ds_status"], 100000001)
        self.assertEqual(consume_card["runAfter"], {"Create_decision": ["Succeeded"]})

        application_updates = [
            action
            for action in flatten_actions(actions)
            if isinstance(action.get("inputs"), dict)
            and action.get("inputs", {}).get("host", {}).get("operationId") == "UpdateRecord"
            and action.get("inputs", {}).get("parameters", {}).get("entityName") == "ds_applications"
        ]
        self.assertEqual(application_updates, [])

    def test_issue_flow_returns_card_instance_id_for_copilot_owned_card_json(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_issue_decision_card_clientdata())
        triggers = clientdata["properties"]["definition"]["triggers"]
        actions = clientdata["properties"]["definition"]["actions"]

        trigger = triggers["manual"]
        self.assertEqual(trigger["type"], "Request")
        self.assertEqual(trigger["kind"], "Skills")
        trigger_properties = trigger["inputs"]["schema"]["properties"]
        self.assertEqual(set(trigger_properties), {"applicationId", "actorAadObjectId", "actorUpn"})
        self.assertEqual(trigger["inputs"]["schema"]["required"], ["applicationId", "actorUpn"])

        create_card = actions["Create_decisioncard"]
        self.assertEqual(create_card["inputs"]["host"]["operationId"], "CreateRecord")
        self.assertEqual(create_card["inputs"]["parameters"]["entityName"], "ds_decisioncards")
        self.assertEqual(create_card["runAfter"], {"Supersede_prior_issued_decisioncards": ["Succeeded"]})
        self.assertEqual(create_card["inputs"]["parameters"]["item"]["ds_status"], 100000000)
        self.assertIn("ds_name", create_card["inputs"]["parameters"]["item"])
        self.assertIn("ds_cardinstanceid", create_card["inputs"]["parameters"]["item"])
        self.assertIn("actorAadObjectId", create_card["inputs"]["parameters"]["item"]["ds_actoraadobjectid"])
        self.assertIn("actorUpn", create_card["inputs"]["parameters"]["item"]["ds_actorupn"])

        response = actions["Return_card_context"]
        self.assertEqual(response["type"], "Response")
        self.assertEqual(response["kind"], "Skills")
        body_json = json.dumps(response["inputs"]["body"], ensure_ascii=False)
        self.assertIn("cardInstanceId", body_json)
        self.assertIn("applicationId", body_json)
        # status は 2026-08-09 に追加。トピックが発行の可否で分岐するために要る。
        self.assertEqual(
            set(response["inputs"]["schema"]["properties"]),
            {"applicationId", "cardInstanceId", "status"},
        )

    def test_issue_flow_validates_actor_and_submitted_application_before_creating_a_card(self):
        """カード発行にも実行者・Submitted・判断者の検証を要求する。

        2026-08-09 の実機確認で、Draft の申請に対してカードが発行されることが分かった。
        検証が1つも無く、docs が「Submitted かつ実行者が判断者であることを確認し」と
        書いていたのは誤りだった。設計は docs/AGENT_WRITE_BOUNDARY.md の表で固定した。
        """
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        actions = json.loads(deploy.build_issue_decision_card_clientdata())["properties"]["definition"]["actions"]

        # 1. 実行者が systemuser として解決できること
        self.assertIn("List_current_user", actions)
        user_gate = actions["Validate_user_found"]
        self.assertEqual(user_gate["type"], "If")
        self.assertEqual(user_gate["actions"], {}, "拒否は else 側に置く（confirm_decision と同じ形）")
        self.assertIn("Return_forbidden_user_not_found", user_gate["else"]["actions"])

        # 2-3. 申請を取得して Submitted であること
        self.assertEqual(
            actions["Get_application"]["inputs"]["parameters"]["entityName"],
            "ds_applications",
        )
        submitted_gate = actions["Validate_submitted_application"]
        self.assertEqual(submitted_gate["expression"], {"equals": ["@outputs('Get_application')?['body/ds_stage']", 100000001]})
        self.assertIn("Return_invalid_application", submitted_gate["else"]["actions"])

        # 4. 実行者が判断者であること（判断者未割当ては coalesce で forbidden に倒す）
        decider_gate = actions["Validate_actor_is_decider"]
        self.assertEqual(
            decider_gate["expression"],
            {
                "equals": [
                    "@toLower(coalesce(outputs('Get_application')?['body/_ds_deciderid_value'], ''))",
                    "@toLower(first(outputs('List_current_user')?['body/value'])?['systemuserid'])",
                ]
            },
        )
        self.assertIn("Return_forbidden_not_decider", decider_gate["else"]["actions"])

        # 1 の式も固定する。他2つと違って未検証だと、反転しても緑のままになる。
        self.assertEqual(
            user_gate["expression"],
            {"greater": ["@length(outputs('List_current_user')?['body/value'])", 0]},
        )

        # 検証どうしの順序。runAfter を見ないと「順序」の半分が担保されない。
        self.assertEqual(actions["Get_application"]["runAfter"], {"Validate_user_found": ["Succeeded"]})
        self.assertEqual(
            actions["Validate_submitted_application"]["runAfter"],
            {"Validate_application_found": ["Succeeded"]},
            "2.5 の found 判定を挟む。飛ばすと 404 でフローが throw する",
        )
        self.assertEqual(
            actions["Validate_actor_is_decider"]["runAfter"],
            {"Validate_submitted_application": ["Succeeded"]},
        )

    def test_issue_flow_terminates_the_run_on_every_rejection(self):
        """**不変条件4を実際に担保しているのは Terminate であって runAfter ではない。**

        Power Automate の If は条件が偽でも Succeeded になる。つまり
        `Get_application` の `runAfter: {Validate_user_found: [Succeeded]}` は、
        ユーザーが見つからなかった場合にも満たされる。鎖が切れる理由は else 側の
        Terminate がラン全体を止めるから。

        したがって Stop_after_* の runAfter を ["Failed"] などに書き換えると
        Terminate が Skipped になり、拒否経路から書き込みへ到達する。ここを
        固定していないと、不変条件4は無防備になる。
        """
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        actions = json.loads(deploy.build_issue_decision_card_clientdata())["properties"]["definition"]["actions"]

        expected_status = {
            ("Validate_user_found", "Return_forbidden_user_not_found"): "forbidden",
            ("Validate_submitted_application", "Return_invalid_application"): "invalid_target",
            ("Validate_actor_is_decider", "Return_forbidden_not_decider"): "forbidden",
        }
        for (gate_name, response_name), status in expected_status.items():
            else_actions = actions[gate_name]["else"]["actions"]

            stop = else_actions[f"Stop_after_{response_name}"]
            self.assertEqual(stop["type"], "Terminate")
            self.assertEqual(
                stop["runAfter"],
                {response_name: ["Succeeded"]},
                f"{response_name} の成功で止める。Failed 等にすると Terminate が Skipped になる",
            )
            self.assertEqual(stop["inputs"], {"runStatus": "Succeeded"})

            # 拒否時に返す status も固定する。成功時だけ固定していると片手落ち。
            self.assertEqual(else_actions[response_name]["inputs"]["body"]["status"], status)
            self.assertEqual(else_actions[response_name]["inputs"]["body"]["cardInstanceId"], "")

    def test_both_flows_answer_instead_of_throwing_when_the_application_is_missing(self):
        """不変条件7: どの拒否経路でもフローは status を返して Succeeded で終わる。

        2026-08-09 の実測。生成オーケストレーションが applicationId に**ナレッジ
        ソースの ID**（9bf68d84-...）を渡し、GetItem が 404 で失敗し、利用者の画面に
        生の BadGateway とリクエスト追跡 ID が出た。設計は
        docs/AGENT_WRITE_BOUNDARY.md「フローが status を返さず throw する経路を塞ぐ」。

        Failed を拾わないと throw に戻る。runAfter から "Failed" が落ちると
        この経路が黙って復活するので、そこを名指しで固定する。
        """
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        for builder, response_properties in (
            ("build_issue_decision_card_clientdata", {"applicationId", "cardInstanceId", "status"}),
            ("build_confirm_decision_clientdata", {"applicationId", "decisionRecordId", "decidedAt", "message", "status"}),
        ):
            with self.subTest(builder=builder):
                actions = json.loads(getattr(deploy, builder)())["properties"]["definition"]["actions"]

                gate = actions["Validate_application_found"]
                self.assertEqual(gate["type"], "If")
                self.assertEqual(
                    gate["runAfter"],
                    {"Get_application": ["Succeeded", "Failed", "Skipped", "TimedOut"]},
                    "Succeeded 以外を全部拾う。Failed だけだと 404 が別状態に割り当てられたとき素通りする",
                )
                self.assertEqual(
                    gate["expression"],
                    {"equals": ["@actions('Get_application')?['status']", "Succeeded"]},
                )
                self.assertEqual(gate["actions"], {}, "拒否は else 側に置く（他の段と同じ形）")

                rejection = gate["else"]["actions"]["Return_application_not_found"]
                self.assertEqual(rejection["inputs"]["body"]["status"], "invalid_target")
                self.assertEqual(set(rejection["inputs"]["schema"]["properties"]), response_properties)

                stop = gate["else"]["actions"]["Stop_after_Return_application_not_found"]
                self.assertEqual(stop["type"], "Terminate")
                self.assertEqual(stop["inputs"], {"runStatus": "Succeeded"})

                # 判定順 1 → 2 → 2.5(found) → 3。found を飛ばして Submitted を見ると
                # outputs('Get_application') が空のまま比較され、また throw する。
                self.assertEqual(
                    actions["Validate_submitted_application"]["runAfter"],
                    {"Validate_application_found": ["Succeeded"]},
                )

    def test_both_flows_treat_an_unassigned_decider_as_forbidden_instead_of_throwing(self):
        """不変条件7 の続き。判断者が未割当ての申請でも throw しない。

        `toLower(null)` は If を Failed にする。docs の表 #4 は「拒否 / forbidden」と
        書いていたが、実際は status が返っていなかった。coalesce で空文字に倒すと
        systemuserid と一致せず、既存の else（forbidden）へ落ちる。

        **判定の意味は変えていない**（不変条件8）。null を「判断者でない」に倒すだけ。
        """
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        for builder in ("build_issue_decision_card_clientdata", "build_confirm_decision_clientdata"):
            with self.subTest(builder=builder):
                actions = json.loads(getattr(deploy, builder)())["properties"]["definition"]["actions"]

                self.assertEqual(
                    actions["Validate_actor_is_decider"]["expression"],
                    {
                        "equals": [
                            "@toLower(coalesce(outputs('Get_application')?['body/_ds_deciderid_value'], ''))",
                            "@toLower(first(outputs('List_current_user')?['body/value'])?['systemuserid'])",
                        ]
                    },
                )

    def test_issue_flow_never_writes_a_card_before_every_validation_passed(self):
        """不変条件4: 拒否されたら ds_decisioncard に行が増えない。

        これは runAfter の鎖だけで担保される。書き込み系アクションが最後の検証より
        前に走る形になっていないかを見る。
        """
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        actions = json.loads(deploy.build_issue_decision_card_clientdata())["properties"]["definition"]["actions"]

        # 既存カードの Superseded も書き込みなので、検証後でなければならない。
        self.assertEqual(
            actions["List_prior_issued_decisioncards"]["runAfter"],
            {"Validate_actor_is_decider": ["Succeeded"]},
        )
        self.assertEqual(
            actions["Supersede_prior_issued_decisioncards"]["runAfter"],
            {"List_prior_issued_decisioncards": ["Succeeded"]},
        )
        self.assertEqual(
            actions["Create_decisioncard"]["runAfter"],
            {"Supersede_prior_issued_decisioncards": ["Succeeded"]},
        )

    def test_issue_flow_returns_status_so_the_topic_can_branch(self):
        """不変条件6: 拒否されたらトピックはカードを出さない。

        そのためにフローが status を返す必要がある。成功時は issued。
        """
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        actions = json.loads(deploy.build_issue_decision_card_clientdata())["properties"]["definition"]["actions"]

        response = actions["Return_card_context"]
        self.assertEqual(
            set(response["inputs"]["schema"]["properties"]),
            {"applicationId", "cardInstanceId", "status"},
        )
        self.assertEqual(response["inputs"]["body"]["status"], "issued")

    def test_decision_topic_refuses_channels_that_cannot_render_cards(self):
        """不変条件9: 対話UIを持たないチャネルでは判断カードを発行しない。

        Code Apps パネル（コネクタ経由）は Adaptive Card を描画できない。それでも
        トピックに入ると issue_decision_card が ds_decisioncard を発行し、Teams で
        出したカードを Superseded にしたうえで行き止まる。

        チャネル ID の実値は conversationtranscript から確認した（2026-08-10）。
        テストパネルが pva-studio、コネクタ経由が pva-autonomous。

        **ガードは issue_decision_card より前になければ意味がない。** 位置を
        index で固定する。条件式だけ見ていると、後ろへ移動しても緑のままになる。
        """
        import yaml

        topic = yaml.safe_load(DECISION_TOPIC_PATH.read_text(encoding="utf-8"))
        steps = topic["beginDialog"]["actions"]

        guard_index = next(
            i for i, s in enumerate(steps)
            if s.get("id") == "validateCardCapableChannel"
        )
        issue_index = next(
            i for i, s in enumerate(steps)
            if s.get("kind") == "InvokeFlowAction" and str(s.get("flowId", "")).startswith("c37ed747")
        )
        self.assertLess(guard_index, issue_index, "ガードはカード発行フローより前に置く")
        self.assertEqual(guard_index, 0, "トピックの先頭に置く")

        guard = steps[guard_index]
        condition = guard["conditions"][0]
        self.assertEqual(
            condition["condition"],
            '=System.Activity.ChannelId = "pva-autonomous"',
        )

        # 止めるのは pva-autonomous だけにする。許可リストにすると Teams や
        # M365 Copilot を巻き込んで壊す。
        self.assertNotIn("msteams", yaml.safe_dump(guard, allow_unicode=True))

        kinds = [action["kind"] for action in condition["actions"]]
        self.assertEqual(kinds, ["SendActivity", "EndConversation"])
        self.assertIn("判断タブ", condition["actions"][0]["activity"])

    def test_decision_topic_stops_before_the_card_when_issue_is_rejected(self):
        """トピック側。issueStatus が issued 以外ならカードを出さずに終える。

        文字列の index 比較ではなく YAML をパースして構造で見る。文字列一致だと
        EndConversation を消しても ConditionGroup ごと壊しても、目印の文字列さえ
        残っていれば緑になり、不変条件6が黙って壊れる。
        """
        import yaml

        topic = yaml.safe_load(DECISION_TOPIC_PATH.read_text(encoding="utf-8"))
        steps = topic["beginDialog"]["actions"]

        # issue のフロー（c37ed747）の出力が issueStatus に束縛されていること。
        issue_invoke = next(
            s for s in steps
            if s["kind"] == "InvokeFlowAction" and s["flowId"].startswith("c37ed747")
        )
        self.assertEqual(issue_invoke["output"]["binding"]["status"], "Topic.issueStatus")

        # confirm 側は Topic.status のまま。名前が衝突していないこと。
        confirm_invokes = [
            s for s in _flatten_topic_steps(steps)
            if s.get("kind") == "InvokeFlowAction" and str(s.get("flowId", "")).startswith("f8502159")
        ]
        self.assertEqual(len(confirm_invokes), 1)
        self.assertEqual(confirm_invokes[0]["output"]["binding"]["status"], "Topic.status")

        # ガードがカード表示より前にあること。
        kinds = [s["kind"] for s in steps]
        guard_index = next(
            i for i, s in enumerate(steps)
            if s["kind"] == "ConditionGroup" and s["id"] == "validateIssueResult"
        )
        self.assertLess(guard_index, kinds.index("AdaptiveCardPrompt"))

        # ガードが「issued 以外」で会話を終えること。EndConversation まで見る。
        guard = steps[guard_index]
        rejected = next(c for c in guard["conditions"] if c["id"] == "issueRejected")
        self.assertEqual(rejected["condition"], '=Topic.issueStatus <> "issued"')
        self.assertIn(
            "EndConversation",
            [a["kind"] for a in rejected["actions"]],
            "カードを出さないだけでなく会話を終える必要がある",
        )

        # 追加した SendActivity が = プレフィックスのスカラー式でないこと。
        for action in rejected["actions"]:
            if action["kind"] == "SendActivity":
                self.assertFalse(
                    action["activity"].lstrip().startswith("="),
                    "= プレフィックスのスカラー式は評価されず、そのまま画面に出る",
                )

    def test_issue_flow_supersedes_prior_issued_cards_for_same_application_and_actor(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_issue_decision_card_clientdata())
        actions = clientdata["properties"]["definition"]["actions"]

        prior_cards = actions["List_prior_issued_decisioncards"]
        self.assertEqual(prior_cards["inputs"]["host"]["operationId"], "ListRecords")
        self.assertEqual(prior_cards["inputs"]["parameters"]["entityName"], "ds_decisioncards")
        prior_filter = json.dumps(prior_cards["inputs"]["parameters"].get("$filter"), ensure_ascii=False)
        self.assertIn("_ds_applicationid_value", prior_filter)
        self.assertIn("ds_status eq 100000000", prior_filter)
        self.assertIn("ds_actoraadobjectid", prior_filter)
        self.assertIn("ds_actorupn", prior_filter)

        supersede = actions["Supersede_prior_issued_decisioncards"]
        self.assertEqual(supersede["type"], "Foreach")
        self.assertEqual(supersede["foreach"], "@outputs('List_prior_issued_decisioncards')?['body/value']")
        update_prior = supersede["actions"]["Supersede_prior_issued_decisioncard"]
        self.assertEqual(update_prior["inputs"]["host"]["operationId"], "UpdateRecord")
        self.assertEqual(update_prior["inputs"]["parameters"]["item"]["ds_status"], 100000002)
        self.assertIn("ds_supersededat", update_prior["inputs"]["parameters"]["item"])

    def test_confirm_flow_uses_skills_trigger_and_consistent_agent_responses(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_confirm_decision_clientdata())
        definition = clientdata["properties"]["definition"]
        trigger = definition["triggers"]["manual"]

        self.assertEqual(trigger["type"], "Request")
        self.assertEqual(trigger["kind"], "Skills")
        trigger_properties = trigger["inputs"]["schema"]["properties"]
        self.assertEqual(
            set(trigger_properties),
            {"applicationId", "decisionOption", "rationale", "cardInstanceId", "actorAadObjectId", "actorUpn"},
        )
        self.assertEqual(
            trigger["inputs"]["schema"]["required"],
            ["applicationId", "decisionOption", "rationale", "cardInstanceId", "actorUpn"],
        )

        response_actions = [action for action in flatten_actions(definition["actions"]) if action.get("type") == "Response"]
        self.assertGreaterEqual(len(response_actions), 2)
        expected_outputs = {"status", "applicationId", "decisionRecordId", "decidedAt", "message"}
        for response in response_actions:
            self.assertEqual(response.get("kind"), "Skills")
            self.assertEqual(set(response["inputs"]["schema"]["properties"]), expected_outputs)
            self.assertEqual(set(response["inputs"]["body"]), expected_outputs)

    def test_confirm_flow_defines_forbidden_invalid_and_already_processed_responses(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_confirm_decision_clientdata())
        actions_json = json.dumps(clientdata["properties"]["definition"]["actions"], ensure_ascii=False)

        self.assertIn("Return_forbidden_user_not_found", actions_json)
        self.assertIn("Return_forbidden_not_decider", actions_json)
        self.assertIn("Return_invalid_decision_option", actions_json)
        self.assertIn("Return_invalid_application", actions_json)
        self.assertIn("Return_invalid_empty_rationale", actions_json)
        self.assertIn("Return_already_processed_card", actions_json)
        self.assertIn("Return_already_processed", actions_json)

    def test_deployment_prerequisite_validation_requires_environment_and_connection_refs(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        self.assertEqual(
            deploy.validate_deployment_prerequisites(
                dataverse_url="https://example.crm.dynamics.com",
                solution_name="DecisionSupport",
                prefix="ds",
                connection_names=["shared-connection"],
                dataverse_connref="ds_shared_commondataserviceforapps",
            ),
            "shared-connection",
        )
        with self.assertRaises(RuntimeError):
            deploy.validate_deployment_prerequisites(
                dataverse_url="",
                solution_name="DecisionSupport",
                prefix="ds",
                connection_names=["shared-connection"],
            )
        with self.assertRaises(RuntimeError):
            deploy.validate_deployment_prerequisites(
                dataverse_url="https://example.crm.dynamics.com",
                solution_name="DecisionSupport",
                prefix="ds",
                connection_names=[],
            )
        with self.assertRaises(RuntimeError):
            deploy.validate_deployment_prerequisites(
                dataverse_url="https://example.crm.dynamics.com",
                solution_name="DecisionSupport",
                prefix="ds",
                connection_names=["shared-connection"],
                dataverse_connref="",
            )

    def test_confirm_flow_validates_allowed_active_option_and_submitted_application(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_confirm_decision_clientdata())
        actions = clientdata["properties"]["definition"]["actions"]

        self.assertFalse([action for action in flatten_actions(actions) if action.get("type") == "Switch"])

        decision_option_lookup = find_action(actions, "Get_decision_option")
        self.assertEqual(decision_option_lookup["inputs"]["host"]["operationId"], "ListRecords")
        self.assertEqual(decision_option_lookup["inputs"]["parameters"]["entityName"], "ds_decisionoptions")
        self.assertEqual(decision_option_lookup["runAfter"], {"Validate_user_found": ["Succeeded"]})
        decision_option_filter = json.dumps(decision_option_lookup["inputs"]["parameters"].get("$filter"), ensure_ascii=False)
        self.assertIn("ds_name eq", decision_option_filter)
        self.assertIn("decisionOption", decision_option_filter)
        self.assertIn("statecode eq 0", decision_option_filter)
        self.assertIn("statuscode eq 1", decision_option_filter)

        validate_option = find_action(actions, "Validate_decision_option_found")
        self.assertIsInstance(validate_option["expression"], dict)
        option_json = json.dumps(validate_option, ensure_ascii=False)
        self.assertIn("length(outputs('Get_decision_option')?['body/value'])", option_json)

        create_decision = find_action(actions, "Create_decision")
        decision_option_bind = create_decision["inputs"]["parameters"]["item"]["ds_decisionoptionid@odata.bind"]
        self.assertIn("first(outputs('Get_decision_option')?['body/value'])?['ds_decisionoptionid']", decision_option_bind)

        validate_application = find_action(actions, "Validate_submitted_application")
        self.assertIsInstance(validate_application["expression"], dict)
        self.assertEqual(validate_application["runAfter"], {"Validate_application_found": ["Succeeded"]})
        application_json = json.dumps(validate_application, ensure_ascii=False)
        self.assertIn("ds_stage", application_json)
        self.assertIn("100000001", application_json)

    def test_confirm_flow_allows_redecision_after_resubmission_cycle(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_confirm_decision_clientdata())
        actions = clientdata["properties"]["definition"]["actions"]

        get_application = find_action(actions, "Get_application")
        self.assertIn("ds_submittedat", get_application["inputs"]["parameters"]["$select"])

        existing_decisions = find_action(actions, "List_existing_decisions")
        filter_json = json.dumps(existing_decisions["inputs"]["parameters"].get("$filter"), ensure_ascii=False)
        self.assertIn("Get_application", filter_json)
        self.assertIn("ds_submittedat", filter_json)
        self.assertIn("ds_decidedat ge", filter_json)
        self.assertIn("empty(outputs('Get_application')?['body/ds_submittedat'])", filter_json)

    def test_confirm_flow_conditions_use_designer_friendly_expression_objects(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_confirm_decision_clientdata())
        condition_actions = [
            action
            for action in flatten_actions(clientdata["properties"]["definition"]["actions"])
            if action.get("type") == "If"
        ]

        self.assertGreaterEqual(len(condition_actions), 6)
        for action in condition_actions:
            self.assertIsInstance(action.get("expression"), dict, action)

    def test_confirm_flow_resolves_actor_and_issued_card_inside_flow(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_confirm_decision_clientdata())
        actions = clientdata["properties"]["definition"]["actions"]

        current_user = find_action(actions, "List_current_user")
        self.assertEqual(current_user["inputs"]["host"]["operationId"], "ListRecords")
        self.assertEqual(current_user["inputs"]["parameters"]["entityName"], "systemusers")
        user_filter = json.dumps(current_user["inputs"]["parameters"].get("$filter"), ensure_ascii=False)
        self.assertIn("azureactivedirectoryobjectid", user_filter)
        self.assertIn("actorAadObjectId", user_filter)

        issued_card = find_action(actions, "List_current_issued_decisioncard")
        self.assertEqual(issued_card["inputs"]["host"]["operationId"], "ListRecords")
        self.assertEqual(issued_card["inputs"]["parameters"]["entityName"], "ds_decisioncards")
        card_filter = json.dumps(issued_card["inputs"]["parameters"].get("$filter"), ensure_ascii=False)
        self.assertIn("ds_status eq 100000000", card_filter)
        self.assertIn("ds_actoraadobjectid", card_filter)
        self.assertIn("ds_actorupn", card_filter)

        create_decision = find_action(actions, "Create_decision")
        create_item = create_decision["inputs"]["parameters"]["item"]
        self.assertNotIn("triggerBody()?['deciderSystemUserId']", json.dumps(create_item, ensure_ascii=False))
        self.assertIn("List_current_user", json.dumps(create_item, ensure_ascii=False))

        consume_card = find_action(actions, "Consume_decisioncard")
        self.assertNotEqual(consume_card["inputs"]["parameters"]["recordId"], "@triggerBody()?['decisionCardId']")
        self.assertIn("List_current_issued_decisioncard", json.dumps(consume_card["inputs"]["parameters"], ensure_ascii=False))

    def test_confirm_flow_requires_current_issued_card_for_same_actor(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        clientdata = json.loads(deploy.build_confirm_decision_clientdata())
        actions = clientdata["properties"]["definition"]["actions"]

        issued_card = find_action(actions, "List_current_issued_decisioncard")
        self.assertEqual(issued_card["runAfter"], {"Validate_rationale_exists": ["Succeeded"]})
        current_filter = json.dumps(issued_card["inputs"]["parameters"].get("$filter"), ensure_ascii=False)
        self.assertIn("_ds_applicationid_value", current_filter)
        self.assertIn("ds_status eq 100000000", current_filter)
        self.assertIn("ds_actoraadobjectid", current_filter)
        self.assertIn("ds_actorupn", current_filter)

        validate_card = find_action(actions, "Validate_current_issued_card")
        validate_json = json.dumps(validate_card, ensure_ascii=False)
        self.assertIn("length(outputs('List_current_issued_decisioncard')?['body/value'])", validate_json)
        self.assertIn("first(outputs('List_current_issued_decisioncard')?['body/value'])?['ds_cardinstanceid']", validate_json)
        self.assertIn("triggerBody()?['cardInstanceId']", validate_json)
        self.assertIn("Return_already_processed_card", validate_json)

    def test_script_declares_deployable_adaptive_card_tool_flows(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")

        definitions = deploy.adaptive_card_tool_flow_definitions()

        self.assertEqual(set(definitions), {"issue_decision_card", "confirm_decision"})
        for flow_name, flow in definitions.items():
            self.assertEqual(flow["name"], flow_name)
            self.assertIn("description", flow)
            self.assertIn("clientdata", flow)
            clientdata = json.loads(flow["clientdata"])
            self.assertIn("definition", clientdata["properties"])

    def test_script_deploys_adaptive_card_tool_flows_idempotently(self):
        deploy = importlib.import_module("scripts.deploy_adaptive_card_decision_confirmation")
        calls = []

        def fake_deploy_flow(flow_name, description, clientdata):
            calls.append((flow_name, description, clientdata))
            return f"{flow_name}-id", True

        result = deploy.deploy_adaptive_card_tool_flows(fake_deploy_flow)

        self.assertEqual(set(result), {"issue_decision_card", "confirm_decision"})
        self.assertEqual([call[0] for call in calls], ["issue_decision_card", "confirm_decision"])


if __name__ == "__main__":
    unittest.main()