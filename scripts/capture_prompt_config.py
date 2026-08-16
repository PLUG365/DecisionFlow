"""AI Builder プロンプトの CustomConfiguration を読み戻して、形をそのまま捕まえる。

**なぜ要るか。** code interpreter とドキュメント入力を CustomConfiguration に
どう書くかは一次情報に無く、既存の text 専用プロンプトからも逆算できなかった
（保存された JSON が、`deploy_ai_decision.py` が書いた JSON と1バイト違わない）。
Learn の開発者向け記事は「You must use the UI to create code interpreter enabled
prompts」と書いている。

そこで **UI で1つ作らせて、プラットフォームが書いた形を読む。** invoker のときに
`_api/web/currentUser` で身元を名乗らせたのと同じ手で、推測を実測に変える。

使い方（MinoDev2 へ向ける場合）:

    $env:PP_AUTH_RECORD_PATH="<repo>\\.auth_record.minodev2.json"
    $env:PP_TOKEN_CACHE_NAME="power_platform_token_cache_minodev2"
    py scripts/capture_prompt_config.py ResourceDescription

**主環境の認証レコードを上書きしないため、この2つは必ずセットで指定する。**
読み取りのみ。書き込みはしない。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from auth_helper import api_get  # noqa: E402

# 既存プロンプトと見比べたいので、両方まとめて出せるようにしておく。
DEFAULT_PROMPT_NAME = "ResourceDescription"

# 全文を置く先。生成物なのでリポジトリには入れない。
OUTPUT_DIR = ROOT / "scripts" / "_captured"

# 「text 専用と何が違うか」を見たいので、差が出そうなキーだけ名指しで覗く。
# ここに無いキーが増えていたら全文ファイルのほうに出る。
NOTABLE_TOP_LEVEL_KEYS = ("code", "signature", "codeInterpreter", "runtime", "tools")


def dump_model(prompt_name: str) -> int:
    models = api_get(
        f"msdyn_aimodels?$filter=msdyn_name eq '{prompt_name}'"
        "&$select=msdyn_aimodelid,msdyn_name,statecode,createdon"
        "&$orderby=createdon desc"
    ).get("value", [])

    if not models:
        print(f"'{prompt_name}' という名前のプロンプトが見つかりません。")
        print("AI Hub で作成されているか、名前が一致しているかを確認してください。")
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for model in models:
        model_id = model["msdyn_aimodelid"]
        print(f"\n===== {model['msdyn_name']}  id={model_id}  statecode={model['statecode']}")

        configs = api_get(
            f"msdyn_aiconfigurations?$filter=_msdyn_aimodelid_value eq '{model_id}'"
            "&$select=msdyn_aiconfigurationid,msdyn_name,msdyn_type,statecode,"
            "msdyn_customconfiguration&$orderby=createdon desc"
        ).get("value", [])

        for config in configs:
            raw = config.get("msdyn_customconfiguration")
            print(
                f"\n--- {config['msdyn_name']}  type={config['msdyn_type']} "
                f"state={config['statecode']}  "
                f"customconfiguration={'あり' if raw else 'null'}"
            )
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                print("    JSON として読めませんでした。生のまま先頭だけ出します:")
                print(raw[:3000])
                continue

            target = OUTPUT_DIR / f"{prompt_name}_{config['msdyn_aiconfigurationid']}.json"
            target.write_text(
                json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"    → {target}")

            print(f"    version : {parsed.get('version')}")
            print(f"    settings: {json.dumps(parsed.get('settings'), ensure_ascii=False)}")
            for key in NOTABLE_TOP_LEVEL_KEYS:
                if key in parsed:
                    value = parsed[key]
                    shown = value if isinstance(value, (bool, int)) else str(value)[:200]
                    print(f"    {key:9}: {shown}")
            print("    inputs  :")
            for item in parsed.get("definitions", {}).get("inputs", []):
                print(f"      - {json.dumps(item, ensure_ascii=False)[:400]}")
            output = parsed.get("definitions", {}).get("output")
            print(f"    output  : {json.dumps(output, ensure_ascii=False)[:400]}")

    return 0


def main() -> None:
    names = sys.argv[1:] or [DEFAULT_PROMPT_NAME]
    exit_code = 0
    for name in names:
        exit_code |= dump_model(name)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
