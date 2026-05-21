# Contract: Code Apps Submit and Regulation UI

## Category Regulation Management

### Actors

- Applicant: can view category regulation text, cannot edit.
- Decider role holder: can edit regulation text for all categories.
- Admin: can edit regulation text for all categories.

### UI Contract

- Category master UI includes one multi-line `レギュレーション` field.
- Existing category fields remain: name, description, recommended format, sort order.
- Decision options remain read-only fixed values.

## Application Validation

### Category Required Rule

| Condition                                                                   | Required behavior                                                    |
| --------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `categories.length > 0` and user attempts final submission with no category | Block submit attempt before AI flow and show category-required error |
| `categories.length === 0`                                                   | Allow AI check and submission without category                       |

### Decider Rule

Existing rule remains: final submission requires a decider.

## Draft AI Pre-check

- Applicant can manually run AI pre-check while application is Draft.
- The operation uses a saved `ds_application` record ID.
- Result overwrites existing latest AI fields and refreshes the application data.

## Submit Confirmation Flow

1. Applicant clicks submit on a draft application.
2. UI validates title, body, decider, and category-required rule.
3. UI saves the record as Draft with latest form fields and `ds_submittedat = null`.
4. UI calls existing `Application_GenerateAiDecision` using saved application ID.
5. UI displays latest AI result.
6. Applicant chooses either:
   - `本提出`: update `ds_stage = Submitted` and `ds_submittedat = now`.
   - `下書き維持`: leave `ds_stage = Draft` and `ds_submittedat = null`.

## Notification Boundary

- Submitted notification and decider queue behavior must only happen after `ds_stage` becomes Submitted.
- Keeping Draft after AI confirmation must not set `ds_submittedat` and must not trigger submitted notification flows.

## AI Result Boundary

- AI warnings, risks, or concerns do not block final submission.
- UI must make warning/recommendation content visible before final submission.
- If AI flow fails, UI keeps Draft and offers retry guidance.
