import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import opentype from 'opentype.js';
import { serializePath } from '../src/lettering.mjs';

test('near-integer floating point coordinates remain valid SVG numbers', () => {
  assert.equal(serializePath({ commands: [
    { type: 'M', x: 243.00000000000006, y: 119.67999999999999 },
    { type: 'L', x: -.00000000000001, y: 82.00000000000001 },
    { type: 'Z' },
  ] }), 'M243 119.68L0 82Z');
});

test('quadratic and cubic contours preserve their control points and closure', () => {
  assert.equal(serializePath({ commands: [
    { type: 'M', x: 1, y: 2 },
    { type: 'Q', x1: 3, y1: 4, x: 5, y: 6 },
    { type: 'C', x1: 7, y1: 8, x2: 9, y2: 10, x: 11, y: 12 },
    { type: 'Z' },
  ] }), 'M1 2Q3 4 5 6C7 8 9 10 11 12Z');
});

test('invalid and unsupported outlines fail instead of publishing missing glyphs', () => {
  for (const value of [NaN, Infinity, undefined]) {
    assert.throws(() => serializePath({ commands: [{ type: 'M', x: value, y: 0 }] }), /Invalid outline coordinate/);
  }
  assert.throws(() => serializePath({ commands: [{ type: 'A' }] }), /Unsupported outline command/);
});

test('the actual header fonts preserve every visible glyph, including the missing y', async () => {
  for (const [file, text, left, baseline, size, spacing] of [
    ['Manrope-Light.ttf', 'Hriday Vig.', 38, 100, 82, -.01],
    ['Manrope-Light.ttf', 'Ideas, with', 40, 183, 50, 0],
    ['Newsreader-LightItalic.ttf', 'follow-through.', 100, 274, 82, 0],
    // These published positions previously produced invalid s/g coordinates.
    ['Manrope-Light.ttf', 'Ideas, with', 40, 177, 50, -.045],
    ['Newsreader-LightItalic.ttf', 'follow-through.', 119, 252, 82, -.027],
  ]) {
    const bytes = await readFile(new URL(`../fonts/${file}`, import.meta.url));
    const font = opentype.parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    const paths = font.getPaths(text, left, baseline, size, { kerning: true, letterSpacing: spacing });
    assert.equal(paths.length, text.length);
    for (const [index, path] of paths.entries()) {
      const data = serializePath(path);
      assert.doesNotMatch(data, /NaN|Infinity|undefined/);
      if (text[index] !== ' ') assert.ok(data.length > 0, `Missing glyph: ${text[index]}`);
    }
  }
});
