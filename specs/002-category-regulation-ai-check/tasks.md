# Tasks: カテゴリ別レギュレーションAIチェック

**Input**: Design documents from `/specs/002-category-regulation-ai-check/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Automated test tasks are included because this feature changes Dataverse metadata, role security, Power Automate AI flow definitions, and submit behavior. Test tasks must be written and verified RED before implementation tasks for the same behavior.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing. Shared Dataverse schema, generated types, service plumbing, and AI flow contract work are placed in Setup/Foundation because all stories depend on them.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: User story label (`US1`, `US2`, `US3`) for story-scoped tasks only
- Every task includes an exact repository path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the existing project wiring and prepare the feature for test-first implementation.

- [x] T001 Review the current AI flow and category schema baseline in `scripts/deploy_ai_decision.py`
- [x] T002 [P] Review the current category metadata and Memo helper patterns in `scripts/setup_dataverse.py`
- [x] T003 [P] Review the current category role privilege constants in `scripts/setup_security_roles.py`
- [x] T004 [P] Review existing Code Apps category and submit behavior in `src/pages/applications.tsx`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schema, service, and AI contract work that must be complete before user stories can be finished.

**CRITICAL**: No user story is complete until this phase is complete.

- [x] T005 [P] Add failing schema metadata test for `ds_category.ds_regulationtext` in `tests/test_ai_decision.py`
- [x] T006 [P] Add failing category regulation service serialization tests in `src/services/dataverse-service.test.ts`
- [x] T007 [P] Add failing category type expectations for `ds_regulationtext` in `src/lib/decisionflow-utils.test.ts`
- [x] T008 Add `ds_regulationtext` Memo column definition to `scripts/setup_dataverse.py`
- [x] T009 Regenerate or refresh Code Apps Dataverse schemas so `ds_regulationtext` appears in `src/generated/index.ts`
- [x] T010 Add `ds_regulationtext` to the `Category` type in `src/types/decisionflow.ts`
- [x] T011 Update category read/create/update payload handling for `ds_regulationtext` in `src/services/dataverse-service.ts`
- [x] T012 Add category regulation prompt-input structure test for the existing AI flow in `tests/test_ai_decision.py`
- [x] T013 Extend `Application_GenerateAiDecision` data collection and prompt inputs with category regulation in `scripts/deploy_ai_decision.py`
- [x] T014 Ensure AI output still writes only existing latest AI fields in `scripts/deploy_ai_decision.py`
- [x] T015 Run foundational tests and record RED/GREEN evidence for schema, service, and AI flow in `specs/002-category-regulation-ai-check/tasks.md`

**Checkpoint**: Dataverse category regulation text, Code Apps types/services, and AI flow inputs are available for story work.

---

## Phase 3: User Story 1 - 申請者が提出前にレギュレーション観点を確認する (Priority: P1) MVP

**Goal**: Applicants can manually run AI pre-check on a saved draft, and final submission saves Draft first, runs AI, shows the latest AI result, then lets the applicant choose final submit or keep draft.

**Independent Test**: As an applicant, create or edit a draft application, run AI pre-check, attempt submit with missing category when categories exist, then submit with category selected and choose both `下書き維持` and `本提出` paths while confirming `ds_stage` and `ds_submittedat` behavior.

### Tests for User Story 1

- [x] T016 [US1] Add failing tests for category-required final submission validation in `src/lib/decisionflow-utils.test.ts`
- [x] T017 [US1] Add failing tests for draft-first submit state transitions in `src/lib/decisionflow-utils.test.ts`
- [x] T018 [P] [US1] Add failing tests for AI pre-check and final-submit service payloads in `src/services/dataverse-service.test.ts`
- [x] T019 [P] [US1] Add failing notification boundary test for Draft-kept submit confirmation in `tests/test_notification_flows.py`

### Implementation for User Story 1

- [x] T020 [US1] Implement category-required and draft submit validation helpers in `src/lib/decisionflow-utils.ts`
- [x] T021 [US1] Implement draft-save, AI pre-check, final-submit, and keep-draft service operations in `src/services/dataverse-service.ts`
- [x] T022 [US1] Add manual draft AI pre-check control and loading/error states to `src/pages/applications.tsx`
- [x] T023 [US1] Change submit action to save Draft before calling AI generation in `src/pages/applications.tsx`
- [x] T024 [US1] Add AI result confirmation UI with `本提出` and `下書き維持` actions in `src/pages/applications.tsx`
- [x] T025 [US1] Ensure `ds_stage=Submitted` and `ds_submittedat` are set only after applicant chooses final submit in `src/pages/applications.tsx`
- [x] T026 [US1] Surface AI generation failures as retry guidance while preserving Draft in `src/pages/applications.tsx`
- [x] T027 [US1] Run `npm test` for US1-focused tests using scripts defined in `package.json`

**Checkpoint**: User Story 1 is complete and independently testable as the MVP.

---

## Phase 4: User Story 2 - 判断者がレギュレーション観点で申請をチェックする (Priority: P2)

**Goal**: Deciders can view and refresh AI judgment on submitted applications with the latest category regulation context, without creating new AI result storage or changing fixed decision options.

**Independent Test**: As a decider, open a submitted application with category regulation, refresh AI judgment, and confirm the latest result displays regulation-aware risks/comment/basis while the application remains Submitted and no new AI history or snapshot is stored.

### Tests for User Story 2

- [x] T028 [US2] Add failing tests for regulation context in AI basis parsing in `src/lib/ai-decision.test.ts`
- [x] T029 [P] [US2] Add failing tests that the AI flow does not create regulation snapshot or history fields in `tests/test_ai_decision.py`
- [x] T030 [P] [US2] Add failing tests for submitted-stage AI refresh service behavior in `src/services/dataverse-service.test.ts`

### Implementation for User Story 2

- [x] T031 [US2] Update AI basis parsing to expose concise regulation context without requiring new storage in `src/lib/ai-decision.ts`
- [x] T032 [US2] Update submitted application AI judgment display for regulation-aware risks and missing-regulation messages in `src/pages/application-detail.tsx`
- [x] T033 [US2] Ensure decider AI refresh keeps `ds_stage` unchanged and refreshes latest AI fields in `src/services/dataverse-service.ts`
- [x] T034 [US2] Ensure the AI prompt keeps fixed decision options and existing output schema in `scripts/deploy_ai_decision.py`
- [x] T035 [US2] Run US2-focused Vitest and Python AI flow tests using `package.json` and `tests/test_ai_decision.py`

**Checkpoint**: User Story 2 works independently after foundational AI flow support.

---

## Phase 5: User Story 3 - 判断者と管理者がカテゴリ別レギュレーションを管理する (Priority: P3)

**Goal**: Decider role holders and admins can edit one multi-line regulation text for every category, while applicants can read but not edit regulation content.

**Independent Test**: As a decider/admin, update a category regulation and confirm it is saved; as an applicant, confirm regulation text is visible but edit controls and write operations are unavailable or blocked.

### Tests for User Story 3

- [x] T036 [US3] Add failing decider-write and applicant-read-only role tests for `ds_category` in `tests/test_security_roles.py`
- [x] T037 [P] [US3] Add failing category regulation create/update tests in `src/services/dataverse-service.test.ts`
- [x] T038 [P] [US3] Add failing category regulation validation tests in `src/lib/decisionflow-utils.test.ts`

### Implementation for User Story 3

- [x] T039 [US3] Update `ds_Decider` category privileges and keep `ds_Applicant` read-only in `scripts/setup_security_roles.py`
- [x] T040 [US3] Add `レギュレーション` multi-line field to category create/edit UI in `src/pages/masters.tsx`
- [x] T041 [US3] Allow decider/admin category regulation editing while preserving applicant read-only visibility in `src/pages/masters.tsx`
- [x] T042 [US3] Display empty-regulation explanatory text for category records in `src/pages/masters.tsx`
- [x] T043 [US3] Ensure category regulation changes flow through category service payloads in `src/services/dataverse-service.ts`
- [x] T044 [US3] Run US3-focused role and service tests using `tests/test_security_roles.py` and `package.json`

**Checkpoint**: User Story 3 is independently functional and can be verified by role.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, verification, and release-readiness work spanning all stories.

- [x] T045 [P] Update architecture notes for regulation field, AI flow extension, and submit confirmation in `docs/ARCHITECTURE.md`
- [x] T046 [P] Update project plan/backlog tracking for category regulation AI check in `docs/PLAN.md`
- [x] T047 [P] Update setup and operation guidance for regulation permissions and no-category fallback in `README.md`
- [x] T048 Update feature quickstart with final implementation and verification notes in `specs/002-category-regulation-ai-check/quickstart.md`
- [x] T049 Run full frontend verification commands from `package.json` and record results in `specs/002-category-regulation-ai-check/tasks.md`
- [x] T050 Run targeted Python verification for AI, roles, and notifications in `tests/test_ai_decision.py`, `tests/test_security_roles.py`, and `tests/test_notification_flows.py`
- [x] T051 Verify solution membership and environment-specific values remain non-secret in `scripts/setup_dataverse.py`
- [x] T052 Record manual Power Platform runtime check results for draft AI check, final submit, and role behavior in `specs/002-category-regulation-ai-check/quickstart.md`

---

## Dependencies & Execution Order

## Verification Evidence

- RED frontend: `npm test -- src/lib/decisionflow-utils.test.ts src/lib/ai-decision.test.ts src/services/dataverse-service.test.ts` failed before implementation with 13 failing tests and 40 passing tests, covering missing regulation helpers, AI basis context, and submit-confirmation service methods.
- RED Python: `python -m unittest tests.test_ai_decision tests.test_security_roles tests.test_notification_flows` failed before implementation on missing `ds_regulationtext`, missing AI flow `categoryRegulation`, and missing `ds_Decider` category Write privilege.
- GREEN targeted frontend: `npm test -- src/lib/decisionflow-utils.test.ts src/lib/ai-decision.test.ts src/services/dataverse-service.test.ts` passed with 53 tests.
- GREEN full frontend: `npm test` passed with 6 test files and 62 tests.
- GREEN build: `npm run build` passed with TypeScript project build and Vite production build.
- GREEN lint: `npm run lint` passed after excluding repository skill reference files from app lint scope and disabling React Fast Refresh export-only rule for `src/router.tsx`.
- GREEN Python: `python -m unittest tests.test_ai_decision tests.test_security_roles tests.test_notification_flows` passed with 34 tests.
- GREEN follow-up seed/backfill: `npm test -- src/lib/initial-data.test.ts src/services/dataverse-service.test.ts` passed with 15 tests, and `python -m unittest tests.test_ai_decision` passed with 9 tests.
- Environment deployment: `scripts/setup_dataverse.py` added `ds_regulationtext` and backfilled all five default categories; `scripts/setup_security_roles.py` updated roles; `scripts/deploy_ai_decision.py` deployed active flow `c690997e-4e46-f111-bec6-7c1e525c11fc` with `categoryRegulation`; `npx power-apps push --non-interactive` pushed Code Apps successfully.
- Environment verification: Dataverse query confirmed 顧客案件 / 部内案件 / 課内案件 / 他部署案件 / 事務処理 all have non-empty `ds_regulationtext`; workflow query confirmed state=1/status=2 and clientdata contains `categoryRegulation` and `ds_regulationtext`.
- UI follow-up: Application form now shows category regulation through an info-button modal instead of inline text, preventing form height changes when category selection changes. Verification: `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `npm run lint`; deployment: `npx power-apps push --non-interactive`.
- AI check UX follow-up: AI execution now shows a blocking wait overlay; draft pre-check and submit-time AI check share an AI comment dialog; draft mode has close/details actions and submit mode has final-submit/keep-draft/details actions; details deep-links to `/applications/{id}?tab=decision`. Verification: `npm test -- src/lib/decisionflow-utils.test.ts src/services/dataverse-service.test.ts`, `npm run build`, `npm run lint`; deployment: `npx power-apps push --non-interactive`.
- AI overlay/friendly copy follow-up: Operation wait overlay now uses a body portal and `z-[9999]` app-top layer so it appears above application dialogs. AI wait/result copy uses restrained emoji accents. Verification: `npm test -- src/components/operation-wait-overlay.test.ts src/lib/decisionflow-utils.test.ts`, `npm run build`, `npm run lint`; deployment: `npx power-apps push --non-interactive`.
- Decision-tab AI refresh follow-up: `AI判断更新` on the application detail decision tab is now enabled for Draft and Submitted applications and disabled only for Decided applications or while AI is pending. Because the result is already shown in the decision tab AI card, this path does not open the AI comment dialog. Verification: RED/GREEN `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, `npm run lint`; deployment: `npx power-apps push --non-interactive`.
- Diagnostics: VS Code problem check for `src` and `scripts` reported no errors.
- Diff hygiene: `git diff --check` produced no output.
- Data hygiene: targeted diff scan for common secret patterns across changed `scripts`, `src`, `tests`, `specs/002-category-regulation-ai-check`, `docs/ARCHITECTURE.md`, `docs/PLAN.md`, `README.md`, and `eslint.config.js` produced no output.
- Python note: `pytest` is not installed in the current venv, so targeted Python verification used the repository's existing `unittest` tests.
- Manual runtime note: Power Platform live checks for Code Apps + Power Automate wiring were not executed in this local pass. They are recorded in [quickstart.md](quickstart.md) as required follow-up checks with residual runtime risk.

---

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup; blocks completion of all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; MVP scope.
- **User Story 2 (Phase 4)**: Depends on Foundational; can proceed in parallel with US1 after shared AI flow support exists, but should not change US1 submit behavior.
- **User Story 3 (Phase 5)**: Depends on Foundational; can proceed in parallel with US1/US2 after category service/type support exists.
- **Polish (Phase 6)**: Depends on whichever user stories are included in the release.

### User Story Dependencies

- **US1 (P1)**: No dependency on US2 or US3 after Foundational; delivers MVP applicant pre-submit AI flow.
- **US2 (P2)**: No dependency on US1 UI, but depends on Foundational AI prompt/flow and latest AI field reuse.
- **US3 (P3)**: No dependency on US1/US2 behavior, but depends on Foundational category regulation field and service support.

### Dependency Graph

```text
Phase 1 Setup
  -> Phase 2 Foundational
      -> Phase 3 US1 (MVP)
      -> Phase 4 US2
      -> Phase 5 US3
          -> Phase 6 Polish
```

### Within Each User Story

- Write failing tests first and verify RED before implementation.
- Implement minimal code to pass tests.
- Keep changes scoped to the listed files.
- Validate the story independently before moving to the next priority.

---

## Parallel Opportunities

- T002, T003, and T004 can run in parallel during setup.
- T005, T006, and T007 can run in parallel because they target different test concerns.
- After T008 through T014 complete, US1, US2, and US3 can be developed in parallel by different contributors.
- Within US1, T018 and T019 can run in parallel because they edit different test files.
- Within US2, T029 and T030 can run in parallel with T028.
- Within US3, T037 and T038 can run in parallel with T036.
- T045, T046, and T047 can run in parallel during polish.

---

## Parallel Example: User Story 1

```bash
Task: "T018 [US1] Add failing tests for AI pre-check and final-submit service payloads in src/services/dataverse-service.test.ts"
Task: "T019 [US1] Add failing notification boundary test for Draft-kept submit confirmation in tests/test_notification_flows.py"
```

## Parallel Example: User Story 2

```bash
Task: "T029 [US2] Add failing tests that the AI flow does not create regulation snapshot or history fields in tests/test_ai_decision.py"
Task: "T030 [US2] Add failing tests for submitted-stage AI refresh service behavior in src/services/dataverse-service.test.ts"
```

## Parallel Example: User Story 3

```bash
Task: "T036 [US3] Add failing decider-write and applicant-read-only role tests for ds_category in tests/test_security_roles.py"
Task: "T037 [US3] Add failing category regulation create/update tests in src/services/dataverse-service.test.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational schema, services, and AI input support.
3. Complete Phase 3: User Story 1.
4. Stop and validate the applicant draft AI pre-check and submit-confirmation flow independently.
5. Demo the MVP before adding decider-specific display or regulation management polish.

### Incremental Delivery

1. Deliver Setup + Foundational.
2. Deliver US1 for applicant pre-submit value.
3. Deliver US2 for decider regulation-aware review.
4. Deliver US3 for operational regulation maintenance.
5. Finish Polish with documentation, full verification, and manual runtime checks.

### Verification Strategy

1. Run focused RED/GREEN tests for each task group before broader suites.
2. Run `npm test` and `npm run build` after Code Apps behavior is complete.
3. Run `python -m unittest tests.test_ai_decision tests.test_security_roles tests.test_notification_flows` after Python flow/role changes.
4. Complete manual checks from `specs/002-category-regulation-ai-check/quickstart.md` before handoff.

---

## Task Summary

- Total tasks: 52
- Setup: 4 tasks
- Foundational: 11 tasks
- US1: 12 tasks
- US2: 8 tasks
- US3: 9 tasks
- Polish: 8 tasks
- MVP scope: Phase 1 + Phase 2 + Phase 3 (US1)
