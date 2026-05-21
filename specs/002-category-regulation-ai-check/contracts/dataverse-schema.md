# Contract: Dataverse Schema Changes

## `ds_category` Extension

Add one field to the existing category table.

| Property     | Value                                                                   |
| ------------ | ----------------------------------------------------------------------- |
| Logical name | `ds_regulationtext`                                                     |
| Display name | `レギュレーション`                                                      |
| Type         | Memo                                                                    |
| Required     | No                                                                      |
| Max length   | Prefer 50000, aligned with existing long AI Memo fields where supported |
| Default      | null                                                                    |
| Solution     | `SOLUTION_NAME` from `.env`                                             |

## Compatibility Rules

- Existing rows remain valid with null/empty `ds_regulationtext`.
- Existing category lookup from `ds_application` remains unchanged.
- Existing decision options remain unchanged: `承認`, `却下`, `差し戻し`.
- No AI history table or regulation snapshot table is created.

## Security Role Contract

| Role           | Required category privileges                                                   |
| -------------- | ------------------------------------------------------------------------------ |
| `ds_Applicant` | Read=Global, AppendTo=Global, no Write/Create/Delete for regulation management |
| `ds_Decider`   | Read=Global, Write=Global, AppendTo=Global for `ds_category`                   |
| `ds_Admin`     | Global privileges for all verbs                                                |

## Deployment Contract

- `scripts/setup_dataverse.py` must add the column idempotently.
- `scripts/setup_security_roles.py` must update role definitions idempotently.
- Deployment must keep all components in the configured solution.
- If an existing environment lacks `ds_category`, setup must still follow the repository's existing table creation order.
