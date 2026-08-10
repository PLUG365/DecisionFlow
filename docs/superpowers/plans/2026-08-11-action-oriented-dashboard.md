# Action-Oriented Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the dashboard surface the signed-in user's overdue submission and decision work, with an all-records switch, and give the decision tab a 40/60 sticky action-and-reading layout.

**Architecture:** Put overdue, stage, scope, and identity rules in one pure `src/lib` module whose clock is injected for deterministic tests. Keep `dashboard.tsx` responsible for query state and presentation only, and limit `application-detail.tsx` to responsive layout classes. No Dataverse contract or write path changes.

**Tech Stack:** React 19, TypeScript 5.9, TanStack Query 5, Tailwind CSS 4, Vitest 4, existing Power Apps Code App runtime.

## Global Constraints

- Initial dashboard scope is `mine`; the alternative scope is `all`.
- `mine` means Draft created by the current system user and Submitted assigned to the current system user as decider.
- Participants and mention targets do not make an application part of `mine`.
- An application is overdue only when its due calendar date is earlier than the user's current local calendar date; today is not overdue.
- Decided, missing-due-date, invalid-due-date, and unknown-stage rows are excluded from both action lists.
- An unresolved current user must never make the `mine` scope show all records.
- Scope state stays in React memory; do not write it to the URL, Dataverse, or browser storage.
- Do not change Dataverse schema, generated SDK files, services, API calls, write behavior, access control, Copilot Studio, or Power Automate.
- Do not add dependencies.
- Desktop decision layout is 40% sticky action rail and 60% AI reading area; below `lg` it is one non-sticky column.
- D4 requires human verification at desktop and narrow widths even after mechanical gates pass.
- User-approved TDD boundary: the pure classifier uses red-green TDD; dashboard JSX wiring and CSS-only layout use build, lint, and browser verification because this repository has no DOM test harness and this plan adds no dependency.

---

### Task 1: Add deterministic dashboard action classification

**Files:**
- Create: `src/lib/dashboard-actions.ts`
- Create: `src/lib/dashboard-actions.test.ts`

**Interfaces:**
- Consumes: `Application` and `ApplicationStage` from `@/types/decisionflow`; `normalizeGuid` from `@/lib/decisionflow-utils`.
- Produces: `DashboardActionScope`, `DashboardActionGroups`, and `groupDashboardActionApplications(input)` for `dashboard.tsx`.

- [ ] **Step 1: Write the failing classification tests**

Create `src/lib/dashboard-actions.test.ts` with fixtures that cover date boundaries, stages, ownership, GUID formatting, and unresolved identity:

```ts
import { describe, expect, it } from "vitest";

import { groupDashboardActionApplications } from "./dashboard-actions";
import { ApplicationStage, type Application } from "@/types/decisionflow";

const NOW = new Date(2026, 7, 11, 12, 0, 0);

function application(
  id: string,
  overrides: Partial<Application> = {},
): Application {
  return {
    ds_applicationid: id,
    ds_name: id,
    ds_stage: ApplicationStage.Draft,
    ds_duedate: "2026-08-10",
    ...overrides,
  };
}

describe("groupDashboardActionApplications", () => {
  it("separates overdue Draft and Submitted rows", () => {
    const rows = [
      application("draft-overdue"),
      application("submitted-overdue", {
        ds_stage: ApplicationStage.Submitted,
      }),
    ];

    const result = groupDashboardActionApplications({
      applications: rows,
      scope: "all",
      currentSystemUserId: null,
      now: NOW,
    });

    expect(result.submitOrRevise.map((row) => row.ds_applicationid)).toEqual([
      "draft-overdue",
    ]);
    expect(result.decide.map((row) => row.ds_applicationid)).toEqual([
      "submitted-overdue",
    ]);
  });

  it("excludes rows that are not overdue actionable stages", () => {
    const rows = [
      application("due-today", { ds_duedate: "2026-08-11" }),
      application("due-future", { ds_duedate: "2026-08-12" }),
      application("decided", { ds_stage: ApplicationStage.Decided }),
      application("missing-due", { ds_duedate: undefined }),
      application("unknown-stage", { ds_stage: 999 as never }),
      application("invalid-due", { ds_duedate: "not-a-date" }),
    ];

    const result = groupDashboardActionApplications({
      applications: rows,
      scope: "all",
      currentSystemUserId: null,
      now: NOW,
    });

    expect(result).toEqual({ submitOrRevise: [], decide: [] });
  });

  it("uses creator ownership for Draft and decider ownership for Submitted", () => {
    const rows = [
      application("my-draft", { _createdby_value: "{USER-A}" }),
      application("other-draft", { _createdby_value: "USER-B" }),
      application("my-decision", {
        ds_stage: ApplicationStage.Submitted,
        _ds_deciderid_value: "USER-A",
      }),
      application("other-decision", {
        ds_stage: ApplicationStage.Submitted,
        _ds_deciderid_value: "USER-B",
      }),
    ];

    const result = groupDashboardActionApplications({
      applications: rows,
      scope: "mine",
      currentSystemUserId: "user-a",
      now: NOW,
    });

    expect(result.submitOrRevise.map((row) => row.ds_applicationid)).toEqual([
      "my-draft",
    ]);
    expect(result.decide.map((row) => row.ds_applicationid)).toEqual([
      "my-decision",
    ]);
  });

  it("returns no mine rows when the current user is unresolved", () => {
    const result = groupDashboardActionApplications({
      applications: [
        application("draft"),
        application("submitted", { ds_stage: ApplicationStage.Submitted }),
      ],
      scope: "mine",
      currentSystemUserId: null,
      now: NOW,
    });

    expect(result).toEqual({ submitOrRevise: [], decide: [] });
  });

  it("does not apply ownership filtering to the all scope", () => {
    const rows = [
      application("draft", { _createdby_value: "USER-B" }),
      application("submitted", {
        ds_stage: ApplicationStage.Submitted,
        _ds_deciderid_value: "USER-B",
      }),
    ];

    const result = groupDashboardActionApplications({
      applications: rows,
      scope: "all",
      currentSystemUserId: null,
      now: NOW,
    });

    expect(result.submitOrRevise).toEqual([rows[0]]);
    expect(result.decide).toEqual([rows[1]]);
  });
});
```

- [ ] **Step 2: Run the targeted test and verify the red state**

Run:

```powershell
npm test -- src/lib/dashboard-actions.test.ts
```

Expected: FAIL because `./dashboard-actions` does not exist.

- [ ] **Step 3: Implement the minimal pure classifier**

Create `src/lib/dashboard-actions.ts`:

```ts
import { normalizeGuid } from "@/lib/decisionflow-utils";
import {
  ApplicationStage,
  type Application,
} from "@/types/decisionflow";

export type DashboardActionScope = "mine" | "all";

export type DashboardActionGroups = {
  submitOrRevise: Application[];
  decide: Application[];
};

export type DashboardActionInput = {
  applications: Application[];
  scope: DashboardActionScope;
  currentSystemUserId: string | null | undefined;
  now: Date;
};

function calendarDateKey(value: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(year, month - 1, day);
  if (
    parsed.getFullYear() !== year ||
    parsed.getMonth() !== month - 1 ||
    parsed.getDate() !== day
  ) {
    return null;
  }

  return year * 10000 + month * 100 + day;
}

function currentCalendarDateKey(now: Date): number {
  return (
    now.getFullYear() * 10000 +
    (now.getMonth() + 1) * 100 +
    now.getDate()
  );
}

function comparableGuid(value: string | null | undefined): string | null {
  return normalizeGuid(value)?.replace(/^\{|\}$/g, "") ?? null;
}

export function groupDashboardActionApplications({
  applications,
  scope,
  currentSystemUserId,
  now,
}: DashboardActionInput): DashboardActionGroups {
  const groups: DashboardActionGroups = { submitOrRevise: [], decide: [] };
  const currentUserId = comparableGuid(currentSystemUserId);
  if (scope === "mine" && !currentUserId) return groups;

  const today = currentCalendarDateKey(now);
  applications.forEach((application) => {
    const dueDate = application.ds_duedate
      ? calendarDateKey(application.ds_duedate)
      : null;
    if (dueDate === null || dueDate >= today) return;

    if (application.ds_stage === ApplicationStage.Draft) {
      if (
        scope === "all" ||
        comparableGuid(application._createdby_value) === currentUserId
      ) {
        groups.submitOrRevise.push(application);
      }
      return;
    }

    if (
      application.ds_stage === ApplicationStage.Submitted &&
      (scope === "all" ||
        comparableGuid(application._ds_deciderid_value) === currentUserId)
    ) {
      groups.decide.push(application);
    }
  });

  return groups;
}
```

- [ ] **Step 4: Run the targeted test and verify the green state**

Run:

```powershell
npm test -- src/lib/dashboard-actions.test.ts
```

Expected: 1 test file and 5 tests pass, with 0 failures.

- [ ] **Step 5: Run local type and lint gates for the new module**

Run:

```powershell
npm run build
npm run lint
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit the classifier and tests**

```powershell
git add src/lib/dashboard-actions.ts src/lib/dashboard-actions.test.ts
git commit -m "feat: classify dashboard action items"
```

---

### Task 2: Wire the mine/all action lists into the dashboard

**Files:**
- Modify: `src/pages/dashboard.tsx:1-296`
- Test: `src/lib/dashboard-actions.test.ts`

**Interfaces:**
- Consumes: `DashboardActionScope` and `groupDashboardActionApplications` from Task 1; `useCurrentSystemUser()` from `src/hooks/use-decisionflow.ts`.
- Produces: a dashboard action section with a shared `mine`/`all` scope and two `ListTable` instances.

- [ ] **Step 1: Add the dashboard state and classifier imports**

Change the React import to include `useState`, add `useCurrentSystemUser`, and import the Task 1 API:

```ts
import { useMemo, useState, type CSSProperties } from "react";
```

```ts
import {
  useApplications,
  useCategories,
  useCurrentSystemUser,
  useDecisionOptions,
  useDecisions,
  useSystemUsers,
} from "@/hooks/use-decisionflow";
```

```ts
import {
  groupDashboardActionApplications,
  type DashboardActionScope,
} from "@/lib/dashboard-actions";
```

Because the removed `stalledApplications` block is the last use of the constant, also remove
`ApplicationStage` from the `@/types/decisionflow` import while retaining `stageMeta`, `Application`,
and `ApplicationStageValue`:

```ts
import {
  stageMeta,
  type Application,
  type ApplicationStageValue,
} from "@/types/decisionflow";
```

- [ ] **Step 2: Replace the combined stalled filter with scoped action groups**

Inside `DashboardPage`, add the scope and current-user query next to the existing hooks:

```ts
const [actionScope, setActionScope] =
  useState<DashboardActionScope>("mine");
const {
  systemUserId,
  isLoading: isCurrentUserLoading,
  isError: isCurrentUserError,
} = useCurrentSystemUser();
```

Delete `stalledApplications` and replace it with:

```ts
const actionGroups = useMemo(
  () =>
    groupDashboardActionApplications({
      applications,
      scope: actionScope,
      currentSystemUserId: systemUserId,
      now: new Date(),
    }),
  [applications, actionScope, systemUserId],
);

const isMineIdentityPending =
  actionScope === "mine" && isCurrentUserLoading;
const isMineIdentityUnavailable =
  actionScope === "mine" &&
  !isCurrentUserLoading &&
  (isCurrentUserError || !systemUserId);
```

- [ ] **Step 3: Replace the two existing lower tables with the action section**

Replace the bottom `xl:grid-cols-2` block with a section that owns one shared scope switch and both lists:

```tsx
<section className="space-y-3" aria-labelledby="dashboard-actions-heading">
  <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
    <div>
      <h3 id="dashboard-actions-heading" className="text-lg font-semibold">
        対応が必要な申請
      </h3>
      <p className="text-sm text-muted-foreground">
        希望期限を過ぎ、提出・修正または判断が必要な申請です。
      </p>
    </div>
    <div
      className="inline-flex w-fit rounded-md border p-1"
      role="group"
      aria-label="申請の表示範囲"
    >
      <Button
        type="button"
        size="sm"
        variant={actionScope === "mine" ? "default" : "ghost"}
        aria-pressed={actionScope === "mine"}
        onClick={() => setActionScope("mine")}
      >
        自分
      </Button>
      <Button
        type="button"
        size="sm"
        variant={actionScope === "all" ? "default" : "ghost"}
        aria-pressed={actionScope === "all"}
        onClick={() => setActionScope("all")}
      >
        全体
      </Button>
    </div>
  </div>

  {isMineIdentityPending ? (
    <Card>
      <CardContent className="p-6 text-sm text-muted-foreground">
        本人情報を確認しています。
      </CardContent>
    </Card>
  ) : isMineIdentityUnavailable ? (
    <Card>
      <CardContent className="p-6 text-sm text-muted-foreground">
        本人情報を取得できませんでした。「全体」に切り替えると、閲覧可能な申請を確認できます。
      </CardContent>
    </Card>
  ) : (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <ListTable
        data={actionGroups.submitOrRevise as ApplicationRow[]}
        columns={columns}
        title="提出・修正が必要"
        description={
          actionScope === "mine"
            ? "自分が作成した、希望期限超過の下書き・差し戻し申請"
            : "希望期限超過の下書き・差し戻し申請"
        }
        searchKeys={["ds_name"]}
        itemsPerPage={5}
        emptyMessage={
          actionScope === "mine"
            ? "自分が提出・修正する期限超過申請はありません"
            : "提出・修正が必要な期限超過申請はありません"
        }
        onRowClick={(row) =>
          navigate(`/applications/${row.ds_applicationid}`)
        }
      />
      <ListTable
        data={actionGroups.decide as ApplicationRow[]}
        columns={columns}
        title="判断が必要"
        description={
          actionScope === "mine"
            ? "自分が判断者の、希望期限超過の提出済み申請"
            : "希望期限超過の提出済み申請"
        }
        searchKeys={["ds_name"]}
        itemsPerPage={5}
        emptyMessage={
          actionScope === "mine"
            ? "自分が判断する期限超過申請はありません"
            : "判断が必要な期限超過申請はありません"
        }
        onRowClick={(row) =>
          navigate(`/applications/${row.ds_applicationid}`)
        }
      />
    </div>
  )}
</section>
```

- [ ] **Step 4: Run the classifier regression test, build, and lint**

Run:

```powershell
npm test -- src/lib/dashboard-actions.test.ts
npm run build
npm run lint
```

Expected: 5 targeted tests pass; build and lint exit 0.

- [ ] **Step 5: Commit the dashboard UI**

```powershell
git add src/pages/dashboard.tsx
git commit -m "feat: add personal dashboard action scope"
```

---

### Task 3: Apply the selected B layout to the decision tab

**Files:**
- Modify: `src/pages/application-detail.tsx:663-853`

**Interfaces:**
- Consumes: existing latest-decision card, decision form, and AI-decision card.
- Produces: a responsive 40/60 decision-tab grid without changing child behavior.

- [ ] **Step 1: Change only the decision grid and width-safety classes**

Replace the equal two-column wrapper and its direct child classes with:

```tsx
<div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[2fr_3fr]">
  <div className="min-w-0 space-y-4 lg:sticky lg:top-4">
```

Add `className="min-w-0"` to the direct AI decision `Card`:

```tsx
<Card className="min-w-0">
```

Do not change card order, conditions, form state, button behavior, or AI decision rendering.

- [ ] **Step 2: Run build and lint**

Run:

```powershell
npm run build
npm run lint
```

Expected: both commands exit 0.

- [ ] **Step 3: Commit the responsive layout**

```powershell
git add src/pages/application-detail.tsx
git commit -m "style: widen decision reading area"
```

---

### Task 4: Verify the app and update the roadmap with observed evidence

**Files:**
- Modify: `docs/UX_ROADMAP.md:1-457`

**Interfaces:**
- Consumes: the completed Task 1-3 implementation and the repository's documented gate commands.
- Produces: current, evidence-backed D1/D4 status and the next-work pointer.

- [ ] **Step 1: Run every mechanical gate from the roadmap**

Run:

```powershell
npm run build
npm test
npm run lint
npm run test:ai-tooling
$env:PYTHONUTF8="1"
$env:PYTHONPATH=(Get-Location).Path
py -m unittest discover -s tests -p "test_*.py"
```

Expected: every command exits 0; Vitest reports no failed test files or tests; Python ends with `OK`, not `FAILED` or an import error.

- [ ] **Step 2: Start the local Power Apps development host**

Run:

```powershell
npm run dev
```

Open the complete `https://apps.powerapps.com/play/e/{environmentId}/a/local?_localAppUrl=...` URL printed by the development server. Keep the terminal running while verifying.

- [ ] **Step 3: Verify D1 with real application data**

Confirm all of the following in the running app:

1. The initial scope is `自分`.
2. A current user's overdue Draft appears only under `提出・修正が必要`.
3. A current user's overdue Submitted assignment appears only under `判断が必要`.
4. Switching to `全体` updates both lists and can reveal other users' matching rows.
5. Switching back to `自分` removes other users' rows.
6. Empty-state wording matches the active scope.
7. Clicking a row opens that application's detail page.
8. A due-today row does not appear as overdue.

- [ ] **Step 4: Verify D4 at desktop and narrow widths**

Confirm all of the following in the judgment tab of an application with generated AI content:

1. At desktop width, the left operation rail is visibly narrower than the AI decision area.
2. Scrolling the long AI decision keeps the latest decision and decision form reachable on the left.
3. The AI decision text does not overflow or force horizontal page scrolling.
4. Below the `lg` breakpoint, the cards form one column and the left area no longer sticks.
5. Decision controls and AI-refresh behavior are unchanged.

- [ ] **Step 5: Update `docs/UX_ROADMAP.md` using only observed results**

Make these concrete updates after Steps 1-4:

- Change the final-updated date to the verification date.
- Record the current branch and latest commit under `現在地`.
- Replace the old D1 note with the implemented mine/all switch and the two action lists.
- Replace D4 `❓` with `✅` only if both desktop and narrow-width checks passed; otherwise record the exact remaining visual defect and leave it `🔶`.
- Replace the D1/D4 entries in the real-device verification table with the observed outcomes.
- Move `次にやること` to Phase 3 investigation in the documented F-b → F-a → F-d order.
- Record the actual Vitest and Python test counts from Step 1; do not copy earlier counts.

- [ ] **Step 6: Check the final documentation diff**

Run:

```powershell
git diff --check
git diff -- docs/UX_ROADMAP.md
git status --short
```

Expected: `git diff --check` exits 0; the roadmap claims only results observed in Steps 1-4; no generated Visual Companion or Playwright files are tracked.

- [ ] **Step 7: Commit the verified roadmap state**

```powershell
git add docs/UX_ROADMAP.md
git commit -m "docs: record dashboard UX verification"
```
