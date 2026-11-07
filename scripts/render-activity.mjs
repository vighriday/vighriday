import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';
import { palette, svgDocument, escapeXml } from '../src/theme.mjs';
import { validateSnapshot } from '../src/activity.mjs';

const number = value => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const date = value => `${Number(value.slice(8, 10))} ${months[Number(value.slice(5, 7)) - 1]} ${value.slice(0, 4)}`;
export function renderActivity(snapshot) {
  validateSnapshot(snapshot);
  const { days, total, activeDays, peakDaily, window, fetchedAt } = snapshot;
  const x = 48, chartWidth = 864, bottom = 248, chartHeight = 112;
  const step = chartWidth / days.length;
  const bars = days.map((day, index) => {
    const height = peakDaily === 0 ? 0 : day.count / peakDaily * chartHeight;
    const fill = day.count === peakDaily && peakDaily > 0 ? palette.acid : palette.paper;
    return `<rect x="${(x + index * step + 1).toFixed(2)}" y="${(bottom - height).toFixed(2)}" width="${(step - 2).toFixed(2)}" height="${height.toFixed(2)}" fill="${fill}" opacity="${day.count === peakDaily ? 1 : .53}"><title>${escapeXml(day.date)}: ${day.count} contributions</title></rect>`;
  }).join('\n');
  const stats = [[48, total, 'CONTRIBUTIONS'], [364, activeDays, 'ACTIVE DAYS / 90'], [680, peakDaily, 'PEAK DAILY COUNT']].map(([left, value, label]) => `<text x="${left}" y="80" class="number">${number(value)}</text><text x="${left}" y="103" class="label">${label}</text>`).join('');
  const refreshed = `${date(fetchedAt)} ${fetchedAt.slice(11, 16)}`;
  return svgDocument({
    height: 310,
    title: `${number(total)} GitHub-reported contributions across 90 completed UTC dates`,
    description: `Public-profile calendar from ${window.from} through ${window.to}. ${activeDays} active days, peak ${peakDaily} contributions in a day. Refreshed ${fetchedAt}. Contributions follow GitHub's rules and are not a count of commits or working hours.`,
    defs: `<style>.label{font:11px ui-monospace,Consolas,monospace;letter-spacing:1px;fill:${palette.muted}}.number{font:300 36px Arial,sans-serif;letter-spacing:-1px;fill:${palette.paper}}.date{font:12px ui-monospace,Consolas,monospace;fill:${palette.muted}}</style>`,
    body: `<text x="48" y="29" class="label">ACTIVITY / 90 COMPLETED UTC DATES</text>
      ${stats}
      <path d="M48 120H912M48 248H912" stroke="${palette.line}" stroke-width="1"/>
      <path d="M48 192H912M48 136H912" stroke="${palette.line}" stroke-width=".6" opacity=".45"/>
      ${bars}
      <text x="48" y="272" class="date">${date(window.from)}</text>
      <text x="912" y="272" text-anchor="end" class="date">${date(window.to)}</text>
      <circle cx="51" cy="296" r="2" fill="${palette.acid}"/>
      <text x="61" y="300" class="date">PUBLIC GITHUB CALENDAR</text>
      <text x="912" y="300" text-anchor="end" class="date">Updated ${escapeXml(refreshed)} UTC</text>`,
  });
}

async function main() {
  const snapshot = JSON.parse(await readFile(new URL('../data/activity.json', import.meta.url), 'utf8'));
  const image = renderActivity(snapshot);
  const target = new URL('../assets/activity.svg', import.meta.url);
  if (process.argv.includes('--check')) assert.equal(await readFile(target, 'utf8'), image, 'Activity SVG differs from its source snapshot.');
  else {
    await mkdir(new URL('../assets/', import.meta.url), { recursive: true });
    await writeFile(target, image);
  }
  console.log(`Activity chart: ${snapshot.total} contributions, ${snapshot.window.from} through ${snapshot.window.to}.`);
}
if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) main().catch(error => { console.error(error.message); process.exitCode = 1; });
