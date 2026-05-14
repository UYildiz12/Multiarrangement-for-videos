import { spawn } from "node:child_process";
import { realpathSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = realpathSync(resolve(scriptDir, ".."));
const nextBin = resolve(projectRoot, "node_modules", "next", "dist", "bin", "next");
const args = process.argv.slice(2);

const child = spawn(process.execPath, [nextBin, ...args], {
  cwd: projectRoot,
  env: {
    ...process.env,
    INIT_CWD: projectRoot,
    PWD: projectRoot,
  },
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
