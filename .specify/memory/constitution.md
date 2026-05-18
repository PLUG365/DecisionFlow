<!--
Sync Impact Report
- Version change: N/A (template) -> 1.0.0
- Modified principles:
	- Template Principle 1 -> I. Single-Solution Integrity
	- Template Principle 2 -> II. Deterministic, Idempotent Deployment
	- Template Principle 3 -> III. Security and Data Hygiene
	- Template Principle 4 -> IV. Verification Before Merge
	- Template Principle 5 -> V. Documentation as Source of Truth
- Added sections:
	- Operational Constraints
	- Delivery Workflow and Quality Gates
- Removed sections:
	- None
- Templates requiring updates:
	- ✅ Reviewed (no content change required): .specify/templates/plan-template.md
	- ✅ Reviewed (no content change required): .specify/templates/spec-template.md
	- ✅ Reviewed (no content change required): .specify/templates/tasks-template.md
	- ✅ Reviewed (no content change required): .github/prompts/speckit.constitution.prompt.md
	- ✅ Reviewed (no content change required): .github/prompts/speckit.specify.prompt.md
	- ✅ Reviewed (no content change required): .github/prompts/speckit.plan.prompt.md
	- ✅ Reviewed (no content change required): .github/prompts/speckit.tasks.prompt.md
	- ✅ Reviewed (no content change required): .github/prompts/speckit.implement.prompt.md
- Follow-up TODOs:
	- None
-->

# DecisionFlow Constitution

## Core Principles

### I. Single-Solution Integrity

Dataverse tables, Power Automate flows, Code Apps, and Copilot Studio assets MUST
be managed under one logical solution identity (`SOLUTION_NAME` and
`PUBLISHER_PREFIX`) across all phases. Components MUST NOT be deployed as
out-of-solution one-offs unless explicitly documented as temporary and tracked in
`docs/PLAN.md`. Rationale: this preserves ALM traceability, predictable migration,
and reproducible environment rebuilds.

### II. Deterministic, Idempotent Deployment

Automation scripts MUST be safe to rerun, MUST prefer update-or-create behavior, and
MUST avoid hardcoded tenant-specific identifiers (connection IDs, environment IDs,
user IDs). Runtime configuration MUST come from `.env` with documented retrieval
steps in `README.md` or `.env.example`. Rationale: reproducibility and low-risk
recovery are mandatory for multi-environment Power Platform delivery.

### III. Security and Data Hygiene

Secrets, auth artifacts, and tenant-specific sensitive data MUST NOT be committed.
Changes affecting authentication, authorization, privacy, billing, data deletion, or
production environment controls MUST receive human review before merge. External AI
tools MUST NOT receive production secrets or personal data. Rationale: governance and
compliance failures are high-impact and non-recoverable after publication.

### IV. Verification Before Merge

Every change MUST include evidence of verification proportional to impact (build,
lint, unit/integration tests, and where relevant runtime checks for deployed flows).
When verification cannot be executed, the PR or handoff note MUST state what was
skipped, why it was skipped, and the residual risk. Rationale: explicit quality
signals prevent silent regressions in mixed frontend/Dataverse/flow systems.

### V. Documentation as Source of Truth

Behavioral or operational changes MUST be reflected in repository documentation
(`README.md`, `docs/PLAN.md`, `docs/ARCHITECTURE.md`, and related guides) within the
same change set. Manual steps that cannot be automated MUST be documented with
operator prerequisites and expected outcomes. Rationale: this project is intended to
be reproducible by first-time contributors, not only current maintainers.

## Operational Constraints

- Primary stack MUST remain Power Platform-centric: Dataverse + Power Automate +
  Power Apps Code Apps + Copilot Studio.
- Generated artifacts and local auth/cache files MUST remain excluded from git as
  defined in `.gitignore`.
- Script execution environment MUST stay compatible with documented prerequisites
  (Windows + PowerShell, Node.js 20+, Python 3.11+, PAC CLI).
- Environment-specific values MUST be injected via `.env`; defaults may exist only
  for non-sensitive developer convenience.

## Delivery Workflow and Quality Gates

1. Specification workflow MUST follow the sequence:
   `/speckit.constitution` -> `/speckit.specify` -> `/speckit.plan` ->
   `/speckit.tasks` -> `/speckit.implement`.
2. Each feature spec MUST define independently testable user stories with measurable
   success criteria before implementation.
3. Implementation plans MUST pass a Constitution Check gate before design or code
   execution.
4. Task breakdowns MUST preserve dependency order and identify parallel-safe work
   explicitly.
5. Release/publish changes MUST include documentation updates and a check that no
   secrets or tenant-specific credentials are introduced.

## Governance

This constitution supersedes ad-hoc working habits for this repository. Compliance
is reviewed at planning time and again at PR/review time.

Amendment policy:

- Amendments MUST be proposed with rationale and explicit impact on templates,
  prompts, and runtime documentation.
- Amendment approval requires maintainer review and a synchronized update of affected
  artifacts in the same change set.

Versioning policy (Semantic Versioning for governance text):

- MAJOR: incompatible governance changes or principle removals/redefinitions.
- MINOR: new principle/section or materially expanded mandatory guidance.
- PATCH: clarifications, wording improvements, and non-semantic edits.

Compliance expectations:

- Every PR or release-prep review SHOULD state whether the Constitution Check passes.
- Exceptions MUST be documented with owner, rationale, mitigation, and follow-up date
  in `docs/PLAN.md` or equivalent tracked record.

**Version**: 1.0.0 | **Ratified**: 2026-05-18 | **Last Amended**: 2026-05-18
