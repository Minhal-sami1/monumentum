#!/usr/bin/env node
// Reproduces the UC1 failure class: a postinstall step that fails under
// npm's hook environment and succeeds under pnpm's. The package manager
// is passed explicitly (headless fixture; no network, no real installs):
//   node install.js npm   -> exits 1 (the failure the producer hits)
//   node install.js pnpm  -> exits 0 (the lesson)
const pm = process.argv[2] || (process.env.npm_config_user_agent || "").split("/")[0];
if (pm === "pnpm") {
  console.log("postinstall ok under pnpm");
  process.exit(0);
}
console.error(`postinstall FAILED under '${pm || "unknown"}': hook environment mismatch`);
process.exit(1);
