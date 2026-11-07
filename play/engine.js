export const WIDTH = 960;
export const HEIGHT = 480;
export const TOTAL = 60;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

function field() {
  const width = (864 - 11 * 8) / 12;
  return Array.from({ length: TOTAL }, (_, index) => ({
    x: 48 + (index % 12) * (width + 8),
    y: 65 + Math.floor(index / 12) * 31,
    width, height: 21, row: Math.floor(index / 12), active: true,
  }));
}

function serve(game) {
  game.paddle.x = WIDTH / 2;
  Object.assign(game.ball, {
    x: WIDTH / 2, y: game.paddle.y - game.ball.radius - 9,
    vx: (game.attempts % 2 ? 1 : -1) * 165, vy: -325,
  });
}

export function createGame() {
  const game = {
    status: 'ready', cleared: 0, attempts: 3, event: null,
    paddle: { x: WIDTH / 2, y: 435, width: 144, height: 10, speed: 650 },
    ball: { x: WIDTH / 2, y: 420, vx: 165, vy: -325, radius: 6 },
    bricks: field(),
  };
  serve(game);
  return game;
}

export function startGame(game) {
  const source = game.status === 'won' || game.status === 'lost' ? createGame() : game;
  return { ...source, status: 'running', event: null };
}

export function pauseGame(game) {
  return game.status === 'running' ? { ...game, status: 'paused', event: null } : game;
}

export function moveReceiver(game, x) {
  return { ...game, paddle: { ...game.paddle, x: clamp(x, game.paddle.width / 2 + 16, WIDTH - game.paddle.width / 2 - 16) } };
}

// The engine has no DOM, clock, randomness, or external state. Every transition
// returns a new snapshot and leaves its input untouched.
export function stepGame(game, seconds, input = {}) {
  if (game.status !== 'running') return game;
  const duration = clamp(Number.isFinite(seconds) ? seconds : 0, 0, 0.04);
  const next = { ...game, paddle: { ...game.paddle }, ball: { ...game.ball }, bricks: game.bricks.map(brick => ({ ...brick })), event: null };
  const steps = Math.max(1, Math.ceil(duration / 0.008));
  const delta = duration / steps;
  for (let index = 0; index < steps && next.status === 'running'; index += 1) advance(next, delta, input);
  return next;
}

function advance(game, delta, input) {
  const { ball, paddle } = game;
  const direction = clamp(input.direction || 0, -1, 1);
  paddle.x = clamp(paddle.x + direction * paddle.speed * delta, paddle.width / 2 + 16, WIDTH - paddle.width / 2 - 16);
  const previousX = ball.x;
  const previousY = ball.y;
  ball.x += ball.vx * delta;
  ball.y += ball.vy * delta;

  if (ball.x - ball.radius < 16) { ball.x = 16 + ball.radius; ball.vx = Math.abs(ball.vx); }
  else if (ball.x + ball.radius > WIDTH - 16) { ball.x = WIDTH - 16 - ball.radius; ball.vx = -Math.abs(ball.vx); }
  if (ball.y - ball.radius < 16) { ball.y = 16 + ball.radius; ball.vy = Math.abs(ball.vy); }

  if (ball.vy > 0 && previousY + ball.radius <= paddle.y && ball.y + ball.radius >= paddle.y && ball.x + ball.radius >= paddle.x - paddle.width / 2 && ball.x - ball.radius <= paddle.x + paddle.width / 2) {
    const offset = clamp((ball.x - paddle.x) / (paddle.width / 2), -1, 1);
    const speed = Math.max(360, Math.min(565, Math.hypot(ball.vx, ball.vy)));
    ball.vx = Math.sin(offset * 1.07) * speed;
    if (Math.abs(ball.vx) < 45) ball.vx = offset < 0 ? -45 : 45;
    ball.vy = -Math.sqrt(speed * speed - ball.vx * ball.vx);
    ball.y = paddle.y - ball.radius;
    game.event = 'return';
  }

  for (const brick of game.bricks) {
    if (!brick.active || ball.x + ball.radius < brick.x || ball.x - ball.radius > brick.x + brick.width || ball.y + ball.radius < brick.y || ball.y - ball.radius > brick.y + brick.height) continue;
    brick.active = false;
    game.cleared += 1;
    if (previousX + ball.radius <= brick.x || previousX - ball.radius >= brick.x + brick.width) ball.vx *= -1;
    else ball.vy *= -1;
    const speed = Math.hypot(ball.vx, ball.vy);
    const factor = speed ? Math.min(1.008, 565 / speed) : 1;
    ball.vx *= factor;
    ball.vy *= factor;
    game.event = 'tile';
    if (game.cleared === TOTAL) { game.status = 'won'; game.event = 'won'; }
    break;
  }

  if (ball.y - ball.radius > HEIGHT) {
    game.attempts -= 1;
    game.status = game.attempts === 0 ? 'lost' : 'retry';
    game.event = game.status;
    if (game.attempts > 0) serve(game);
  }
}
