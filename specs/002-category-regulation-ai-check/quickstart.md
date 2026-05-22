# Quickstart: カテゴリ別レギュレーションAIチェック

## Prerequisites

- `.env` contains `DATAVERSE_URL`, `TENANT_ID`, `SOLUTION_NAME`, and `PUBLISHER_PREFIX`.
- Power Apps Code Apps is enabled for the target environment.
- Dataverse and Power Automate connections already exist for the environment.
- Existing `Application_GenerateAiDecision` flow and `DecisionRecommendation` AI Builder prompt are deployable with current scripts.

## Implementation Steps

1. Extend Dataverse metadata.
   - Add `ds_category.ds_regulationtext` as a Memo column in `scripts/setup_dataverse.py`.
   - Run the setup script after configuring the Python environment.
   - Confirm the column is in the configured solution.

2. Update security roles.
   - Keep applicant category access read-only.
   - Grant decider role holders global write access to `ds_category`.
   - Keep admin full access.

3. Regenerate Code Apps data source schemas.
   - Use the existing documented Power Apps SDK/PAC pattern.
   - Do not hand-edit generated schema files except as a last resort with clear notes.

4. Extend Code Apps types and services.
   - Add `ds_regulationtext` to `Category`.
   - Include the field in category create/update payloads.
   - Add submit-confirmation helpers and tests for category-required behavior.

5. Update category management UI.
   - Add a multi-line regulation field to category editing.
   - Allow decider/admin editing and applicant read-only visibility according to the final role design.

6. Update application submit flow.
   - Manual draft AI pre-check runs against a saved draft record.
   - Submit action saves Draft first, runs AI, shows result, then lets applicant choose final submit or keep draft.
   - Final submit alone sets `ds_stage=Submitted` and `ds_submittedat=now`.

7. Extend existing AI flow and prompt.
   - Add category regulation retrieval to `Application_GenerateAiDecision`.
   - Add regulation context to prompt inputs.
   - Save output to existing AI columns only unless the user approves a storage change.

8. Update documentation.
   - Document regulation editing permissions.
   - Document category-required behavior and no-category-master fallback.
   - Document submit confirmation and AI storage constraints.

## Verification Commands

```powershell
npm test
npm run build
python -m unittest tests.test_ai_decision tests.test_security_roles tests.test_notification_flows
```

`pytest` is not listed in `requirements.txt` in this repository. Use the standard `unittest` command above unless pytest is intentionally added as a project dependency.

## Implementation Verification Notes

- 2026-05-22: `npm test` passed: 6 files, 62 tests.
- 2026-05-22: `npm run build` passed with TypeScript and Vite production build.
- 2026-05-22: `python -m unittest tests.test_ai_decision tests.test_security_roles tests.test_notification_flows` passed: 34 tests.
- 2026-05-22: Default category regulation text is seeded by `scripts/setup_dataverse.py` and Code Apps startup initial data. Existing standard categories with blank regulation text are backfilled without overwriting edited regulation text.
- 2026-05-22: Target environment deployment completed for Dataverse metadata/data, security roles, `Application_GenerateAiDecision`, and Code Apps. Environment verification confirmed five default categories have regulation text and the active AI flow definition includes `categoryRegulation` / `ds_regulationtext`.
- 2026-05-22: Existing published AI Builder run configuration rejected direct `msdyn_customconfiguration` PATCH. Deployment archived/recreated the AI Builder model and patched the existing active flow clientdata without changing the flow ID.
- 2026-05-22: Application form regulation display changed from inline text to an info-button modal to avoid form height changes after category selection, then pushed to Code Apps with `npx power-apps push --non-interactive`. `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, and `npm run lint` passed.
- 2026-05-22: AI check UX follow-up added and pushed to Code Apps with `npx power-apps push --non-interactive`. AI execution now shows a wait overlay; draft AI pre-check and submit-time AI check share the same AI comment dialog; draft mode shows close/details only, submit mode shows final submit/keep draft/details; details opens the application decision tab via `?tab=decision`. `npm test -- src/lib/decisionflow-utils.test.ts src/services/dataverse-service.test.ts`, `npm run build`, and `npm run lint` passed.
- 2026-05-22: Wait overlay layering/friendly copy follow-up updated the AI wait overlay to render through a body portal with the app-top z-index so it appears above application dialogs. AI wait/result labels now use restrained emoji accents. Verification: `npm test -- src/components/operation-wait-overlay.test.ts src/lib/decisionflow-utils.test.ts`, `npm run build`, and `npm run lint` passed. Deployment: `npx power-apps push --non-interactive` succeeded.
- 2026-05-22: Decision-tab AI refresh follow-up changed `AI判断更新` so it is available for Draft and Submitted applications and disabled only for Decided applications or while AI is already running. The decision tab updates the embedded AI judgment card directly and does not open the AI comment dialog. Verification: `npm test -- src/lib/decisionflow-utils.test.ts`, `npm run build`, and `npm run lint` passed. Deployment: `npx power-apps push --non-interactive` succeeded.
- 2026-05-22: Power Platform deployment checks are complete. Residual risk remains for end-to-end user runtime behavior until the manual checks below are run in the target environment.

## Manual Runtime Checks

1. Create or edit a category regulation as a decider or admin.
2. Confirm applicant can view but not edit the regulation.
3. Create a draft application with category and run AI pre-check manually.
4. Attempt final submission with category missing while categories exist and confirm it is blocked before AI execution.
5. Submit a draft with category selected and confirm the record remains Draft while AI runs.
6. Confirm AI result is visible, then choose `下書き維持`; verify no submitted notification and no `ds_submittedat`.
7. Submit again and choose `本提出`; verify `ds_stage=Submitted`, `ds_submittedat` is set, and submitted notification behavior runs.
8. Run AI judgment as a decider on a Submitted application and confirm regulation context is reflected in the existing AI judgment display.

## Rollback Notes

- Category regulation text is nullable; clearing `ds_regulationtext` returns categories to pre-regulation behavior.
- AI output continues using existing application AI columns, so no history cleanup is required.
- If role changes cause access issues, re-run `scripts/setup_security_roles.py` after correcting role definitions.
