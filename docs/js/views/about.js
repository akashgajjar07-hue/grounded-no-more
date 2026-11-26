/**
 * About · the author, the tools, the downloads, an honest note on how it was built, and (v2.1) how the method would
 * be used for real: E2 "How this transfers to an MRO" (docs/content/mro.md), E3 "What real data would make this
 * useful" (docs/content/real_data.md) and "Next experiments" (docs/content/next_experiments.md), rendered with the
 * small safe Markdown renderer in ./about/md.js. Deep links: #/about?section=mro | real-data | next-experiments.
 * The "Why I made these planning decisions" section holds the questions only: the answers are the author's to write.
 * Data: none (static copy + the three content files).
 */
import { h, pageHead, card, icon, intro3, stateBlock } from '../ui.js';
import { assetURL } from '../data.js';
import { byMode } from '../lib/mode.js';
import { isPolicyCode } from '../lib/names.js';
import { renderMarkdown, fetchMarkdown } from './about/md.js';

export const data = [];

const AUTHOR = {
  name: 'Akash Gajjar',
  degree: 'MSc Supply Chain Management, University of Liverpool (2025)',
  experience: 'Retail operations and inventory experience at Primark and Uniqlo',
  github: 'https://github.com/akashgajjar07-hue',
};
const REPO = 'https://github.com/akashgajjar07-hue/grounded-no-more';

/** Skills: [heading, [[simple wording, expert wording], …]] */
const SKILLS = [
  ['Planning methods', [
    ['Forecasting parts that are needed only now and then', 'Intermittent-demand forecasting (Croston, SBA, TSB, bootstrap)'],
    ['Sizing the pool of repairable spares', 'Rotable float sizing (Palm’s theorem, METRIC-inspired)'],
    ['Placing spares across the hub and outstations', 'Multi-echelon stock positioning'],
    ['Weighing money against aircraft readiness', 'Capital-vs-readiness trade-off (greedy marginal allocation)'],
    ['Emergency ways to get a part, and what they cost', 'AOG sourcing options and exposure'],
  ]],
  ['Analysis and testing', [
    ['A computer model of a fictional airline network', 'Discrete-event simulation of a fictional airline network'],
    ['Fair tests: every plan faces the same events', 'Paired-seed evaluation with a frozen holdout'],
    ['A stated target for the starting point', 'Calibration against stated targets'],
    ['A list of every assumption and where it came from', 'Assumption register with provenance tags'],
  ]],
  ['Tools', [
    ['Python (pandas, NumPy)', 'Python (pandas, NumPy)'],
    ['DuckDB and SQL', 'DuckDB / SQL'],
    ['D3 for the interactive charts', 'D3 for the interactive charts'],
    ['Playwright browser tests', 'Playwright browser tests'],
    ['An Excel planner workbook', 'Excel planner workbook'],
  ]],
];

/** The six unanswered questions ([simple, expert] where the wording differs). Wording follows the v2.1 forbidden-word list. */
const QUESTIONS = [
  ['How to handle parts needed only now and then', 'Intermittent demand handling'],
  'Why maximum local stock isn’t the best plan',
  ['How repair time drives the pool of spares', 'How TAT drives float'],
  'Why point accuracy isn’t enough',
  ['How the planner balances readiness and money', 'How the optimiser balances readiness and capital'],
  'What data I’d request from a real airline',
];

/** The three content pages rendered on About, in order. */
const CONTENT = [
  { id: 'mro', file: 'content/mro.md', kicker: 'Using it for real', fallback: 'How this transfers to an MRO' },
  { id: 'real-data', file: 'content/real_data.md', kicker: 'Using it for real', fallback: 'What real data would make this useful' },
  { id: 'next-experiments', file: 'content/next_experiments.md', kicker: 'Proposed, not run', fallback: 'Next experiments' },
];
const LINKS = { 'mro.md': 'mro', 'real_data.md': 'real-data', 'next_experiments.md': 'next-experiments' };
/** Content links between the .md files become on-page section links; study/ and repo files go to GitHub. */
export function aboutLink(href) {
  const file = String(href).split('#')[0].split('/').pop();
  if (LINKS[file]) return `#/about?section=${LINKS[file]}`;
  if (/^https?:|^#|^mailto:/.test(href)) return href;
  return `${REPO}/blob/main/${String(href).replace(/^(\.\.\/)+|^\.\//g, '')}`;
}

/** Inline `P0`-style policy codes in the content: shown only in Expert mode (with their brackets). */
function codesExpertOnly(root) {
  root.querySelectorAll('code.md-code').forEach((c) => {
    if (!isPolicyCode(c.textContent.trim())) return;
    const prev = c.previousSibling, next = c.nextSibling;
    const wrap = h('span', { class: 'expert-only' });
    if (prev?.nodeType === 3 && /\($/.test(prev.nodeValue) && next?.nodeType === 3 && /^\)/.test(next.nodeValue)) {
      prev.nodeValue = prev.nodeValue.replace(/\s*\($/, ' ');
      next.nodeValue = next.nodeValue.slice(1);
      c.replaceWith(wrap); wrap.append('(', c, ')');
    } else { c.replaceWith(wrap); wrap.append(c); }
    c.classList.add('mono-tag');
  });
}

function scrollToSection(id, user = true) {
  // instant jump (smooth scrolling fought later clicks while still moving; motion stays transform/opacity only).
  // A user action (onParams) jumps synchronously and moves focus there; after a render, wait for the router's scroll reset.
  const go = () => { const t = document.getElementById(`ab-${id}`); if (!t) return; t.scrollIntoView({ block: 'start' }); if (user) t.focus?.({ preventScroll: true }); };
  if (user) go(); else requestAnimationFrame(() => setTimeout(go, 30));
}

/** #/about?section=… on the same route: scroll, no re-render. */
export function onParams(params) {
  if (params.section) scrollToSection(params.section);
  else window.scrollTo({ top: 0 });
  return true;
}

export async function render(el, ctx) {
  if (!document.querySelector('link[data-view-css="about"]')) {
    document.head.append(h('link', { rel: 'stylesheet', href: new URL('../../css/views/about.css', import.meta.url).href, dataset: { viewCss: 'about' } }));
  }
  el.append(pageHead({
    num: null, eyebrow: 'About',
    title: 'About this project',
    lede: 'GROUNDED NO MORE is an independent aviation spare-parts planning simulation, built as a portfolio project. Falcon Hub Airways and every part number in it are fictional.',
  }));
  el.append(intro3({
    what: 'Who built this project, with which tools, and how it could be used for real.',
    why: 'A model is only useful if you know its limits and what it would need next.',
    action: 'Read how it carries over to a repair shop, and which real records it would need first.',
  }));

  const links = h('div', { class: 'ab-links' },
    h('a', { class: 'btn btn--sm', href: AUTHOR.github, target: '_blank', rel: 'noopener noreferrer' }, 'GitHub', icon('chevron-right')),
    h('a', { class: 'btn btn--sm', href: 'downloads/grounded_no_more_planner_workbook.xlsx', download: '' }, icon('download'), 'Excel planner workbook'),
    h('a', { class: 'btn btn--sm', href: 'downloads/case_study_deck.pdf', download: '' }, icon('download'), 'Case-study deck (PDF)'));

  el.append(h('div', { class: 'grid-12' },
    card({
      cls: 'span-7 md-span-12 ab-author', kicker: 'Author', title: AUTHOR.name,
      body: h('div', { class: 'ab-body' },
        h('ul', { class: 'ab-facts list-reset' },
          h('li', {}, icon('book'), h('span', {}, AUTHOR.degree)),
          h('li', {}, icon('warehouse'), h('span', {}, AUTHOR.experience))),
        h('h4', { class: 'ab-h' }, 'Role in the project'),
        h('p', {}, 'I defined the planning problem, the fictional airline network and the question each page answers. I chose the forecasting, stock and planning methods. I set the test rules: tuning runs, fresh test runs kept apart, and stated targets. I reviewed every result and design decision.'),
        links,
        h('p', { class: 'ab-more t-14' }, 'More: ', h('a', { href: '#/planner' }, 'The Planner Behind the Project'), ' · ', h('a', { href: '#/mission?section=results' }, 'Results'), ' · ', h('a', { href: '#/glossary' }, 'Glossary'))),
    }),
    card({
      cls: 'span-5 md-span-12', kicker: 'How it was built', title: 'A transparent note',
      body: h('div', { class: 'ab-body' },
        h('p', { class: 'ab-note', dataset: { role: 'ai-note' } }, 'Built with AI-assisted development; analysis, decisions and validation reviewed by the author.'),
        h('p', { class: 'muted' }, 'The models run offline. This site loads results exported from a simulated planning snapshot. It is not an airline system, and not an approved maintenance, airworthiness or dispatch tool.')),
    })));

  el.append(h('div', { class: 'grid-12 mt-3' },
    card({
      cls: 'span-12', kicker: 'Skills and tools', title: 'What the project exercises',
      body: h('div', { class: 'ab-skills' }, SKILLS.map(([head, items]) => h('div', { class: 'ab-skill' }, h('h4', { class: 'ab-h' }, head), h('ul', { class: 'ab-list' }, items.map(([s, x]) => h('li', {}, byMode(s, x))))))),
    })));

  // E2 / E3 / next experiments: the AUTHOR's content files, rendered safely
  const docs = await Promise.all(CONTENT.map((c) => fetchMarkdown(assetURL(c.file)).then((src) => ({ c, src }), (err) => ({ c, err }))));
  el.append(h('nav', { class: 'ab-jump', 'aria-label': 'On this page' }, h('span', { class: 'ab-jump-k' }, 'Using it for real:'),
    docs.map(({ c, src }) => h('a', { href: `#/about?section=${c.id}` }, (src && renderMarkdown(src).title) || c.fallback))));
  docs.forEach(({ c, src, err }) => {
    let body, title = c.fallback;
    if (err || !src) body = stateBlock('error', `This section could not load (${c.file}).`);
    else {
      const md = renderMarkdown(src, { headingBase: 3, dropTitle: true, link: aboutLink, idPrefix: `ab-${c.id}-` });
      title = md.title || c.fallback;
      body = h('div', { class: 'ab-md' }, md.nodes);
      codesExpertOnly(body);
    }
    el.append(h('div', { class: 'grid-12 mt-3' }, card({
      cls: `span-12 ab-doc ab-doc--${c.id}`, kicker: c.kicker, title, body,
    })));
    const sec = el.lastElementChild.querySelector('.card');
    sec.id = `ab-${c.id}`;
    sec.tabIndex = -1;   // section jumps move focus here (keyboard users land on the section)
    sec.dataset.role = `about-${c.id}`;
  });

  // questions only: the author writes the answers (no drafted text here)
  el.append(h('div', { class: 'grid-12 mt-3' },
    card({
      cls: 'span-12 ab-why', kicker: 'Planning decisions', title: 'Why I made these planning decisions',
      body: h('div', { class: 'stack-2' },
        h('ol', { class: 'ab-q', dataset: { role: 'why-questions' } }, QUESTIONS.map((q) => h('li', { class: 'ab-q-item' }, h('span', { class: 'ab-q-t' }, Array.isArray(q) ? byMode(q[0], q[1]) : q)))),
        h('p', { class: 'ab-q-note t-12 faint m-0', dataset: { role: 'why-note' } }, 'Author’s answers to follow.')),
    })));

  if (ctx?.params?.section) scrollToSection(ctx.params.section, false);
  return null;
}
