import { mkdir, readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import opentype from 'opentype.js';
import { palette, width, svgDocument } from '../src/theme.mjs';

const height = 304;
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

const bounds = [];
function lettering(font, text, x, y, size, fill, letterSpacing = 0) {
  const options = { kerning: true, letterSpacing };
  const path = fonts[font].getPath(text, x, y, size, options);
  bounds.push({ text, ...path.getBoundingBox() });
  // Preserve glyph contours independently. A merged path can change how open
  // contours fill in SVG renderers; v2 also requires explicit SVG options.
  return fonts[font].getPaths(text, x, y, size, options)
    .map(glyph => `<path fill="${fill}" d="${glyph.toPathData({ decimalPlaces: 2, flipY: false, optimize: false })}"/>`)
    .join('');
}

function arc(cx, cy, rx, ry, rotation, start, end) {
  const rotate = rotation * Math.PI / 180;
  return Array.from({ length: 65 }, (_, index) => {
    const angle = (start + (end - start) * index / 64) * Math.PI / 180;
    const x = rx * Math.cos(angle);
    const y = ry * Math.sin(angle);
    return `${index ? 'L' : 'M'}${(cx + x * Math.cos(rotate) - y * Math.sin(rotate)).toFixed(2)} ${(cy + x * Math.sin(rotate) + y * Math.cos(rotate)).toFixed(2)}`;
  }).join(' ');
}

const nameSize = 82;
const nameOptions = { kerning: true, letterSpacing: -.055 };
const surnameX = 38 + fonts.sans.getAdvanceWidth('Hriday ', nameSize, nameOptions);
const name = lettering('sans', 'Hriday ', 38, 106, nameSize, palette.paper, -.055)
  + lettering('sans', 'Vig.', surnameX, 106, nameSize, palette.acid, -.055);
const idea = lettering('sans', 'Ideas, with', 40, 177, 50, palette.paper, -.045);
const followThrough = lettering('serif', 'follow-through.', 119, 252, 82, palette.red, -.027);

const defs = `
    <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse"><path d="M48 0H0V48" fill="none" stroke="${palette.paper}" stroke-width=".7" opacity=".055"/></pattern>
    <linearGradient id="trajectory"><stop stop-color="${palette.paper}" stop-opacity="0"/><stop offset=".45" stop-color="${palette.paper}" stop-opacity=".16"/><stop offset="1" stop-color="${palette.acid}" stop-opacity=".75"/></linearGradient>
    <linearGradient id="rule"><stop stop-color="${palette.paper}" stop-opacity=".18"/><stop offset="1" stop-color="${palette.paper}" stop-opacity=".04"/></linearGradient>`;

const body = `
  <rect width="${width}" height="${height}" fill="url(#grid)"/>
  <path d="M40 24H920M40 280H920" stroke="url(#rule)" stroke-width=".7"/>
  <g fill="none" stroke-width=".85">
    <path d="${arc(795, 154, 123, 53, -24, -191, 132)}" stroke="${palette.paper}" opacity=".27"/>
    <path d="${arc(799, 147, 87, 100, 31, -140, 161)}" stroke="${palette.paper}" opacity=".15"/>
    <path d="M624 217C669 228 707 204 755 172S848 81 899 98" stroke="url(#trajectory)"/>
    <path d="M899 84V90M899 106V112M885 98H891M907 98H913" stroke="${palette.acid}" stroke-width=".65" opacity=".28"/>
    <path d="M677 52V250" stroke="${palette.paper}" stroke-width=".6" opacity=".07"/>
  </g>
  <circle cx="899" cy="98" r="3.2" fill="${palette.acid}"/>
  <circle cx="899" cy="98" r="10" fill="none" stroke="${palette.acid}" stroke-width=".7" opacity=".18"/>
  ${name}
  ${idea}
  ${followThrough}`;

for (const box of bounds) {
  assert.ok(box.x1 >= 32 && box.x2 <= 654, `Lettering outside horizontal safe area: ${box.text}`);
  assert.ok(box.y1 >= 36 && box.y2 <= 272, `Lettering outside vertical safe area: ${box.text}`);
}

const image = svgDocument({
  height,
  title: 'Hriday Vig. Ideas, with follow-through.',
  description: 'A static editorial profile header. Thin paper and acid Manrope lettering meets red italic Newsreader on a charcoal grid, alongside open orbital paths. All visible lettering is outlined and needs no external fonts.',
  defs,
  body,
});
assert.ok(Buffer.byteLength(image) < 100_000, 'The static header must remain below 100 KB.');
assert.ok(!/<(?:script|foreignObject|text|animate)\b/.test(image), 'Header must remain self-contained, outlined, and static.');

if (process.argv.includes('--check')) {
  assert.equal(await readFile(file, 'utf8'), image, 'Run node scripts/render-brand.mjs to refresh assets/header.svg.');
} else {
  await mkdir(new URL('../assets/', import.meta.url), { recursive: true });
  await writeFile(file, image);
}
console.log(JSON.stringify({ asset: 'assets/header.svg', width, height, bytes: Buffer.byteLength(image), outlined: true, static: true, bounds }, null, 2));
