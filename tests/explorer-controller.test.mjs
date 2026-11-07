import test from 'node:test';
import assert from 'node:assert/strict';
import { mountExplorer } from '../explore/app.js';
import { PROJECT_IDS, LENSES } from '../explore/model.mjs';

function controller(initial = '?project=veris&lens=problem', clipboard = async () => {}) {
  let document;
  class Element {
    constructor(id = '') { this.id = id; this.attributes = {}; this.dataset = {}; this.listeners = {}; this.children = []; this.textContent = ''; this.disabled = true; this.hidden = false; }
    setAttribute(name, value) { this.attributes[name] = value; }
    getAttribute(name) { return this.attributes[name]; }
    addEventListener(type, listener) { (this.listeners[type] ??= []).push(listener); }
    async dispatch(type, extra = {}) {
      const event = { key: '', defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...extra };
      for (const listener of this.listeners[type] ?? []) await listener(event);
      return event;
    }
    replaceChildren(...children) { this.children = children; }
    querySelector(selector) { assert.equal(selector, '.node-label'); return this.label; }
    focus() { document.activeElement = this; }
    select() { this.selected = true; }
  }
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element(id)); return elements.get(id); };
  const projectTabs = PROJECT_IDS.map(project => { const element = get(`project-${project}`); element.dataset.project = project; return element; });
  const lensTabs = LENSES.map(lens => { const element = get(`lens-${lens}`); element.dataset.lens = lens; return element; });
  const nodes = [0, 1, 2].map(index => { const element = get(`node-${index}`); element.dataset.node = String(index); element.label = new Element(); return element; });
  document = {
    getElementById: get,
    querySelectorAll: selector => ({ '[data-project]': projectTabs, '[data-lens]': lensTabs, '[data-node]': nodes })[selector],
    createElement: () => new Element(),
    createTextNode: text => ({ textContent: text }),
  };
  const history = [`https://vighriday.github.io/vighriday/explore/${initial}`];
  let position = 0;
  const listeners = {};
  const environment = {
    location: { href: history[0] },
    navigator: { clipboard: clipboard ? { writeText: clipboard } : undefined },
    history: { pushState(data, title, url) { history.splice(position + 1); history.push(url); position++; environment.location.href = url; } },
    addEventListener(type, callback) { listeners[type] = callback; },
  };
  const app = mountExplorer(document, environment);
  function moveHistory(delta) {
    position += delta;
    environment.location.href = history[position];
    listeners.popstate();
  }
  return { ...app, get, document, environment, history, back: () => moveHistory(-1), forward: () => moveHistory(1) };
}

test('deep links render the selected project, evidence boundary, and correct real links', () => {
  const app = controller('?project=hive&lens=evidence');
  assert.deepEqual(app.getState(), { project: 'hive', lens: 'evidence', node: 2 });
  assert.equal(app.get('project-hive').getAttribute('aria-selected'), 'true');
  assert.equal(app.get('lens-evidence').getAttribute('aria-selected'), 'true');
  assert.equal(app.get('node-2').getAttribute('aria-pressed'), 'true');
  assert.match(app.get('view-copy').textContent, /recorded engine output/);
  assert.equal(app.get('project-links').children[1].href, 'https://vighriday.github.io/hive-agent-security/console/');
  assert.equal(app.get('project-panel').getAttribute('aria-labelledby'), 'project-hive');
  assert.equal(app.get('lens-panel').getAttribute('aria-labelledby'), 'lens-evidence');
  assert.equal(app.history.length, 1, 'Initial rendering must not add a history entry.');
});

test('project and lens clicks update content, selected nodes, accessible state, and URL', async () => {
  const app = controller();
  await app.get('project-offside').dispatch('click');
  await app.get('lens-decisions').dispatch('click');
  assert.deepEqual(app.getState(), { project: 'offside', lens: 'decisions', node: 1 });
  assert.match(app.get('view-copy').textContent, /Granite Guardian/);
  assert.equal(app.get('project-veris').tabIndex, -1);
  assert.equal(app.get('project-offside').tabIndex, 0);
  assert.equal(app.get('active-route').getAttribute('stroke-dashoffset'), '300');
  assert.equal(new URL(app.environment.location.href).search, '?project=offside&lens=decisions');
  assert.match(app.get('view-announcement').textContent, /OFFSIDE\. decisions\. Audit/);
  assert.equal(app.get('project-offside').disabled, false);
});

test('clicking a workflow node reveals its detail without changing project or lens', async () => {
  const app = controller('?project=pulse&lens=decisions');
  await app.get('node-2').dispatch('click');
  assert.deepEqual(app.getState(), { project: 'pulse', lens: 'decisions', node: 2 });
  assert.equal(app.get('node-note-title').textContent, '03 / APPROVE');
  assert.match(app.get('node-note-copy').textContent, /tool approvals/);
  assert.equal(app.get('node-1').getAttribute('aria-pressed'), 'false');
  assert.equal(new URL(app.environment.location.href).searchParams.get('node'), '2');
});

test('both tablists support arrow and endpoint keys with correct focus, leaving modified keys alone', async () => {
  const app = controller();
  const arrow = await app.get('project-veris').dispatch('keydown', { key: 'ArrowUp' });
  assert.equal(arrow.defaultPrevented, true);
  assert.equal(app.getState().project, 'pulse');
  assert.equal(app.document.activeElement.id, 'project-pulse');
  await app.get('lens-problem').dispatch('keydown', { key: 'End' });
  assert.equal(app.getState().lens, 'evidence');
  assert.equal(app.document.activeElement.id, 'lens-evidence');
  const modified = await app.get('lens-evidence').dispatch('keydown', { key: 'ArrowLeft', ctrlKey: true });
  assert.equal(modified.defaultPrevented, false);
  assert.equal(app.getState().lens, 'evidence');
});

test('browser back and forward restore the complete view without adding more history', async () => {
  const app = controller();
  await app.get('project-pulse').dispatch('click');
  await app.get('lens-evidence').dispatch('click');
  await app.get('node-0').dispatch('click');
  assert.equal(app.history.length, 4);
  app.back();
  assert.deepEqual(app.getState(), { project: 'pulse', lens: 'evidence', node: 2 });
  app.back();
  assert.deepEqual(app.getState(), { project: 'pulse', lens: 'problem', node: 0 });
  app.forward();
  assert.equal(app.get('node-2').getAttribute('aria-pressed'), 'true');
  assert.equal(app.history.length, 4);
});

test('share copies the exact current view and announces success', async () => {
  let copied;
  const app = controller('?project=offside&lens=evidence&node=0', async value => { copied = value; });
  await app.get('share-view').dispatch('click');
  assert.equal(copied, 'https://vighriday.github.io/vighriday/explore/?project=offside&lens=evidence&node=0');
  assert.equal(app.get('share-status').textContent, 'View link copied.');
  assert.equal(app.get('share-fallback').hidden, true);
});

test('blocked or unavailable clipboard reveals a selected, labelled fallback URL', async () => {
  for (const clipboard of [null, async () => { throw new Error('Permission denied'); }]) {
    const app = controller('?project=hive&lens=problem', clipboard);
    await app.get('share-view').dispatch('click');
    assert.equal(app.get('share-fallback').hidden, false);
    assert.equal(app.get('share-url').selected, true);
    assert.equal(app.document.activeElement.id, 'share-url');
    assert.equal(app.get('share-url').value, 'https://vighriday.github.io/vighriday/explore/?project=hive&lens=problem');
  }
});

test('a slow clipboard response cannot overwrite feedback for a newer view', async () => {
  let reject;
  const app = controller('', () => new Promise((resolve, rejectPromise) => { reject = rejectPromise; }));
  const pendingShare = app.get('share-view').dispatch('click');
  await app.get('project-pulse').dispatch('click');
  reject(new Error('Late failure'));
  await pendingShare;
  assert.equal(app.get('share-fallback').hidden, true);
  assert.equal(app.get('share-status').textContent, '');
  assert.equal(app.getState().project, 'pulse');
});
