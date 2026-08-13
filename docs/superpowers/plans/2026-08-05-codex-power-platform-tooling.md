# Codex Power Platform Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable Codex to use the same official FlowAgent, Dataverse, PAC, and Power CAT development workflows as Claude Code and GitHub Copilot CLI, without putting credentials or environment URLs in the repository.

**Architecture:** Install official Power Automate and Dataverse plugins into the developer's Codex profile; each plugin owns its own skills and, for FlowAgent, its bundled MCP server. Track a project-scoped `.codex/config.toml` that starts only the token-free PAC MCP. Register Dataverse through the official `@microsoft/dataverse` stdio proxy in developer-local Codex configuration after the developer selects and authorizes a Dev environment. Add a skill-only Codex wrapper for Power CAT only if the official marketplace package is not natively visible in Codex.

**Tech Stack:** Codex plugin marketplace and MCP CLI, Node.js 22, `dnx Microsoft.PowerApps.CLI.Tool`, `@microsoft/dataverse` MCP proxy, Power Automate FlowAgent, Node built-in test runner.

## Global Constraints

- Do not add FlowStudio, API keys, access tokens, Authorization headers, secrets, or a Dataverse environment URL to tracked files.
- Never authenticate to, inspect, or change a production environment as part of this work.
- Dev flow creation, editing, execution, and diagnosis are allowed only after the developer chooses the Dev environment and completes interactive authentication; new flows remain stopped until separately approved for publication.
- Flow publishing, deletion, permission/security changes, Dataverse writes/deletes, PAC import/publish/push/delete, and replacing existing DecisionFlow flows require a separate explicit approval showing target and impact.
- Existing Python deployment scripts and Solution artifacts remain the source of truth for existing DecisionFlow flows.
- Do not commit, push, or create a pull request unless the user explicitly requests it.

---

## File Structure

- `.codex/config.toml` — project-scoped, token-free PAC MCP declaration for Codex.
- `tests/ai-tooling.node.mjs` — validates both cross-client MCP configs contain only approved, non-secret declarations.
- `AGENTS.md` — clarifies the client-neutral safety policy and points agents to one procedure.
- `docs/AI_DEVELOPMENT_TOOLING.md` — documents the precise Codex installation and user-local Dataverse setup alongside Claude/Copilot instructions.
- `docs/superpowers/specs/2026-08-05-codex-power-platform-tooling-design.md` — approved design and operation boundaries.
- `docs/superpowers/plans/2026-08-05-codex-power-platform-tooling.md` — this implementation plan.
- `.codex-plugin/powercat-decisionflow/plugin.json` and `.codex-plugin/powercat-decisionflow/skills/powercat-review/SKILL.md` — created only if official Power CAT packages are unavailable to Codex; provides guidance only and no external tool server.

### Task 1: Add and test the project-scoped Codex PAC configuration

**Files:**
- Create: `.codex/config.toml`
- Modify: `tests/ai-tooling.node.mjs`
- Modify: `docs/AI_DEVELOPMENT_TOOLING.md`
- Test: `tests/ai-tooling.node.mjs`

**Interfaces:**
- Consumes: the existing PAC declaration in `.mcp.json`.
- Produces: the `[mcp_servers.pac-cli]` Codex table, containing only `dnx Microsoft.PowerApps.CLI.Tool --yes copilot mcp --run`.

- [x] **Step 1: Write the failing Codex-config test**

  Add a `readCodexConfig()` helper that reads `.codex/config.toml`, then add this assertion:

  ```js
  test("shares a token-free PAC MCP server with Codex", async () => {
    const config = await readCodexConfig();
    const serialized = config.toLowerCase();

    assert.match(config, /\[mcp_servers\.pac-cli\]/);
    assert.match(config, /command = "dnx"/);
    assert.match(config, /args = \["Microsoft\.PowerApps\.CLI\.Tool", "--yes", "copilot", "mcp", "--run"\]/);
    assert.doesNotMatch(serialized, /dataverse|flowstudio|api[_-]?key|authorization|secret|token|https?:\/\//);
  });
  ```

- [x] **Step 2: Run the focused test to verify it fails**

  Run: `node --test tests/ai-tooling.node.mjs`

  Expected: FAIL because `.codex/config.toml` does not exist.

- [x] **Step 3: Add the minimal Codex configuration**

  Create `.codex/config.toml` with exactly:

  ```toml
  [mcp_servers.pac-cli]
  command = "dnx"
  args = ["Microsoft.PowerApps.CLI.Tool", "--yes", "copilot", "mcp", "--run"]
  ```

  Update the documentation to state that `.mcp.json` is for Claude/Copilot-compatible clients and `.codex/config.toml` is the Codex project configuration. Neither config may contain Dataverse details.

- [x] **Step 4: Run the focused test to verify it passes**

  Run: `npm run test:ai-tooling`

  Expected: all AI-tooling tests pass.

- [x] **Step 5: Check the file scope and whitespace**

  Run: `git diff --check -- .codex/config.toml tests/ai-tooling.node.mjs docs/AI_DEVELOPMENT_TOOLING.md`

  Expected: no output.

### Task 2: Install and validate the official Codex plugins

**Files:**
- Modify: `docs/AI_DEVELOPMENT_TOOLING.md`
- Modify: `AGENTS.md`
- Test: Codex user configuration and plugin inventory; no repository credential files.

**Interfaces:**
- Consumes: Codex CLI `plugin marketplace add`, `plugin add`, and the official Microsoft plugin manifests.
- Produces: user-profile plugins named `power-automate` and `dataverse`, with FlowAgent exposed by the first and Dataverse skills exposed by the second.

- [x] **Step 1: Inspect the current Codex plugin and MCP inventory**

  Run:

  ```powershell
  codex plugin marketplace list
  codex plugin list
  codex mcp list
  ```

  Expected: record existing entries; do not remove unrelated plugins or MCP servers.

- [x] **Step 2: Add the official Power Platform marketplace and install FlowAgent**

  Run, with approval for the Git download and user-profile configuration:

  ```powershell
  codex plugin marketplace add microsoft/power-platform-skills --ref main
  codex plugin add power-automate@power-platform-skills
  ```

  Expected: Codex reports the plugin was installed. If the marketplace manifest is rejected, capture the exact error and stop this task; do not copy or fork `server/mcp.mjs`.

- [x] **Step 3: Add the Dataverse source and install its Codex plugin**

  Prefer its official source. Run, with approval for the Git download and user-profile configuration:

  ```powershell
  codex plugin marketplace add microsoft/Dataverse-skills --ref main
  codex plugin add dataverse@dataverse-skills
  ```

  If this source is not a Codex marketplace, use `github/awesome-copilot` only after confirming that the `dataverse` plugin has Microsoft as its author and includes `.codex-plugin/plugin.json`; then run `codex plugin add dataverse@awesome-copilot`.

- [x] **Step 4: Verify the installed plugin inventory**

  Run: `codex plugin list`

  Expected: `power-automate` and `dataverse` appear, with source marketplace and version. Restart Codex before claiming their skills or MCP tools are callable.

- [x] **Step 5: Document the exact successful source and restart requirement**

  Update the Codex section in `docs/AI_DEVELOPMENT_TOOLING.md` with the successful commands, state that plugins are user-profile installations, and state that Codex must be restarted. Add to `AGENTS.md` that FlowAgent may be used in Codex only after its official plugin is installed and visible.

### Task 3: Configure the developer-local Dataverse MCP with the official proxy

**Files:**
- Modify: `docs/AI_DEVELOPMENT_TOOLING.md`
- Test: `codex mcp list` and a read-only Dataverse tool call after interactive authorization.

**Interfaces:**
- Consumes: an ignored local `.env` value named `DATAVERSE_URL`, the official Dataverse plugin, `npx`, and the Dev environment's PPAC MCP client allowlist.
- Produces: a user-local `[mcp_servers.dataverse-<org>]` entry in `~/.codex/config.toml` that starts the official stdio proxy.

- [x] **Step 1: Validate preconditions without revealing values**

  Verify that `.env` exists locally and has a non-empty `DATAVERSE_URL`, then check `npx --version`, `az --version`, `dataverse auth who`, and `pac auth list`. Do not print `.env` and do not authenticate automatically.

- [x] **Step 2: Have the developer select the Dev environment and complete interactive authorization**

  The developer uses the official Dataverse skill's `dv-connect` workflow, selects the Dev environment, and completes `az login`, `dataverse auth create --environment <DEV_URL>`, and `pac auth create --environment <DEV_URL>` as prompted. The task stops for user interaction if credentials or tenant permission are required.

- [x] **Step 3: Register the Codex Dataverse MCP in user configuration**

  Run the official equivalent, substituting the local Dev URL only at command execution:

  ```powershell
  codex mcp add dataverse-<org> --env DATAVERSE_OPERATION_CONTEXT=app=dataverse-skills/1.10.0\;skill=mcp-direct\;agent=codex -- npx -y @microsoft/dataverse@latest mcp <DEV_URL>
  ```

  Confirm the command writes only `~/.codex/config.toml`; it must not modify tracked project files with the URL.

- [x] **Step 4: Restart Codex and prove read-only connectivity**

  Run: `codex mcp list`, then in a new Codex task request the names of Dataverse tables in the selected Dev environment.

  Expected: the MCP is listed and the table-list action succeeds. If it fails, diagnose tenant consent, PPAC client allowlisting, authentication, and endpoint reachability; do not fall back to production or direct Web API writes.

- [x] **Step 5: Document the exact per-user boundary**

  State that the URL, authorization cache, and Dataverse MCP entry are local only; all write, delete, security, and environment actions continue to require explicit approval.

### Task 4: Make Power CAT guidance available in Codex

**Files:**
- Create if necessary: `.codex-plugin/powercat-decisionflow/plugin.json`
- Create if necessary: `.codex-plugin/powercat-decisionflow/skills/powercat-review/SKILL.md`
- Modify: `docs/AI_DEVELOPMENT_TOOLING.md`
- Test: `codex plugin list` after local plugin installation; review the skill file for prohibited live-action instructions.

**Interfaces:**
- Consumes: the installed official Power CAT skill packages (`powercat-code-apps`, `powercat-dataverse`, `powercat-procode-eval`, and `powercat-overflow`).
- Produces: Codex-accessible instructions to invoke Power CAT for design review, code evaluation, Dataverse query review, and Solution Zip audit without adding an MCP server.

- [x] **Step 1: Test whether the official Power CAT marketplace packages are already visible to Codex**

  Add the `microsoft/power-cat-skills` marketplace and run `codex plugin list` without installing unrelated packages. If its four Power CAT packages are visible and include their skills, install those packages directly and skip Steps 2–4.

- [x] **Step 2: Write the failing local-wrapper assertion when native packages are unavailable**

  Extend `tests/ai-tooling.node.mjs` to require the local manifest and skill to contain `powercat-review`, `powercat-code-apps`, `powercat-procode-eval`, and `powercat-overflow`, and to reject `mcpServers`, `http://`, `https://`, `api_key`, `token`, and `secret`.

- [x] **Step 3: Create the minimal skill-only Codex plugin**

  Create this manifest:

  ```json
  {
    "name": "powercat-decisionflow",
    "version": "1.0.0",
    "description": "DecisionFlow routing guidance for the official Microsoft Power CAT skills.",
    "skills": "./skills/"
  }
  ```

  Create `powercat-review/SKILL.md` that routes UI/design tasks to `powercat-code-apps`, static review to `powercat-procode-eval`, read-only query review to `powercat-dataverse`, and exported Solution Zip review to `powercat-overflow`; it must state that suggested changes are review inputs and must not run deployment, publish, delete, or security actions.

- [x] **Step 4: Install the local plugin and verify its visibility**

  Add the repository-local plugin marketplace or package through the Codex CLI, restart Codex, and run `codex plugin list`.

  Expected: the Power CAT guidance is visible. If the local plugin format is rejected, preserve the error and stop; do not add a remote Power CAT MCP server.

- [x] **Step 5: Run the focused configuration test**

  Run: `npm run test:ai-tooling`

  Expected: all tests pass and no tracked skill or configuration file contains an endpoint or credential marker.

### Task 5: Reconcile documentation and complete non-destructive verification

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/AI_DEVELOPMENT_TOOLING.md`
- Modify: `tests/ai-tooling.node.mjs`
- Test: `tests/ai-tooling.node.mjs`

**Interfaces:**
- Consumes: configuration and install results from Tasks 1–4.
- Produces: one authoritative, client-neutral DecisionFlow tooling procedure and evidence that repository configuration is credential-free.

- [x] **Step 1: Reconcile client-specific terminology**

  Ensure documentation says:

  - `.mcp.json` is not Codex configuration.
  - `.codex/config.toml` contains the token-free PAC declaration.
  - FlowAgent is provided by the official Power Automate plugin after Codex restart.
  - Dataverse uses per-user `~/.codex/config.toml` and the official stdio proxy.
  - Power CAT has no external MCP in this repository.

- [x] **Step 2: Run all non-destructive checks**

  Run:

  ```powershell
  npm run test:ai-tooling
  git diff --check
  codex plugin list
  codex mcp list
  ```

  Expected: focused tests pass; Git whitespace check has no output; inventories contain the configured components. Report an existing full-suite failure caused by missing generated SDK files separately rather than changing generated files.

- [x] **Step 3: Perform the required human review checkpoint**

  Review the final diff for: no URLs or credentials, no FlowStudio setup, no production target, no application source change, and clear explicit-approval rules for all destructive or security-sensitive actions.

- [x] **Step 4: Report the actual state without overclaiming**

  Distinguish among: installed, visible after restart, authenticated to Dev, read-only connectivity proven, and Dev write operations intentionally not exercised. Do not claim a FlowAgent or Dataverse action is available until its corresponding verification has passed.
