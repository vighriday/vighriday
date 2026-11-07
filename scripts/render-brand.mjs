import { mkdir, readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import opentype from 'opentype.js';
import { palette, width, svgDocument } from '../src/theme.mjs';
import { serializePath } from '../src/lettering.mjs';

const height = 336;
const file = new URL('../assets/header.svg', import.meta.url);
const fontFiles = {
  sans: new URL('../fonts/Manrope-Light.ttf', import.meta.url),
  serif: new URL('../fonts/Newsreader-LightItalic.ttf', import.meta.url),
};
const fonts = {};
for (const [name, url] of Object.entries(fontFiles)) {
  const bytes = await readFile(url);
  fonts[name] = opentype.parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
}
const portrait = JSON.parse(await readFile(new URL('../src/portrait.json', import.meta.url), 'utf8'));
assert.equal(portrait.columns, 64);
assert.equal(portrait.rows.length, 46);
assert.ok(portrait.rows.every(row => row.length === portrait.columns && [...row].every(character => portrait.levels.includes(character))), 'The original pixel portrait must remain complete.');

const bounds = [];
function lettering(font, text, x, y, size, fill, letterSpacing = 0) {
  const options = { kerning: true, letterSpacing };
  const path = fonts[font].getPath(text, x, y, size, options);
  bounds.push({ text, ...path.getBoundingBox() });
  // Preserve glyph contours and serialize finite, rounded coordinates directly.
  // The font library's decimal formatter can turn near-integer floats into NaN.
  return fonts[font].getPaths(text, x, y, size, options)
    .map(glyph => `<path fill="${fill}" stroke="${fill}" stroke-width="${size >= 40 ? .3 : .1}" stroke-linejoin="round" paint-order="stroke fill" d="${serializePath(glyph)}"/>`)
    .join('');
}

// Keep the original portrait's tonal cells as vector geometry. No remote photo,
// font-dependent block glyphs, raster payload, or animation is required.
const pixels = Array.from({ length: portrait.levels.length }, () => []);
portrait.rows.forEach((row, rowIndex) => {
  [...row].forEach((character, column) => {
    const level = portrait.levels.indexOf(character);
    if (!level) return;
    const x = 699 + column * 3;
    const y = 38 + rowIndex * 4.8;
    pixels[level].push(`M${x.toFixed(1)} ${y.toFixed(1)}h2.4v4.1h-2.4z`);
  });
});
const pixelPortrait = pixels.map((path, level) => path.length ? `<path fill="${palette.paper}" opacity="${[0, .19, .43, .72, 1][level]}" d="${path.join('')}"/>` : '').join('');

const nameSize = 82;
const nameOptions = { kerning: true, letterSpacing: -.01 };
const surnameX = 38 + fonts.sans.getAdvanceWidth('Hriday ', nameSize, nameOptions);
const name = lettering('sans', 'Hriday ', 38, 100, nameSize, palette.paper, nameOptions.letterSpacing)
  + lettering('sans', 'Vig.', surnameX, 100, nameSize, palette.acid, nameOptions.letterSpacing);
const idea = lettering('sans', 'Ideas, with', 40, 183, 50, palette.paper);
const followThrough = lettering('serif', 'follow-through.', 100, 274, 82, palette.red);
const portraitCaption = lettering('sans', 'A FEW PIXELS. A WHOLE PERSON.', 687, 287, 10, palette.muted, .035);

const defs = `
    <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M48 0H0V48" fill="none" stroke="${palette.paper}" stroke-width=".7" opacity=".055"/></pattern>
    <linearGradient id="rule"><stop stop-color="${palette.paper}" stop-opacity=".18"/><stop offset="1" stop-color="${palette.paper}" stop-opacity=".04"/></linearGradient>`;

const body = `
  <rect width="${width}" height="${height}" fill="url(#grid)"/>
  <path d="M40 24H920M40 312H920" stroke="url(#rule)" stroke-width=".7"/>
  <path d="M644 42V262" stroke="${palette.paper}" stroke-width=".6" opacity=".1"/>
  <path d="M678 54V30H702M895 30H919V54M919 240V264H895M702 264H678V240" fill="none" stroke="${palette.paper}" stroke-width=".7" opacity=".34"/>
  <path d="M900 49h5v5h-5zM910 64h3v3h-3zM689 245h4v4h-4z" fill="${palette.acid}"/>
  ${pixelPortrait}
  ${name}
  ${idea}
  ${followThrough}
  ${portraitCaption}`;

for (const box of bounds.slice(0, 4)) {
  assert.ok(box.x1 >= 32 && box.x2 <= 654, `Lettering outside horizontal safe area: ${box.text}`);
  assert.ok(box.y1 >= 36 && box.y2 <= height - 40, `Lettering outside vertical safe area: ${box.text}`);
}
assert.ok(bounds[2].y1 - Math.max(bounds[0].y2, bounds[1].y2) >= 24, 'Keep the name and subtitle on clearly separated lines.');
assert.ok(bounds[3].y1 - bounds[2].y2 >= 24, 'Keep the subtitle clear of the italic lettering.');
assert.ok(bounds[4].x2 <= 920 && bounds[4].y2 <= 290, 'Portrait caption must stay within its frame.');

const image = svgDocument({
  height,
  title: 'Hriday Vig. Ideas, with follow-through.',
  description: 'Hriday Vig beside his original pixel portrait, rebuilt as tonal vector cells with registration marks on a charcoal grid. Paper and acid Manrope lettering meets red italic Newsreader. All visible lettering is outlined and needs no external fonts.',
  defs,
  body,
});
assert.ok(Buffer.byteLength(image) < 100_000, 'The static header must remain below 100 KB.');
assert.ok(!/<(?:script|foreignObject|text|animate)\b/.test(image), 'Header must remain self-contained, outlined, and static.');
assert.doesNotMatch(image, /NaN|Infinity|undefined/, 'Every visible glyph must have valid coordinates.');

if (process.argv.includes('--check')) {
  assert.equal(await readFile(file, 'utf8'), image, 'Run node scripts/render-brand.mjs to refresh assets/header.svg.');
} else {
  await mkdir(new URL('../assets/', import.meta.url), { recursive: true });
  await writeFile(file, image);
}
console.log(JSON.stringify({ asset: 'assets/header.svg', width, height, bytes: Buffer.byteLength(image), outlined: true, static: true, bounds }, null, 2));
