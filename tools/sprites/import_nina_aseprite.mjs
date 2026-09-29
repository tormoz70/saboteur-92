#!/usr/bin/env node
// Turn the Nina strips into tagged Aseprite files through aseprite-mcp.
//
//   ASEPRITE_PATH=... node tools/sprites/import_nina_aseprite.mjs

import { Client } from "../aseprite-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js";
import { StdioClientTransport } from "../aseprite-mcp/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const aseprite = process.env.ASEPRITE_PATH;
if (!aseprite) {
  console.error("ASEPRITE_PATH is not set");
  process.exit(1);
}

const lua = String.raw`
local root = [[${root.replace(/\\/g, "/")}]]
local function split(srcPath, tags, outAse)
  local src = app.open(srcPath)
  local cellW = 96
  local h = src.height
  local count = math.floor(src.width / cellW)
  local sheet = Sprite(cellW, h, ColorMode.RGB)
  for i = 2, count do
    sheet:newFrame()
  end
  local source = src.cels[1].image
  for i = 1, count do
    local part = Image(cellW, h, ColorMode.RGB)
    part:drawImage(source, Point(-(i - 1) * cellW, 0))
    sheet.cels[i].image = part
    sheet.frames[i].duration = 0.08
  end
  local cursor = 1
  for _, tag in ipairs(tags) do
    local last = cursor + tag[2] - 1
    local mark = sheet:newTag(cursor, last)
    mark.name = tag[1]
    cursor = last + 1
  end
  sheet:saveAs(outAse)
  src:close()
  sheet:close()
end

split(
  root .. "/assets/sprites/saboteur26_player.png",
  {
    {"idle", 4}, {"run", 4}, {"punch", 3}, {"kick", 4},
    {"jump", 2}, {"jump_kick", 4}, {"climb", 6}, {"crouch", 2}, {"death", 3},
  },
  root .. "/assets/sprites/saboteur26_player.aseprite"
)
split(
  root .. "/assets/sprites/saboteur26_player_moves.png",
  {{"crouch_punch", 3}, {"somersault", 8}, {"roll", 8}},
  root .. "/assets/sprites/saboteur26_player_moves.aseprite"
)
return "tagged"
`;

const transport = new StdioClientTransport({
  command: process.execPath,
  args: [path.join(root, "tools/aseprite-mcp/build/index.js")],
  env: { ...process.env, ASEPRITE_PATH: aseprite },
});
const client = new Client({ name: "nina-import", version: "1.0.0" });
await client.connect(transport);
const version = await client.callTool({ name: "get_aseprite_version", arguments: {} });
console.log(JSON.stringify(version));
const result = await client.callTool({
  name: "run_script",
  arguments: { script: lua },
});
console.log(JSON.stringify(result));
await client.close();
