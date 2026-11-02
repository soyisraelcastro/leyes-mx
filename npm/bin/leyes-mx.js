#!/usr/bin/env node
import { main } from "../src/cli.js";

main(process.argv.slice(2)).then((code) => { process.exitCode = code ?? 0; }, (e) => {
  process.stderr.write(`Error: ${e && e.message ? e.message : e}\n`);
  process.exitCode = 1;
});
