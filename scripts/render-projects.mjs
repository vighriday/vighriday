import { mkdir, readFile, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import opentype from 'opentype.js';
import { palette, width, svgDocument } from '../src/theme.mjs';
import { serializePath } from '../src/lettering.mjs';

const height = 164;
const bytes = await readFile(new URL('../fonts/Manrope-Light.ttf', import.meta.url));
const font = opentype.parse(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));

function lettering(text, x, y, size, fill, tracking = 0) {
  const options = { kerning: true, letterSpacing: tracking };
  const bounds = font.getPath(text, x, y, size, options).getBoundingBox();
  assert.ok(bounds.x1 >= 38 && bounds.x2 <= 550, `Horizontal lettering bounds: ${text}`);
  assert.ok(bounds.y1 >= 23 && bounds.y2 <= 136, `Vertical lettering bounds: ${text}`);
  return font.getPaths(text, x, y, size, options)
    .map(glyph => `<path fill="${fill}" d="${serializePath(glyph)}"/>`)
    .join('');
}

function hexagon(cx, cy, radius) {
  const points = Array.from({ length: 6 }, (_, index) => {
    const angle = index * Math.PI / 3;
    return `${(cx + radius * Math.cos(angle)).toFixed(2)} ${(cy + radius * Math.sin(angle)).toFixed(2)}`;
  });
  return `M${points.join('L')}Z`;
}

function verisDiagram() {
  return `
    <g fill="${palette.black}" stroke="${palette.paper}" stroke-width=".85">
      <path d="M695 26H847V117H695Z" stroke-opacity=".15"/>
      <path d="M675 39H827V130H675Z" stroke-opacity=".28"/>
      <path d="M655 52H807V143H655Z" stroke-opacity=".62"/>
    </g>
    <g fill="none" stroke-width="1.25">
      <path d="M672 72H746M672 85H725M672 111H756M672 124H733" stroke="${palette.paper}" opacity=".23"/>
      <path d="M672 98H751" stroke="${palette.red}"/>
      <path d="M672 94L751 102" stroke="${palette.red}" opacity=".45"/>
      <path class="trace-intro" d="M774 85H864V98H893" stroke="${palette.acid}"/>
      <path d="M863 71V120" stroke="${palette.paper}" opacity=".15" stroke-dasharray="2 5"/>
    </g>
    <circle cx="774" cy="85" r="2.75" fill="${palette.acid}"/>
    <circle cx="893" cy="98" r="3.5" fill="${palette.acid}"/>
    <circle cx="893" cy="98" r="10" fill="none" stroke="${palette.acid}" stroke-width=".75" opacity=".23"/>`;
}

function hiveDiagram() {
  const cells = [
    [690, 58], [690, 110], [735, 32], [735, 84], [735, 136],
    [780, 58], [780, 110], [825, 32], [825, 84], [825, 136], [870, 58], [870, 110],
  ];
  return `
    <g transform="translate(117 12.6) scale(.85)">
    <g fill="none" stroke="${palette.paper}" stroke-width=".75">
      ${cells.map(([x, y]) => `<path d="${hexagon(x, y, 30)}" opacity="${x === 735 && y === 84 ? '.5' : '.14'}"/>`).join('')}
    </g>
    <path d="M690 110L735 84L780 110L825 84L870 58" fill="none" stroke="${palette.paper}" stroke-width="1.1" opacity=".38"/>
    <path class="trace-intro" d="M735 84L825 32" fill="none" stroke="${palette.red}" stroke-width="1.6"/>
    <circle cx="735" cy="84" r="4" fill="${palette.acid}"/>
    <circle cx="690" cy="110" r="2.5" fill="${palette.paper}" opacity=".6"/>
    <circle cx="780" cy="110" r="2.5" fill="${palette.paper}" opacity=".6"/>
    <circle cx="825" cy="84" r="2.5" fill="${palette.paper}" opacity=".6"/>
    <circle cx="870" cy="58" r="2.5" fill="${palette.paper}" opacity=".6"/>
    <circle cx="825" cy="32" r="3.5" fill="${palette.red}"/>
    <circle cx="825" cy="32" r="10" fill="none" stroke="${palette.red}" stroke-width=".75" opacity=".28"/>
    </g>`;
}

function offsideDiagram() {
  return `
    <g fill="none" stroke="${palette.paper}" stroke-width=".8" opacity=".26">
      <path d="M639 33H899V135H639ZM769 33V135M639 60H672V108H639M899 60H866V108H899"/>
      <circle cx="769" cy="84" r="24"/>
      <path d="M632 72H639M632 72V96H639M899 72H906V96H899"/>
    </g>
    <circle cx="769" cy="84" r="1.6" fill="${palette.paper}" opacity=".45"/>
    <path class="trace-intro" d="M661 115C710 114 734 67 814 65" fill="none" stroke="${palette.acid}" stroke-width="1.3"/>
    <path d="M814 29V139" stroke="${palette.red}" stroke-width="1.25"/>
    <path d="M806 29H822M806 139H822" stroke="${palette.red}" stroke-width=".8" opacity=".6"/>
    <path d="M723 98L814 65L866 47" fill="none" stroke="${palette.paper}" stroke-width=".75" opacity=".45" stroke-dasharray="3 5"/>
    <circle cx="661" cy="115" r="3" fill="${palette.acid}"/>
    <circle cx="723" cy="98" r="3" fill="${palette.acid}"/>
    <circle cx="814" cy="65" r="4" fill="${palette.red}"/>
    <circle cx="814" cy="65" r="11" fill="none" stroke="${palette.red}" stroke-width=".75" opacity=".25"/>
    <circle cx="866" cy="47" r="2.5" fill="${palette.paper}" opacity=".65"/>`;
}

const projects = [
  {
    id: 'veris', index: '01.1 /', name: 'Veris', size: 92,
    diagram: verisDiagram,
    description: 'An original editorial banner for Veris. Three offset evidence sheets carry red changed lines, with an acid line connecting an observed change to its evidence.',
  },
  {
    id: 'hive', index: '01.2 /', name: 'HIVE', size: 92,
    diagram: hiveDiagram,
    description: 'An original editorial banner for HIVE. A quiet honeycomb holds a connected network; one red connection emerges between the cells.',
  },
  {
    id: 'offside', index: '01.3 /', name: 'OFFSIDE', size: 78,
    diagram: offsideDiagram,
    description: 'An original editorial banner for OFFSIDE. A football pitch, an acid movement path, and a single red decision line form a diagram of evidence in context.',
  },
];

await mkdir(new URL('../assets/', import.meta.url), { recursive: true });
for (const project of projects) {
  const body = `
    <path d="M116 31H550M40 153H920M585 31V135" fill="none" stroke="${palette.paper}" stroke-width=".7" opacity=".12"/>
    ${lettering(project.index, 40, 39, 16, palette.muted, .03)}
    ${lettering(project.name, 38, 131, project.size, palette.paper, -.04)}
    ${project.diagram()}`;
  const defs = `<style>
    .trace-intro{stroke-dasharray:320;stroke-dashoffset:0;animation:trace-in 2.2s ease-out 1}
    @keyframes trace-in{from{stroke-dashoffset:320}to{stroke-dashoffset:0}}
    @media(prefers-reduced-motion:reduce){.trace-intro{animation:none}}
  </style>`;
  const image = svgDocument({ height, title: project.name, description: project.description, defs, body });
  assert.ok(Buffer.byteLength(image) < 100_000, `Project banner must remain below 100 KB: ${project.id}`);
  assert.ok(!/<(?:script|foreignObject|text|animate)\b/.test(image), 'Project banners must remain self-contained and outlined, with only a brief CSS introduction.');
  assert.doesNotMatch(image, /NaN|Infinity|undefined/, 'Every project glyph must have valid coordinates.');
  const file = new URL(`../assets/project-${project.id}.svg`, import.meta.url);
  if (process.argv.includes('--check')) {
    assert.equal(await readFile(file, 'utf8'), image, `Run node scripts/render-projects.mjs to refresh assets/project-${project.id}.svg.`);
  } else {
    await writeFile(file, image);
  }
  console.log(JSON.stringify({ asset: `assets/project-${project.id}.svg`, width, height, bytes: Buffer.byteLength(image), outlined: true, introSeconds: 2.2 }));
}
