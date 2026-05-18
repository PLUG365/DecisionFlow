# Implementation Plan: Copilot Studio チャットで Adaptive Card 判断確定

**Branch**: `001-confirm-adaptive-card` | **Date**: 2026-05-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-confirm-adaptive-card/spec.md`

## Summary

Copilot Studio チャットで提示する Adaptive Card から、案件に割り当て済み判断者のみが判断を確定できるようにする。
競合時は first-write-wins、カードは single-use（1回表示限り）とし、入力は Code Apps と同じく判断選択肢（承認・却下・差し戻しの3択）と判断理由の2項目を必須にする。
判断確定の正本は `ds_decision` 作成に集約し、Code Apps と Copilot Studio のどちらから判断が作成されても、Power Automate の判断後整合フローが案件状態・案件詳細画面・既存通知フローを自動的に同じ結果へ揃える。

## Technical Context

**Language/Version**:

- TypeScript 5.x / React 19 / Vite 7（Code Apps 側）
- Python 3.11（デプロイスクリプト・フロー定義側）

**Primary Dependencies**:

- `@microsoft/power-apps`, TanStack Query, shadcn/ui
- Dataverse Web API, Power Automate Flow API, Copilot Studio 設定スクリプト群

**Storage**:

- Dataverse (`ds_application`, `ds_decision`, `ds_decisionoption`, `ds_participant`)

**Testing**:

- Frontend: `npm test` (Vitest)
- Scripts/Flow: `py -m unittest`（既存 `tests/test_notification_flows.py` など）

**Target Platform**:

- Power Apps Code Apps + Power Automate + Copilot Studio（Teams/M365 Copilot 経由）

**Project Type**:

- 既存モノレポ内の Web app + automation scripts 拡張

**Performance Goals**:

- SC-001: 95% の判断者がカード提示から 60 秒以内に確定完了
- SC-004: 確定後 1 分以内に 95% の関係者へ可視化/通知

**Constraints**:

- single-use card（再表示時は再発行）
- first-write-wins（後続確定拒否）
- Adaptive Card の入力は Code Apps と同じく判断選択肢3択（承認・却下・差し戻し）と判断理由の2項目、いずれも必須
- 実行許可は「案件割り当て済み判断者のみ」
- `ds_application` のステージ更新は Copilot カード処理に直接持たせず、`ds_decision` 作成トリガーの Power Automate 整合フローへ委譲

**Scale/Scope**:

- 初期リリースは 1 件ずつの個別確定のみ（一括確定は対象外）
- 既存 DecisionFlow ソリューション内での機能追加

## Constitution Check (Pre-Phase 0 Gate)

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

- I. Single-Solution Integrity: **PASS**
  - 既存 `DecisionSupport` ソリューション内で Dataverse/Flow/Copilot を拡張する計画。
- II. Deterministic, Idempotent Deployment: **PASS**
  - 競合時 first-write-wins と single-use card により重複確定防止。判断後整合は `ds_decision` 作成トリガーに集約し、Code Apps/Copilot Studio 間の二重実装を避ける。環境値は `.env` 前提。
- III. Security and Data Hygiene: **PASS**
  - 案件割り当て済み判断者のみに確定許可。秘匿情報追加なし。
- IV. Verification Before Merge: **PASS**
  - `npm test`, `npm run build`, Python unittest を計画に含む。
- V. Documentation as Source of Truth: **PASS**
  - この計画に加え research/data-model/contracts/quickstart を同一 feature 配下に作成。

## Phase 0: Research Outcome

Research artifacts completed in [research.md](research.md):

- 競合制御: first-write-wins
- カード有効性: single-use
- 入力必須: 判断選択肢（承認・却下・差し戻し）と判断理由
- 共有チャネル: 画面 + 既存通知フロー
- 実行権限: 案件割り当て済み判断者のみ
- Code Apps/Copilot Studio 整合: `ds_decision` 作成を正本イベントにし、Power Automate 整合フローで案件状態・通知を自動反映

All previously open decisions are now resolved.

## Phase 1: Design & Contracts

### Data Model

- Completed: [data-model.md](data-model.md)
- 主要エンティティ:
  - `ds_application`（状態遷移: Submitted -> Decided）
  - `ds_decision`（監査履歴）
  - `ds_decisionoption`（判断結果マスタ）
  - `ds_participant`（通知対象）
  - `Decision_OnCreated` / 判断後整合フロー（`ds_decision` 作成後の案件状態・通知自動整合）

### Interface Contracts

- Completed: [contracts/adaptive-card-decision-confirmation.md](contracts/adaptive-card-decision-confirmation.md)
- 契約内容:
  - Adaptive Card submit リクエスト形
  - `succeeded / already_processed / forbidden / invalid_target` 応答
  - single-use / authorization / `ds_decision` 正本イベント / propagation の振る舞い契約

### Quickstart

- Completed: [quickstart.md](quickstart.md)
- 実装順序、最小検証、ロールバック方針を記載

## Project Structure

### Documentation (this feature)

```text
specs/001-confirm-adaptive-card/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── adaptive-card-decision-confirmation.md
└── tasks.md
```

### Source Code (repository root)

```text
src/
├── hooks/
│   └── use-decisionflow.ts
├── pages/
│   ├── application-detail.tsx
│   └── applications.tsx
├── services/
│   └── dataverse-service.ts
└── generated/
    └── services/

scripts/
├── deploy_copilot_agent.py
├── deploy_notification_flows.py
├── (new or updated) deploy_decision_reconciliation_flow.py
└── setup_security_roles.py

tests/
├── test_notification_flows.py
├── test_security_roles.py
└── (new tests for card confirmation)
```

**Structure Decision**: 既存の single project 構成を維持し、Copilot Studio 側は `ds_decision` 作成までを担当する。案件状態・通知・表示整合は `scripts` で追加/更新する Power Automate フローに集約し、Code Apps 側に同じ確定処理を再実装しない。

## Post-Design Constitution Check

- I. Single-Solution Integrity: **PASS**（新規成果物は既存ソリューション前提）
- II. Deterministic, Idempotent Deployment: **PASS**（契約・モデルで `ds_decision` 正本イベントと Power Automate 整合ルールを明記）
- III. Security and Data Hygiene: **PASS**（許可対象ユーザー範囲を仕様化）
- IV. Verification Before Merge: **PASS**（quickstart に検証手順を明記）
- V. Documentation as Source of Truth: **PASS**（Phase 0/1成果物一式を作成）

## Complexity Tracking

No constitution violations requiring justification.
