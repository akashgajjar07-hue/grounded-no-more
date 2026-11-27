/**
 * The Planner Behind the Project (#/planner) · a first-person essay rendered from docs/content/planner.md (written by
 * the author) with the safe Markdown renderer in ./about/md.js. The page reads the same in Simple and Expert (a note under the header says so). A pull quote is lifted from the essay itself (no invented words). Links: About, Results, and the project documents
 * on GitHub (methodology, limitations, decision log, model card, validation report). Data: none.
 */
import { h, icon, intro3, stateBlock } from '../ui.js';
import { assetURL } from '../data.js';
import { renderMarkdown, fetchMarkdown } from './about/md.js';
import { aboutLink } from './about.js';

export const data = [];

const REPO = 'https://github.com/akashgajjar07-hue/grounded-no-more';
const DOCS = [
  ['Methodology', 'METHODOLOGY.md', 'How the simulation, forecasts and plans work'],
  ['Limitations', 'LIMITATIONS.md', 'What the model leaves out, and how much it matters'],
  ['Decision log', 'docs/DECISIONS.md', 'Every modelling choice, with the reason'],
  ['Model card', 'MODEL_CARD.md', 'What the model is for, and what it is not for'],
  ['Validation report', 'reports/VALIDATION_REPORT.md', 'How the results were checked'],
];
/** The pull quote: the first essay sentence that matches, so the words are always the author's. */
const QUOTE_RE = /[^.]*a missing part can mean[^.]*\./i;

function ensureCSS() {
  if (document.querySelector('link[data-view-css="planner"]')) return;
  document.head.append(h('link', { rel: 'stylesheet', href: assetURL('css/views/planner.css'), dataset: { viewCss: 'planner' } }));
}

export async function render(el) {
  ensureCSS();
  // wait for the view stylesheet before building the DOM: an unstyled first paint shifts the layout (CLS)
  await new Promise((res) => { const l = document.querySelector('link[data-view-css="planner"]'); if (!l || l.sheet) return res(); l.addEventListener('load', res, { once: true }); l.addEventListener('error', res, { once: true }); setTimeout(res, 3000); });
  let src = null;
  try { src = await fetchMarkdown(assetURL('content/planner.md')); } catch (e) { console.warn('planner.md unavailable', e); }

  const md = src ? renderMarkdown(src, { headingBase: 1, dropTitle: true, link: aboutLink, idPrefix: 'pl-' }) : { title: null, nodes: [] };
  // the closing "Written with AI…" line becomes the signature note
  let sig = null;
  const nodes = md.nodes.filter((n) => {
    const t = n.textContent.trim();
    if (n.tagName === 'P' && /^written with ai/i.test(t)) { sig = n; return false; }
    return true;
  });
  const quote = src ? (src.replace(/\*/g, '').match(QUOTE_RE)?.[0] || '').trim() : '';
  // the lede: the essay's opening paragraph sits larger, before the first section
  const firstP = nodes.find((n) => n.tagName === 'P');
  firstP?.classList.add('pl-lede');

  const header = h('header', { class: 'pl-head' },
    h('div', { class: 'pl-eyebrow' }, h('span', {}, 'Project'), h('span', { class: 'pl-dot', 'aria-hidden': 'true' }, '·'), h('span', {}, 'In my own words')),
    h('h1', { class: 'pl-title' }, md.title || 'The Planner Behind the Project'),
    h('p', { class: 'pl-byline' }, 'By Akash Gajjar'),
    h('p', { class: 'mode-same-note pl-mode-note', dataset: { role: 'mode-same' } }, 'This page reads the same in Simple and Expert.'));
  el.append(header);
  el.append(intro3({
    what: 'The person behind this project, why it exists, and what it taught.',
    why: 'You can judge the work better when you know the choices and the mistakes behind it.',
    action: 'Read the essay, then check its claims on the Results and About pages.',
  }));

  if (!src) { el.append(stateBlock('error', 'The essay could not load (content/planner.md).')); return null; }

  const body = h('div', { class: 'pl-body' });
  // the pull quote goes before the third section heading (after "Why aviation"), or after the lede
  const heads = nodes.filter((n) => /^H[2-6]$/.test(n.tagName));
  const anchor = heads[1] || null;
  nodes.forEach((n) => {
    if (n === anchor && quote) body.append(pullQuote(quote));
    body.append(n);
  });
  if (!anchor && quote) firstP?.after(pullQuote(quote));
  if (sig) { sig.classList.add('pl-sig'); body.append(h('hr', { class: 'pl-rule', 'aria-hidden': 'true' }), sig); }

  el.append(h('article', { class: 'pl-essay', dataset: { role: 'planner-essay' }, 'aria-labelledby': 'pl-title' }, body));
  el.querySelector('.pl-title').id = 'pl-title';

  el.append(h('section', { class: 'pl-next', 'aria-label': 'Read next' },
    h('div', { class: 'pl-next-col' },
      h('h2', { class: 'pl-next-h' }, 'Read next'),
      h('ul', { class: 'pl-links list-reset' },
        h('li', {}, h('a', { href: '#/about', dataset: { role: 'link-about' } }, icon('info'), h('span', {}, h('b', {}, 'About this project'), h('small', {}, 'Skills, tools, downloads, and how it would work for real')))),
        h('li', {}, h('a', { href: '#/mission?section=results' }, icon('aircraft'), h('span', {}, h('b', {}, 'The results'), h('small', {}, 'The numbers, next to their limits')))),
        h('li', {}, h('a', { href: '#/about?section=real-data' }, icon('book'), h('span', {}, h('b', {}, 'What real data would make this useful'), h('small', {}, 'The records a real airline would need')))))),
    h('div', { class: 'pl-next-col' },
      h('h2', { class: 'pl-next-h' }, 'Project documents ', h('span', { class: 'pl-gh' }, 'on GitHub')),
      h('ul', { class: 'pl-links list-reset', dataset: { role: 'project-docs' } }, DOCS.map(([t, path, d]) => h('li', {},
        h('a', { href: `${REPO}/blob/main/${path}`, target: '_blank', rel: 'noopener noreferrer' }, icon('book'), h('span', {}, h('b', {}, t), h('small', {}, d)))))))));
  return null;
}

function pullQuote(text) {
  return h('figure', { class: 'pl-quote', dataset: { role: 'pull-quote' } },
    h('blockquote', {}, h('p', {}, text)),
    h('figcaption', {}, '— from the essay'));
}
