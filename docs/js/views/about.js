/**
 * About · the author, the project's scope, the tools, the downloads and an honest note on how it was built.
 * Data: none (static copy about the author and the project). Downloads are served from docs/downloads/.
 * The "Why I made these planning decisions" section holds the questions only: the answers are the author's to write.
 */
import { h, pageHead, card, icon } from '../ui.js';

export const data = [];

const AUTHOR = {
  name: 'Akash Gajjar',
  degree: 'MSc Supply Chain Management, University of Liverpool (2025)',
  experience: 'Retail operations and inventory experience at Primark and Uniqlo',
  github: 'https://github.com/akashgajjar07-hue',
};

const SKILLS = [
  ['Planning methods', ['Intermittent-demand forecasting (Croston, SBA, TSB, bootstrap)', 'Rotable float sizing (Palm’s theorem, METRIC-inspired)', 'Multi-echelon stock positioning', 'Capital-vs-readiness trade-off (greedy marginal allocation)', 'AOG sourcing options and exposure']],
  ['Analysis and evaluation', ['Discrete-event simulation of a fictional airline network', 'Paired-seed evaluation with a frozen holdout', 'Calibration against stated targets', 'Assumption register with provenance tags']],
  ['Tools', ['Python (pandas, NumPy)', 'DuckDB / SQL', 'D3 for the interactive charts', 'Playwright browser tests', 'Excel planner workbook']],
];

const QUESTIONS = [
  'Intermittent demand handling',
  'Why maximum local stock isn’t optimal',
  'How TAT drives float',
  'Why point accuracy isn’t enough',
  'How the optimiser balances readiness and capital',
  'What data I’d request from a real airline',
];

export async function render(el) {
  if (!document.querySelector('link[data-view-css="about"]')) {
    document.head.append(h('link', { rel: 'stylesheet', href: new URL('../../css/views/about.css', import.meta.url).href, dataset: { viewCss: 'about' } }));
  }
  el.append(pageHead({
    num: null, eyebrow: 'About',
    title: 'About this project',
    lede: 'GROUNDED NO MORE is an independent aviation materials-planning simulation built as a portfolio project. Falcon Hub Airways and every part number in it are fictional.',
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
        h('p', {}, 'Defined the planning problem, the fictional airline network and the questions each workspace answers; chose the forecasting, inventory and optimisation methods; set the evaluation rules (selection seeds, a frozen holdout, stated calibration targets); and reviewed every result and design decision.'),
        links),
    }),
    card({
      cls: 'span-5 md-span-12', kicker: 'How it was built', title: 'A transparent note',
      body: h('div', { class: 'ab-body' },
        h('p', { class: 'ab-note', dataset: { role: 'ai-note' } }, 'Built with AI-assisted development; analysis, decisions and validation reviewed by the author.'),
        h('p', { class: 'muted' }, 'Models run offline; this site loads exported results from a simulated planning snapshot. It is not an airline system or an approved maintenance, airworthiness or dispatch tool.')),
    })));

  el.append(h('div', { class: 'grid-12 mt-3' },
    card({
      cls: 'span-12', kicker: 'Skills and tools', title: 'What the project exercises',
      body: h('div', { class: 'ab-skills' }, SKILLS.map(([head, items]) => h('div', { class: 'ab-skill' }, h('h4', { class: 'ab-h' }, head), h('ul', { class: 'ab-list' }, items.map((t) => h('li', {}, t)))))),
    })));

  // questions only: the author writes the answers (no drafted text here)
  el.append(h('div', { class: 'grid-12 mt-3' },
    card({
      cls: 'span-12 ab-why', kicker: 'Planning decisions', title: 'Why I made these planning decisions',
      // wave C: an intentional list of the six questions, with a one-line note; the answers are the author's to write
      body: h('div', { class: 'stack-2' },
        h('ol', { class: 'ab-q', dataset: { role: 'why-questions' } }, QUESTIONS.map((q) => h('li', { class: 'ab-q-item' }, h('span', { class: 'ab-q-t' }, q)))),
        h('p', { class: 'ab-q-note t-12 faint m-0', dataset: { role: 'why-note' } }, 'Author’s answers to follow.')),
    })));
  return null;
}
