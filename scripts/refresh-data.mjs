#!/usr/bin/env node
/** Refresh the public activity snapshot, preserving the last good file on error. */
import { mkdir, rename, rm, writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { fetchActivity, validateSnapshot } from '../src/activity.mjs';

export async function writeSnapshotAtomic(snapshot, output, options = {}) {
  validateSnapshot(snapshot, options);
  const target = resolve(output);
  await mkdir(dirname(target), { recursive: true });
  const temporary = `${target}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporary, `${JSON.stringify(snapshot, null, 2)}\n`, { encoding: 'utf8', flag: 'wx', mode: 0o644 });
    await rename(temporary, target);
  } finally {
    await rm(temporary, { force: true });
  }
  return target;
}

export async function refreshData({ output = fileURLToPath(new URL('../data/activity.json', import.meta.url)), fetchOptions } = {}) {
  const snapshot = await fetchActivity(fetchOptions);
  await writeSnapshotAtomic(snapshot, output);
  return snapshot;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length && (args.length !== 2 || args[0] !== '--output')) throw new Error('Usage: node scripts/refresh-data.mjs [--output path]');
  const snapshot = await refreshData(args.length ? { output: args[1] } : {});
  console.log(`Activity refreshed: ${snapshot.window.from} to ${snapshot.window.to}, ${snapshot.total} public-profile contributions across 90 completed UTC days.`);
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  main().catch(error => {
    console.error(`Activity refresh failed; previous snapshot preserved: ${error.message}`);
    process.exitCode = 1;
  });
}
