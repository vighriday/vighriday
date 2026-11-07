import test from 'node:test';
import assert from 'node:assert/strict';

let instance = 0;

async function controller(t) {
  const originals = new Map();
  const pending = new Map();
  let frameId = 0;
  let now = 0;
  let document;

  class Element {
    constructor(id, parent = null) {
      this.id = id;
      this.parent = parent;
      this.listeners = new Map();
      this.textContent = '';
      this.innerHTML = '';
      this.hidden = false;
      this.disabled = false;
      const classes = new Set();
      this.classList = { add: name => classes.add(name), remove: name => classes.delete(name), contains: name => classes.has(name) };
    }
    addEventListener(type, listener) {
      if (!this.listeners.has(type)) this.listeners.set(type, []);
      this.listeners.get(type).push(listener);
    }
    dispatch(type, properties = {}) {
      const event = {
        type, target: this, currentTarget: this, button: 0, detail: 1,
        repeat: false, defaultPrevented: false,
        preventDefault() { this.defaultPrevented = true; },
        ...properties,
      };
      for (const listener of this.listeners.get(type) ?? []) listener(event);
      return event;
    }
    contains(element) {
      for (let current = element; current; current = current.parent) if (current === this) return true;
      return false;
    }
    focus() {
      if (document.activeElement === this) return;
      const previous = document.activeElement;
      previous?.dispatch('blur', { relatedTarget: this });
      if (region.contains(previous)) region.dispatch('focusout', { target: previous, relatedTarget: this });
      document.activeElement = this;
    }
    setPointerCapture() {}
    getBoundingClientRect() { return { left: 0, top: 0, width: 800, height: 400 }; }
  }

  const body = new Element('body');
  const region = new Element('game', body);
  const ids = ['board', 'overlay', 'start', 'pause', 'reset', 'game-status', 'score', 'lives', 'overlay-kicker', 'overlay-title', 'overlay-description', 'move-left', 'move-right'];
  const elements = new Map(ids.map(id => [id, new Element(id, region)]));
  const drawing = {};
  for (const method of ['clearRect', 'fillRect', 'beginPath', 'moveTo', 'lineTo', 'stroke', 'strokeRect', 'fillText', 'arc', 'fill', 'setTransform']) drawing[method] = () => {};
  elements.get('board').getContext = () => drawing;

  document = new Element('document');
  document.body = body;
  document.activeElement = body;
  document.hidden = false;
  document.getElementById = id => elements.get(id);
  document.querySelector = selector => selector === '.game' ? region : null;
  document.querySelectorAll = selector => selector === '.touch-controls button' ? [elements.get('move-left'), elements.get('move-right')] : [];

  const motion = new Element('motion');
  motion.matches = false;
  const window = new Element('window');
  window.devicePixelRatio = 1;
  window.matchMedia = () => motion;

  function install(name, value) {
    originals.set(name, Object.getOwnPropertyDescriptor(globalThis, name));
    Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  }
  install('document', document);
  install('window', window);
  install('performance', { now: () => now });
  install('requestAnimationFrame', callback => { const id = ++frameId; pending.set(id, callback); return id; });
  install('cancelAnimationFrame', id => pending.delete(id));
  t.after(() => {
    pending.clear();
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else delete globalThis[name];
    }
  });

  await import(`../play/game.js?controller-test=${++instance}`);

  function frame() {
    now += 16;
    const callbacks = [...pending.values()];
    pending.clear();
    callbacks.forEach(callback => callback(now));
  }
  function settlePaused() {
    for (let index = 0; index < 5 && pending.size; index += 1) frame();
    assert.equal(pending.size, 0, 'a paused or reset controller must stop scheduling frames');
  }
  function click(id) {
    const element = elements.get(id);
    assert.equal(element.disabled, false, `${id} must be available`);
    element.focus();
    return element.dispatch('click');
  }

  return {
    elements, document, window, body, region, frame, settlePaused, click,
    get frames() { return pending.size; },
    get status() { return elements.get('game-status').textContent; },
    get overlayVisible() { return !elements.get('overlay').hidden; },
    get canvas() { return elements.get('board'); },
  };
}

test('the real controller waits for start, pauses, resumes, and resets without an orphan loop', async t => {
  const game = await controller(t);
  const initialScore = game.elements.get('score').textContent;
  const initialAttempts = game.elements.get('lives').textContent;
  assert.equal(game.frames, 0, 'initialising the page must not autoplay');
  assert.equal(game.overlayVisible, true);
  assert.equal(game.elements.get('pause').disabled, true);
  assert.match(game.status, /ready/i);

  game.click('start');
  assert.equal(game.overlayVisible, false);
  assert.equal(game.document.activeElement, game.canvas);
  assert.equal(game.elements.get('pause').disabled, false);
  game.frame();
  assert.ok(game.frames > 0, 'starting must create a continuing animation loop');

  game.click('pause');
  assert.equal(game.overlayVisible, true);
  assert.match(game.status, /paused/i);
  game.settlePaused();

  game.click('pause');
  assert.equal(game.overlayVisible, false);
  assert.match(game.status, /in progress/i);
  game.frame();
  assert.ok(game.frames > 0);

  game.click('reset');
  game.settlePaused();
  assert.equal(game.overlayVisible, true);
  assert.match(game.status, /ready/i);
  assert.equal(game.elements.get('score').textContent, initialScore);
  assert.equal(game.elements.get('lives').textContent, initialAttempts);
  assert.equal(game.elements.get('pause').disabled, true);
});

test('backgrounding the page pauses without automatically resuming on return', async t => {
  const game = await controller(t);
  game.click('start');
  game.document.hidden = true;
  game.document.dispatch('visibilitychange');
  game.settlePaused();
  assert.equal(game.overlayVisible, true);
  assert.match(game.status, /background/i);
  game.document.hidden = false;
  game.document.dispatch('visibilitychange');
  assert.equal(game.frames, 0);
  assert.equal(game.overlayVisible, true);
  game.click('start');
  assert.equal(game.overlayVisible, false);
  assert.ok(game.frames > 0);
});

test('focus moving within controls is safe; leaving the game or window pauses', async t => {
  const game = await controller(t);
  game.click('start');
  game.elements.get('pause').focus();
  game.frame();
  assert.equal(game.overlayVisible, false, 'focusing an internal control must not pause the run');

  game.body.focus();
  game.settlePaused();
  assert.match(game.status, /not focused/i);
  assert.equal(game.overlayVisible, true);

  game.click('start');
  // Non-focusable page content may provide no relatedTarget at all.
  game.document.activeElement = game.body;
  game.region.dispatch('focusout', { target: game.canvas, relatedTarget: null });
  game.settlePaused();
  assert.match(game.status, /not focused/i);

  game.click('start');
  game.window.dispatch('blur');
  game.settlePaused();
  assert.match(game.status, /window is not active/i);
});

test('keyboard shortcuts are scoped to the focused canvas and respect browser modifiers', async t => {
  const game = await controller(t);
  game.click('start');
  assert.equal(game.window.dispatch('keydown', { key: 'ArrowLeft' }).defaultPrevented, false);
  assert.equal(game.document.dispatch('keydown', { key: 'ArrowRight' }).defaultPrevented, false);
  assert.equal(game.canvas.dispatch('keydown', { key: 'ArrowLeft' }).defaultPrevented, true);
  game.canvas.dispatch('keyup', { key: 'ArrowLeft' });
  assert.equal(game.canvas.dispatch('keydown', { key: 'r', ctrlKey: true }).defaultPrevented, false);

  const pause = game.canvas.dispatch('keydown', { key: 'p' });
  assert.equal(pause.defaultPrevented, true);
  game.settlePaused();
  assert.equal(game.overlayVisible, true);
  assert.equal(game.canvas.dispatch('keydown', { key: 'ArrowRight' }).defaultPrevented, false);
  const resume = game.canvas.dispatch('keydown', { key: ' ' });
  assert.equal(resume.defaultPrevented, true);
  assert.equal(game.overlayVisible, false);
  assert.equal(game.document.dispatch('keydown', { key: 'p' }).defaultPrevented, false);
});
