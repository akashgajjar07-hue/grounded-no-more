/**
 * Glossary · STUB created by the SHELL agent (v2.1). A page agent owns this file from wave 2 and replaces it.
 * Route: #/glossary (optional ?term=<key> to highlight one entry). Data: none — entries come from
 * lib/glossary.js glossaryEntries() ({key, expert, simple, definition, example, why, category, aliases}).
 */
import { h, pageHead, card, intro3 } from '../ui.js';
import { glossaryEntries, GLOSSARY_CATEGORIES } from '../lib/glossary.js';
import { getMode } from '../lib/mode.js';

export const data = [];

export async function render(el, ctx) {
  const simple = getMode() === 'simple';
  const entries = glossaryEntries();
  el.append(
    pageHead({ eyebrow: 'Project', title: 'Glossary', lede: 'Plain-English meanings for the planning terms used on this site.' }),
    intro3({ what: 'Every planning word on this site, in plain English.', why: 'Aviation planning has a lot of jargon.', action: 'Look up a word, then go back to the page you were reading.' }),
    ...GLOSSARY_CATEGORIES.map((cat) => card({ title: cat, body: h('dl', { class: 'stack' }, entries.filter((e) => e.category === cat).flatMap((e) => [
      h('dt', { id: `g-${e.key}`, dataset: { term: e.key } }, h('strong', {}, simple ? e.simple : e.expert), ' ', h('small', { class: 'term-expert' }, `(${simple ? e.expert : e.simple})`)),
      h('dd', {}, e.definition, ' ', h('span', { class: 'muted' }, `Example: ${e.example} Why it matters: ${e.why}`)),
    ])) })),
  );
  if (ctx.params.term) document.getElementById(`g-${ctx.params.term}`)?.scrollIntoView({ block: 'center' });
}
