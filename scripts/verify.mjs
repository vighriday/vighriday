import { readFile, readdir, access } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import YAML from 'yaml';
import { validateSnapshot } from '../src/activity.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const read = path => readFile(resolve(root, path), 'utf8');
const readme = await read('README.md');
assert.ok(readme.trim().length > 500 && readme.trim().length < 9000, 'Keep the profile substantive and concise.');
assert.doesNotMatch(readme, /AI Product Manager|Shipping production systems since|streak-stats|shields\.io|komarev|skillicons|pac.?man|snake|wakatime|3d-contrib/i);
assert.doesNotMatch(readme, /<(?:script|iframe|style|canvas|input)\b/i, 'Unsupported README interaction.');
const images = [...readme.matchAll(/<img\b([^>]*)>/g)];
const expectedImages = ['assets/header.svg', 'assets/project-veris.svg', 'assets/project-hive.svg', 'assets/project-offside.svg', 'assets/activity.svg', 'assets/game-preview.svg'];
assert.equal(images.length, expectedImages.length, 'One portrait header, three project studies, one activity chart, and one game poster.');
assert.deepEqual(images.map(([, attributes]) => attributes.match(/\bsrc="([^"]+)"/)?.[1]?.split('?')[0]), expectedImages, 'Keep each illustration purposeful and in reading order.');
for (const [, attributes] of images) {
  const source = attributes.match(/\bsrc="([^"]+)"/)?.[1];
  assert.ok(source && !/^https?:|^\/\//i.test(source), 'Image dependencies must be repository assets.');
  assert.ok(/\balt="[^"]{12,}"/.test(attributes), 'Images need meaningful alternative text.');
  assert.ok(/\bwidth="960"/.test(attributes));
  await access(resolve(root, source.split('?')[0]));
}
for (const image of expectedImages) {
  const contents = await read(image);
  const viewBox = contents.match(/viewBox="0 0 (\d+) (\d+)"/);
  assert.ok(/<svg\b/.test(contents) && viewBox && Number(viewBox[1]) >= 800 && Number(viewBox[2]) <= 400);
  assert.doesNotMatch(contents, /<(?:script|foreignObject|animate|animateTransform)\b|@import|onload=|javascript:|url\(\s*https?:|(?:href|src)="https?:/i);
  assert.doesNotMatch(contents, /NaN|Infinity|undefined/, 'SVG geometry must contain only valid coordinates.');
  if (/@keyframes/.test(contents)) {
    assert.match(contents, /prefers-reduced-motion:reduce/);
    assert.doesNotMatch(contents, /animation[^;{}]*\binfinite\b/, 'README motion must settle after a brief introduction.');
  }
  assert.ok(Buffer.byteLength(contents) < 100_000, 'SVG assets should stay below 100 KB.');
}
const snapshot = validateSnapshot(JSON.parse(await read('data/activity.json')));
for (const name of ['index.html', 'game.js', 'style.css', 'engine.js']) await access(resolve(root, 'play', name));
for (const name of ['index.html', 'app.js', 'style.css', 'model.mjs']) await access(resolve(root, 'explore', name));
assert.match(readme, /https:\/\/vighriday\.github\.io\/vighriday\/explore\/\?lens=problem/);
const explorerHtml = await read('explore/index.html');
const explorerApp = await read('explore/app.js');
const explorerCss = await read('explore/style.css');
const explorerIds = [...explorerHtml.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(new Set(explorerIds).size, explorerIds.length, 'Explorer controls need unique identifiers.');
for (const [, id] of explorerApp.matchAll(/\bget\('([^']+)'\)/g)) {
  assert.ok(explorerIds.includes(id), `Explorer control is missing from HTML: ${id}`);
}
for (const [, asset] of explorerHtml.matchAll(/(?:href|src)="\.\/([^"]+)"/g)) {
  await access(resolve(root, 'explore', asset));
}
assert.match(explorerCss, /prefers-reduced-motion:reduce/);
assert.doesNotMatch(explorerCss, /animation[^;{}]*\binfinite\b/);
const workflowFiles = (await readdir(resolve(root, '.github/workflows'))).filter(path => /\.ya?ml$/.test(path)).sort();
assert.deepEqual(workflowFiles, ['refresh.yml', 'verify.yml']);
for (const filename of workflowFiles) {
  const contents = await read(`.github/workflows/${filename}`);
  const workflow = YAML.parse(contents);
  assert.ok(workflow.on && workflow.permissions.contents === 'read');
  assert.doesNotMatch(contents, /METRICS_TOKEN|WAKATIME_API_KEY|pull_request_target|curl.*\|.*(?:sh|bash)/);
  for (const job of Object.values(workflow.jobs)) {
    assert.ok(job['timeout-minutes'] <= 5);
    for (const step of job.steps) {
      if (step.uses) assert.match(step.uses, /^actions\/(?:checkout|setup-node)@[a-f0-9]{40}$/);
      if (step.uses?.startsWith('actions/checkout')) assert.equal(step.with['persist-credentials'], false);
    }
  }
}
console.log(`Profile verified: six self-contained SVGs, supported README markup, one explorer, one game, 90 dated contribution records, two pinned workflows. Last successful snapshot: ${snapshot.fetchedAt}.`);
