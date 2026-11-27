/**
 * About · the author, the methods used, the downloads, a note on how it was built, and how the method would
 * be used for real: E2 "How this transfers to an MRO" (docs/content/mro.md), E3 "What real data would make this
 * useful" (docs/content/real_data.md) and "Next experiments" (docs/content/next_experiments.md), rendered with the
 * small safe Markdown renderer in ./about/md.js. Deep links: #/about?section=mro | real-data | next-experiments.
 * "Planning decisions": each question links to the page (or section) that answers it, with a one-line answer.
 * Data: none (static copy + the three content files).
 */
import { h, pageHead, card, icon, intro3, stateBlock } from '../ui.js';
import { assetURL } from '../data.js';
import { byMode } from '../lib/mode.js';
import { isPolicyCode } from '../lib/names.js';
import { renderMarkdown, fetchMarkdown } from './about/md.js';
import { jumpTo, sameRouteLinks } from './about/section.js';

export const data = [];

const AUTHOR = {
  name: 'Akash Gajjar',
  degree: 'MSc Supply Chain Management, University of Liverpool (2025)',
  experience: 'Retail operations and inventory experience at Primark and Uniqlo',
  github: 'https://github.com/akashgajjar07-hue',
};
const REPO = 'https://github.com/akashgajjar07-hue/grounded-no-more';

/** Methods used: [heading, [[simple wording, expert wording], …]] — what the project uses. */
const METHODS = [
  ['Planning methods', [
    ['Forecasting parts that are needed only now and then', 'Intermittent-demand forecasting (Croston, SBA, TSB, bootstrap)'],
    ['Sizing the pool of repairable spares', 'Rotable float sizing (Palm’s theorem, METRIC-inspired)'],
    ['Placing spares across the hub and outstations', 'Multi-echelon stock positioning'],
    ['Weighing money against aircraft readiness', 'Capital-vs-readiness trade-off (greedy marginal allocation)'],
    ['Emergency ways to get a part, and what they cost', 'AOG sourcing options and exposure'],
  ]],
  ['How results are tested', [
    ['A computer model of a fictional airline network', 'Discrete-event simulation of a fictional airline network'],
    ['Fair tests: every plan faces the same events', 'Paired-seed evaluation with a frozen holdout'],
    ['A stated target for the starting point', 'Calibration against stated targets'],
    ['A list of every assumption and where it came from', 'Assumption register with provenance tags'],
  ]],
  ['Built with', [
    ['Python (pandas, NumPy)', 'Python (pandas, NumPy)'],
    ['DuckDB and SQL', 'DuckDB / SQL'],
    ['D3 for the interactive charts', 'D3 for the interactive charts'],
    ['Playwright browser tests', 'Playwright browser tests'],
    ['An Excel planner workbook', 'Excel planner workbook'],
  ]],
];

/**
 * Planning decisions: [question (string or [simple, expert]), href, one-line answer (string or [simple, expert])].
 * Each answer only points at what the linked page already shows.
 */
const QUESTIONS = [
  [['How to handle parts needed only now and then', 'Intermittent demand handling'], '#/forecast',
    ['The Forecast Lab tests methods made for parts with rare, uneven demand.', 'Forecast Lab: Croston, SBA, TSB and bootstrap compared by demand class.']],
  ['Why maximum local stock isn’t the best plan', '#/network',
    ['Network Positioning compares spares at every airport with spares shared across the network.', 'Network Positioning: local stocking against hub pooling, plan by plan.']],
  [['How repair time drives the pool of spares', 'How TAT drives float'], '#/rotables',
    ['Rotable & Repair sizes the pool from removals × repair time. You can change the repair time.', 'Rotable & Repair: float from removal rate × TAT (Palm), with a TAT what-if.']],
  ['Why point accuracy isn’t enough', '#/forecast',
    ['The Forecast Lab follows each forecast through to the spares it would put on the shelf.', 'Forecast Lab: forecast error carried through to lead-time demand and stock.']],
  [['How the planner balances readiness and money', 'How the optimiser balances readiness and capital'], '#/capital',
    ['The Capital Optimiser adds spares one at a time, where each one cuts the most waiting.', 'Capital Optimiser: greedy marginal allocation along the capital-vs-readiness frontier.']],
  ['What data I’d request from a real airline', '#/about?section=real-data',
    ['The real-data table above lists each record, why it matters and its first use.', 'Data request: ten record types, each with its first use in a back-test.']],
];
const pick = (v) => (Array.isArray(v) ? byMode(v[0], v[1]) : v);

/** The three content pages rendered on About, in order. */
const CONTENT = [
  { id: 'mro', file: 'content/mro.md', kicker: 'Using it for real', fallback: 'How this transfers to an MRO' },
  { id: 'real-data', file: 'content/real_data.md', kicker: 'Using it for real', fallback: 'What real data would make this useful' },
  { id: 'next-experiments', file: 'content/next_experiments.md', kicker: 'Proposed, not run', fallback: 'Next experiments' },
];
const LINKS = { 'mro.md': 'mro', 'real_data.md': 'real-data', 'next_experiments.md': 'next-experiments' };
/** Content links between the .md files become on-page section links; repo files go to GitHub. */
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

/** Jump to an About section (#ab-<id>) once it is rendered; focus lands on its heading. */
function scrollToSection(id) {
  return jumpTo(() => document.getElementById(`ab-${id}`), { heading: (t) => t.querySelector('.card-title') || t });
}

/** #/about?section=… on the same route: jump, no re-render. */
export function onParams(params) {
  if (params.section) scrollToSection(params.section);
  else window.scrollTo({ top: 0, behavior: 'instant' });
  return true;
}

export async function render(el, ctx) {
  // a navigation render starts hidden (the router reveals it); a mode switch re-renders in place and keeps the scroll
  const navRender = el.style.visibility === 'hidden';
  if (!document.querySelector('link[data-view-css="about"]')) {
    document.head.append(h('link', { rel: 'stylesheet', href: new URL('../../css/views/about.css', import.meta.url).href, dataset: { viewCss: 'about' } }));
  }
  el.append(pageHead({
    num: null, eyebrow: 'About',
    title: 'About this project',
    lede: 'GROUNDED NO MORE is an independent simulation project about aviation spare-parts planning. Falcon Hub Airways and every part number in it are fictional.',
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
      cls: 'span-12', kicker: 'Methods used', title: 'What the project uses',
      body: h('div', { class: 'ab-skills' }, METHODS.map(([head, items]) => h('div', { class: 'ab-skill' }, h('h4', { class: 'ab-h' }, head), h('ul', { class: 'ab-list' }, items.map(([s, x]) => h('li', {}, byMode(s, x))))))),
    })));

  // E2 / E3 / next experiments: the author's content files, rendered safely
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
    const head = sec.querySelector('.card-title');
    if (head) { head.tabIndex = -1; head.id = `ab-${c.id}-h`; sec.setAttribute('aria-labelledby', head.id); }   // section jumps move focus to the heading
    sec.dataset.role = `about-${c.id}`;
  });

  // each planning question links to where the site already answers it
  el.append(h('div', { class: 'grid-12 mt-3' },
    card({
      cls: 'span-12 ab-why', kicker: 'Planning decisions', title: 'Where each decision is explained',
      body: h('ol', { class: 'ab-q', dataset: { role: 'why-questions' } }, QUESTIONS.map(([q, href, a]) => h('li', { class: 'ab-q-item' },
        h('a', { class: 'ab-q-t', href }, pick(q)),
        h('p', { class: 'ab-q-a t-14 muted m-0' }, pick(a))))),
    })));

  if (ctx?.params?.section && navRender) scrollToSection(ctx.params.section);
  // a repeat click on the link of the section already in the URL fires no hashchange: jump directly
  return sameRouteLinks(el, 'about', (p) => (p.section ? scrollToSection(p.section) : window.scrollTo({ top: 0, behavior: 'instant' })));
}
