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

test("shares a token-free PAC MCP server with Codex", async () => {
  const config = await readCodexConfig();
  const serialized = config.toLowerCase();

  assert.match(config, /\[mcp_servers\.pac-cli\]/);
  assert.match(config, /command = "dnx"/);
  assert.match(
    config,
    /args = \["Microsoft\.PowerApps\.CLI\.Tool", "--yes", "copilot", "mcp", "--run"\]/,
  );
  assert.doesNotMatch(
    serialized,
    /dataverse|flowstudio|api[_-]?key|authorization|secret|token|https?:\/\//,
  );
});

test("directs agents to the shared AI tooling policy", async () => {
  const instructions = await readFile(path.join(root, "AGENTS.md"), "utf8");

  assert.match(instructions, /docs\/AI_DEVELOPMENT_TOOLING\.md/);
  assert.match(instructions, /FlowStudio/);
});
