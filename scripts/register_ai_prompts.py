"""AI Hub の UI で作成済みの AI Builder プロンプト3本を検査し、ソリューションのコンポーネントに登録する。

**プロンプト自体の作成はこのスクリプトの範囲外。** `ResourceDescription` /
`ResourceDescriptionText` / `DecisionRecommendation` はどれも、この環境の権限では
API 経由の新規作成・更新ができない（実測。各フロー配備スクリプトの docstring を参照）。
先に AI Hub の UI で3本とも作成・保存してから、このスクリプトを実行する。
指示文の正本は `docs/ai-builder-prompts/` にある。

**検査は自前で持たず、各フロー配備スクリプトの検査関数をそのまま呼ぶ。**
`_require_prompt` / `deploy_ai_prompt` は入力名・code interpreter の ON/OFF・
指示文の中身まで見ている（`deploy_resource_description_flow.py` / `deploy_ai_decision.py`
の docstring を参照）。ここで存在確認だけの緩い検査を別に持つと、8-1 では通ったのに
8-2 のフロー配備で初めて壊れているのが分かる、という二度手間になる。

このスクリプトができるのは検査と、ソリューションへの追加（`AddSolutionComponent`）だけ。
追加は冪等（2026-08-20、MinoDev2 で実測）なので、繰り返し実行しても壊れない。

`setup_dataverse.py` は新しい環境を作るたびにソリューションを作り直すため、この登録は
一度きりの作業ではなく**環境を作るたびに繰り返し必要**。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from auth_helper import api_post  # noqa: E402
import deploy_ai_decision as _ai_decision  # noqa: E402
import deploy_resource_description_flow as _resource_description  # noqa: E402

load_dotenv()

SOLUTION_NAME = os.environ.get("SOLUTION_NAME", "DecisionSupport")

# **`AddSolutionComponent` の `ComponentType` は当てずっぽうでは出せない。**
# 標準の componenttype グローバル選択肢に AI Model は載っておらず（Microsoft Learn の
# 記載どおり、一部の新しい種別はここに無い）、MinoDev2 で実際に UI から「既存を追加」した
# プロンプトの `solutioncomponent` 行を読んで実測した値
# （2026-08-20、`componenttypename` = 「AI プロジェクト」）。
AI_MODEL_COMPONENT_TYPE = 401

# (表示名, 検査関数)。検査関数は使える状態なら model_id を返し、
# 使えない状態なら中身つきの RuntimeError を投げる（それぞれの docstring を参照）。
CHECKS = [
    (_resource_description.AI_PROMPT_NAME, _resource_description.find_ai_prompt),
    (_resource_description.AI_TEXT_PROMPT_NAME, _resource_description.find_text_prompt),
    (_ai_decision.AI_PROMPT_NAME, _ai_decision.deploy_ai_prompt),
]


def _add_to_solution(model_id: str, name: str) -> None:
    api_post(
        "AddSolutionComponent",
        {
            "ComponentId": model_id,
            "ComponentType": AI_MODEL_COMPONENT_TYPE,
            "SolutionUniqueName": SOLUTION_NAME,
            "AddRequiredComponents": False,
            "DoNotIncludeSubcomponents": False,
        },
    )
    print(f"  {name}: ソリューション '{SOLUTION_NAME}' のコンポーネントに追加しました")


def main() -> None:
    print("=== AI Builder プロンプトを検査し、ソリューションへ登録 ===")
    failures: list[str] = []

    for name, check in CHECKS:
        try:
            model_id = check()
        except RuntimeError as exc:
            failures.append(f"--- {name} ---\n{exc}")
            print(f"  {name}: 検査に失敗しました")
            continue
        _add_to_solution(model_id, name)

    if failures:
        raise RuntimeError("\n\n".join(failures))

    print("=== 3本とも検査を通り、ソリューションへの登録を確認しました ===")


if __name__ == "__main__":
    main()
