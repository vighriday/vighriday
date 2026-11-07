/** Public GitHub contribution counts. No token, private API, or inferred counts. */
export const USERNAME = 'vighriday';
export const COMPLETED_DAYS = 90;
const DAY_MS = 86_400_000;
const MAX_HTML_BYTES = 2_000_000;
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

function instant(value, name = 'date') {
  const result = value instanceof Date ? new Date(value.getTime()) : new Date(value);
  if (!Number.isFinite(result.getTime())) throw new Error(`Invalid ${name}.`);
  return result;
}

function dayTimestamp(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new Error(`Invalid calendar date: ${String(value)}.`);
  }
  const stamp = Date.parse(`${value}T00:00:00.000Z`);
  if (!Number.isFinite(stamp) || new Date(stamp).toISOString().slice(0, 10) !== value) {
    throw new Error(`Invalid calendar date: ${value}.`);
  }
  return stamp;
}

export function dateRange(from, to) {
  const first = dayTimestamp(from);
  const last = dayTimestamp(to);
  if (last < first || (last - first) / DAY_MS > 366) throw new Error('Invalid calendar range.');
  return Array.from({ length: (last - first) / DAY_MS + 1 }, (_, index) =>
    new Date(first + index * DAY_MS).toISOString().slice(0, 10));
}

/** Exactly 90 dates ending yesterday. The local timezone never changes the cutoff. */
export function completedUtcWindow(now = new Date()) {
  const current = instant(now, 'current time');
  const midnight = Date.UTC(current.getUTCFullYear(), current.getUTCMonth(), current.getUTCDate());
  return {
    from: new Date(midnight - COMPLETED_DAYS * DAY_MS).toISOString().slice(0, 10),
    to: new Date(midnight - DAY_MS).toISOString().slice(0, 10),
    timezone: 'UTC',
    completedDays: COMPLETED_DAYS,
  };
}

function assertWindow(window) {
  if (!window || window.timezone !== 'UTC' || window.completedDays !== COMPLETED_DAYS) {
    throw new Error('The activity window must contain 90 completed UTC days.');
  }
  const dates = dateRange(window.from, window.to);
  if (dates.length !== COMPLETED_DAYS) throw new Error('The activity window must contain exactly 90 dates.');
  return dates;
}

function decodeEntities(text) {
  return text.replace(/&(#x[\da-f]+|#\d+|amp|quot|apos|lt|gt|nbsp);/gi, (entity, code) => {
    if (code[0] === '#') {
      const value = code[1].toLowerCase() === 'x' ? Number.parseInt(code.slice(2), 16) : Number.parseInt(code.slice(1), 10);
      if (!Number.isInteger(value) || value < 0 || value > 0x10ffff) throw new Error('Invalid HTML entity.');
      return String.fromCodePoint(value);
    }
    return { amp: '&', quot: '"', apos: "'", lt: '<', gt: '>', nbsp: ' ' }[code.toLowerCase()] ?? entity;
  });
}

function attributes(text) {
  const values = new Map();
  const pattern = /([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))/g;
  for (const match of text.matchAll(pattern)) {
    const name = match[1].toLowerCase();
    if (values.has(name)) throw new Error(`Duplicate HTML attribute: ${name}.`);
    values.set(name, decodeEntities(match[2] ?? match[3] ?? match[4]));
  }
  return values;
}

function tooltipCount(content, date) {
  const text = decodeEntities(content.replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();
  const pattern = /^(No|0|[1-9]\d{0,2}(?:,\d{3})+|[1-9]\d*) (contribution|contributions) on ([A-Za-z]+) ([1-9]|[12]\d|3[01])(?:st|nd|rd|th)?(?:,? (\d{4}))?\.$/;
  const match = text.match(pattern);
  if (!match) throw new Error(`Unrecognized contribution tooltip for ${date}: ${text.slice(0, 100)}`);
  const count = match[1] === 'No' ? 0 : Number(match[1].replaceAll(',', ''));
  if (!Number.isSafeInteger(count) || count < 0) throw new Error(`Invalid contribution count for ${date}.`);
  if (match[2] !== (count === 1 ? 'contribution' : 'contributions')) {
    throw new Error(`Inconsistent contribution count for ${date}.`);
  }
  const [year, month, day] = date.split('-').map(Number);
  if (MONTHS[month - 1] !== match[3] || day !== Number(match[4]) || (match[5] && year !== Number(match[5]))) {
    throw new Error(`Tooltip date does not match its calendar cell: ${date}.`);
  }
  return count;
}

/**
 * Match dated cells to their own tooltips by ID, never by DOM order or color.
 * GitHub sends a full year; cells outside the requested window are ignored.
 * Missing cells remain missing so normalizeDays can reject an incomplete fetch.
 */
export function parseCalendarHtml(html, window) {
  const dates = new Set(assertWindow(window));
  if (typeof html !== 'string' || !html.trim() || Buffer.byteLength(html, 'utf8') > MAX_HTML_BYTES) {
    throw new Error('The public contribution calendar is empty or too large.');
  }
  const cells = new Map();
  let datedCells = 0;
  for (const match of html.matchAll(/<td\b([^>]*)>/gi)) {
    const attrs = attributes(match[1]);
    const date = attrs.get('data-date');
    if (!date) continue;
    dayTimestamp(date);
    datedCells += 1;
    if (!dates.has(date)) continue;
    const id = attrs.get('id');
    if (!id || cells.has(id) || [...cells.values()].includes(date)) throw new Error(`Missing or duplicate calendar cell for ${date}.`);
    cells.set(id, date);
  }
  if (!datedCells) throw new Error('No dated contribution cells were returned by GitHub.');
  const found = new Map();
  for (const match of html.matchAll(/<tool-tip\b([^>]*)>([\s\S]*?)<\/tool-tip\s*>/gi)) {
    const id = attributes(match[1]).get('for');
    const date = cells.get(id);
    if (!date) continue;
    if (found.has(date)) throw new Error(`Duplicate contribution tooltip for ${date}.`);
    found.set(date, tooltipCount(match[2], date));
  }
  for (const date of cells.values()) {
    if (!found.has(date)) throw new Error(`Missing contribution tooltip for ${date}.`);
  }
  return [...found].map(([date, count]) => ({ date, count }));
}

/** Sort a complete set of explicit daily counts; missing is never converted to zero. */
export function normalizeDays(entries, window) {
  const dates = assertWindow(window);
  const expected = new Set(dates);
  if (!Array.isArray(entries)) throw new Error('Daily contribution counts must be an array.');
  const byDate = new Map();
  for (const entry of entries) {
    if (!entry || typeof entry !== 'object') throw new Error('Invalid daily contribution entry.');
    dayTimestamp(entry.date);
    if (!expected.has(entry.date)) throw new Error(`Contribution date outside the requested window: ${entry.date}.`);
    if (byDate.has(entry.date)) throw new Error(`Duplicate contribution date: ${entry.date}.`);
    if (!Number.isSafeInteger(entry.count) || entry.count < 0) throw new Error(`Invalid contribution count for ${entry.date}.`);
    byDate.set(entry.date, entry.count);
  }
  for (const date of dates) {
    if (!byDate.has(date)) throw new Error(`Missing contribution date: ${date}.`);
  }
  return dates.map(date => ({ date, count: byDate.get(date) }));
}

export function validateSnapshot(snapshot, { now = new Date(), expectedUsername = USERNAME } = {}) {
  if (!snapshot || snapshot.schemaVersion !== 1 || snapshot.username !== expectedUsername) throw new Error('Invalid activity snapshot identity.');
  const fetched = instant(snapshot.fetchedAt, 'fetchedAt');
  if (typeof snapshot.fetchedAt !== 'string' || fetched.toISOString() !== snapshot.fetchedAt) throw new Error('fetchedAt must be an ISO UTC timestamp.');
  if (fetched.getTime() > instant(now, 'current time').getTime()) throw new Error('Activity fetchedAt cannot be in the future.');
  const expected = completedUtcWindow(fetched);
  assertWindow(snapshot.window);
  if (snapshot.window.from !== expected.from || snapshot.window.to !== expected.to) {
    throw new Error('Activity must describe the 90 completed UTC days before fetchedAt.');
  }
  const days = normalizeDays(snapshot.days, snapshot.window);
  if (days.some((day, index) => day.date !== snapshot.days[index].date)) throw new Error('Snapshot dates must be in chronological order.');
  const total = days.reduce((sum, day) => sum + day.count, 0);
  const activeDays = days.filter(day => day.count > 0).length;
  const peakDaily = Math.max(...days.map(day => day.count));
  if (!Number.isSafeInteger(total) || snapshot.total !== total || snapshot.activeDays !== activeDays || snapshot.peakDaily !== peakDaily) {
    throw new Error('Activity aggregates do not match the daily contribution counts.');
  }
  if (snapshot.source?.kind !== 'github-public-contribution-calendar' || snapshot.source?.url !== `https://github.com/users/${expectedUsername}/contributions`) {
    throw new Error('Activity source must be the official public GitHub contribution calendar.');
  }
  return snapshot;
}

function calendarUrl(username, from, to) {
  const url = new URL(`https://github.com/users/${username}/contributions`);
  url.searchParams.set('from', from);
  url.searchParams.set('to', to);
  return url.href;
}

/** Fetch one public calendar per year touched by the 90-day window. */
export async function fetchActivity({ username = USERNAME, now = new Date(), fetchImpl = globalThis.fetch } = {}) {
  if (typeof username !== 'string' || !/^[a-z\d](?:[a-z\d-]{0,37}[a-z\d])?$/i.test(username)) throw new Error('Invalid GitHub username.');
  if (typeof fetchImpl !== 'function') throw new Error('A fetch implementation is required.');
  const fetchedAt = instant(now, 'current time').toISOString();
  const window = completedUtcWindow(fetchedAt);
  const dates = dateRange(window.from, window.to);
  const years = [...new Set(dates.map(date => date.slice(0, 4)))];
  const entries = [];
  for (const year of years) {
    const yearDates = dates.filter(date => date.startsWith(`${year}-`));
    const response = await fetchImpl(calendarUrl(username, yearDates[0], yearDates.at(-1)), {
      headers: { Accept: 'text/html', 'Accept-Language': 'en-US,en;q=0.9', 'User-Agent': 'vighriday-public-profile/1.0' },
      credentials: 'omit',
      redirect: 'error',
      signal: AbortSignal.timeout(25_000),
    });
    if (!response.ok) throw new Error(`Public GitHub calendar request failed: HTTP ${response.status}.`);
    const contentType = response.headers?.get('content-type') ?? '';
    if (!/^text\/html\b/i.test(contentType)) throw new Error('GitHub returned a non-HTML contribution calendar.');
    const parsed = parseCalendarHtml(await response.text(), window);
    // Some calendar responses include neighboring dates. Each year's request
    // owns only that year's requested dates, avoiding duplicate day records.
    entries.push(...parsed.filter(day => day.date.startsWith(`${year}-`)));
  }
  const days = normalizeDays(entries, window);
  const snapshot = {
    schemaVersion: 1,
    username,
    fetchedAt,
    window,
    days,
    total: days.reduce((sum, day) => sum + day.count, 0),
    activeDays: days.filter(day => day.count > 0).length,
    peakDaily: Math.max(...days.map(day => day.count)),
    source: { kind: 'github-public-contribution-calendar', url: `https://github.com/users/${username}/contributions` },
  };
  return validateSnapshot(snapshot, { now: fetchedAt, expectedUsername: username });
}
