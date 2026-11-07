import test from 'node:test';
import assert from 'node:assert/strict';
import { PROJECTS, PROJECT_IDS, LENSES, normalizeState, stateFromUrl, urlForState, transitionState, nextTabId } from '../explore/model.mjs';

const base = 'https://vighriday.github.io/vighriday/explore/';

test('every project has three distinct lenses, three meaningful nodes, and real sources', () => {
  assert.deepEqual(Object.keys(PROJECTS), PROJECT_IDS);
  for (const project of Object.values(PROJECTS)) {
    assert.equal(new Set(project.nodes).size, 3);
    assert.deepEqual(Object.keys(project.views), LENSES);
    assert.ok(project.links.some(([label, url]) => label === 'Source' && new URL(url).hostname === 'github.com'));
    for (const view of Object.values(project.views)) {
      assert.ok(view.title.length > 20 && view.copy.length > 50);
      assert.equal(view.notes.length, 3);
      assert.equal(new Set(view.notes).size, 3);
    }
  }
});

test('all 36 project, lens, and node combinations survive sharing', () => {
  for (const project of PROJECT_IDS) for (const lens of LENSES) for (let node = 0; node < 3; node++) {
    const state = { project, lens, node };
    assert.deepEqual(stateFromUrl(urlForState(base, state)), state);
  }
});

test('untrusted or malformed URL values cannot become project content', () => {
  assert.deepEqual(stateFromUrl(`${base}?project=%3Cscript%3E&lens=__proto__&node=-1`), { project: 'veris', lens: 'problem', node: 0 });
  assert.deepEqual(stateFromUrl(`${base}?project=hive&lens=evidence&node=1.0`), { project: 'hive', lens: 'evidence', node: 2 });
  assert.deepEqual(normalizeState({ project: 'constructor', lens: 'toString', node: NaN }), { project: 'veris', lens: 'problem', node: 0 });
});

test('share links keep project and lens while dropping unrelated query and fragments', () => {
  const url = new URL(urlForState(`${base}?unrelated=hello#stale`, { project: 'pulse', lens: 'decisions', node: 0 }));
  assert.equal(url.pathname, '/vighriday/explore/');
  assert.equal(url.search, '?project=pulse&lens=decisions&node=0');
  assert.equal(url.hash, '');
});

test('changing a lens highlights its corresponding node and keeps the project', () => {
  assert.deepEqual(transitionState({ project: 'offside', lens: 'problem', node: 0 }, { lens: 'evidence' }), { project: 'offside', lens: 'evidence', node: 2 });
  assert.deepEqual(transitionState({ project: 'hive', lens: 'evidence', node: 1 }, { project: 'pulse' }), { project: 'pulse', lens: 'evidence', node: 1 });
  assert.deepEqual(transitionState({ project: 'pulse', lens: 'evidence', node: 2 }, { node: 0 }), { project: 'pulse', lens: 'evidence', node: 0 });
});

test('keyboard tab navigation wraps and supports both orientations and endpoints', () => {
  assert.equal(nextTabId(PROJECT_IDS, 'veris', 'ArrowLeft'), 'pulse');
  assert.equal(nextTabId(PROJECT_IDS, 'pulse', 'ArrowDown'), 'veris');
  assert.equal(nextTabId(PROJECT_IDS, 'hive', 'Home'), 'veris');
  assert.equal(nextTabId(PROJECT_IDS, 'hive', 'End'), 'pulse');
  assert.equal(nextTabId(LENSES, 'decisions', 'ArrowRight'), 'evidence');
  assert.equal(nextTabId(LENSES, 'problem', 'ArrowUp'), 'evidence');
  assert.equal(nextTabId(LENSES, 'problem', 'Tab'), null);
});

test('public evidence descriptions retain the important limits', () => {
  assert.match(PROJECTS.veris.views.evidence.notes.join(' '), /does not execute your tests or certify a deployment/);
  assert.match(PROJECTS.hive.views.evidence.copy, /recorded engine output/);
  assert.match(PROJECTS.hive.views.problem.notes.join(' '), /fictional actors/);
  assert.match(PROJECTS.offside.views.evidence.copy, /precomputed analyses/);
  assert.match(PROJECTS.pulse.views.evidence.copy, /no hosted session or live terminal/);
});
