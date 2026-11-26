/**
 * data.js — fetch + cache the exported JSON files.
 *
 * Resolution order for `load('parts')`:
 *   1. docs/data/manifest.json lists the real exports that exist ({"files": ["parts", ...]}).
 *      If 'parts' is listed → docs/data/parts.json
 *   2. otherwise → docs/data/fixtures/parts.json (layout fixtures; meta.fixture === true)
 * If the manifest itself is missing we try the real file first and fall back to the fixture.
 *
 * Whenever a loaded file has meta.fixture, every `onFixture` listener fires so the shell can
 * show the "FIXTURE DATA" chip. Paths are resolved from this module's URL, so the loader
 * works from index.html and from docs/design/gallery.html alike.
 */

const DATA_BASE = new URL('../data/', import.meta.url);
const cache = new Map();
const fixtureFiles = new Set();
const listeners = new Set();
let manifestPromise = null;

async function fetchJSON(url) {
  const res = await fetch(url, { cache: 'no-cache' });
  if (!res.ok) throw Object.assign(new Error(`HTTP ${res.status} for ${url}`), { status: res.status });
  return res.json();
}

function getManifest() {
  if (!manifestPromise) {
    manifestPromise = fetchJSON(new URL('manifest.json', DATA_BASE)).catch(() => null);
  }
  return manifestPromise;
}

function markFixture(name, json) {
  if (json?.meta?.fixture) {
    fixtureFiles.add(name);
    listeners.forEach((fn) => fn([...fixtureFiles]));
  }
  return json;
}

/**
 * Load one export by base name (no extension). Cached; concurrent calls share one request.
 * @param {string} name e.g. 'kpis', 'parts', 'network'
 * @returns {Promise<object>} the parsed JSON ({meta, ...payload})
 */
export function load(name) {
  if (cache.has(name)) return cache.get(name);
  const p = (async () => {
    const manifest = await getManifest();
    const real = new URL(`${name}.json`, DATA_BASE);
    const fixture = new URL(`fixtures/${name}.json`, DATA_BASE);
    if (manifest && Array.isArray(manifest.files)) {
      const url = manifest.files.includes(name) ? real : fixture;
      return markFixture(name, await fetchJSON(url));
    }
    try {
      return markFixture(name, await fetchJSON(real));
    } catch {
      return markFixture(name, await fetchJSON(fixture));
    }
  })();
  cache.set(name, p);
  p.catch(() => cache.delete(name));
  return p;
}

/**
 * Load several exports at once.
 * @param {string[]} names
 * @returns {Promise<Record<string, object>>} keyed by name
 */
export async function loadMany(names = []) {
  const entries = await Promise.all(names.map(async (n) => [n, await load(n)]));
  return Object.fromEntries(entries);
}

/** Subscribe to "a fixture file was loaded". Callback receives the list of fixture file names. */
export function onFixture(fn) {
  listeners.add(fn);
  if (fixtureFiles.size) fn([...fixtureFiles]);
  return () => listeners.delete(fn);
}

export const isFixtureLoaded = () => fixtureFiles.size > 0;
export const assetURL = (path) => new URL(`../${path}`, import.meta.url).href;
