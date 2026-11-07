import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { completedUtcWindow, dateRange, fetchActivity, normalizeDays, parseCalendarHtml, validateSnapshot } from '../src/activity.mjs';
import { refreshData, writeSnapshotAtomic } from '../scripts/refresh-data.mjs';

const NOW = new Date('2026-11-07T12:34:56.000Z');
const WINDOW = completedUtcWindow(NOW);
const dates = dateRange(WINDOW.from, WINDOW.to);
const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function tooltip(date, count) {
  const [year, month, day] = date.split('-').map(Number);
  return `${count === 0 ? 'No' : count.toLocaleString('en-US')} ${count === 1 ? 'contribution' : 'contributions'} on ${months[month - 1]} ${day}th.`;
}

function calendar(entries) {
  // Matches GitHub's real dated td + ID-associated tool-tip markup. Tooltips
  // intentionally appear in reverse order to exercise ID-based association.
  return `<table><tr>${entries.map(({ date }, index) => `<td tabindex="0" data-ix="${index}" aria-selected="false" aria-describedby="contribution-graph-legend-level-0" style="width: 11px" data-date="${date}" id="contribution-day-component-0-${index}" data-level="0" role="gridcell" data-view-component="true" class="ContributionCalendar-day"></td>`).join('')}</tr></table>`
    + entries.map(({ date, count }, index) => `<tool-tip style="pointer-events: none;" id="tooltip-${index}" for="contribution-day-component-0-${index}" popover="manual" data-direction="n" data-type="label" data-view-component="true" class="sr-only position-absolute">${tooltip(date, count)}</tool-tip>`).reverse().join('');
}

function entries(count = 0) {
  return dates.map((date, index) => ({ date, count: typeof count === 'function' ? count(index) : count }));
}

function snapshot(count = 0, now = NOW) {
  const window = completedUtcWindow(now);
  const days = dateRange(window.from, window.to).map((date, index) => ({ date, count: typeof count === 'function' ? count(index) : count }));
  return {
    schemaVersion: 1, username: 'vighriday', fetchedAt: now.toISOString(), window, days,
    total: days.reduce((sum, day) => sum + day.count, 0),
    activeDays: days.filter(day => day.count > 0).length,
    peakDaily: Math.max(...days.map(day => day.count)),
    source: { kind: 'github-public-contribution-calendar', url: 'https://github.com/users/vighriday/contributions' },
  };
}

const validAt = { now: NOW };

test('90 completed UTC days exclude today and are independent of the host timezone', () => {
  assert.deepEqual(WINDOW, { from: '2026-08-09', to: '2026-11-06', timezone: 'UTC', completedDays: 90 });
  assert.equal(dates.length, 90);
  assert.deepEqual(completedUtcWindow('2026-11-08T02:00:00+05:30'), WINDOW);
});

test('UTC year boundary and leap day remain consecutive and complete', () => {
  assert.deepEqual(completedUtcWindow('2026-01-01T00:00:00Z'), { from: '2025-10-03', to: '2025-12-31', timezone: 'UTC', completedDays: 90 });
  assert.deepEqual(completedUtcWindow('2026-01-01T00:15:00+05:30'), { from: '2025-10-02', to: '2025-12-30', timezone: 'UTC', completedDays: 90 });
  assert.deepEqual(dateRange('2024-02-28', '2024-03-01'), ['2024-02-28', '2024-02-29', '2024-03-01']);
});

test('invalid dates, reversed ranges, oversized ranges and malformed windows fail', () => {
  assert.throws(() => completedUtcWindow('not-a-date'), /Invalid/);
  assert.throws(() => dateRange('2026-02-30', '2026-03-01'), /Invalid/);
  assert.throws(() => dateRange('2026-11-07', '2026-11-06'), /Invalid/);
  assert.throws(() => dateRange('2024-01-01', '2026-01-01'), /Invalid/);
  assert.throws(() => normalizeDays([], { ...WINDOW, completedDays: 89 }), /90 completed/);
});

test('real calendar markup associates explicit zero, singular and comma-formatted counts by cell ID', () => {
  const expected = [{ date: dates[0], count: 0 }, { date: dates[1], count: 1 }, { date: dates[2], count: 1234 }];
  const parsed = parseCalendarHtml(calendar(expected), WINDOW).sort((a, b) => a.date.localeCompare(b.date));
  assert.deepEqual(parsed, expected);
});

test('HTML whitespace and entities do not change an explicit tooltip count', () => {
  const html = calendar([{ date: dates[0], count: 1234 }]).replace('1,234 contributions on', '1,234&nbsp;contributions&#32;on');
  assert.deepEqual(parseCalendarHtml(html, WINDOW), [{ date: dates[0], count: 1234 }]);
});

test('color levels never substitute for tooltip counts, and empty HTML is not zero activity', () => {
  assert.throws(() => parseCalendarHtml('', WINDOW), /empty/);
  assert.throws(() => parseCalendarHtml('<html>Sign in to GitHub</html>', WINDOW), /No dated/);
  assert.throws(() => parseCalendarHtml(`<td data-date="${dates[0]}" id="day" data-level="4"></td>`, WINDOW), /Missing contribution tooltip/);
});

test('unknown, mismatched, malformed and duplicated tooltips are rejected', () => {
  const html = calendar([{ date: dates[0], count: 2 }]);
  assert.throws(() => parseCalendarHtml(html.replace('2 contributions', 'some contributions'), WINDOW), /Unrecognized/);
  assert.throws(() => parseCalendarHtml(html.replace('August 9th', 'August 10th'), WINDOW), /Tooltip date/);
  assert.throws(() => parseCalendarHtml(html.replace('2 contributions', '2 contribution'), WINDOW), /Inconsistent/);
  assert.throws(() => parseCalendarHtml(html.replace('2 contributions', '12,34 contributions'), WINDOW), /Unrecognized/);
  assert.throws(() => parseCalendarHtml(`${html}<tool-tip for="contribution-day-component-0-0">2 contributions on August 9th.</tool-tip>`, WINDOW), /Duplicate contribution tooltip/);
});

test('duplicate cells and dates are rejected, while unrelated full-year cells are ignored', () => {
  assert.throws(() => parseCalendarHtml(calendar([{ date: dates[0], count: 1 }, { date: dates[0], count: 1 }]), WINDOW), /duplicate calendar cell/i);
  const html = `${calendar([{ date: dates[0], count: 1 }])}<td data-date="2026-12-31" id="future" data-level="0"></td>`;
  assert.deepEqual(parseCalendarHtml(html, WINDOW), [{ date: dates[0], count: 1 }]);
});

test('normalization sorts a complete calendar and rejects missing, duplicate and out-of-window dates', () => {
  const full = entries(index => index % 3);
  assert.deepEqual(normalizeDays([...full].reverse(), WINDOW), full);
  assert.throws(() => normalizeDays(full.slice(1), WINDOW), /Missing contribution date/);
  assert.throws(() => normalizeDays([...full, full[0]], WINDOW), /Duplicate contribution date/);
  assert.throws(() => normalizeDays([], WINDOW), /Missing contribution date/);
  assert.throws(() => normalizeDays([...full, { date: '2026-11-07', count: 0 }], WINDOW), /outside the requested window/);
  for (const count of [-1, 0.5, NaN, '2', Number.MAX_SAFE_INTEGER + 1]) {
    assert.throws(() => normalizeDays([{ ...full[0], count }, ...full.slice(1)], WINDOW), /Invalid contribution count/);
  }
});

test('an explicitly observed 90-day all-zero calendar is a valid snapshot', () => {
  const zero = snapshot(0);
  assert.equal(validateSnapshot(zero, validAt), zero);
  assert.equal(zero.total, 0);
  assert.equal(zero.activeDays, 0);
  assert.equal(zero.peakDaily, 0);
});

test('aggregate mismatches, unsorted dates and overflow fail validation', () => {
  for (const key of ['total', 'activeDays', 'peakDaily']) {
    const data = snapshot(index => index % 5);
    data[key] += 1;
    assert.throws(() => validateSnapshot(data, validAt), /aggregates/);
  }
  const unsorted = snapshot(1);
  unsorted.days.reverse();
  assert.throws(() => validateSnapshot(unsorted, validAt), /chronological/);
  assert.throws(() => validateSnapshot(snapshot(Number.MAX_SAFE_INTEGER), validAt), /aggregates/);
});

test('future timestamps, partial-today windows and untrusted source identities fail', () => {
  const future = snapshot(0, new Date('2026-11-08T00:00:00.000Z'));
  assert.throws(() => validateSnapshot(future, validAt), /future/);
  const wrongWindow = snapshot(0);
  wrongWindow.window = completedUtcWindow('2026-11-08T00:00:00.000Z');
  assert.throws(() => validateSnapshot(wrongWindow, validAt), /before fetchedAt/);
  const source = snapshot(0);
  source.source.url = 'https://example.com/calendar';
  assert.throws(() => validateSnapshot(source, validAt), /official public/);
});

test('fetch uses one unauthenticated public HTML request for a single-year window', async () => {
  const expected = entries(index => index % 7);
  const calls = [];
  const result = await fetchActivity({ now: NOW, fetchImpl: async (url, options) => {
    calls.push(url);
    assert.equal(options.credentials, 'omit');
    assert.equal(Object.keys(options.headers).some(key => key.toLowerCase() === 'authorization'), false);
    return new Response(calendar(expected), { headers: { 'content-type': 'text/html; charset=utf-8' } });
  } });
  assert.equal(calls.length, 1);
  assert.equal(calls[0], 'https://github.com/users/vighriday/contributions?from=2026-08-09&to=2026-11-06');
  assert.deepEqual(result.days, expected);
  assert.equal(result.total, expected.reduce((sum, day) => sum + day.count, 0));
});

test('a cross-year window requests each calendar year and retains all 90 completed days', async () => {
  const now = new Date('2026-01-15T12:00:00.000Z');
  const expected = snapshot(index => index % 4, now);
  const calls = [];
  const result = await fetchActivity({ now, fetchImpl: async url => {
    calls.push(url);
    const year = new URL(url).searchParams.get('from').slice(0, 4);
    return new Response(calendar(expected.days.filter(day => day.date.startsWith(year))), { headers: { 'content-type': 'text/html' } });
  } });
  assert.equal(calls.length, 2);
  assert.match(calls[0], /to=2025-12-31$/);
  assert.match(calls[1], /from=2026-01-01&to=2026-01-14$/);
  assert.deepEqual(result, expected);
});

test('HTTP, changed markup and incomplete calendar responses fail without publishing', async () => {
  await assert.rejects(fetchActivity({ now: NOW, fetchImpl: async () => new Response('rate limited', { status: 429 }) }), /HTTP 429/);
  await assert.rejects(fetchActivity({ now: NOW, fetchImpl: async () => new Response('{}', { headers: { 'content-type': 'application/json' } }) }), /non-HTML/);
  await assert.rejects(fetchActivity({ now: NOW, fetchImpl: async () => new Response(calendar(entries(0).slice(1)), { headers: { 'content-type': 'text/html' } }) }), /Missing contribution date/);
});

test('atomic writer validates before replacing the last good snapshot', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'profile-activity-'));
  const output = join(directory, 'activity.json');
  try {
    const good = snapshot(index => index % 2);
    await writeSnapshotAtomic(good, output, validAt);
    const original = await readFile(output, 'utf8');
    await assert.rejects(writeSnapshotAtomic({ ...good, total: 999 }, output, validAt), /aggregates/);
    assert.equal(await readFile(output, 'utf8'), original);
    assert.deepEqual(await readdir(directory), ['activity.json']);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});

test('fetch failure preserves the existing file, including its old timestamp', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'profile-fetch-'));
  const output = join(directory, 'activity.json');
  try {
    const previous = `${JSON.stringify(snapshot(3))}\n`;
    await writeFile(output, previous);
    await assert.rejects(refreshData({ output, fetchOptions: { now: NOW, fetchImpl: async () => { throw new Error('offline'); } } }), /offline/);
    assert.equal(await readFile(output, 'utf8'), previous);
    assert.deepEqual(await readdir(directory), ['activity.json']);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
});
