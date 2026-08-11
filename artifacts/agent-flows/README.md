# Agent flow snapshots

このディレクトリは、Copilot Studio の agent flow を FlowAgent MCP の `get_flow` で読み取った
監査用スナップショットを保持する。接続トークンや実行 URL は保存しない。

`DecisionFlow_Phase3_AgentNode_Harness/flowagent.snapshot.json` は Phase 3 の再現可能性調査用で、
2026-08-11 時点の MinoruEnv の**公開前の下書き**を表す履歴資料である。未公開時は PAC CLI の
component type 29 による追加が `workflow ... Does Not Exist`、Power Automate の Add existing cloud flow も
候補なしだった。

公開後は同じ Flow ID を `DecisionSupport` Solution へ component type 29 として追加できた。
`solution-export.workflow.json` は、unmanaged Solution export に含まれた公式 Workflow JSON から
対象フローだけを保存したもの。`InvokeAgent`、エージェント schema name、6個の必須 trigger 入力、structured output、
接続参照の論理名をSolution成果物として再現できることを確認した。`decision-output.schema.json` は現行
AI Builder契約と同じ6項目を持ち、全項目・ネスト項目を必須化して追加プロパティを禁止するAgent node用契約。
手動 Button trigger の `application` / `resources` / `conversation` / `similarCases` / `decisionOptions` /
`categoryRegulation` をプロンプトへ動的に差し込み、代表入力のデザイナーテストで6項目とネスト配列を
実機確認済み。Power Apps V2 trigger への置換とDataverse読取りはまだ行っていない。試験後のクラウド上の
フローは停止状態へ戻している。

採用・運用の正本へ昇格する前に、次を満たすこと。

1. 環境固有の接続参照を Solution の publisher prefix に置き換える。
2. 別環境への import 後も agent flow、Copilot Studio plan、Stopped 状態が維持されることを確認する。
3. 実運用のプロンプトと structured output を正本化し、意味的な受入テストを通す。
4. 通常実行による Credits 測定は、回数と影響を示して別途承認を得る。
