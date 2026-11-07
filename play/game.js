import { WIDTH, HEIGHT, TOTAL, createGame, startGame, pauseGame, moveReceiver, stepGame } from './engine.js';

(() => {
  'use strict';

  const canvas = document.getElementById('board');
  const context = canvas.getContext('2d');
  const overlay = document.getElementById('overlay');
  const startButton = document.getElementById('start');
  const pauseButton = document.getElementById('pause');
  const resetButton = document.getElementById('reset');
  const status = document.getElementById('game-status');
  const score = document.getElementById('score');
  const lives = document.getElementById('lives');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const colors = { paper: '#e8e7df', acid: '#c8ff4d', red: '#ff4d35', muted: '#95a183', dark: '#0d100b' };
  const keys = new Set();
  const heldPointers = new Map();
  const trail = [];
  let game = createGame();
  let dragging = null;
  let lastTime = 0;
  let animationFrame = null;

  if (!context) {
    status.textContent = 'Canvas is unavailable in this browser. Please try another browser to play.';
    startButton.disabled = true;
    return;
  }

  const count = value => String(value).padStart(2, '0');

  function releaseButtons() {
    heldPointers.clear();
    document.querySelectorAll('.touch-controls button').forEach(button => button.classList.remove('is-held'));
  }

  function refreshReadouts() {
    score.textContent = `${count(game.cleared)} / ${TOTAL}`;
    lives.textContent = count(game.attempts);
  }

  function setState(next, announcement) {
    game = { ...game, status: next };
    const { status: state, attempts, cleared } = game;
    overlay.hidden = state === 'running';
    pauseButton.disabled = state !== 'running' && state !== 'paused';
    pauseButton.innerHTML = state === 'paused' ? 'Resume <kbd>P</kbd>' : 'Pause <kbd>P</kbd>';
    keys.clear();
    releaseButtons();
    const labels = {
      ready: ['YOUR MOVE / NO AUTOPILOT', 'Find your <em>signal.</em>', 'Clear all 60 tiles. Keep the signal above the receiver. You have three attempts.', 'Start run'],
      paused: ['TAKE YOUR TIME / KEEP YOUR PLACE', 'A little <em>space.</em>', 'Your run is right here. Resume when you are ready.', 'Resume run'],
      retry: ['SIGNAL DROPPED / STILL IN THE GAME', 'Another <em>angle.</em>', `${attempts} ${attempts === 1 ? 'attempt remains' : 'attempts remain'}. The cleared tiles stay clear.`, 'Continue run'],
      won: ['FIELD CLEAR / RUN COMPLETE', 'Clarity, <em>earned.</em>', 'All 60 tiles cleared. A small idea, followed all the way through.', 'Play again'],
      lost: ['RUN COMPLETE / TRY A NEW APPROACH', 'Signal <em>lost.</em>', `You cleared ${cleared} of 60 tiles. Try a different angle on the next run.`, 'Try again'],
    };
    if (labels[state]) {
      const [kicker, title, description, button] = labels[state];
      document.getElementById('overlay-kicker').textContent = kicker;
      document.getElementById('overlay-title').innerHTML = title;
      document.getElementById('overlay-description').textContent = description;
      startButton.innerHTML = `${button} <span aria-hidden="true">↗</span>`;
    }
    if (announcement) status.textContent = announcement;
    draw();
    if (state === 'running') schedule();
  }

  function reset() {
    if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    animationFrame = null;
    game = createGame();
    trail.length = 0;
    refreshReadouts();
    setState('ready', 'Ready when you are. Start the run to play.');
  }

  function start() {
    if (game.status === 'running') return;
    if (game.status === 'won' || game.status === 'lost') trail.length = 0;
    game = startGame(game);
    refreshReadouts();
    lastTime = performance.now();
    setState('running', 'Run in progress. Clear the field. Space or P pauses.');
    canvas.focus({ preventScroll: true });
  }

  function togglePause() {
    if (game.status === 'running') { game = pauseGame(game); setState('paused', 'Run paused. Resume when you are ready.'); }
    else if (game.status === 'paused') start();
  }

  function schedule() {
    if (animationFrame === null && game.status === 'running') animationFrame = requestAnimationFrame(frame);
  }

  function frame(time) {
    animationFrame = null;
    if (game.status !== 'running') return;
    const delta = Math.min((time - lastTime) / 1000, 0.04);
    lastTime = time;
    update(delta);
    if (!reducedMotion.matches && game.status === 'running') {
      trail.push({ x: game.ball.x, y: game.ball.y });
      if (trail.length > 10) trail.shift();
    }
    draw();
    schedule();
  }

  function update(delta) {
    let direction = 0;
    if (keys.has('arrowleft') || keys.has('a') || [...heldPointers.values()].includes(-1)) direction -= 1;
    if (keys.has('arrowright') || keys.has('d') || [...heldPointers.values()].includes(1)) direction += 1;
    const previous = game;
    game = stepGame(game, delta, { direction });
    if (game.cleared !== previous.cleared || game.attempts !== previous.attempts) refreshReadouts();
    if (game.status === previous.status) return;
    trail.length = 0;
    if (game.status === 'won') setState('won', 'Run complete. You cleared all 60 tiles. Well played.');
    else if (game.status === 'lost') setState('lost', `Run over. You cleared ${game.cleared} of 60 tiles. Try again when you are ready.`);
    else if (game.status === 'retry') setState('retry', `Signal dropped. ${game.attempts} ${game.attempts === 1 ? 'attempt remains' : 'attempts remain'}. Continue when ready.`);
  }

  function draw() {
    const { paddle, ball, bricks } = game;
    context.clearRect(0, 0, WIDTH, HEIGHT);
    context.fillStyle = colors.dark;
    context.fillRect(0, 0, WIDTH, HEIGHT);
    context.strokeStyle = '#d4e1ba08';
    context.lineWidth = 1;
    for (let x = 0; x <= WIDTH; x += 40) { context.beginPath(); context.moveTo(x, 0); context.lineTo(x, HEIGHT); context.stroke(); }
    for (let y = 0; y <= HEIGHT; y += 40) { context.beginPath(); context.moveTo(0, y); context.lineTo(WIDTH, y); context.stroke(); }
    context.strokeStyle = '#8b987b33';
    context.strokeRect(16.5, 16.5, WIDTH - 33, HEIGHT - 33);
    context.fillStyle = colors.muted;
    context.font = '10px monospace';
    context.fillText('SIGNAL FIELD / 60 TARGETS', 48, 42);
    context.textAlign = 'right';
    context.fillText('KEEP THE LOOP OPEN', WIDTH - 48, 42);
    context.textAlign = 'left';

    for (const brick of bricks) {
      if (!brick.active) continue;
      context.fillStyle = brick.row === 0 ? '#c8ff4d' : brick.row === 1 ? '#a6bd73' : brick.row === 2 ? '#808f61' : brick.row === 3 ? '#626f4c' : '#424f34';
      context.fillRect(brick.x, brick.y, brick.width, brick.height);
      context.fillStyle = brick.row < 2 ? '#151b0b' : '#d7e3c0';
      context.fillRect(brick.x + 5, brick.y + brick.height / 2, brick.row % 2 ? 9 : 4, 1);
    }
    if (!reducedMotion.matches) {
      trail.forEach((point, index) => {
        context.globalAlpha = index / trail.length * 0.22;
        context.fillStyle = colors.acid;
        context.beginPath(); context.arc(point.x, point.y, ball.radius * index / trail.length, 0, Math.PI * 2); context.fill();
      });
      context.globalAlpha = 1;
    }
    context.fillStyle = colors.red;
    context.beginPath(); context.arc(ball.x, ball.y, ball.radius, 0, Math.PI * 2); context.fill();
    context.fillStyle = colors.acid;
    context.fillRect(paddle.x - paddle.width / 2, paddle.y, paddle.width, paddle.height);
    context.fillStyle = '#e8e7df';
    context.fillRect(paddle.x - 1, paddle.y - 5, 2, paddle.height + 10);
    context.strokeStyle = '#c8ff4d35';
    context.beginPath(); context.moveTo(paddle.x, paddle.y + 20); context.lineTo(paddle.x, HEIGHT - 18); context.stroke();
  }

  function fitCanvas() {
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = WIDTH * ratio;
    canvas.height = HEIGHT * ratio;
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    draw();
  }

  function placeReceiver(event) {
    const bounds = canvas.getBoundingClientRect();
    game = moveReceiver(game, (event.clientX - bounds.left) / bounds.width * WIDTH);
    if (game.status !== 'running') draw();
  }

  canvas.addEventListener('keydown', event => {
    const key = event.key.toLowerCase();
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (['arrowleft', 'arrowright', 'a', 'd'].includes(key) && game.status === 'running') {
      event.preventDefault(); keys.add(key);
    } else if ((key === ' ' || key === 'p') && !event.repeat) {
      event.preventDefault();
      if (game.status === 'running' || game.status === 'paused') togglePause();
      else if (key === ' ') start();
    } else if (key === 'r' && !event.repeat) { event.preventDefault(); reset(); }
  });
  canvas.addEventListener('keyup', event => keys.delete(event.key.toLowerCase()));
  canvas.addEventListener('blur', () => keys.clear());
  document.querySelector('.game').addEventListener('focusout', event => {
    const region = event.currentTarget;
    // Wait until focus has settled: a click on non-focusable page content can
    // have a null relatedTarget, while our Pause and touch controls stay inside.
    requestAnimationFrame(() => {
      if (!region.contains(document.activeElement) && game.status === 'running') setState('paused', 'Run paused while the field is not focused. Resume when ready.');
    });
  });
  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    dragging = event.pointerId;
    canvas.setPointerCapture(event.pointerId);
    canvas.focus({ preventScroll: true });
    placeReceiver(event);
  });
  canvas.addEventListener('pointermove', event => { if (dragging === event.pointerId) placeReceiver(event); });
  const releaseDrag = event => { if (dragging === event.pointerId) dragging = null; };
  canvas.addEventListener('pointerup', releaseDrag);
  canvas.addEventListener('pointercancel', releaseDrag);
  canvas.addEventListener('lostpointercapture', releaseDrag);

  [[document.getElementById('move-left'), -1], [document.getElementById('move-right'), 1]].forEach(([button, direction]) => {
    button.addEventListener('pointerdown', event => {
      if (event.button !== 0 || game.status !== 'running') return;
      event.preventDefault();
      button.setPointerCapture(event.pointerId);
      heldPointers.set(event.pointerId, direction);
      button.classList.add('is-held');
    });
    const release = event => { heldPointers.delete(event.pointerId); button.classList.remove('is-held'); };
    button.addEventListener('pointerup', release);
    button.addEventListener('pointercancel', release);
    button.addEventListener('lostpointercapture', release);
    button.addEventListener('click', event => {
      if (event.detail === 0 && game.status === 'running') {
        game = moveReceiver(game, game.paddle.x + direction * 70);
        canvas.focus({ preventScroll: true });
      }
    });
  });

  startButton.addEventListener('click', start);
  pauseButton.addEventListener('click', togglePause);
  resetButton.addEventListener('click', reset);
  document.addEventListener('visibilitychange', () => { if (document.hidden && game.status === 'running') setState('paused', 'Run paused while this page is in the background.'); });
  window.addEventListener('blur', () => { if (game.status === 'running') setState('paused', 'Run paused while this window is not active.'); });
  window.addEventListener('resize', fitCanvas);
  reducedMotion.addEventListener('change', () => { trail.length = 0; draw(); });
  fitCanvas();
  reset();
})();
