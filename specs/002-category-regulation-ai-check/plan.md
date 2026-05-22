# Implementation Plan: カテゴリ別レギュレーションAIチェック

**Branch**: `003-category-regulation-ai-check` | **Date**: 2026-05-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-category-regulation-ai-check/spec.md`

## Summary

カテゴリごとに1つの複数行レギュレーション文章を保持し、申請者の下書き時AI事前確認、提出時の必須AI確認、判断者向けAI判断支援に活用する。実装は既存の `ds_category`、`ds_application`、`Application_GenerateAiDecision`、既存AI判断格納列を拡張して行い、AI判断結果の履歴やレギュレーションスナップショットは追加しない。提出操作は直接 Submitted へ遷移せず、下書き保存後にAI判断取得フローを実行し、申請者が結果を確認してから本提出または下書き維持を選ぶ。

## Technical Context

**Language/Version**: TypeScript 5.9 + React 19 + Vite 7 for Code Apps; Python 3.11 for Dataverse/Power Automate deployment scripts

**Primary Dependencies**: `@microsoft/power-apps`, React Router, TanStack Query, Radix UI, Tailwind CSS, Vitest, Python `requests`, `python-dotenv`, `azure-identity`, Dataverse Web API, Power Automate, AI Builder custom prompt

**Storage**: Microsoft Dataverse. Extend `ds_category` with one Memo regulation text column. Reuse `ds_application` AI columns: `ds_aiapplicationsummary`, `ds_aiconversationsummary`, `ds_aidecisionoptiontext`, `ds_aidecisioncomment`, `ds_aidecisionbasis`, `ds_aidecisionupdatedat`

**Testing**: `npm test`, `npm run build`, `python -m pytest tests/test_ai_decision.py tests/test_security_roles.py tests/test_notification_flows.py`, targeted unit tests for submission flow and AI basis parsing

**Target Platform**: Power Apps Code Apps running against Dataverse, Power Automate cloud flows, AI Builder prompt in the same Power Platform environment

**Project Type**: Power Platform solution with Code Apps frontend, Dataverse data model, Power Automate flow automation, AI Builder prompt

**Performance Goals**: 90% of applicant pre-submission AI checks complete within 30 seconds or return a clear failure/retry message; category and regulation reads remain within existing Code Apps query patterns

**Constraints**: Keep all components in `DecisionSupport` solution; extend existing `Application_GenerateAiDecision` flow rather than creating an equivalent new AI flow; keep AI output/storage as close as possible to existing columns; no AI result history table; no regulation snapshot persistence; AI result alone must not block final submission

**Scale/Scope**: One category regulation text per `ds_category`; applicant draft/manual AI check; mandatory AI check during submit confirmation; decider/admin regulation editing for all categories; applicant read-only regulation visibility

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

- **Single-Solution Integrity**: PASS. Dataverse column additions, security role updates, Code Apps UI changes, Power Automate flow updates, and AI Builder prompt updates remain part of the existing `DecisionSupport` solution and existing publisher prefix.
- **Deterministic, Idempotent Deployment**: PASS. `setup_dataverse.py`, `setup_security_roles.py`, and `deploy_ai_decision.py` will be extended using existing update-or-create and metadata retry patterns. No tenant-specific IDs are hardcoded.
- **Security and Data Hygiene**: PASS with human review required for authorization changes. The feature changes role privileges for `ds_category`, displays regulation text by role, and sends application/regulation text to AI Builder inside the tenant. No secrets or production data are introduced.
- **Verification Evidence**: Required evidence: `npm test`, `npm run build`, targeted Vitest coverage for category-required and submit-confirmation behavior, `python -m pytest tests/test_ai_decision.py tests/test_security_roles.py`, deployment script dry run or deployment output, and manual runtime check of draft AI check plus submit confirmation.
- **Documentation Impact**: Update `docs/ARCHITECTURE.md`, `docs/PLAN.md`, `README.md` or feature quickstart with regulation text, role permissions, submit confirmation flow, and AI output/storage constraints.

## Project Structure

### Documentation (this feature)

```text
specs/002-category-regulation-ai-check/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
scripts/
├── setup_dataverse.py                 # Add ds_category regulation Memo column
├── setup_security_roles.py            # Decider/Admin edit, Applicant read-only category regulation
└── deploy_ai_decision.py              # Extend existing AI prompt/flow inputs with category regulation

src/
├── types/decisionflow.ts              # Category type gains regulation text
├── services/dataverse-service.ts      # Category CRUD and submit-confirmation updates
├── hooks/use-decisionflow.ts          # Existing mutations reused/extended
├── lib/decisionflow-utils.ts          # Category-required and submit-flow validation helpers
├── lib/ai-decision.ts                 # Parse existing AI basis JSON with optional regulation context
└── pages/
    ├── masters.tsx                    # Regulation text edit UI for decider/admin scope
    ├── applications.tsx               # Draft manual AI check and submit-confirmation flow
    └── application-detail.tsx         # AI judgment display and decider refresh behavior

tests/
├── test_ai_decision.py                # Prompt/flow includes regulation and keeps existing AI columns
├── test_security_roles.py             # Decider category write, applicant read-only
└── test_notification_flows.py         # Submitted notifications fire only after true Submitted

src/**/*.test.ts                       # Vitest coverage for UI helpers and AI parsing
```

**Structure Decision**: Use the existing single Code Apps project plus existing Python deployment scripts. No new service, table for AI history, or separate Power Automate AI flow is introduced.

## Phase 0 Research

See [research.md](research.md). All technical unknowns from the Technical Context are resolved with existing repository patterns.

## Phase 1 Design

See [data-model.md](data-model.md), [contracts/dataverse-schema.md](contracts/dataverse-schema.md), [contracts/ai-decision-flow.md](contracts/ai-decision-flow.md), [contracts/ui-submit-flow.md](contracts/ui-submit-flow.md), and [quickstart.md](quickstart.md).

## Post-Design Constitution Check

- **Single-Solution Integrity**: PASS. Design uses existing solution components and adds only a `ds_category` column plus existing script/UI/flow updates.
- **Deterministic, Idempotent Deployment**: PASS. Dataverse metadata and flow deployment remain script-driven and rerunnable.
- **Security and Data Hygiene**: PASS with explicit review. Role changes are documented and testable; no secret or tenant-specific value is introduced.
- **Verification Evidence**: PASS. Required checks are captured in quickstart and will become tasks in `/speckit.tasks`.
- **Documentation Impact**: PASS. Architecture, plan, quickstart, and user-facing notes are identified for update.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No constitution violations.
