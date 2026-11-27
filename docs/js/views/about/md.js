/**
 * views/about/md.js — a tiny, safe Markdown renderer for the docs/content/*.md pages (About, The Planner).
 * Supports: # headings, paragraphs, - / * and 1. lists (one level), pipe tables, [links](url), *em*, **strong**,
 * `code` and horizontal rules, plus mode blocks: a line `<!-- expert -->` … `<!-- /expert -->` wraps the lines between in
 * `<div class="md-expert expert-only">` (shown only in Expert mode, labelled "Expert detail"); `<!-- simple -->` …
 * `<!-- /simple -->` wraps them in `.simple-only`. Other single-line `<!-- … -->` comments are dropped. Everything is built as DOM nodes with text nodes, so no HTML in the source is ever
 * interpreted (raw tags show as text). Links: only http(s), mailto, # and relative URLs; the caller can rewrite hrefs
 * (opts.link(href) → new href, or null to drop the link and keep its text).
 *
 *   import { renderMarkdown, fetchMarkdown } from './about/md.js';
 *   const { title, nodes } = renderMarkdown(src, { headingBase: 2, dropTitle: true, link: (u) => u });
 */

const SAFE_URL = /^(https?:\/\/|mailto:|#|\.{0,2}\/|[\w.-]+(\/[\w.-]+)*(\.md|\.html|\.pdf|\.xlsx)?([#?].*)?$)/i;

function el(tag, attrs = {}, kids = []) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => { if (v != null && v !== false) e.setAttribute(k, v === true ? '' : v); });
  (Array.isArray(kids) ? kids : [kids]).forEach((k) => { if (k != null) e.append(k instanceof Node ? k : document.createTextNode(String(k))); });
  return e;
}

/** Inline Markdown → array of Nodes (text, a, em, strong, code). */
export function inline(text, opts = {}) {
  const out = [];
  const re = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*\s][^*]*\*)|(_[^_\s][^_]*_)|(\[[^\]]+\]\([^)\s]+\))/g;
  let last = 0, m;
  const s = String(text ?? '');
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(document.createTextNode(s.slice(last, m.index)));
    const t = m[0];
    if (m[1]) out.push(el('code', { class: 'md-code' }, t.slice(1, -1)));
    else if (m[2]) out.push(el('strong', {}, inline(t.slice(2, -2), opts)));
    else if (m[3] || m[4]) out.push(el('em', {}, inline(t.slice(1, -1), opts)));
    else if (m[5]) {
      const mm = t.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
      let href = mm[2];
      if (typeof opts.link === 'function') href = opts.link(href);
      if (href && SAFE_URL.test(href) && !/^\s*(javascript|data|vbscript):/i.test(href)) {
        const ext = /^https?:\/\//i.test(href);
        out.push(el('a', { href, class: 'md-link', target: ext ? '_blank' : null, rel: ext ? 'noopener noreferrer' : null }, inline(mm[1], opts)));
      } else out.push(...inline(mm[1], opts));
    }
    last = m.index + t.length;
  }
  if (last < s.length) out.push(document.createTextNode(s.slice(last)));
  return out;
}

const cells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
const slug = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

/**
 * Render a Markdown string. opts:
 *   headingBase: the tag level a "#" maps to (default 1; "##" → headingBase + 1 …, capped at h6)
 *   dropTitle: drop the first "# " heading from the output (returned as `title`)
 *   link(href): rewrite / drop link targets
 *   idPrefix: prefix for heading ids (default 'md-')
 * Returns {title, nodes: Node[]}.
 */
export function renderMarkdown(src, { headingBase = 1, dropTitle = false, link, idPrefix = 'md-' } = {}) {
  const lines = String(src ?? '').replace(/\r\n?/g, '\n').split('\n');
  const root = [];
  let nodes = root;   // where blocks go: the top level, or the children of an open mode block
  let block = null;
  let title = null, i = 0, para = [];
  const opts = { link };
  const flush = () => { if (para.length) { nodes.push(el('p', {}, inline(para.join(' '), opts))); para = []; } };
  const close = () => { if (block) { block.el.append(...block.kids); root.push(block.el); block = null; nodes = root; } };
  while (i < lines.length) {
    const line = lines[i];
    const cm = line.match(/^\s*<!--\s*(\/?)\s*(expert|simple)?\s*-->\s*$/i) || (/^\s*<!--.*-->\s*$/.test(line) ? [line, '', undefined] : null);
    if (cm) {
      flush();
      const kind = cm[2] && cm[2].toLowerCase();
      if (kind && !cm[1]) {
        close();
        const e = el('div', { class: kind === 'expert' ? 'md-expert expert-only' : 'md-simple simple-only', 'data-mode-block': kind });
        if (kind === 'expert') e.append(el('span', { class: 'md-expert-k' }, 'Expert detail'));
        block = { el: e, kids: [] };
        nodes = block.kids;
      } else if (kind) close();
      i += 1; continue;
    }
    const hm = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
    if (!line.trim()) { flush(); i += 1; continue; }
    if (hm) {
      flush();
      const level = hm[1].length;
      if (level === 1 && dropTitle && title == null) { title = hm[2]; i += 1; continue; }
      if (level === 1 && title == null) title = hm[2];
      const tag = `h${Math.min(6, headingBase + level - 1)}`;
      nodes.push(el(tag, { id: `${idPrefix}${slug(hm[2])}`, class: 'md-h' }, inline(hm[2], opts)));
      i += 1; continue;
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flush(); nodes.push(el('hr', { class: 'md-hr' })); i += 1; continue; }
    // table: a header row followed by a |---| separator
    if (/^\s*\|.*\|\s*$/.test(line) && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1] || '')) {
      flush();
      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(cells(lines[i])); i += 1; }
      const table = el('table', { class: 'data-table data-table--dense md-table' }, [
        el('thead', {}, el('tr', {}, head.map((c) => el('th', { scope: 'col' }, inline(c, opts))))),
        el('tbody', {}, rows.map((r) => el('tr', {}, head.map((_, j) => el(j ? 'td' : 'th', j ? {} : { scope: 'row' }, inline(r[j] ?? '', opts)))))),
      ]);
      nodes.push(el('div', { class: 'table-wrap md-table-wrap' }, table));
      continue;
    }
    const lm = line.match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
    if (lm) {
      flush();
      const ordered = /\d/.test(lm[1]);
      const list = el(ordered ? 'ol' : 'ul', { class: 'md-list' });
      while (i < lines.length) {
        const m2 = lines[i].match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
        if (!m2 || /\d/.test(m2[1]) !== ordered) break;
        let txt = m2[2];
        i += 1;
        // continuation lines (indented, not a new item)
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) { txt += ` ${lines[i].trim()}`; i += 1; }
        list.append(el('li', {}, inline(txt, opts)));
      }
      nodes.push(list);
      continue;
    }
    para.push(line.trim());
    i += 1;
  }
  flush();
  close();
  return { title, nodes: root };
}

const cache = new Map();
/** Fetch a Markdown file (cached per URL). Resolves to the text, or rejects. */
export function fetchMarkdown(url) {
  if (!cache.has(url)) {
    cache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(`${r.status} ${url}`); return r.text(); }).catch((e) => { cache.delete(url); throw e; }));
  }
  return cache.get(url);
}
