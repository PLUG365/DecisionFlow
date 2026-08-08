"""DecisionFlow Assistant のうち、YAML 正本が持たない設定だけを適用する。

エージェント定義（Instructions・会話の開始・トピック・アクション・チャネル・
AI設定）の正本は copilot/DecisionFlowAssistant/ 配下の YAML であり、
反映は `pac copilot push`、取り込みは `pac copilot pull` で行う。

このスクリプトが残っているのは、YAML に含まれない次の2つのためだけ:

- Teams アプリマニフェストの説明文・アクセントカラー・開発者名
  （bots.applicationmanifestinformation）
- アイコンの生成と適用（icon.png を YAML 側に持たせる前の経路）

**トピックを削除する処理はここから取り除いた。** 以前の delete_custom_topics は
「システムトピック以外を全消し」する実装で、UI や YAML で作った 判断確定 /
post_application_message のトピックを巻き込んで消していた。同じ理由で
Instructions と会話の開始を上書きする処理も削除した。上書きしたい場合は
YAML を編集して push すること。
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from auth_helper import DATAVERSE_URL, api_get, api_patch, api_post  # noqa: E402

AGENT_YAML_PATH = ROOT / "copilot" / "DecisionFlowAssistant" / "agent.mcs.yml"

load_dotenv()

SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
SOLUTION_DISPLAY_NAME = os.environ.get("SOLUTION_DISPLAY_NAME", "意思決定支援 (Decision Support)")
PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")

BOT_NAME = "DecisionFlow Assistant"
BOT_SCHEMA_NAME = f"{PREFIX}_DecisionFlowAssistant"

TEAMS_SHORT_DESCRIPTION = "DecisionFlowの判断支援AIアシスタント"
TEAMS_LONG_DESCRIPTION = (
    "DecisionFlow Assistant は、判断者が申請内容を素早く把握し、的確な判断を行うためのAIアシスタントです。"
    "申請タイトルまたはアプリリンクを受け取り、申請概要、関連資料リンク、過去類似案件、推奨判断、判断コメントドラフトを提示します。"
    "また、提出済みステージの判断待ち申請一覧を、利用者が参照できる範囲で表示します。"
)
TEAMS_ACCENT_COLOR = "#1e3a5f"
TEAMS_DEVELOPER_NAME = "DecisionFlow"


def read_agent_instructions(yaml_text: str | None = None) -> str:
    """agent.mcs.yml の instructions ブロックを取り出す。

    Instructions の正本は YAML なので、テストも運用もここを読む。
    PyYAML に依存させたくないので、リテラルブロック（`instructions: |-`）を
    インデント2で切り出すだけの最小実装にしている。
    """
    if yaml_text is None:
        yaml_text = AGENT_YAML_PATH.read_text(encoding="utf-8")
    lines = yaml_text.splitlines()
    for index, line in enumerate(lines):
        if line.rstrip() != "instructions: |-":
            continue
        body: list[str] = []
        for candidate in lines[index + 1:]:
            if candidate.strip() and not candidate.startswith("  "):
                break
            body.append(candidate[2:] if candidate.startswith("  ") else candidate)
        return "\n".join(body).strip("\n")
    raise RuntimeError(f"{AGENT_YAML_PATH} に instructions ブロックが見つかりません。")


def extract_bot_id(value: str) -> str | None:
    match = re.search(r"/bots/([0-9a-fA-F-]{36})", value)
    if match:
        return match.group(1)
    value = value.strip()
    if re.fullmatch(r"[0-9a-fA-F-]{36}", value):
        return value
    return None


def find_bot() -> str:
    env_bot_id = os.environ.get("BOT_ID", "")
    if env_bot_id:
        bot_id = extract_bot_id(env_bot_id)
        if bot_id:
            print(f"BOT_ID: {bot_id}")
            return bot_id
        raise RuntimeError("BOT_ID は Copilot Studio の Bot URL または GUID で指定してください。")

    result = api_get(f"bots?$filter=name eq '{BOT_NAME}'&$select=botid,name")
    if result.get("value"):
        bot_id = result["value"][0]["botid"]
        print(f"既存 Bot を発見: {bot_id}")
        return bot_id

    print_manual_bot_creation_steps()
    raise RuntimeError("Copilot Studio UI で Bot を作成し、.env に BOT_ID を設定してから再実行してください。")


def print_manual_bot_creation_steps() -> None:
    print("Copilot Studio UI でエージェントを作成してください。")
    print(f"- 名前: {BOT_NAME}")
    print("- 言語: 日本語 (日本)")
    print(f"- ソリューション表示名: {SOLUTION_DISPLAY_NAME}")
    print(f"- ソリューション一意名: {SOLUTION_NAME}")
    print(f"- スキーマ名: {BOT_SCHEMA_NAME}")
    print("作成後、トピック一覧が表示されるまで待ち、ブラウザURLを .env の BOT_ID に貼り付けてください。")


def wait_for_provisioning(bot_id: str, timeout: int = 120) -> None:
    print("\n=== プロビジョニング待ち ===")
    for elapsed in range(0, timeout + 1, 10):
        topics = api_get(
            "botcomponents?"
            f"$filter=_parentbotid_value eq '{bot_id}' and componenttype eq 1"
            "&$select=botcomponentid"
        )
        gpt = api_get(
            "botcomponents?"
            f"$filter=_parentbotid_value eq '{bot_id}' and componenttype eq 15"
            "&$select=botcomponentid"
        )
        if topics.get("value") or gpt.get("value"):
            print("プロビジョニング完了")
            return
        print(f"待機中... {elapsed}/{timeout}秒")
        time.sleep(10)
    print("警告: プロビジョニング完了を確認できませんでした。UI のロード状態を確認してください。")


def generate_icons() -> dict[str, str]:
    from PIL import Image, ImageDraw, ImageFont

    def draw_icon(size: int, outline_only: bool = False) -> Image.Image:
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        scale = size / 240
        if not outline_only:
            draw.rounded_rectangle(
                [0, 0, size - 1, size - 1],
                radius=int(42 * scale),
                fill=(30, 58, 95, 255),
            )
            draw.ellipse([int(34 * scale), int(38 * scale), int(206 * scale), int(202 * scale)], outline=(125, 211, 252, 255), width=max(2, int(8 * scale)))
            draw.line([int(64 * scale), int(122 * scale), int(108 * scale), int(154 * scale), int(176 * scale), int(78 * scale)], fill=(250, 204, 21, 255), width=max(3, int(12 * scale)), joint="curve")
            draw.line([int(82 * scale), int(82 * scale), int(158 * scale), int(82 * scale)], fill=(226, 232, 240, 255), width=max(2, int(7 * scale)))
            draw.line([int(82 * scale), int(176 * scale), int(158 * scale), int(176 * scale)], fill=(226, 232, 240, 255), width=max(2, int(7 * scale)))
            try:
                font = ImageFont.truetype("arial.ttf", int(42 * scale))
            except OSError:
                font = ImageFont.load_default()
            draw.text((int(91 * scale), int(102 * scale)), "DF", fill=(255, 255, 255, 255), font=font)
        else:
            draw.ellipse([3, 3, size - 4, size - 4], outline=(255, 255, 255, 255), width=3)
            draw.line([8, 18, 15, 23, 25, 10], fill=(255, 255, 255, 255), width=3)
        return image

    def to_base64(image) -> str:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    return {
        "main": to_base64(draw_icon(240)),
        "color": to_base64(draw_icon(192)),
        "outline": to_base64(draw_icon(32, outline_only=True)),
    }


def set_icon(bot_id: str) -> None:
    print("\n=== アイコン設定 ===")
    icons = generate_icons()
    bot = api_get(f"bots({bot_id})?$select=name,applicationmanifestinformation")
    name = bot.get("name", BOT_NAME)
    api_patch(f"bots({bot_id})", {"name": name, "iconbase64": icons["main"]})

    manifest = json.loads(bot.get("applicationmanifestinformation", "{}") or "{}")
    teams = manifest.setdefault("teams", {})
    teams["colorIcon"] = icons["color"]
    teams["outlineIcon"] = icons["outline"]
    api_patch(f"bots({bot_id})", {"name": name, "applicationmanifestinformation": json.dumps(manifest)})
    print("アイコン設定完了")


def publish_bot(bot_id: str) -> None:
    print("\n=== 公開 ===")
    try:
        api_post(f"bots({bot_id})/Microsoft.Dynamics.CRM.PvaPublish", {})
        print("公開完了")
    except Exception as exc:
        print(f"公開に失敗しました。Copilot Studio UI で手動公開してください: {exc}")


def set_channel_manifest(bot_id: str) -> None:
    print("\n=== Teams / Microsoft 365 Copilot チャネル設定 ===")
    bot = api_get(f"bots({bot_id})?$select=name,configuration,applicationmanifestinformation")
    name = bot.get("name", BOT_NAME)
    manifest = json.loads(bot.get("applicationmanifestinformation", "{}") or "{}")
    teams = manifest.setdefault("teams", {})
    teams["shortDescription"] = TEAMS_SHORT_DESCRIPTION[:80]
    teams["longDescription"] = TEAMS_LONG_DESCRIPTION[:3400]
    teams["accentColor"] = TEAMS_ACCENT_COLOR
    teams["developerName"] = TEAMS_DEVELOPER_NAME[:32]
    manifest.setdefault("copilotChat", {})["isEnabled"] = True
    api_patch(f"bots({bot_id})", {"name": name, "applicationmanifestinformation": json.dumps(manifest)})

    config = json.loads(bot.get("configuration", "{}") or "{}")
    channels = []
    channel_ids = set()
    for channel in config.get("channels", []):
        channel_id = channel.get("channelId") or ""
        normalized_id = channel_id.lower()
        if normalized_id in channel_ids:
            continue
        if normalized_id == "msteams":
            channel["channelId"] = "MsTeams"
        channel_ids.add(normalized_id)
        channels.append(channel)
    for channel_id in ["MsTeams", "Microsoft365Copilot"]:
        if channel_id.lower() not in channel_ids:
            channels.append({"id": None, "channelId": channel_id, "channelSpecifier": None, "displayName": None})
            channel_ids.add(channel_id.lower())
    config["channels"] = channels
    api_patch(f"bots({bot_id})", {"configuration": json.dumps(config)})
    print("チャネル設定完了")


def print_manual_followups() -> None:
    print("\n手動確認が必要です。")
    print("1. Copilot Studio UI で認証を Microsoft Entra ID ユーザー認証に設定してください。")
    print("2. ナレッジに Dataverse の ds_application, ds_message, ds_applicationresource, ds_decision, ds_decisionoption を追加してください。")
    print("3. Teams チャネルを利用可能にし、Bot manifest の botChannelRegistrationAppId を控えてください。")
    print("4. 通知メールのリンクを使う場合は、ソリューション環境変数 ds_DecisionFlowAppBaseUrl / ds_CopilotTeamsAppId をインポート先環境で設定してください。")
    print("5. 申請詳細リンク用に Get_ApplicationDetailUrl ツールフローをデプロイし、Copilot Studio UI でエージェントツールとして登録してください。")
    print("   - python -m scripts.deploy_application_link_flow")
    print("   - Copilot Studio UI: Agents > DecisionFlow Assistant > Tools > Add a tool > 既存フローから Get_ApplicationDetailUrl を選択")
    print("6. 会話投稿用に post_application_message ツールフローをデプロイし、UI でツール登録してください。")
    print("   - python -m scripts.deploy_agent_message_flow")
    print("   - Copilot Studio UI: Agents > DecisionFlow Assistant > Tools > Add a tool > 既存フローから post_application_message を選択")
    print("7. 判断確定用の専用 Adaptive Card Topic と Power Automate ツールを確認してください。")
    for step in decision_confirmation_topic_setup_steps():
        print(f"   - {step}")


def decision_confirmation_topic_setup_steps() -> list[str]:
    return [
        "Keep the agent in Generative Orchestration mode; use a dedicated Adaptive Card Topic only as the card display and submit surface.",
        "Create or verify a dedicated Adaptive Card Topic for decision confirmation.",
        "Call the issue_decision_card Power Automate tool flow before rendering the card to create ds_decisioncard and return cardInstanceId.",
        "Render the Copilot Studio-owned Adaptive Card with schema 1.5 and Action.Submit only.",
        "Capture decisionOption, rationale, applicationId, cardInstanceId, and actor context from submit.",
        "Call the confirm_decision Power Automate tool flow after submit; the flow must create ds_decision and never patch ds_application directly.",
        "The Topic itself lives in copilot/DecisionFlowAssistant/topics/ as YAML; edit it there and run pac copilot push. Do not hand-edit botcomponents rows.",
        "Registering a flow as an agent tool is still manual UI work; pushing the Topic does not create the tool entry.",
    ]


def main() -> None:
    if not DATAVERSE_URL:
        raise RuntimeError("DATAVERSE_URL が .env に設定されていません。")
    print("=" * 72)
    print("DecisionFlow Copilot Studio agent")
    print(f"Bot: {BOT_NAME}")
    print(f"Solution: {SOLUTION_NAME}")
    print("=" * 72)
    if not AGENT_YAML_PATH.exists():
        raise RuntimeError(
            f"{AGENT_YAML_PATH} が見つかりません。"
            "エージェント定義の正本は YAML です。pac copilot clone で取得してください。"
        )
    print("Instructions・トピック・チャネル・AI設定は YAML 正本が持ちます。")
    print("  適用: pac copilot push --project-dir copilot/DecisionFlowAssistant")
    print("  取込: pac copilot pull --project-dir copilot/DecisionFlowAssistant")
    print("このスクリプトが適用するのは、アイコンと Teams マニフェストだけです。")
    bot_id = find_bot()
    wait_for_provisioning(bot_id)
    set_icon(bot_id)
    set_channel_manifest(bot_id)
    publish_bot(bot_id)
    print_manual_followups()
    print("\n完了")


if __name__ == "__main__":
    main()
