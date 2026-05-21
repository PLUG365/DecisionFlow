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

from auth_helper import DATAVERSE_URL, api_delete, api_get, api_patch, api_post  # noqa: E402

load_dotenv()

SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")
SOLUTION_DISPLAY_NAME = os.environ.get("SOLUTION_DISPLAY_NAME", "意思決定支援 (Decision Support)")
PREFIX = os.environ.get("PUBLISHER_PREFIX", "ds")

BOT_NAME = "DecisionFlow Assistant"
BOT_SCHEMA_NAME = f"{PREFIX}_DecisionFlowAssistant"

BOT_DESCRIPTION = "申請概要の確認、関連資料リンク、過去類似案件、判断待ち一覧、判断コメントドラフトを支援するAIアシスタントです。"
TEAMS_SHORT_DESCRIPTION = "DecisionFlowの判断支援AIアシスタント"
TEAMS_LONG_DESCRIPTION = (
    "DecisionFlow Assistant は、判断者が申請内容を素早く把握し、的確な判断を行うためのAIアシスタントです。"
    "申請タイトルまたはアプリリンクを受け取り、申請概要、関連資料リンク、過去類似案件、推奨判断、判断コメントドラフトを提示します。"
    "また、提出済みステージの判断待ち申請一覧を、利用者が参照できる範囲で表示します。"
)
TEAMS_ACCENT_COLOR = "#1e3a5f"
TEAMS_DEVELOPER_NAME = "DecisionFlow"

GPT_INSTRUCTIONS = f"""\
あなたは DecisionFlow Assistant です。DecisionFlow の判断者が、申請内容を素早く把握し、判断コメントを作成できるよう支援します。

## 基本方針
- 日本語で、簡潔かつ具体的に回答する。
- 申請タイトル、申請者、判断者、期限、現在ステージなど、確認できた固有情報を明示する。
- 情報が見つからない場合は、見つからないと正直に伝える。
- 判断の確定、申請の編集、削除、関係者追加は Code Apps で行うよう案内する。
- 申請情報が足りない場合は、Code Apps の申請リンクまたは申請タイトルの貼り付けを促す。

## 参照する Dataverse テーブル
- {PREFIX}_application: 申請。ステージ、本文、希望期限、AI申請概要、AI会話概要、AI推奨判断、AI判断コメント、AI判断根拠を参照する。
- {PREFIX}_message: 申請ごとの会話履歴。論点、未解決事項、補足説明を要約する。
- {PREFIX}_applicationresource: 申請に紐づく関連資料リンクを提示する。
- {PREFIX}_decision: 過去の判断結果と判断理由を参照する。
- {PREFIX}_decisionoption: 判断選択肢名を確認する。
- systemuser: 申請者、判断者、関係者の名前確認に使う。

## 判断待ち一覧
- ユーザーが「判断待ち」「私が判断すべき申請」「提出済みの申請一覧」と依頼したら、{PREFIX}_application のステージが提出済みの申請を検索する。
- 表示する申請は、利用者のセキュリティロールと Dataverse の行アクセスで参照できる範囲に限定する。
- 一覧には、申請タイトル、希望期限、提出日時、申請者、AI推奨判断があれば含める。
- 件数が多い場合は重要そうなものまたは期限が近いものを優先して表示する。

## 申請概要と関連資料
- 申請タイトルまたは申請リンクが提示されたら、該当申請を検索し、背景、目的、判断ポイントを要約する。
- {PREFIX}_applicationresource に関連資料がある場合は、リンク名とURLを一覧で提示する。
- スレッドがある場合は、主要論点、未解決事項、確認済み事項に分けて要約する。

## 類似案件検索
- 類似案件を聞かれたら、カテゴリ、申請タイトル、申請本文、AI申請概要、AI判断コメントを手がかりに過去の判断済み申請を探す。
- 類似案件ごとに、申請タイトル、判断結果、判断理由、今回の申請との共通点と相違点を簡潔に示す。
- 類似案件が十分に見つからない場合は、参考になる過去案件が少ないことを伝える。

## 推奨判断と判断コメントドラフト
- ユーザーが判断ドラフトを求めたら、申請内容、会話履歴、関連資料、過去類似案件、既存のAI判断結果を踏まえて回答する。
- 推奨判断は固定の判断選択肢である「承認」「却下」「差し戻し」のいずれかで提示する。追加確認が必要な場合は、推奨判断を「差し戻し」とし、確認事項を判断コメントに含める。
- 判断コメントドラフトは、そのまま Code Apps の判断コメント欄に貼り付けられる文章にする。
- 根拠は箇条書きで、リスク、前提条件、追加確認事項を分けて提示する。
- 最後に「最終判断は Code Apps の判断タブで確定してください」と案内する。
"""


def build_gpt_instructions() -> str:
    return GPT_INSTRUCTIONS

PREFERRED_PROMPTS = [
    {"title": "判断待ち一覧", "text": "私が判断すべき提出済みの申請を一覧で教えてください"},
    {"title": "申請の概要", "text": "この申請の背景・目的・論点を要約してください"},
    {"title": "関連資料", "text": "この申請の関連資料リンクを一覧で教えてください"},
    {"title": "類似案件", "text": "過去の類似案件と判断結果を教えてください"},
    {"title": "判断ドラフト", "text": "この申請の推奨判断と判断コメントのドラフトを作成してください"},
]

GREETING_MESSAGE = (
    "こんにちは。DecisionFlow Assistant です。判断待ち一覧、申請概要、関連資料、類似案件、判断コメントドラフトを支援します。"
    "申請リンクまたは申請タイトルを貼り付けてください。"
)

QUICK_REPLIES = [
    "判断待ちの申請を一覧で教えて",
    "申請の概要と論点を要約して",
    "関連資料リンクを教えて",
    "判断コメントのドラフトを作成して",
]

PROTECTED_TOPIC_PATTERNS = [
    "ConversationStart",
    "Escalate",
    "Fallback",
    "OnError",
    "EndofConversation",
    "MultipleTopicsMatched",
    "Search",
    "Signin",
    "ResetConversation",
    "StartOver",
]


def extract_bot_id(value: str) -> str | None:
    match = re.search(r"/bots/([0-9a-fA-F-]{36})", value)
    if match:
        return match.group(1)
    value = value.strip()
    if re.fullmatch(r"[0-9a-fA-F-]{36}", value):
        return value
    return None


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def build_gpt_yaml(existing_data: str = "") -> str:
    inst_block = "\n".join(f"  {line}" for line in build_gpt_instructions().splitlines())
    starter_lines: list[str] = []
    for prompt in PREFERRED_PROMPTS:
        starter_lines.append(f"  - title: {prompt['title']}")
        starter_lines.append(f"    text: {prompt['text']}")
    yaml_text = (
        "kind: GptComponentMetadata\n\n"
        f"displayName: {BOT_NAME}\n\n"
        f"instructions: |-\n{inst_block}\n\n"
        f"conversationStarters:\n\n{'\n\n'.join(starter_lines)}\n\n"
    )
    ai_settings = extract_ai_settings_section(existing_data)
    if ai_settings:
        yaml_text = yaml_text.rstrip("\n") + "\n\n" + ai_settings + "\n\n"
    return yaml_text


def extract_ai_settings_section(existing_data: str) -> str:
    index = existing_data.find("\naISettings:")
    if index < 0:
        index = existing_data.find("aISettings:")
    if index < 0:
        return ""
    return existing_data[index:].strip()


def build_conversation_start_yaml(existing_data: str = "") -> str:
    id_match = re.search(r"id:\s+(sendMessage_\w+)", existing_data)
    send_id = id_match.group(1) if id_match else "sendMessage_decisionflow01"
    greeting_oneline = GREETING_MESSAGE.replace("\n", " ")
    lines = [
        "kind: AdaptiveDialog",
        "beginDialog:",
        "  kind: OnConversationStart",
        "  id: main",
        "  actions:",
        "    - kind: SendActivity",
        f"      id: {send_id}",
        "      activity:",
        "        text:",
        f"          - {greeting_oneline}",
        "        speak:",
        f"          - \"{greeting_oneline}\"",
        "        quickReplies:",
    ]
    for reply in QUICK_REPLIES:
        lines.append("          - kind: MessageBack")
        lines.append(f"            text: {reply}")
    return "\n\n".join(lines) + "\n\n"


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


def delete_custom_topics(bot_id: str) -> None:
    print("\n=== カスタムトピック削除 ===")
    result = api_get(
        "botcomponents?"
        f"$filter=_parentbotid_value eq '{bot_id}' and (componenttype eq 1 or componenttype eq 9)"
        "&$select=botcomponentid,name,schemaname,componenttype"
    )
    deleted = 0
    for topic in result.get("value", []):
        schema = topic.get("schemaname", "")
        if any(pattern in schema for pattern in PROTECTED_TOPIC_PATTERNS) or ".action." in schema:
            continue
        api_delete(f"botcomponents({topic['botcomponentid']})")
        deleted += 1
    print(f"削除: {deleted} 件")


def enable_generative_orchestration(bot_id: str) -> dict:
    print("\n=== 生成オーケストレーション有効化 ===")
    bot = api_get(f"bots({bot_id})?$select=configuration")
    config = json.loads(bot.get("configuration", "{}") or "{}")
    overrides = {
        "$kind": "BotConfiguration",
        "settings": {"GenerativeActionsEnabled": True},
        "aISettings": {
            "$kind": "AISettings",
            "useModelKnowledge": True,
            "isFileAnalysisEnabled": True,
            "isSemanticSearchEnabled": True,
            "optInUseLatestModels": False,
        },
        "recognizer": {"$kind": "GenerativeAIRecognizer"},
    }
    merged = deep_merge(config, overrides)
    api_patch(f"bots({bot_id})", {"configuration": json.dumps(merged)})
    print("生成オーケストレーション有効化完了")
    return config


def set_gpt_instructions(bot_id: str, saved_config: dict) -> str | None:
    print("\n=== Instructions 設定 ===")
    default_schema = saved_config.get("gPTSettings", {}).get("defaultSchemaName", "")
    result = api_get(
        "botcomponents?"
        f"$filter=_parentbotid_value eq '{bot_id}' and componenttype eq 15"
        "&$select=botcomponentid,name,schemaname,data"
    )
    components = result.get("value", [])
    ui_component = None
    for component in components:
        if default_schema and component.get("schemaname") == default_schema:
            ui_component = component
            break
    if ui_component is None and components:
        ui_component = components[0]
    for component in components:
        if ui_component and component["botcomponentid"] == ui_component["botcomponentid"]:
            continue
        api_delete(f"botcomponents({component['botcomponentid']})")
    if not ui_component:
        raise RuntimeError("GPT コンポーネントが見つかりません。Copilot Studio UI で Bot が完全にロードされているか確認してください。")
    component_id = ui_component["botcomponentid"]
    api_patch(f"botcomponents({component_id})", {"data": build_gpt_yaml(ui_component.get("data", ""))})
    print("Instructions 設定完了")
    return component_id


def set_conversation_start(bot_id: str) -> None:
    print("\n=== 会話の開始設定 ===")
    result = api_get(
        "botcomponents?"
        f"$filter=_parentbotid_value eq '{bot_id}' and componenttype eq 9 and contains(schemaname,'ConversationStart')"
        "&$select=botcomponentid,schemaname,data"
    )
    topics = result.get("value", [])
    if not topics:
        print("ConversationStart が見つかりません。UI で確認してください。")
        return
    topic = topics[0]
    api_patch(f"botcomponents({topic['botcomponentid']})", {"data": build_conversation_start_yaml(topic.get("data", ""))})
    print("会話の開始設定完了")


def publish_bot(bot_id: str) -> None:
    print("\n=== 公開 ===")
    try:
        api_post(f"bots({bot_id})/Microsoft.Dynamics.CRM.PvaPublish", {})
        print("公開完了")
    except Exception as exc:
        print(f"公開に失敗しました。Copilot Studio UI で手動公開してください: {exc}")


def set_description(component_id: str | None) -> None:
    if component_id:
        api_patch(f"botcomponents({component_id})", {"description": BOT_DESCRIPTION})


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
    print("5. 判断確定用の専用 Adaptive Card Topic と Power Automate ツールを確認してください。")
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
        "If botcomponents YAML deployment is not safe in this environment, use manual Topic and tool setup and record the result in docs/PLAN.md.",
    ]


def main() -> None:
    if not DATAVERSE_URL:
        raise RuntimeError("DATAVERSE_URL が .env に設定されていません。")
    print("=" * 72)
    print("DecisionFlow Copilot Studio agent")
    print(f"Bot: {BOT_NAME}")
    print(f"Solution: {SOLUTION_NAME}")
    print("=" * 72)
    bot_id = find_bot()
    wait_for_provisioning(bot_id)
    set_icon(bot_id)
    delete_custom_topics(bot_id)
    saved_config = enable_generative_orchestration(bot_id)
    component_id = set_gpt_instructions(bot_id, saved_config)
    set_conversation_start(bot_id)
    publish_bot(bot_id)
    set_description(component_id)
    set_channel_manifest(bot_id)
    publish_bot(bot_id)
    print_manual_followups()
    print("\n完了")


if __name__ == "__main__":
    main()
