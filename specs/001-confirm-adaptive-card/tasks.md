# Tasks: Copilot Studio チャットで Adaptive Card 判断確定

**Input**: Design documents from `/specs/001-confirm-adaptive-card/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [quickstart.md](quickstart.md), [contracts/adaptive-card-decision-confirmation.md](contracts/adaptive-card-decision-confirmation.md)

**Tests**: Included because the feature specification defines independent tests for each user story and quickstart defines minimum validation scenarios. Write test tasks first and verify they fail before implementation.

**Organization**: Tasks are grouped by setup, foundational prerequisites, and user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks in the same phase
- **[Story]**: User story label from [spec.md](spec.md): [US1], [US2], [US3]
- Every task includes an exact repository file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish file boundaries, deployment entry points, constants, and reusable fixtures before detailed implementation.

- [x] T001 Create the Adaptive Card decision confirmation deployment script skeleton in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T002 [P] Add shared decision confirmation constants for allowed option labels, card statuses, response statuses, and stage values in scripts/decision_confirmation_constants.py
- [x] T003 [P] Add TypeScript decision confirmation helpers for option-to-stage derivation in src/lib/decision-confirmation.ts
- [x] T004 [P] Add Adaptive Card contract fixture covering schema 1.5, Action.Submit, required fields, and response statuses in tests/fixtures/adaptive_card_decision_confirmation.json
- [x] T005 Document local setup variables, Copilot Studio-owned Adaptive Card JSON setup, and manual action wiring assumptions in specs/001-confirm-adaptive-card/quickstart.md

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Define Dataverse schema, canonical validation, reconciliation, file ownership, migration rules, and the Copilot Studio integration proof point before any user story implementation.

**CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 [P] Add Dataverse schema tests for ds_decisioncard fields, Issued/Consumed/Superseded/Expired statuses, and application relationship in tests/test_adaptive_card_decision_confirmation.py
- [x] T007 [P] Add unit tests proving Decision_OnCreated derives ds_application.ds_stage from ds_decisionoption and never branches by source channel in tests/test_notification_flows.py
- [x] T008 [P] Add Code Apps regression tests proving createDecision does not directly patch ds_application after migration in src/lib/decision-confirmation.test.ts
- [x] T009 Add ds_decisioncard table creation with application relationship and Issued, Consumed, Superseded, and Expired status choices in scripts/setup_dataverse.py
- [x] T010 Add ds_decisioncard security role privileges for flow owners and assigned actors in scripts/setup_security_roles.py
- [x] T011 Implement shared Python validation helpers for applicationId, decisionOption, rationale, cardInstanceId, actor AAD object ID, and actor UPN in scripts/decision_confirmation_constants.py
- [x] T012 Update Decision_OnCreated flow generation to derive ds_application.ds_stage from ds_decisionoption and clear ds_submittedat only when the derived stage is Draft in scripts/deploy_notification_flows.py
- [x] T013 Migrate Code Apps createDecision to stop directly updating ds_application and remove nextApplicationStage write coupling in src/services/dataverse-service.ts
- [x] T014 Add an early Copilot Studio validation spike proving a Generative Orchestration agent can route into a dedicated Adaptive Card Topic that calls a Power Automate action in the intended chat channel in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T015 Update Copilot agent deployment to maintain Generative Orchestration instructions, dedicated Topic setup guidance or botcomponents YAML deployment, Copilot Studio card JSON setup guidance, manual Power Automate tool guidance, and existing agent setting checks in scripts/deploy_copilot_agent.py
- [x] T016 Add MVP first-write-wins tests documenting lookup-then-insert behavior and deferred ETag optimistic concurrency in tests/test_adaptive_card_decision_confirmation.py

**Checkpoint**: Foundation ready. ds_decisioncard exists, Decision_OnCreated handles notification/final reconciliation, Code Apps performs immediate ds_application stage feedback, and Copilot Studio action feasibility is proven before detailed flow build-out.

---

## Phase 3: User Story 1 - チャット上で判断確定する (Priority: P1) MVP

**Goal**: A valid assigned decider can submit an Adaptive Card in Copilot Studio chat and create exactly one canonical ds_decision record.

**Independent Test**: Submit a card for a Submitted application as the assigned decider with one of 承認, 却下, 差し戻し and a non-empty rationale; verify a ds_decision is created, a success response is returned, and no card handler directly patches ds_application.

### Tests for User Story 1

- [x] T017 [P] [US1] Add contract tests for valid confirm_decision submit and succeeded response in tests/test_adaptive_card_decision_confirmation.py
- [x] T018 [P] [US1] Add flow definition tests proving submit creates ds_decision and consumes ds_decisioncard without any ds_application update action in tests/test_adaptive_card_decision_confirmation.py
- [x] T019 [P] [US1] Add contract tests proving the Copilot Studio-owned Adaptive Card uses schema 1.5, Action.Submit, decision option, and rationale inputs in tests/test_adaptive_card_decision_confirmation.py

### Implementation for User Story 1

- [x] T020 [US1] Build Adaptive Card issue flow definition that returns cardInstanceId and context for the Copilot Studio-owned card JSON in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T021 [US1] Build Adaptive Card submit Power Automate definition for confirm_decision in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T022 [US1] Add submit payload parsing for applicationId, decisionOption, rationale, cardInstanceId, actor.aadObjectId, and actor.upn in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T023 [US1] Add decision option lookup constrained to active 承認, 却下, and 差し戻し records in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T024 [US1] Add ds_application lookup requiring an existing accessible Submitted application before decision creation in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T025 [US1] Add MVP first-write-wins check that returns already_processed when a ds_decision already exists for the current Submitted cycle in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T026 [US1] Add ds_decision create action with application, decision option, decider, rationale, and decidedAt bindings in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T027 [US1] Add ds_decisioncard Consumed update after successful ds_decision creation in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T028 [US1] Ensure issue and submit flow definitions contain no ds_application update action in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T029 [US1] Add or document dedicated Copilot Studio Topic deployment for schema 1.5 Action.Submit Adaptive Card in scripts/deploy_copilot_agent.py or specs/001-confirm-adaptive-card/quickstart.md
- [x] T030 [US1] Update Copilot Studio instructions, dedicated Topic guidance, card JSON setup guidance, and manual action guidance for the Generative Orchestration Power Automate tool in scripts/deploy_copilot_agent.py

**Checkpoint**: US1 is independently testable with a valid assigned decider and produces a canonical ds_decision without direct application updates in the card path.

---

## Phase 4: User Story 2 - 不正・不適切な確定を防ぐ (Priority: P2)

**Goal**: Unauthorized users, invalid targets, invalid input, duplicate submissions, and reused cards are rejected without changing application state.

**Independent Test**: Submit the same card as an unassigned user, with an invalid application, with an invalid option, with blank rationale, and with a reused cardInstanceId; verify forbidden or invalid_target responses and no ds_decision creation.

### Tests for User Story 2

- [x] T031 [P] [US2] Add contract tests for forbidden and invalid_target responses in tests/test_adaptive_card_decision_confirmation.py
- [x] T032 [P] [US2] Add validation tests for missing decisionOption, unsupported option labels, blank rationale, missing cardInstanceId, and missing actor in tests/test_adaptive_card_decision_confirmation.py
- [x] T033 [P] [US2] Add single-use and reissue tests for Issued, Consumed, Superseded, and Expired ds_decisioncard statuses in tests/test_adaptive_card_decision_confirmation.py

### Implementation for User Story 2

- [x] T034 [US2] Add assigned-decider authorization lookup using actor AAD object ID or UPN in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T035 [US2] Add invalid_target handling for missing, deleted, inaccessible, or non-Submitted applications in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T036 [US2] Add non-empty rationale trimming and required decision option validation before any Dataverse write in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T037 [US2] Add card issue logic that supersedes prior Issued ds_decisioncard rows for the same application and actor before creating a new Issued card in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T038 [US2] Add submit validation requiring cardInstanceId to match the latest Issued ds_decisioncard for the application and actor in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T039 [US2] Return already_processed for Consumed, Superseded, Expired, non-latest, or reused cardInstanceId submissions in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T040 [US2] Add deterministic response body construction for succeeded, already_processed, forbidden, and invalid_target in scripts/deploy_adaptive_card_decision_confirmation.py
- [x] T041 [US2] Add deployment-time validation that required environment variables and Dataverse connection references exist in scripts/deploy_adaptive_card_decision_confirmation.py

**Checkpoint**: US2 is independently testable by attempting invalid or unauthorized submissions and confirming no application state change or duplicate decision creation occurs.

---

## Phase 5: User Story 3 - 確定結果を関係者へ共有する (Priority: P3)

**Goal**: Any ds_decision created by Code Apps or Copilot Studio reconciles the application stage, clears submitted date for 差し戻し, updates the detail view, and sends existing notifications once.

**Independent Test**: Create ds_decision from both Code Apps and Copilot Studio paths for 承認, 却下, and 差し戻し; verify identical stage outcomes, Draft submitted-date clearing for 差し戻し, current detail display, and no duplicate notifications.

### Tests for User Story 3

- [x] T042 [P] [US3] Add tests proving 承認 and 却下 decisions reconcile ds_application.ds_stage to Decided in tests/test_notification_flows.py
- [x] T043 [P] [US3] Add tests proving 差し戻し reconciles ds_application.ds_stage to Draft and clears ds_submittedat in tests/test_notification_flows.py
- [x] T044 [P] [US3] Add tests proving Code Apps and Copilot Studio ds_decision records use the same Decision_OnCreated flow path in tests/test_notification_flows.py
- [x] T045 [P] [US3] Add Code Apps tests for immediate ds_application stage update and Draft submitted-date clearing in src/services/dataverse-service.test.ts

### Implementation for User Story 3

- [x] T046 [US3] Update Decision_OnCreated flow actions to patch ds_application.ds_stage idempotently from ds_decisionoption name in scripts/deploy_notification_flows.py
- [x] T047 [US3] Update Decision_OnCreated flow actions to clear ds_application.ds_submittedat only when the next stage is Draft in scripts/deploy_notification_flows.py
- [x] T048 [US3] Add idempotent no-op behavior when ds_application is already reconciled to the derived stage in scripts/deploy_notification_flows.py
- [x] T049 [US3] Ensure existing email and Teams notifications run after successful stage reconciliation in scripts/deploy_notification_flows.py
- [x] T050 [US3] Keep Code Apps immediate stage feedback by updating ds_application after ds_decision creation in src/services/dataverse-service.ts
- [x] T051 [US3] Keep Code Apps query invalidation after decision creation so lists and detail data refresh through TanStack Query in src/hooks/use-decisionflow.ts
- [x] T052 [US3] Update application detail submission to derive the selected decision's next stage and pass it to the decision service in src/pages/application-detail.tsx
- [x] T053 [US3] Document direct Code Apps stage update coexistence with Decision_OnCreated final reconciliation in docs/PLAN.md and specs/001-confirm-adaptive-card/quickstart.md

**Checkpoint**: US3 is independently testable from either decision entry point and confirms Code Apps and Copilot Studio converge through the same reconciliation flow.

---

## Phase 6: Validation & Polish

**Purpose**: Cross-cutting checks, documentation, and end-to-end verification.

- [x] T054 [P] Update implementation notes and rollback guidance for ds_decisioncard, Generative Orchestration + dedicated Topic action wiring, schema 1.5 Action.Submit, first-write-wins MVP limits, and Code Apps immediate stage feedback in specs/001-confirm-adaptive-card/quickstart.md
- [x] T055 [P] Update architecture documentation to state that ds_decision is canonical and Copilot card processing never directly updates ds_application in docs/ARCHITECTURE.md
- [x] T056 [P] Update development plan notes to describe Code Apps immediate ds_application stage feedback and Decision_OnCreated final reconciliation in docs/PLAN.md
- [x] T057 [P] Record ds_decisioncard table/security-role migration steps and application result in docs/MIGRATIONS.md
- [x] T058 Run Python unit tests for adaptive card, notification flow, Dataverse setup, and security role definitions with py -m unittest tests.test_adaptive_card_decision_confirmation tests.test_notification_flows tests.test_security_roles
- [x] T059 Run Code Apps unit tests covering src/lib/decision-confirmation.test.ts with npm test from package.json
- [x] T060 Run Code Apps production build with npm run build from package.json
- [x] T061 Execute quickstart validation scenarios for normal, validation, Code Apps convergence, conflict, authorization, card reissue, and card replay paths in specs/001-confirm-adaptive-card/quickstart.md
- [x] T062 Record any manual Copilot Studio deployment, Topic YAML limitation, channel limitation, or environment-specific follow-up in docs/PLAN.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion; MVP scope.
- **User Story 2 (Phase 4)**: Depends on Foundational completion and can proceed after US1 contract shape is stable.
- **User Story 3 (Phase 5)**: Depends on Foundational completion and can proceed alongside US1/US2 once Decision_OnCreated reconciliation is test-driven.
- **Validation & Polish (Phase 6)**: Depends on all selected user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2; no dependency on US2 or US3 for canonical ds_decision creation.
- **US2 (P2)**: Can start after Phase 2; builds on the same contract and validation helpers as US1.
- **US3 (P3)**: Can start after Phase 2; validates the shared reconciliation path used by both Code Apps and Copilot Studio.

### Within Each User Story

- Tests first, then implementation.
- Validation helpers before Dataverse writes.
- ds_decisioncard latest Issued validation before ds_decision creation.
- ds_decision creation before card consumption.
- Code Apps immediate stage update and query invalidation.
- Reconciliation stage update before notifications.
- Story checkpoint before moving to the next priority when delivering sequentially.

---

## Parallel Execution Examples

### User Story 1

```text
Task: "T017 [US1] Add contract tests for valid confirm_decision submit and succeeded response in tests/test_adaptive_card_decision_confirmation.py"
Task: "T018 [US1] Add flow definition tests proving submit creates ds_decision and consumes ds_decisioncard without any ds_application update action in tests/test_adaptive_card_decision_confirmation.py"
Task: "T019 [US1] Add contract tests proving the Copilot Studio-owned Adaptive Card uses schema 1.5, Action.Submit, decision option, and rationale inputs in tests/test_adaptive_card_decision_confirmation.py"
```

### User Story 2

```text
Task: "T031 [US2] Add contract tests for forbidden and invalid_target responses in tests/test_adaptive_card_decision_confirmation.py"
Task: "T032 [US2] Add validation tests for missing decisionOption, unsupported option labels, blank rationale, missing cardInstanceId, and missing actor in tests/test_adaptive_card_decision_confirmation.py"
Task: "T033 [US2] Add single-use and reissue tests for Issued, Consumed, Superseded, and Expired ds_decisioncard statuses in tests/test_adaptive_card_decision_confirmation.py"
```

### User Story 3

```text
Task: "T042 [US3] Add tests proving 承認 and 却下 decisions reconcile ds_application.ds_stage to Decided in tests/test_notification_flows.py"
Task: "T043 [US3] Add tests proving 差し戻し reconciles ds_application.ds_stage to Draft and clears ds_submittedat in tests/test_notification_flows.py"
Task: "T045 [US3] Add Code Apps tests for immediate ds_application stage update and Draft submitted-date clearing in src/services/dataverse-service.test.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational schema, reconciliation, Code Apps migration direction, and Copilot Studio action spike.
3. Complete Phase 3 so Copilot Studio can create a canonical ds_decision from Adaptive Card submit.
4. Stop and validate US1 independently before adding broader authorization and notification proof.

### Incremental Delivery

1. Deliver canonical ds_decision creation from chat as the MVP.
2. Add strict authorization, invalid target handling, input parity, ds_decisioncard single-use, and reissue protections.
3. Complete reconciliation convergence so Copilot Studio relies on Decision_OnCreated for stage and notification outcomes, while Code Apps performs an immediate stage update for user feedback and still uses Decision_OnCreated for notification/final reconciliation.
4. Finish quickstart validation and documentation updates.

### Migration Decision

This task plan preserves Code Apps immediate feedback: Code Apps creates `ds_decision` and updates `ds_application.ds_stage` in the same operation so the stage changes without a manual refresh. Copilot Studio card submit never updates `ds_application` directly; `Decision_OnCreated` remains the notification and final reconciliation path for both entry points.

---

## Notes

- `ds_decision` creation is the canonical judgment event.
- Copilot card processing must not directly update `ds_application`.
- Adaptive Card display layout JSON is owned by Copilot Studio card/response configuration, not by the Power Automate deployment script.
- `scripts/deploy_adaptive_card_decision_confirmation.py` owns Adaptive Card issue/submit flow definitions, `ds_decisioncard` state management, Dataverse validation actions, and Dataverse write actions.
- `scripts/deploy_copilot_agent.py` owns Copilot instructions, dedicated Adaptive Card Topic setup or botcomponents YAML deployment guidance, card JSON setup guidance, manual Power Automate tool guidance, and existing agent setting checks.
- Copilot Studio integration uses Generative Orchestration plus a dedicated Adaptive Card Topic as the card display and submit surface; it must not rely on rigid trigger-phrase topic orchestration.
- Adaptive Card display must use schema 1.5 and Action.Submit only for Teams compatibility.
- First-write-wins is MVP lookup-then-insert; production hardening may add ds_application ETag / optimistic concurrency.
- `invalid_target` means missing, deleted/inaccessible, or not Submitted.
- Adaptive Card input must stay in parity with Code Apps: decision option is required and limited to `承認`, `却下`, `差し戻し`; rationale is required and non-empty after trimming.
- Old, consumed, superseded, expired, or non-latest cards return `already_processed`.
- Code Apps and Copilot Studio decision paths both create `ds_decision`; Copilot Studio delegates stage changes to `Decision_OnCreated`, and Code Apps mirrors the derived stage immediately for UX while `Decision_OnCreated` performs notification/final reconciliation.
- Do not commit generated task changes from this workflow.
