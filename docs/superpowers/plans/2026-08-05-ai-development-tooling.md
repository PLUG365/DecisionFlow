# AI Development Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure DecisionFlow development to use the official Power Automate, Dataverse, Power CAT, and PAC MCP tools without enabling unreviewed production changes.

**Architecture:** A committed `.mcp.json` exposes only the token-free PAC MCP declaration. Repository guidance defines which tool can be used for which action, while developer-machine plugins supply the actual Power Automate, Dataverse, and Power CAT capabilities. Dataverse uses `dv-connect` to register the environment-specific endpoint in each developer's user settings. Automated Node tests validate that no secret, environment URL, or excluded FlowStudio endpoint enters the shared configuration.

**Tech Stack:** Claude Code plugins, GitHub Copilot CLI plugins, Dataverse MCP, PAC CLI MCP, Node.js built-in test runner.

## Global Constraints

- FlowStudio is excluded: no package, endpoint, API key, or configuration is added.
- Dataverse MCP is read-only by default; record writes, security changes, deletes, imports, solution imports, and environment settings require explicit user approval in the active task.
- Power Automate generation targets a development environment, uses existing solution connection references, creates flows disabled, and requires explicit approval before publish.
- The seven existing DecisionFlow flows and their Python deployment scripts remain the source of truth; generated changes require review and source-controlled reproduction before adoption.
- PAC MCP is for local development and validation. Destructive or environment-mutating PAC commands require explicit approval.
- Do not add tenant URLs, tokens, connection IDs, environment IDs, or personal data to the repository.

## State / Operation Rules

| Tool | Allowed state / action | Denied without active approval | Verification |
|---|---|---|---|
| Dataverse MCP | Metadata and read queries in the selected development environment | CRUD, bulk import/delete, role/environment changes | MCP client allow list and Dataverse role are checked by the developer |
| FlowAgent (official Power Automate plugin) | Generate, validate, and create a new flow in **Stopped** state | Publish, delete, replace existing DecisionFlow flows, use production | Definition, connection references, and preflight result are reviewed |
| Power CAT | Static Code Apps evaluation and Solution Zip flow audit | Environment provisioning, Canvas migration, production writes | Findings are stored as review artifacts, not auto-fixed |
| PAC MCP | List, inspect, validate, pack locally | Push, import, delete, publish, tenant setting changes | Command and target environment are shown before execution |

---

### Task 1: Share token-free MCP declarations

**Files:**
- Create: `.mcp.json`
- Test: `tests/ai-tooling.node.mjs`

- [x] Write a failing Node test requiring the `pac-cli` MCP server and forbidding environment-specific Dataverse URLs, secret-like fields, or FlowStudio.
- [x] Add `.mcp.json` with the PAC MCP stdio server only; use `dv-connect` for each developer's Dataverse endpoint.
- [x] Run `node --test tests/ai-tooling.node.mjs` and confirm it passes.

### Task 2: Add tool routing and safety guidance

**Files:**
- Create: `docs/AI_DEVELOPMENT_TOOLING.md`
- Modify: `.github/skills/power-automate/SKILL.md`

- [x] Document Claude Code and GitHub Copilot CLI marketplace installation commands for the official Power Automate, Dataverse, and Power CAT plugins.
- [x] Add mandatory FlowAgent review, validation, stopped-state creation, and explicit publish approval rules to the local Power Automate skill.
- [x] Document that existing DecisionFlow flows remain script-managed until a reviewed migration is deliberately approved.

### Task 3: Provide a repeatable local configuration check

**Files:**
- Modify: `package.json`
- Test: `tests/ai-tooling.node.mjs`

- [x] Add `test:ai-tooling` using Node's built-in test runner outside Vitest's `*.test.*` discovery pattern.
- [x] Verify the script succeeds independently of generated Dataverse SDK files.

### Task 4: Configure developer-machine plugins

**Files:**
- No repository files required

- [x] Install the Microsoft Power Platform and Dataverse plugins for Claude Code.
- [x] Install GitHub Copilot CLI, then register the Microsoft Power Platform and Power CAT marketplaces and install their supported plugins.
- [x] Register PAC MCP in Claude Code at user scope.
- [x] Do not authenticate to GitHub, Azure, Power Platform, or Dataverse automatically. Report any interactive login requirement for the user to complete.

### Task 5: Verify and report

**Files:**
- Verify: `.mcp.json`, `docs/AI_DEVELOPMENT_TOOLING.md`, `.github/skills/power-automate/SKILL.md`, `package.json`, `tests/ai-tooling.node.mjs`

- [x] Run `node --test tests/ai-tooling.node.mjs` and JSON parse validation for `.mcp.json`.
- [x] Confirm FlowStudio, tenant identifiers, tokens, and connection IDs are absent from the diff.
- [x] Run the existing test suite and report its known generated-SDK baseline failure separately from these changes.
