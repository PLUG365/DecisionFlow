import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import deploy_copilot_agent as agent  # noqa: E402


class AgentYamlInstructionsTests(unittest.TestCase):
    """Instructions の正本は copilot/DecisionFlowAssistant/agent.mcs.yml。

    以前はここで scripts/deploy_copilot_agent.py の文字列定数を検査していたが、
    デプロイされるのは YAML のほうなので、テストが「デプロイされないもの」を
    守っている状態になっていた。実際に push される成果物を読む。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.instructions = agent.read_agent_instructions()

    def test_read_agent_instructions_extracts_the_literal_block(self):
        extracted = agent.read_agent_instructions(
            "kind: GptComponentMetadata\n"
            "instructions: |-\n"
            "  1行目\n"
            "  \n"
            "  2行目\n"
            "\n"
            "conversationStarters:\n"
            "  - title: これは本文ではない\n"
        )

        self.assertEqual(extracted, "1行目\n\n2行目")

    def test_instructions_do_not_embed_environment_specific_app_url(self):
        self.assertNotIn("apps.powerapps.com/play", self.instructions)
        self.assertNotIn("?deepLink=%2Fapplications%2F", self.instructions)

    def test_instructions_have_no_curly_brace_placeholders(self):
        """Copilot Studio は `{name}` を式ノードとして解釈し ContentValidationError になる。"""
        placeholders = re.findall(r"\{[A-Za-z_][A-Za-z0-9_.]*\}", self.instructions)

        self.assertEqual(
            placeholders,
            [],
            f"Curly-brace placeholders {placeholders} would be parsed as Power Fx expressions by Copilot Studio.",
        )

    def test_instructions_use_fixed_decision_options(self):
        self.assertIn("承認」「却下」「差し戻し", self.instructions)
        self.assertNotIn("条件付き承認", self.instructions)
        self.assertNotIn("否認", self.instructions)

    def test_instructions_delegate_application_detail_url_to_tool(self):
        self.assertIn("Get_ApplicationDetailUrl", self.instructions)
        self.assertIn("applicationId", self.instructions)
        self.assertIn("applicationUrl", self.instructions)

    def test_instructions_forbid_fabricating_the_actor(self):
        # agent flow は接続参照の identity で動くため、実行者はトリガー引数が決める。
        # モデルが actorUpn を作文できると他人として書き込めてしまう。
        self.assertIn("actorUpn", self.instructions)
        self.assertIn("自分で組み立ててはならない", self.instructions)
        self.assertIn("認証済みユーザー", self.instructions)

    def test_instructions_state_what_the_agent_cannot_do(self):
        # docs/AGENT_WRITE_BOUNDARY.md の禁止対象を、エージェント自身にも伝える。
        self.assertIn("できないこと", self.instructions)
        for forbidden in ("関係者の追加", "マスタ", "セキュリティロール"):
            self.assertIn(forbidden, self.instructions)
        self.assertIn("できるふりをしない", self.instructions)


class AgentYamlTopicTests(unittest.TestCase):
    """会話投稿トピックの実行者束縛が、push される YAML に入っていることを守る。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.topic = (
            ROOT / "copilot" / "DecisionFlowAssistant" / "topics" / "postApplicationMessage.mcs.yml"
        ).read_text(encoding="utf-8")

    def test_actor_is_bound_from_authenticated_user_variables(self):
        # ここがモデルの出力や会話本文から埋まると、他人として投稿できてしまう。
        self.assertIn("variable: Topic.actorUpn", self.topic)
        self.assertIn("value: =System.User.PrincipalName", self.topic)
        self.assertIn("variable: Topic.actorAadObjectId", self.topic)
        self.assertIn("value: =System.User.Id", self.topic)

    def test_actor_is_not_declared_as_a_topic_input(self):
        # inputType に actor を置くと、生成オーケストレーションが埋めてしまう。
        inputs = self.topic.split("inputType:", 1)[1]
        self.assertNotIn("actorUpn", inputs)
        self.assertNotIn("actorAadObjectId", inputs)

    def test_topic_invokes_the_post_application_message_flow(self):
        self.assertIn("flowId: 3dfc08d1-7e92-f111-b8db-7c1e524a54ce", self.topic)
        self.assertIn("body: =Topic.messageBody", self.topic)

    def test_the_flow_is_not_registered_as_an_agent_tool(self):
        """ツール登録があると、生成オーケストレーションがトピックを迂回して直接呼ぶ。

        2026-08-08 に実測で確認済み: ツール登録があった状態では、トピックの
        SetVariable を通らず actorUpn をモデルが埋めていた。この YAML を
        置き直すと（ポータルでツール登録し直して pull した場合を含む）、
        実行者の束縛が再び迂回される。
        """
        action_yaml = (
            ROOT / "copilot" / "DecisionFlowAssistant" / "actions" / "post_application_message.mcs.yml"
        )

        self.assertFalse(
            action_yaml.exists(),
            "post_application_message をツール登録すると、専用トピックの実行者束縛が迂回される。",
        )

    def test_the_topic_confirms_before_posting(self):
        # ツール登録を外したことで、Instructions が担っていた投稿前の同意取得が
        # 効かなくなる。トピック側で取り直す。
        self.assertIn("kind: Question", self.topic)
        self.assertIn("BooleanPrebuiltEntity", self.topic)
        self.assertIn("init:Topic.postConfirmed", self.topic)
        self.assertIn("=Topic.postConfirmed = false", self.topic)


class AgentYamlDecisionTopicTests(unittest.TestCase):
    """判断確定トピック（zdI）の YAML の形を守る。

    守るのは YAML の形だけで、**ルーティングが直ったことは守らない**。
    生成オーケストレーションがこのトピックを選ぶかどうかは、テストパネルで
    実際に発話して確かめるしかない（docs/UX_ROADMAP.md）。
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.topic = (
            ROOT / "copilot" / "DecisionFlowAssistant" / "topics" / "zdI.mcs.yml"
        ).read_text(encoding="utf-8")

    def test_actor_is_bound_from_authenticated_user_variables(self):
        # ここがモデルの出力から埋まると、他人として判断を確定できてしまう。
        self.assertIn("variable: Topic.actorUpn", self.topic)
        self.assertIn("value: =System.User.PrincipalName", self.topic)
        self.assertIn("variable: Topic.actorAadObjectId", self.topic)
        self.assertIn("value: =System.User.Id", self.topic)

    def test_actor_is_not_declared_as_a_topic_input(self):
        inputs = self.topic.split("inputType:", 1)[1]
        self.assertNotIn("actorUpn", inputs)
        self.assertNotIn("actorAadObjectId", inputs)

    def test_topic_invokes_both_decision_flows_directly(self):
        # ツール登録ではなく flowId 直書きで呼ぶ。docs/AGENT_WRITE_BOUNDARY.md。
        self.assertIn("flowId: c37ed747-9153-f111-a824-3833c5de99c8", self.topic)  # issue_decision_card
        self.assertIn("flowId: f8502159-9153-f111-a824-3833c5de99c8", self.topic)  # confirm_decision

    def test_the_decision_flows_are_not_registered_as_agent_tools(self):
        """2本ともツール登録されると、実行者を作文した発行→確定の連鎖が成立する。"""
        actions_dir = ROOT / "copilot" / "DecisionFlowAssistant" / "actions"

        for flow in ("issue_decision_card", "confirm_decision"):
            self.assertFalse(
                (actions_dir / f"{flow}.mcs.yml").exists(),
                f"{flow} をツール登録すると、専用トピックの実行者束縛が迂回される。",
            )

    def test_card_issue_failure_stops_before_showing_the_card(self):
        # issue_decision_card が拒否したのにカードを出すと、確定できない
        # カードを判断者に見せることになる。
        self.assertIn("id: validateIssueResult", self.topic)
        self.assertIn('=Topic.issueStatus <> "issued"', self.topic)

    def test_model_description_states_purpose_not_just_phrases(self):
        """生成オーケストレーションはトピックを modelDescription で選ぶ。

        trigger phrases で選ぶのは classic orchestration。この環境は
        settings.mcs.yml が GenerativeAIRecognizer なので、入口は説明文になる。
        語句を並べただけの説明に戻すと、ナレッジ検索に負ける状態へ逆戻りする。
        """
        description = self.topic.split("modelDescription:", 1)[1].split("beginDialog:", 1)[0]

        self.assertIn("使いません", description, "「使わない場面」が無いとナレッジ検索と競合する")
        self.assertIn("ナレッジ検索", description)
        self.assertIn("タイトル", description, "タイトルで指された場合を説明していないと入口を外す")

    def test_application_id_input_allows_resolving_from_a_title(self):
        # 「GUID を渡せ」だけだと、タイトルしか無い発話でプランを組めない。
        application_id = self.topic.split("applicationId:", 1)[1]

        self.assertIn("検索して GUID を解決", application_id)
        self.assertIn("GUID の入力を求めません", application_id)


class CopilotAgentScriptTests(unittest.TestCase):
    def test_extract_bot_id_accepts_guid_or_copilot_url(self):
        guid = "11111111-2222-3333-4444-555555555555"
        self.assertEqual(agent.extract_bot_id(guid), guid)
        self.assertEqual(agent.extract_bot_id(f"https://copilotstudio.microsoft.com/foo/bots/{guid}/overview"), guid)
        self.assertIsNone(agent.extract_bot_id("not-a-bot-id"))

    def test_script_no_longer_deletes_topics_or_overwrites_yaml_owned_content(self):
        """YAML 正本を壊す経路をスクリプトに残さない。

        以前の delete_custom_topics はシステムトピック以外を全消しする実装で、
        判断確定トピックを巻き込んで消していた。
        """
        for removed in (
            "delete_custom_topics",
            "set_gpt_instructions",
            "set_conversation_start",
            "enable_generative_orchestration",
        ):
            self.assertFalse(hasattr(agent, removed), f"{removed} は YAML 正本と競合するため削除済みのはず")

    def test_manual_followups_mention_application_link_flow_deployment(self):
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            agent.print_manual_followups()
        output = buffer.getvalue()
        self.assertIn("Get_ApplicationDetailUrl", output)
        self.assertIn("deploy_application_link_flow", output)
        self.assertIn("post_application_message", output)
        self.assertIn("deploy_agent_message_flow", output)

    def test_decision_confirmation_topic_setup_steps_are_documented(self):
        steps = agent.decision_confirmation_topic_setup_steps()
        joined = "\n".join(steps)

        self.assertIn("Generative Orchestration", joined)
        self.assertIn("dedicated Adaptive Card Topic", joined)
        self.assertIn("schema 1.5", joined)
        self.assertIn("Action.Submit", joined)
        self.assertIn("issue_decision_card", joined)
        self.assertIn("confirm_decision", joined)
        self.assertIn("pac copilot push", joined)
        self.assertIn("manual", joined.lower())
        # 手順書がツール登録を指示していると、塞いだ穴が次のセットアップで開き直る。
        self.assertIn("Do NOT register", joined)
        self.assertIn("bypassing the Topic", joined)


if __name__ == "__main__":
    unittest.main()
