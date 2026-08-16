"""フローの直近の実行を、アクション単位で読む。

**赤いトーストから原因を推測しない。** 画面に出る文言は1つでも、その裏で
起きうることは複数ある。

  - `Get_file_content` の出力に `$content` が入っていない（base64 の受け渡しが違う）
  - `Run_prompt` が分岐の中にあり、`Respond` が分岐の外からそれを参照している
  - プロンプト自体が失敗している（クレジット切れ、ドキュメント入力が通らない）

**この3つは画面上まったく同じ症状**（説明が空 + `generation-failed`）になる。
実行履歴を1回読めば、どれなのかが1往復で分かる。

使い方（MinoDev2 へ向ける場合）:

    $env:PP_AUTH_RECORD_PATH="<repo>\\.auth_record.minodev2.json"
    $env:PP_TOKEN_CACHE_NAME="power_platform_token_cache_minodev2"
    py scripts/inspect_flow_run.py [フロー名]

読み取りのみ。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from auth_helper import api_get, flow_api_call  # noqa: E402

DEFAULT_FLOW_NAME = "ApplicationResource_DescribeLink"

# 中身そのものは見たくない（base64 が数 MB 流れてくる）。
# **「入っているか」と「どれくらいか」だけ**分かればよい。
PREVIEW_CHARS = 300


def _read_environment_id() -> str:
    config_path = ROOT / "power.config.json"
    return json.loads(config_path.read_text(encoding="utf-8"))["environmentId"]


def _summarize(value: object, depth: int = 0) -> object:
    """長い値を要約する。base64 を丸ごと出力に流さないため。"""
    if isinstance(value, str):
        if len(value) > PREVIEW_CHARS:
            return f"<{len(value)} 文字> {value[:PREVIEW_CHARS]}…"
        return value
    if isinstance(value, dict):
        if depth >= 4:
            return f"<dict: {sorted(value)}>"
        return {key: _summarize(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        if depth >= 4:
            return f"<list len={len(value)}>"
        return [_summarize(item, depth + 1) for item in value[:5]]
    return value


def _fetch(url: str) -> dict:
    """入出力の実体を取る。**Authorization ヘッダーを付けない。**

    `inputsLink` / `outputsLink` の URI は既に署名済み（`sig=` を含む SAS）なので、
    Bearer を足すと 401 になる。署名が資格そのものなので、重ねてはいけない。
    """
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    return response.json()


def main() -> None:
    flow_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FLOW_NAME

    workflows = api_get(
        f"workflows?$filter=name eq '{flow_name}' and category eq 5"
        "&$select=workflowid,name&$orderby=createdon desc&$top=1"
    ).get("value", [])
    if not workflows:
        raise RuntimeError(f"フロー '{flow_name}' が見つかりません。")
    workflow_id = workflows[0]["workflowid"]

    environment_id = _read_environment_id()
    base = (
        f"/providers/Microsoft.ProcessSimple/environments/{environment_id}"
        f"/flows/{workflow_id}"
    )
    print(f"flow       : {flow_name} ({workflow_id})")

    runs = flow_api_call("GET", f"{base}/runs").get("value", [])
    if not runs:
        print("実行履歴がありません。まだ一度も呼ばれていません。")
        return

    run = runs[0]
    properties = run.get("properties", {})
    print(f"latest run : {run['name']}")
    print(f"  status   : {properties.get('status')}")
    print(f"  start    : {properties.get('startTime')}  end: {properties.get('endTime')}")
    if properties.get("error"):
        print(f"  error    : {json.dumps(properties['error'], ensure_ascii=False)[:800]}")

    actions = flow_api_call("GET", f"{base}/runs/{run['name']}/actions").get("value", [])

    for action in actions:
        action_properties = action.get("properties", {})
        print(f"\n--- {action['name']}  status={action_properties.get('status')}")
        if action_properties.get("error"):
            print(f"    error : {json.dumps(action_properties['error'], ensure_ascii=False)[:800]}")

        # 入出力は本体ではなくリンクで返る。**取りに行かないと中身は分からない。**
        for label in ("inputsLink", "outputsLink"):
            link = action_properties.get(label)
            if not link or not link.get("uri"):
                continue
            try:
                payload = _fetch(link["uri"])
            except Exception as exc:  # noqa: BLE001
                print(f"    {label}: 取得できませんでした ({exc})")
                continue
            print(f"    {label}:")
            print("      " + json.dumps(_summarize(payload), ensure_ascii=False, indent=2).replace("\n", "\n      ")[:3000])


if __name__ == "__main__":
    main()
