# Contract: `Application_GenerateAiDecision` Flow

## Trigger

Existing Power Apps V2 trigger remains unchanged.

| Input  | Type   | Required | Notes                                                     |
| ------ | ------ | -------: | --------------------------------------------------------- |
| `text` | string |      Yes | Application ID. Existing service wrapper sends this value |

## Data Collection

The flow must continue collecting existing inputs and add category regulation when available.

| Input variable       | Source                           | Required | Behavior                                                                                                         |
| -------------------- | -------------------------------- | -------: | ---------------------------------------------------------------------------------------------------------------- |
| `application`        | `ds_application`                 |      Yes | Existing title/body/due date content                                                                             |
| `resources`          | `ds_applicationresource`         |       No | Existing related resources                                                                                       |
| `conversation`       | `ds_message`                     |       No | Existing conversation summary source                                                                             |
| `similarCases`       | decided `ds_application` records |       No | Existing category-aware similar case lookup                                                                      |
| `decisionOptions`    | `ds_decisionoption`              |      Yes | Existing fixed options                                                                                           |
| `categoryRegulation` | `ds_category.ds_regulationtext`  |       No | New prompt input. If no category, no category master, or empty regulation, pass a clear "not configured" message |

## AI Builder Prompt Contract

- Prompt name remains `DecisionRecommendation` unless the existing deployment pattern requires a model update under the same logical purpose.
- Output should remain compatible with existing fields:
  - `applicationSummary`
  - `conversationSummary`
  - `recommendedOption` or existing fallback paths
  - `comment` or existing fallback paths
  - `risks`
  - `similarCases`
- Regulation-related guidance should be expressed through existing `comment`, `risks`, and basis content where possible.
- If additional structured output is needed, implementation must consult the user before changing the schema.

## Update Contract

The flow must overwrite only latest AI fields on `ds_application`.

| Field                      | Behavior                                                                                                                      |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `ds_aiapplicationsummary`  | Existing application summary output                                                                                           |
| `ds_aiconversationsummary` | Existing conversation summary output                                                                                          |
| `ds_aidecisionoptiontext`  | Existing recommended decision option text                                                                                     |
| `ds_aidecisioncomment`     | Existing AI comment, including regulation guidance when appropriate                                                           |
| `ds_aidecisionbasis`       | Existing JSON/text basis; may include concise regulation context flags, risks, or references but not full regulation snapshot |
| `ds_aidecisionupdatedat`   | `utcNow()` on successful update                                                                                               |

## Failure Contract

- Return existing response shape with `ok`, `applicationid`, and `message`.
- If AI generation fails during submit confirmation, Code Apps keeps the application in Draft and shows retry guidance.
- Do not update `ds_stage` to Submitted inside the AI flow.
