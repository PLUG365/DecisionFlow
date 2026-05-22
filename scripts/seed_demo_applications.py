"""
DecisionFlow デモ申請データ投入スクリプト

初期カテゴリ 5 種（顧客案件 / 部内案件 / 課内案件 / 他部署案件 / 事務処理）に対し、
それぞれ 1 件ずつ合計 5 件の申請を関連資料・申請者参加者・初期コメントとともに作成します。

- 冪等: ds_name で既存レコードを検索し、存在すれば作成をスキップします
- 前提: 対象環境で scripts/setup_dataverse.py を実行済みであること
        （カテゴリと判断選択肢、各テーブルが存在すること）
- 認証: auth_helper 経由（デバイスコード認証 / .auth_record.json を利用）

接続先環境の指定方法:
    1. CLI オプションで明示指定（推奨・自動化向け）
        py scripts/seed_demo_applications.py \
            --dataverse-url https://contoso.crm.dynamics.com \
            --tenant-id 12345678-1234-1234-1234-1234567890ab

    2. オプションを省略すると対話プロンプトで入力
        py scripts/seed_demo_applications.py

    PUBLISHER_PREFIX / SOLUTION_NAME はそれぞれ "ds" / "DecisionSupport" を既定値とし、
    `--publisher-prefix` / `--solution-name` または対話プロンプトで変更可能です。

注意:
    本スクリプトは .env を読み込みません。接続先は CLI オプションまたは対話プロンプトで
    都度指定する設計です（複数環境を意図せず取り違えないため）。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import UTC, datetime, timedelta

DEFAULT_PUBLISHER_PREFIX = "ds"
DEFAULT_SOLUTION_NAME = "DecisionSupport"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DecisionFlow に 5 件のデモ申請データを投入します（.env は使用しません）。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--dataverse-url",
        help="接続先 Dataverse 環境の URL (例: https://contoso.crm.dynamics.com)",
        default=None,
    )
    parser.add_argument(
        "--tenant-id",
        help="Azure AD テナント ID (GUID)",
        default=None,
    )
    parser.add_argument(
        "--publisher-prefix",
        help=f"Publisher の prefix (既定: {DEFAULT_PUBLISHER_PREFIX})",
        default=None,
    )
    parser.add_argument(
        "--solution-name",
        help=f"ソリューションのユニーク名 (既定: {DEFAULT_SOLUTION_NAME})",
        default=None,
    )
    return parser.parse_args()


def prompt_if_missing(value: str | None, label: str, *, default: str | None = None) -> str:
    """CLI で値が指定されていなければ対話プロンプトで取得する。"""
    if value:
        return value.strip()

    prompt = label
    if default:
        prompt += f" [{default}]"
    prompt += ": "

    try:
        entered = input(prompt).strip()
    except EOFError:
        entered = ""

    if not entered and default is not None:
        return default
    if not entered:
        raise SystemExit(f"{label} は必須です。")
    return entered


def resolve_config(args: argparse.Namespace) -> dict[str, str]:
    """CLI 引数を優先しつつ、未指定項目は対話で取得する。"""
    dataverse_url = prompt_if_missing(
        args.dataverse_url,
        "DATAVERSE_URL (例: https://contoso.crm.dynamics.com)",
    ).rstrip("/")

    tenant_id = prompt_if_missing(
        args.tenant_id,
        "TENANT_ID (Azure AD テナント ID)",
    )

    publisher_prefix = prompt_if_missing(
        args.publisher_prefix,
        "PUBLISHER_PREFIX",
        default=DEFAULT_PUBLISHER_PREFIX,
    )

    solution_name = prompt_if_missing(
        args.solution_name,
        "SOLUTION_NAME",
        default=DEFAULT_SOLUTION_NAME,
    )

    return {
        "DATAVERSE_URL": dataverse_url,
        "TENANT_ID": tenant_id,
        "PUBLISHER_PREFIX": publisher_prefix,
        "SOLUTION_NAME": solution_name,
    }


def apply_env(config: dict[str, str]) -> None:
    """os.environ に設定値を上書きし、後続の auth_helper / setup_dataverse 読み込みに反映する。

    auth_helper / setup_dataverse は内部で load_dotenv() を呼ぶが、
    python-dotenv の load_dotenv は既存の環境変数を上書きしない（override=False）ため、
    ここで先に設定すれば CLI / プロンプトで指定した値が優先される。
    """
    for key, value in config.items():
        os.environ[key] = value


STAGE_DRAFT = 100000000
ROLE_APPLICANT = 100000000
MESSAGE_KIND_COMMENT = 100000000

DEMO_APPLICATIONS = [
    {
        "name": "顧客案件: 戦略顧客向け新製品の特別価格適用",
        "category": "顧客案件",
        "body": (
            "戦略顧客 A 社から、新製品ライン X の年間 200 台導入を前提に、"
            "標準価格から 15% 値引きしてほしいとの要請がありました。"
            "標準割引枠（最大 8%）を超えるため、営業部長判断が必要です。\n\n"
            "【背景】A 社は当社売上上位 5 位の継続顧客。3 年契約での導入意向あり。\n"
            "【顧客影響】価格条件次第で競合他社 B への切り替えリスクあり。\n"
            "【判断してほしいこと】特別価格 15% 値引きの可否、適用条件・期間。\n"
            "【期限】先方の購買会議が来週開催のため、それまでに回答が必要です。"
        ),
        "due_days": 5,
        "ai_recommendation": "承認",
        "ai_comment": "戦略顧客の継続取引と将来の追加受注見込みを考慮すると、特別価格適用は妥当と判断します。ただし契約期間と最低発注数の明文化を条件とすることを推奨します。",
        "ai_risks": [
            "他顧客への価格条件波及リスク（特例である旨を契約書に明記すべき）",
            "為替・原材料変動による粗利率悪化リスク",
        ],
        "resources": [
            {
                "name": "A社 提案書（最新版）",
                "url": "https://contoso.sharepoint.com/sites/sales/Shared%20Documents/A_Proposal_v3.pptx",
                "description": "営業担当が作成した提案書。価格条件と導入スケジュールを記載。",
            },
            {
                "name": "標準価格表と割引ポリシー",
                "url": "https://contoso.sharepoint.com/sites/sales/Shared%20Documents/PricingPolicy_2026.pdf",
                "description": "標準割引上限 8% の根拠資料。例外承認のフロー記載あり。",
            },
            {
                "name": "競合B社価格調査メモ",
                "url": "https://contoso.sharepoint.com/sites/sales/Shared%20Documents/Competitor_B_Pricing.xlsx",
                "description": "営業情報部から共有された競合価格水準。",
            },
        ],
    },
    {
        "name": "部内案件: ナレッジ共有会の月次定例化",
        "category": "部内案件",
        "body": (
            "属人化している業務知識を組織化するため、月 1 回・1 時間のナレッジ共有会を"
            "部内全員参加で定例化したいです。業務時間内での開催と発表当番制について判断をお願いします。\n\n"
            "【目的】業務の属人化解消、若手育成、横連携の強化。\n"
            "【対象範囲】営業企画部全 24 名。毎月第 3 火曜 15:00-16:00。\n"
            "【選択肢】(1) 全員必須参加 / (2) 任意参加 / (3) 録画配信併用。\n"
            "【推奨案】(3) 録画配信併用での全員参加。\n"
            "【懸念点】発表準備の負荷増、繁忙期の参加率低下。"
        ),
        "due_days": 10,
        "ai_recommendation": "承認",
        "ai_comment": "中長期の組織力強化に寄与する施策として承認を推奨します。録画配信併用案は柔軟性が高く、繁忙期の参加率低下も緩和できます。",
        "ai_risks": [
            "発表準備が業務負荷となり、本業務に支障が出る可能性",
            "繁忙期に形骸化するリスク（3 ヶ月後にレビュー設定を推奨）",
        ],
        "resources": [
            {
                "name": "他部署事例: 開発部のナレッジ共有会運用",
                "url": "https://contoso.sharepoint.com/sites/devops/Pages/KnowledgeSharing.aspx",
                "description": "開発部で 2 年継続している共有会の運用方法と効果測定資料。",
            },
            {
                "name": "部内アンケート結果（共有会希望調査）",
                "url": "https://contoso.sharepoint.com/sites/salesplan/Lists/SurveyResults/2026Q1.aspx",
                "description": "回答率 92%、共有会開催に賛成 78%。詳細コメントあり。",
            },
        ],
    },
    {
        "name": "課内案件: 週次報告フォーマットの簡素化",
        "category": "課内案件",
        "body": (
            "現行の週次報告（A4 2 枚 + Excel 進捗表）が形骸化しており、"
            "作成に毎週 1 人あたり 2 時間以上かかっています。"
            "Teams メッセージ + 進捗表の 1 シート化に簡素化したいです。\n\n"
            "【現状】Word 報告書 + Excel 進捗表 + Teams 共有の 3 重作業。\n"
            "【課題】作成工数が大きく、内容も読まれていない傾向。\n"
            "【提案】Teams メッセージ（テンプレ）+ Excel 1 シート化。\n"
            "【必要な判断】試行 3 ヶ月の課長承認、上位への報告継続要否。\n"
            "【希望期限】次の月初から試行開始。"
        ),
        "due_days": 7,
        "ai_recommendation": "承認",
        "ai_comment": "報告の質を維持しつつ工数を削減する妥当な提案です。3 ヶ月後のレビューを条件に承認を推奨します。上位部門への報告は別途要件整理が必要です。",
        "ai_risks": [
            "上位部門が現行 Word 報告を前提にしている可能性（要事前確認）",
            "簡素化により重要トピックの埋没リスク",
        ],
        "resources": [
            {
                "name": "現行週次報告サンプル（2026年4月分）",
                "url": "https://contoso.sharepoint.com/sites/salesplan-section1/Shared%20Documents/WeeklyReports/2026-04.docx",
                "description": "現在運用中の Word 報告書サンプル。フォーマット参照用。",
            },
            {
                "name": "簡素化後フォーマット案（Teams テンプレ）",
                "url": "https://contoso.sharepoint.com/sites/salesplan-section1/Shared%20Documents/Proposals/WeeklyReport_Simple.md",
                "description": "提案フォーマット。Teams メッセージ用テンプレート 5 項目構成。",
            },
            {
                "name": "工数試算スプレッドシート",
                "url": "https://contoso.sharepoint.com/sites/salesplan-section1/Shared%20Documents/Proposals/EffortEstimate.xlsx",
                "description": "現行 vs 簡素化案の年間工数差分試算（約 480 時間削減見込み）。",
            },
        ],
    },
    {
        "name": "他部署案件: マーケ・開発合同レビュー会の実施",
        "category": "他部署案件",
        "body": (
            "新製品 Y の市場投入準備にあたり、マーケティング部と開発部の認識ずれを"
            "解消するため、来月 2 週目に合同レビュー会を実施したいです。"
            "両部門の参加調整と議題確定について判断をお願いします。\n\n"
            "【関係部署】マーケティング部、開発部、営業企画部（事務局）。\n"
            "【依頼事項】合同レビュー会の開催承認、両部門メンバーの参加依頼。\n"
            "【影響範囲】新製品 Y の Go-to-Market 計画全体。\n"
            "【期限】来月 2 週目（5/12 週）。\n"
            "【未解決事項】開発部の参加可能メンバー、議事録担当の所属。"
        ),
        "due_days": 14,
        "ai_recommendation": "承認",
        "ai_comment": "市場投入直前に部門間の認識合わせは必須です。事務局を営業企画部が担う前提であれば、開催判断は妥当と判断します。",
        "ai_risks": [
            "開発部側の参加可否が未確認（事前打診が必要）",
            "議事録・タスク管理のオーナーが曖昧になりやすい",
        ],
        "resources": [
            {
                "name": "新製品Y Go-to-Market 計画書 v1.2",
                "url": "https://contoso.sharepoint.com/sites/product-Y/Shared%20Documents/GTM_Plan_v1.2.pptx",
                "description": "現行 GTM 計画。マーケティング施策と開発スケジュールを統合。",
            },
            {
                "name": "前回マーケ・開発調整会議 議事録",
                "url": "https://contoso.sharepoint.com/sites/product-Y/Shared%20Documents/Minutes/2026-04-marketing-dev.docx",
                "description": "前回の調整会議で残った論点と未解決事項のリスト。",
            },
        ],
    },
    {
        "name": "事務処理: 海外出張精算の例外承認（領収書一部欠落）",
        "category": "事務処理",
        "body": (
            "4 月の北米出張において、現地タクシー（合計 ¥18,400 相当）の領収書を紛失しました。"
            "支払証跡として現地支払履歴（クレジットカード明細）と業務日報を添付します。"
            "経費規程上の例外承認をお願いします。\n\n"
            "【処理内容】領収書欠落分の経費精算（タクシー代 ¥18,400）。\n"
            "【根拠】支払履歴（VISA 明細）、業務日報、訪問先メール。\n"
            "【期限】当月精算締め（月末）。\n"
            "【添付資料】カード明細 PDF、業務日報、訪問先確認メール。"
        ),
        "due_days": 3,
        "ai_recommendation": "承認",
        "ai_comment": "支払履歴と業務日報の整合がとれており、金額も社内例外承認の閾値内です。承認可能と判断します。再発防止のため、領収書管理ルールの再周知を推奨します。",
        "ai_risks": [
            "領収書欠落の常態化リスク（同一申請者の例外回数を監視推奨）",
            "金額が高額となる場合は例外承認では対応不可（閾値は経費規程参照）",
        ],
        "resources": [
            {
                "name": "VISA カード明細（4月分・該当部分抜粋）",
                "url": "https://contoso.sharepoint.com/sites/expense/Personal/u12345/Shared%20Documents/Travel_2026-04/VISA_Statement.pdf",
                "description": "現地支払履歴。タクシー利用 4 件、合計 ¥18,400 該当箇所をハイライト。",
            },
            {
                "name": "出張業務日報(4/8-4/12 北米)",
                "url": "https://contoso.sharepoint.com/sites/expense/Personal/u12345/Shared%20Documents/Travel_2026-04/Daily_Report.xlsx",
                "description": "訪問先・移動経路・面談相手を記録した業務日報。",
            },
            {
                "name": "社内経費規程 第 12 条（領収書欠落時の例外承認）",
                "url": "https://contoso.sharepoint.com/sites/hr/Shared%20Documents/Policies/ExpensePolicy_2026.pdf",
                "description": "領収書欠落時の例外承認手続きと閾値の規定。",
            },
        ],
    },
]


def iso_utc(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def find_category_ids(api_get, category_set: str, prefix: str, names: list[str]) -> dict[str, str]:
    rows = api_get(f"{category_set}?$select={prefix}_name,{prefix}_categoryid").get("value", [])
    by_name = {row.get(f"{prefix}_name"): row.get(f"{prefix}_categoryid") for row in rows}
    missing = [name for name in names if name not in by_name]
    if missing:
        raise SystemExit(
            f"次のカテゴリが Dataverse に存在しません: {missing}\n"
            "先に対象環境で `py scripts/setup_dataverse.py` を実行してください。"
        )
    return {name: by_name[name] for name in names}


def seed(config: dict[str, str]) -> None:
    print("=" * 72)
    print("DecisionFlow デモ申請データ投入")
    print("=" * 72)
    print(f"DATAVERSE_URL    : {config['DATAVERSE_URL']}")
    print(f"TENANT_ID        : {config['TENANT_ID']}")
    print(f"PUBLISHER_PREFIX : {config['PUBLISHER_PREFIX']}")
    print(f"SOLUTION_NAME    : {config['SOLUTION_NAME']}")
    print("-" * 72)

    # 環境変数を適用してから auth_helper / setup_dataverse をインポートする
    apply_env(config)

    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

    from auth_helper import api_get  # noqa: WPS433 (import after env apply is intentional)
    from setup_dataverse import (  # noqa: WPS433
        PREFIX,
        current_user_id,
        ensure_row,
        entity_set,
        navprop_by_lookup_attr,
    )

    user_id = current_user_id()
    systemuser_set = entity_set("systemuser")
    category_set = entity_set(f"{PREFIX}_category")
    application_set = entity_set(f"{PREFIX}_application")
    participant_set = entity_set(f"{PREFIX}_participant")
    message_set = entity_set(f"{PREFIX}_message")
    resource_set = entity_set(f"{PREFIX}_applicationresource")

    app_category_nav = navprop_by_lookup_attr(f"{PREFIX}_application", f"{PREFIX}_categoryid")
    participant_app_nav = navprop_by_lookup_attr(f"{PREFIX}_participant", f"{PREFIX}_applicationid")
    participant_user_nav = navprop_by_lookup_attr(f"{PREFIX}_participant", f"{PREFIX}_userid")
    participant_addedby_nav = navprop_by_lookup_attr(f"{PREFIX}_participant", f"{PREFIX}_addedbyid")
    message_app_nav = navprop_by_lookup_attr(f"{PREFIX}_message", f"{PREFIX}_applicationid")
    resource_app_nav = navprop_by_lookup_attr(f"{PREFIX}_applicationresource", f"{PREFIX}_applicationid")

    required_categories = [app["category"] for app in DEMO_APPLICATIONS]
    category_ids = find_category_ids(api_get, category_set, PREFIX, required_categories)

    now = datetime.now(UTC)
    now_iso = iso_utc(now)

    for app in DEMO_APPLICATIONS:
        due_iso = (now + timedelta(days=app["due_days"])).date().isoformat()
        body = {
            f"{PREFIX}_body": app["body"],
            f"{PREFIX}_stage": STAGE_DRAFT,
            f"{PREFIX}_duedate": due_iso,
            # ds_submittedat は Draft のため未設定（提出時にセットされる想定）
            f"{PREFIX}_aiapplicationsummary": (
                f"{app['category']}の申請。判断者向けに目的・背景・依頼内容を要約しています（デモデータ）。"
            ),
            f"{PREFIX}_aiconversationsummary": "提出時点では会話履歴はありません。",
            f"{PREFIX}_aidecisionoptiontext": app["ai_recommendation"],
            f"{PREFIX}_aidecisioncomment": app["ai_comment"],
            f"{PREFIX}_aidecisionbasis": json.dumps(
                {"risks": app["ai_risks"], "similarCases": []}, ensure_ascii=False
            ),
            f"{PREFIX}_aidecisionupdatedat": now_iso,
        }
        if app_category_nav:
            body[f"{app_category_nav}@odata.bind"] = (
                f"/{category_set}({category_ids[app['category']]})"
            )
        # 判断者 (ds_deciderid) は意図的に未設定にする。
        # デモ確認時に Code Apps UI から実環境の判断者ユーザーをアサインできるようにするため。

        app_id = ensure_row(application_set, app["name"], body)
        print(f"\n[OK] Application: {app['name']}")

        if participant_app_nav and participant_user_nav:
            participant_body = {
                f"{PREFIX}_role": ROLE_APPLICANT,
                f"{PREFIX}_addedat": now_iso,
                f"{participant_app_nav}@odata.bind": f"/{application_set}({app_id})",
                f"{participant_user_nav}@odata.bind": f"/{systemuser_set}({user_id})",
            }
            if participant_addedby_nav:
                participant_body[f"{participant_addedby_nav}@odata.bind"] = (
                    f"/{systemuser_set}({user_id})"
                )
            ensure_row(participant_set, f"{app['name']} - 申請者", participant_body)
            print("    - Participant: 申請者")

        if message_app_nav:
            ensure_row(
                message_set,
                f"{app['name']} - 初期コメント",
                {
                    f"{PREFIX}_body": "申請を作成しました。関連資料を確認のうえ、ご判断をお願いします。",
                    f"{PREFIX}_kind": MESSAGE_KIND_COMMENT,
                    f"{message_app_nav}@odata.bind": f"/{application_set}({app_id})",
                },
            )
            print("    - Message: 初期コメント")

        if resource_app_nav:
            for resource in app["resources"]:
                ensure_row(
                    resource_set,
                    f"{app['name']} - {resource['name']}",
                    {
                        f"{PREFIX}_url": resource["url"],
                        f"{PREFIX}_description": resource["description"],
                        f"{resource_app_nav}@odata.bind": f"/{application_set}({app_id})",
                    },
                )
                print(f"    - Resource: {resource['name']}")

    print("\n完了: デモ申請 5 件と関連資料の投入が終わりました。")


def main() -> int:
    args = parse_args()
    config = resolve_config(args)
    seed(config)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}")
        traceback.print_exc()
        raise SystemExit(1)
