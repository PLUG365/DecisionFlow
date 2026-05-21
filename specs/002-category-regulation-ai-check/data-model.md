# Data Model: カテゴリ別レギュレーションAIチェック

## Entity: カテゴリ (`ds_category`)

既存カテゴリマスタを拡張し、AI判断で参照するレギュレーション文章を保持する。

| Field               | Type              | Required | Notes                                                                                                                   |
| ------------------- | ----------------- | -------: | ----------------------------------------------------------------------------------------------------------------------- |
| `ds_categoryid`     | GUID              |      Yes | Primary key                                                                                                             |
| `ds_name`           | String            |      Yes | Category name                                                                                                           |
| `ds_description`    | Memo              |       No | Existing description                                                                                                    |
| `ds_template`       | Memo              |       No | Existing recommended application format                                                                                 |
| `ds_sortorder`      | Integer           |       No | Existing display order                                                                                                  |
| `ds_regulationtext` | Memo              |       No | New. One multi-line regulation text for this category. Empty value means category-specific regulation is not configured |
| `modifiedon`        | DateTime          |   System | Used as last-updated evidence where available                                                                           |
| `modifiedby`        | Lookup SystemUser |   System | Used as last-updated user where available                                                                               |

### Validation Rules

- Each category has at most one regulation text because the field is stored directly on `ds_category`.
- Empty or null `ds_regulationtext` is valid and must not stop AI judgment.
- Applicant can read categories/regulations but cannot create, update, blank, or delete regulation text.
- Decider role holders and administrators can edit regulation text for all categories.

## Entity: 申請 (`ds_application`)

Existing application record. No new AI result table is introduced.

| Field                      | Type                 |                      Required | Notes                                                                                                        |
| -------------------------- | -------------------- | ----------------------------: | ------------------------------------------------------------------------------------------------------------ |
| `ds_applicationid`         | GUID                 |                           Yes | Primary key                                                                                                  |
| `ds_name`                  | String               |                           Yes | Application title                                                                                            |
| `ds_body`                  | Memo                 |                           Yes | Application body                                                                                             |
| `ds_stage`                 | Choice               |                           Yes | Draft=100000000, Submitted=100000001, Decided=100000004                                                      |
| `ds_submittedat`           | DateTime             |                            No | Set only when applicant confirms final submission                                                            |
| `ds_categoryid`            | Lookup `ds_category` |                   Conditional | Required when at least one category exists; optional when category master is empty                           |
| `ds_deciderid`             | Lookup SystemUser    | Required for final submission | Existing decider requirement remains                                                                         |
| `ds_aiapplicationsummary`  | Memo                 |                            No | Existing latest AI application summary                                                                       |
| `ds_aiconversationsummary` | Memo                 |                            No | Existing latest AI conversation summary                                                                      |
| `ds_aidecisionoptiontext`  | String               |                            No | Existing recommended decision option text, fixed options unchanged                                           |
| `ds_aidecisioncomment`     | Memo                 |                            No | Existing AI comment; can include regulation-related guidance                                                 |
| `ds_aidecisionbasis`       | Memo                 |                            No | Existing JSON/text basis; can include risks and regulation context without snapshotting full regulation text |
| `ds_aidecisionupdatedat`   | DateTime             |                            No | Existing latest AI update timestamp                                                                          |

### State Transitions

| From      | Event                                                | To        | Notes                                                                                          |
| --------- | ---------------------------------------------------- | --------- | ---------------------------------------------------------------------------------------------- |
| Draft     | Manual AI pre-check                                  | Draft     | Save current draft if needed, run existing AI flow, overwrite latest AI fields                 |
| Draft     | Submit action                                        | Draft     | Save as Draft, run AI flow, show AI result confirmation                                        |
| Draft     | Applicant chooses final submit after AI confirmation | Submitted | Set `ds_stage=Submitted` and `ds_submittedat=now`; notifications and decider queue can proceed |
| Draft     | Applicant chooses keep draft after AI confirmation   | Draft     | Leave `ds_submittedat` null; do not trigger submitted notifications                            |
| Submitted | Decider refreshes AI judgment                        | Submitted | Run existing AI flow using latest category regulation                                          |
| Submitted | Applicant returns to draft where permitted           | Draft     | Existing return-to-draft behavior clears submitted timestamp                                   |
| Submitted | Decision recorded as approve/reject                  | Decided   | Existing decision confirmation behavior                                                        |
| Submitted | Decision recorded as send back                       | Draft     | Existing decision confirmation behavior                                                        |

## Entity: AI判断結果 (existing fields on `ds_application`)

Logical entity represented by existing AI fields on `ds_application`, not a separate Dataverse table.

### Validation Rules

- Latest result only. Re-running AI overwrites existing AI fields.
- No past result history is stored.
- No regulation text snapshot is stored.
- Output format follows existing AI Builder prompt schema where possible.
- If existing output/storage is insufficient, implementation must pause and consult the user before adding fields.

## Relationships

| From                           | To            | Type        | Notes                                        |
| ------------------------------ | ------------- | ----------- | -------------------------------------------- |
| `ds_application.ds_categoryid` | `ds_category` | Many-to-one | Existing lookup used to find regulation text |
| `ds_application.ds_deciderid`  | `systemuser`  | Many-to-one | Existing decider assignment                  |

## Security Model

| Role           | `ds_category` Read | `ds_category` Write | Notes                                       |
| -------------- | -----------------: | ------------------: | ------------------------------------------- |
| `ds_Applicant` |             Global |                None | Read-only regulation visibility             |
| `ds_Decider`   |             Global |              Global | Can edit regulation text for all categories |
| `ds_Admin`     |             Global |              Global | Full access                                 |

## Migration Notes

- Add `ds_regulationtext` as Memo with max length aligned with existing Memo fields, preferably 50000 if supported by local metadata helper pattern.
- Existing categories receive null regulation text by default.
- Initial seed data includes demo regulation text for the five default categories. These are startup examples, not production regulations, and can be edited or cleared by decider/admin users.
- Regenerate Code Apps data source schemas after Dataverse metadata changes using the documented `npx power-apps add-data-source --org-url {DATAVERSE_URL}` pattern.
