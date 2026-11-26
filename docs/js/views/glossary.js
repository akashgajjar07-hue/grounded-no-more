/**
 * Glossary (v2.1, PAGE-3). Route: #/glossary · #/glossary?term=<key> scrolls to and highlights one entry (the term
 * tooltips' "Glossary" link uses it) · #/glossary?q=<text> pre-fills the search.
 * Data: none. Every entry comes from lib/glossary.js glossaryEntries() ({key, expert, simple, definition, example, why,
 * category, aliases}), grouped by GLOSSARY_CATEGORIES. Simple mode leads with the plain wording (expert term in grey
 * brackets); Expert mode leads with the expert term.
 */
import { h, icon, pageHead, intro3 } from '../ui.js';
import { glossaryEntries, glossaryEntry, GLOSSARY_CATEGORIES } from '../lib/glossary.js';
import { isSimple, byMode } from '../lib/mode.js';
import { assetURL } from '../data.js';

export const data = [];

function ensureCSS(path) {
  const existing = document.querySelector(`link[data-view-css="${path}"]`);
  if (existing) return existing._ready || Promise.resolve();
  const link = h('link', { rel: 'stylesheet', href: assetURL(path), dataset: { viewCss: path } });
  link._ready = new Promise((res) => { link.onload = res; link.onerror = res; });
  document.head.append(link);
  return link._ready;
}

const cap1 = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const slug = (c) => `gl-cat-${c.toLowerCase().replace(/[^a-z]+/g, '-')}`;
const norm = (s) => String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '');

let view = null; // {el, highlight(key)} for onParams

export async function render(el, ctx) {
  await ensureCSS('css/views/glossary.css');
  const S = isSimple();
  const entries = glossaryEntries({ sort: S ? 'simple' : 'expert' });
  const cats = GLOSSARY_CATEGORIES.filter((c) => entries.some((e) => e.category === c));

  el.append(
    pageHead({
      eyebrow: 'Project', title: 'Glossary',
      lede: byMode(`Plain meanings for the ${entries.length} planning words used on this site.`, `Definitions for the ${entries.length} planning terms used on this site, with the plain wording Simple mode shows.`),
    }),
    intro3({
      what: byMode('Every planning word on this site, with a plain meaning, an example and why it matters.', 'Every domain term on the site: expert term, plain wording, definition, example and why it matters.'),
      why: byMode('Aviation planning uses a lot of short codes and jargon. A shared meaning keeps the numbers honest.', 'Terms like fill rate, EBO and TAT drive the numbers; a shared definition keeps comparisons honest.'),
      action: byMode('Search for a word, read it, then go back to the page you came from.', 'Search a term or jump to a group; the tooltip on any underlined term links here.'),
    }),
  );

  // ------------------------------------------------------------------ search + category jumps
  const input = h('input', {
    type: 'search', class: 'input gl-search-input', id: 'gl-search', placeholder: byMode('Search, e.g. repair time', 'Search, e.g. TAT or fill rate'),
    autocomplete: 'off', spellcheck: 'false', 'aria-controls': 'gl-list', 'aria-describedby': 'gl-count',
  });
  const count = h('p', { class: 'gl-count', id: 'gl-count', role: 'status', 'aria-live': 'polite' });
  const jumps = h('nav', { class: 'gl-jumps', 'aria-label': 'Glossary groups' }, cats.map((c) => h('a', { class: 'chip gl-jump', href: `#${slug(c)}`, dataset: { cat: c }, onclick: (ev) => { ev.preventDefault(); document.getElementById(slug(c))?.scrollIntoView({ block: 'start', behavior: 'smooth' }); } }, c)));
  el.append(h('section', { class: 'card gl-tools' },
    h('label', { class: 'gl-search-label', for: 'gl-search' }, icon('filter'), byMode('Find a word', 'Find a term')),
    input, count, jumps));

  // ------------------------------------------------------------------ entries, grouped
  const list = h('div', { class: 'gl-list', id: 'gl-list' });
  const empty = h('p', { class: 'gl-empty', hidden: true }, byMode('No word matches that search. Try a shorter word.', 'No term matches that search.'));
  const items = [];
  cats.forEach((c) => {
    const group = entries.filter((e) => e.category === c);
    const sec = h('section', { class: 'card gl-group', id: slug(c), 'aria-labelledby': `${slug(c)}-h` },
      h('h2', { class: 'gl-group-title', id: `${slug(c)}-h` }, c, h('span', { class: 'gl-group-n' }, String(group.length))));
    const dl = h('div', { class: 'gl-entries' });
    group.forEach((e) => {
      const lead = S ? cap1(e.simple) : e.expert;
      let other = S ? e.expert : e.simple;
      // "Part number (part number (PN))" → "Part number (PN)"
      if (other.toLowerCase().startsWith(lead.toLowerCase()) && other.length > lead.length) other = other.slice(lead.length).trim().replace(/^\((.*)\)$/, '$1');
      const same = lead.toLowerCase() === other.toLowerCase();
      const art = h('article', { class: 'gl-entry', id: `g-${e.key}`, tabindex: '-1', dataset: { term: e.key } },
        h('h3', { class: 'gl-term' }, lead, same ? null : h('small', { class: 'term-expert gl-other' }, ` (${other})`)),
        h('p', { class: 'gl-def' }, e.definition),
        h('p', { class: 'gl-ex' }, h('span', { class: 'gl-k' }, 'Example'), e.example),
        h('p', { class: 'gl-why' }, h('span', { class: 'gl-k' }, 'Why it matters'), e.why),
        e.aliases?.length && !S ? h('p', { class: 'gl-alias' }, `Also: ${e.aliases.join(', ')}`) : null);
      dl.append(art);
      items.push({ e, art, sec, text: norm([e.key, e.expert, e.simple, e.definition, e.example, e.why, ...(e.aliases || [])].join(' ')) });
    });
    sec.append(dl);
    list.append(sec);
  });
  el.append(list, empty);

  function filter(q) {
    const words = norm(q).split(/\s+/).filter(Boolean);
    let n = 0;
    items.forEach((it) => { const ok = words.every((w) => it.text.includes(w)); it.art.hidden = !ok; if (ok) n += 1; });
    list.querySelectorAll('.gl-group').forEach((sec) => { sec.hidden = ![...sec.querySelectorAll('.gl-entry')].some((a) => !a.hidden); });
    jumps.querySelectorAll('.gl-jump').forEach((a) => { a.hidden = !!document.getElementById(slug(a.dataset.cat))?.hidden; });
    empty.hidden = n > 0;
    count.textContent = words.length ? `${n} of ${items.length} ${byMode('words', 'terms')} match` : `${items.length} ${byMode('words', 'terms')} in ${cats.length} groups`;
  }
  input.addEventListener('input', () => { filter(input.value); ctx.setParams({ q: input.value.trim() || '' }); });
  input.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && input.value) { ev.stopPropagation(); input.value = ''; filter(''); ctx.setParams({ q: '' }); } });

  function highlight(key) {
    list.querySelectorAll('.gl-entry.is-target').forEach((a) => a.classList.remove('is-target'));
    const e = key ? glossaryEntry(key) : null;
    if (!e) return false;
    const art = document.getElementById(`g-${e.key}`);
    if (!art) return false;
    if (art.hidden) { input.value = ''; filter(''); }
    art.classList.add('is-target');
    requestAnimationFrame(() => { art.scrollIntoView({ block: 'center' }); art.focus({ preventScroll: true }); });
    return true;
  }

  input.value = ctx.params.q || '';
  filter(input.value);
  highlight(ctx.params.term);
  view = { highlight, el };
  return () => { view = null; };
}

/** Same-route query change (a tooltip "Glossary" link while already here): highlight without a re-render. */
export function onParams(params) {
  if (!view) return false;
  if (params.term) view.highlight(params.term);
  return true;
}
