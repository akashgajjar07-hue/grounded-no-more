/**
 * The Planner Behind the Project · STUB created by the SHELL agent (v2.1). A page agent owns this file from wave 2
 * and replaces it (content source: docs/content/planner.md, written by the AUTHOR agent).
 * Route: #/planner. Data: none.
 */
import { h, pageHead, intro3, stubNote } from '../ui.js';

export const data = [];

export async function render(el) {
  el.append(
    pageHead({ eyebrow: 'Project', title: 'The Planner Behind the Project', lede: 'Why this project exists and how a materials planner would use it.' }),
    intro3({ what: 'The person and the planning questions behind this site.', why: 'Tools only help if they answer real planning questions.', action: 'Read this first if you are new to spare-parts planning.' }),
    h('div', {}, stubNote('This page is being written.')),
  );
}
