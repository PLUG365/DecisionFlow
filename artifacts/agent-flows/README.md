# Agent flow snapshots

このディレクトリは、Copilot Studio の agent flow を FlowAgent MCP の `get_flow` で読み取った
監査用スナップショットを保持する。接続トークンや実行 URL は保存しない。

`DecisionFlow_Phase3_AgentNode_Harness/flowagent.snapshot.json` は Phase 3 の再現可能性調査用で、
2026-08-11 時点の MinoruEnv の下書きを表す。完全な definition と接続参照の論理名は取得できたが、
このフローは Solution 未所属であり、このJSON単体の import / deploy は未検証である。PAC CLI の
component type 29 による追加は `workflow ... Does Not Exist`、Power Automate の Add existing cloud flow は
From Dataverse / Outside Dataverse の双方に候補なしとなった。未公開 agent flow は workflow component として
Solution へ追加できないため、公式 export の確認には公開が必要と判断する。

採用・運用の正本へ昇格する前に、次を満たすこと。

1. 公開の影響とCredits測定回数をレビューした後、Solution に追加して公式成果物との差分を確認する。
2. 環境固有の接続参照を Solution の publisher prefix に置き換える。
3. import 後も agent flow、Copilot Studio plan、Stopped 状態が維持されることを確認する。
4. 公開・実行・Credits 測定は、回数と影響を示して別途承認を得る。
