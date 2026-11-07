import test from 'node:test';
import assert from 'node:assert/strict';
import { WIDTH, HEIGHT, TOTAL, createGame, startGame, pauseGame, moveReceiver, stepGame } from '../play/engine.js';

test('a new run has a 5 by 12 field, three attempts, and waits for explicit start', () => {
  const game = createGame();
  assert.equal(game.status, 'ready');
  assert.equal(game.bricks.length, 60);
  assert.equal(new Set(game.bricks.map(brick => brick.row)).size, 5);
  assert.equal(game.attempts, 3);
  assert.equal(game.cleared, 0);
  assert.strictEqual(stepGame(game, 1), game);
});

test('simulation returns a new snapshot without mutating its input', () => {
  const game = startGame(createGame());
  const before = structuredClone(game);
  const next = stepGame(game, .016, { direction: 1 });
  assert.deepEqual(game, before);
  assert.notEqual(next.ball.y, game.ball.y);
  assert.ok(next.paddle.x > game.paddle.x);
});

test('receiver movement is bounded for pointer and keyboard input', () => {
  let game = moveReceiver(startGame(createGame()), -1000);
  assert.equal(game.paddle.x, 16 + game.paddle.width / 2);
  game = stepGame(game, .04, { direction: -1 });
  assert.equal(game.paddle.x, 16 + game.paddle.width / 2);
  game = moveReceiver(game, 10000);
  assert.equal(game.paddle.x, WIDTH - 16 - game.paddle.width / 2);
});

for (const side of ['left', 'right', 'top']) test(`signal returns from the ${side} boundary`, () => {
  const game = startGame(createGame());
  game.ball.x = side === 'right' ? WIDTH - 23 : side === 'left' ? 23 : WIDTH / 2;
  game.ball.y = side === 'top' ? 23 : 300;
  game.ball.vx = side === 'right' ? 300 : side === 'left' ? -300 : 0;
  game.ball.vy = side === 'top' ? -300 : 0;
  const next = stepGame(game, .016);
  if (side === 'top') { assert.ok(next.ball.vy > 0); assert.ok(next.ball.y >= 22); }
  else if (side === 'left') { assert.ok(next.ball.vx > 0); assert.ok(next.ball.x >= 22); }
  else { assert.ok(next.ball.vx < 0); assert.ok(next.ball.x <= WIDTH - 22); }
});

test('an off-centre receiver return changes direction and sends the signal upward', () => {
  const game = startGame(createGame());
  game.ball.x = game.paddle.x + 45;
  game.ball.y = game.paddle.y - game.ball.radius - 1;
  game.ball.vx = 0;
  game.ball.vy = 360;
  const next = stepGame(game, .016);
  assert.ok(next.ball.vy < 0);
  assert.ok(next.ball.vx > 0);
  assert.ok(next.ball.y + next.ball.radius <= next.paddle.y);
});

test('missing a return costs one attempt and preserves cleared tiles', () => {
  const game = startGame(createGame());
  game.bricks[0].active = false;
  game.cleared = 1;
  game.ball.y = HEIGHT + game.ball.radius + 1;
  game.ball.vy = 325;
  const next = stepGame(game, .016);
  assert.equal(next.status, 'retry');
  assert.equal(next.attempts, 2);
  assert.equal(next.cleared, 1);
  assert.equal(next.bricks[0].active, false);
  assert.equal(next.ball.x, WIDTH / 2);
  assert.equal(startGame(next).status, 'running');
});

test('the final missed return ends the run', () => {
  const game = startGame(createGame());
  game.attempts = 1;
  game.ball.y = HEIGHT + game.ball.radius + 1;
  game.ball.vy = 325;
  const next = stepGame(game, .016);
  assert.equal(next.status, 'lost');
  assert.equal(next.attempts, 0);
  assert.strictEqual(stepGame(next, .04), next);
});

test('a tile collision removes exactly that tile and reflects the signal', () => {
  const game = startGame(createGame());
  const target = game.bricks[0];
  game.ball.x = target.x + target.width / 2;
  game.ball.y = target.y - game.ball.radius - 1;
  game.ball.vx = 0;
  game.ball.vy = 300;
  const next = stepGame(game, .016);
  assert.equal(next.cleared, 1);
  assert.equal(next.bricks.filter(brick => brick.active).length, TOTAL - 1);
  assert.equal(next.bricks[0].active, false);
  assert.ok(next.ball.vy < 0);
});

test('clearing the last tile wins; starting again produces a fresh field', () => {
  const game = startGame(createGame());
  game.bricks.forEach((brick, index) => { brick.active = index === 0; });
  game.cleared = TOTAL - 1;
  const target = game.bricks[0];
  Object.assign(game.ball, { x: target.x + target.width / 2, y: target.y - game.ball.radius - 1, vx: 0, vy: 300 });
  const won = stepGame(game, .016);
  assert.equal(won.status, 'won');
  assert.equal(won.cleared, TOTAL);
  const again = startGame(won);
  assert.equal(again.status, 'running');
  assert.equal(again.cleared, 0);
  assert.equal(again.attempts, 3);
  assert.equal(again.bricks.filter(brick => brick.active).length, TOTAL);
});

test('pause freezes the simulation and resume retains progress', () => {
  const game = startGame(createGame());
  game.cleared = 4;
  const paused = pauseGame(game);
  assert.equal(paused.status, 'paused');
  assert.strictEqual(stepGame(paused, .04, { direction: 1 }), paused);
  const resumed = startGame(paused);
  assert.equal(resumed.status, 'running');
  assert.equal(resumed.cleared, 4);
  assert.deepEqual(resumed.ball, paused.ball);
  const reset = createGame();
  assert.equal(reset.status, 'ready');
  assert.equal(reset.cleared, 0);
});
