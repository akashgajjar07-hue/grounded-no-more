// Build every original SVG illustration into docs/assets/svg/ (favicon into docs/assets/).
//   node docs/assets/svg/src/build.mjs
// Output is deterministic, so regenerated files only diff when the generator changes.
import { writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, '..');
const ctx = {};
const write = (name, svg) => {
  if (!svg) return;
  writeFileSync(join(out, name), svg);
  console.log(`wrote ${name} (${(svg.length / 1024).toFixed(1)} kB)`);
};

const top = await import('./aircraft-top.mjs');
ctx.top = top.build();
write('blueprint-aircraft-top.svg', ctx.top);
for (const m of ['aircraft-elevations', 'aircraft-plan', 'exploded', 'misc']) {
  const mod = await import(`./${m}.mjs`);
  for (const [name, svg] of Object.entries(mod.files(ctx))) write(name, svg);
}
