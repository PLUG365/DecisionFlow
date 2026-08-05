import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function readMcpConfig() {
  const content = await readFile(path.join(root, ".mcp.json"), "utf8");
  return JSON.parse(content);
}

async function readCodexConfig() {
  return readFile(path.join(root, ".codex", "config.toml"), "utf8");
}

test("shares only a token-free PAC MCP server", async () => {
  const config = await readMcpConfig();
  const serialized = JSON.stringify(config).toLowerCase();

  assert.deepEqual(Object.keys(config.mcpServers), ["pac-cli"]);
  assert.deepEqual(config.mcpServers["pac-cli"], {
    type: "stdio",
    command: "dnx",
    args: ["Microsoft.PowerApps.CLI.Tool", "--yes", "copilot", "mcp", "--run"],
  });
  assert.doesNotMatch(serialized, /dataverse|flowstudio|api[_-]?key|authorization|secret|token/);
});

test("shares token-free PAC and Canvas Authoring MCP servers with Codex", async () => {
  const config = await readCodexConfig();
  const serialized = config.toLowerCase();

  assert.match(config, /\[mcp_servers\.pac-cli\]/);
  assert.match(config, /command = "dnx"/);
  assert.match(
    config,
    /args = \["Microsoft\.PowerApps\.CLI\.Tool", "--yes", "copilot", "mcp", "--run"\]/,
  );
  assert.match(config, /\[mcp_servers\.canvas-authoring\]/);
  assert.match(config, /command = "dnx"/);
  assert.match(
    config,
    /args = \["Microsoft\.PowerApps\.CanvasAuthoring\.McpServer", "--yes", "--prerelease", "--source", "https:\/\/api\.nuget\.org\/v3\/index\.json"\]/,
  );
  assert.doesNotMatch(
    serialized,
    /dataverse|flowstudio|api[_-]?key|authorization|secret|token/,
  );
});

test("directs agents to the shared AI tooling policy", async () => {
  const instructions = await readFile(path.join(root, "AGENTS.md"), "utf8");

  assert.match(instructions, /docs\/AI_DEVELOPMENT_TOOLING\.md/);
  assert.match(instructions, /FlowStudio/);
});

test("documents Canvas Apps as an explicit development-environment capability", async () => {
  const tooling = await readFile(path.join(root, "docs", "AI_DEVELOPMENT_TOOLING.md"), "utf8");

  assert.match(tooling, /Canvas Apps/);
  assert.match(tooling, /Canvas Authoring MCP/);
  assert.match(tooling, /coauthoring/i);
  assert.match(tooling, /\.NET 10/);
});

test("distinguishes exploratory MCP work from managed source-controlled delivery", async () => {
  const tooling = await readFile(path.join(root, "docs", "AI_DEVELOPMENT_TOOLING.md"), "utf8");
  const instructions = await readFile(path.join(root, "AGENTS.md"), "utf8");
  const flowSkill = await readFile(
    path.join(root, ".github", "skills", "power-automate", "SKILL.md"),
    "utf8",
  );

  assert.match(tooling, /探索・試作/);
  assert.match(tooling, /採用・運用/);
  assert.match(tooling, /Git 管理された正本/);
  assert.match(tooling, /昇格/);
  assert.match(instructions, /探索・試作/);
  assert.match(flowSkill, /探索・試作/);
});
