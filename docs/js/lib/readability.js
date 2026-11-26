/**
 * lib/readability.js — Flesch–Kincaid grade + longest sentence for a DOM subtree (v2.1 brief §C: Simple-mode copy
 * at grade 9 or below, no sentence over 25 words). No dependencies. Used by tests (and handy in the console):
 *
 *   const { readability } = await import('./js/lib/readability.js');
 *   readability(document.querySelector('#view'))
 *     → { grade: 7.8, words: 812, sentences: 74, syllables: 1190, maxSentenceWords: 22, longest: '…', longSentences: [] }
 *   readabilityOfText('Plain text. Two sentences.')   → same shape
 *
 * What is counted: visible prose only. Skipped: hidden elements (display:none / visibility:hidden / [hidden] /
 * .sr-only), <script>/<style>/<svg>/<code>/<pre>, data tables (`table`, `.table-wrap`, `.data-table-stack`),
 * `.mono` / `.mono-tag` / `.kbd`, the grey first-use brackets `.term-expert`, and anything marked
 * `[data-readability="skip"]`. Block elements (p, li, h1–h6, td, div, …) end a sentence, so headings and list items
 * do not run into the next line. Numbers count as one-syllable words.
 */
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'SVG', 'CODE', 'PRE', 'NOSCRIPT', 'TEMPLATE', 'TABLE', 'KBD', 'SELECT', 'OPTION', 'TEXTAREA', 'INPUT']);
const SKIP_SEL = '.sr-only, .table-wrap, .data-table-stack, .mono, .mono-tag, .kbd, .term-expert, [data-readability="skip"], [aria-hidden="true"]';
const BLOCK = /^(P|LI|H[1-6]|TD|TH|DT|DD|DIV|SECTION|ARTICLE|HEADER|FOOTER|ASIDE|FIGCAPTION|FIGURE|BLOCKQUOTE|SUMMARY|DETAILS|BUTTON|LABEL|CAPTION|UL|OL|DL|NAV|MAIN|TR)$/;

/** Rough English syllable count (the usual vowel-group heuristic; good enough for a grade estimate). */
export function syllables(word) {
  let w = String(word).toLowerCase().replace(/[^a-z]/g, '');
  if (!w) return /\d/.test(word) ? 1 : 0;
  if (w.length <= 3) return 1;
  w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, '').replace(/^y/, '');
  const m = w.match(/[aeiouy]{1,2}/g);
  return Math.max(1, m ? m.length : 1);
}

function visible(el) {
  if (el.hidden) return false;
  const cs = getComputedStyle(el);
  return cs.display !== 'none' && cs.visibility !== 'hidden';
}

/** Visible prose of a subtree as an array of chunks (one per block). */
export function proseChunks(root) {
  const out = [];
  let buf = '';
  const flush = () => { if (buf.trim()) out.push(buf.replace(/\s+/g, ' ').trim()); buf = ''; };
  (function walk(node) {
    if (node.nodeType === 3) { buf += node.nodeValue; return; }
    if (node.nodeType !== 1) return;
    const el = node;
    if (SKIP_TAGS.has(el.tagName.toUpperCase()) || el.matches(SKIP_SEL) || !visible(el)) return;
    const block = BLOCK.test(el.tagName.toUpperCase()) || el.tagName === 'BR';
    if (block) flush();
    el.childNodes.forEach(walk);
    if (block) flush();
  })(root);
  flush();
  return out;
}

const SENT_SPLIT = /(?<=[.!?…])\s+(?=[A-Z0-9“"'(])|(?<=[.!?…])$/;
const wordsOf = (s) => s.match(/[A-Za-z0-9][A-Za-z0-9'’.,%×−-]*/g)?.map((w) => w.replace(/[.,]+$/, '')).filter(Boolean) || [];

/** Readability of an array of text chunks (each chunk ends at least one sentence). */
export function readabilityOfChunks(chunks) {
  const sentences = [];
  chunks.forEach((c) => c.split(SENT_SPLIT).map((s) => s.trim()).filter((s) => wordsOf(s).length).forEach((s) => sentences.push(s)));
  let words = 0, syl = 0, maxW = 0, longest = '';
  const longSentences = [];
  sentences.forEach((s) => {
    const ws = wordsOf(s);
    words += ws.length;
    syl += ws.reduce((a, w) => a + syllables(w), 0);
    if (ws.length > maxW) { maxW = ws.length; longest = s; }
    if (ws.length > 25) longSentences.push(s);
  });
  const n = sentences.length;
  const grade = n && words ? 0.39 * (words / n) + 11.8 * (syl / words) - 15.59 : 0;
  return { grade: Math.round(grade * 10) / 10, words, sentences: n, syllables: syl, maxSentenceWords: maxW, longest, longSentences };
}

/** Readability of plain text. */
export const readabilityOfText = (text) => readabilityOfChunks(String(text).split(/\n+/));

/** Readability of the visible prose in a DOM subtree (default: the current view). */
export function readability(root = document.querySelector('#view')) {
  return readabilityOfChunks(root ? proseChunks(root) : []);
}

if (typeof window !== 'undefined') window.__gnmReadability = readability;
