/**
 * lib/glossary.js — the ONE source of plain-English terms (v2.1 brief §C3 + every other domain term on the site).
 * Depends only on lib/mode.js.
 *
 *   import { term, termText, glossaryEntries, glossaryEntry } from '../lib/glossary.js';
 *   p.append('We cut ', term('aog_hours'), ' by a lot.');
 *     Simple, first use in this view : "hours planes sat grounded waiting for a part (material AOG hours)"
 *                                      (the bracket is <small class="term-expert">, grey)
 *     Simple, later uses             : "hours planes sat grounded waiting for a part"
 *     Expert                         : "material AOG hours"
 *     Always: span.term[tabindex=0][data-term][aria-describedby] with a tooltip (the definition) on hover, focus
 *     and tap; Esc closes it. The router resets "first use" at every view render (resetTermUses()).
 *   termText('tat')                 → 'repair time' (Simple) | 'TAT' (Expert): plain string for chart labels / aria
 *   termText('tat', {mode: 'expert'}) → 'TAT'
 *   glossaryEntries()               → [{key, expert, simple, definition, example, why, category, aliases}] sorted A–Z
 *   glossaryEntry('ebo')            → one entry (or null)
 *   FRONTIER_SUBTITLE               → 'how much readiness each extra dirham buys'
 */
import { getMode } from './mode.js';

export const FRONTIER_SUBTITLE = 'how much readiness each extra dirham buys';

/** Category order for the glossary page. */
export const GLOSSARY_CATEGORIES = ['Downtime and urgency', 'Parts', 'Repair', 'Stock and network', 'Forecasting', 'Plans and money', 'Testing and results'];

const E = (key, expert, simple, category, definition, example, why, aliases = []) => ({ key, expert, simple, category, definition, example, why, aliases });

const ENTRIES = [
  // ---------------------------------------------------------------- C3 table (simple wording is binding)
  E('aog_hours', 'material AOG hours', 'hours planes sat grounded waiting for a part', 'Downtime and urgency',
    'The hours an aircraft could not fly because a needed part was not there in time.',
    'A brake is needed at 08:00 but arrives at 14:00. That adds 6 hours.',
    'It is the main score on this site. Fewer hours means planes fly more.', ['AOG hours', 'material AOG']),
  E('rotable', 'rotable', 'repairable part', 'Parts',
    'A part that is fixed and used again, not thrown away.',
    'A wheel or a pump goes to a repair shop and later comes back as a spare.',
    'Repairable parts are expensive, so how many we own matters a lot.', ['rotables']),
  E('float', 'float', 'pool of repairable spares', 'Stock and network',
    'The spare repairable parts kept ready to swap in while others are away for repair.',
    'Four spare pumps cover the gap while broken pumps are in the shop.',
    'Too small a pool means waits. Too big a pool ties up money.', ['rotable float']),
  E('tat', 'TAT', 'repair time', 'Repair',
    'Turnaround time: how long a broken part takes to come back fixed, including shipping.',
    'A pump leaves on Monday and comes back fixed 12 days later.',
    'Shorter repair time means fewer spares are needed.', ['repair TAT', 'turnaround time']),
  E('mtbur', 'MTBUR', 'how often a part comes off the aircraft', 'Parts',
    'Mean time between unscheduled removals: the average flying hours before a part is taken off unexpectedly.',
    'A part with 5,000 hours between removals comes off about twice a year on a busy aircraft.',
    'It drives how many spares a part needs.', ['mean time between unscheduled removals']),
  E('qpa', 'QPA', 'how many are fitted per aircraft', 'Parts',
    'Quantity per aircraft: how many of one part are fitted on each plane.',
    'A narrowbody has 4 main-wheel brakes, so its QPA is 4.',
    'More fitted parts means more removals across the fleet.', ['quantity per aircraft']),
  E('holdout', 'holdout (paired seeds)', '20 fresh test runs the model never saw, each policy facing identical events', 'Testing and results',
    'A set of simulated years kept aside until the end. Every plan is tested on exactly the same failures.',
    'All plans face the same 20 years of breakdowns, so the comparison is fair.',
    'It stops us picking a plan that only looks good on the runs we tuned it on.', ['holdout', 'paired seeds', 'test runs']),
  E('ci', '95% CI', 'likely range', 'Testing and results',
    'The range where the true average most likely sits, given the random variation between test runs.',
    '210 h with a likely range of 190 to 230 h.',
    'It shows how sure we can be. It covers simulation randomness only.', ['CI', 'confidence interval']),
  E('ebo', 'EBO', 'expected waits for a part', 'Stock and network',
    'Expected backorders: on average, how many requests are waiting for a part at any moment.',
    'An EBO of 0.2 means a request is waiting about one fifth of the time.',
    'It is the quantity the stocking maths tries to push down.', ['expected backorders']),
  E('fill_rate', 'fill rate', 'chance the part is on the shelf', 'Stock and network',
    'The share of requests met straight away from stock.',
    'A fill rate of 95% means 19 out of 20 requests get the part at once.',
    'A high fill rate alone can hide long waits for the few misses.', ['immediate fill rate', 'fill']),
  E('robbery', 'robbery', 'borrowing a part from another of our aircraft', 'Downtime and urgency',
    'Taking a working part off one of our own aircraft to fix another. Also called cannibalisation.',
    'A parked plane gives its pump to a plane due to fly.',
    'It gets one plane flying but can ground the donor. Donor downtime is shown separately.', ['cannibalisation', 'cannibalization', 'donor']),
  E('forecast_methods', 'Croston / SBA / TSB', 'forecasting methods for rarely-needed parts', 'Forecasting',
    'Methods made for parts that are needed only now and then, with many zero weeks.',
    'A part needed 3 times a year gets a small steady forecast, not a guess of zero.',
    'Normal forecasts do badly on rare demand.', ['Croston', 'SBA', 'TSB']),
  E('croston', 'Croston', 'a forecasting method for rarely-needed parts', 'Forecasting',
    'Forecasts how big each demand is and how long the gap between demands is, then combines them.',
    'Demand of 2 units about every 10 weeks gives about 0.2 a week.',
    'It is the classic method for rare demand.'),
  E('sba', 'SBA', 'a forecasting method for rarely-needed parts', 'Forecasting',
    'Syntetos–Boylan approximation: Croston with a small fix so it does not forecast too high.',
    'It trims the Croston forecast by a few per cent.',
    'It often beats plain Croston on rare demand.'),
  E('tsb', 'TSB', 'a forecasting method for rarely-needed parts', 'Forecasting',
    'Teunter–Syntetos–Babai: tracks the chance of any demand each week, so it can react when a part stops being used.',
    'A part being phased out sees its forecast fall over time.',
    'It handles parts that fade away.'),
  E('frontier', 'Readiness Frontier', 'Readiness Frontier', 'Plans and money',
    `A chart of the best plans found at each spending level: ${FRONTIER_SUBTITLE}.`,
    'Each point is a plan. Moving right costs more; moving down means fewer grounded hours.',
    'It shows where extra money stops buying much readiness.', ['frontier', 'readiness frontier']),

  // ---------------------------------------------------------------- downtime and urgency
  E('aog', 'AOG', 'grounded aircraft', 'Downtime and urgency',
    'Aircraft on ground: a plane that cannot fly until something is fixed.',
    'A plane waiting for a brake is AOG.',
    'Every AOG hour is a lost flight or a costly swap.', ['aircraft on ground']),
  E('rectification_window', 'rectification window', 'time allowed to fix it', 'Downtime and urgency',
    'How long a fault may wait before the aircraft must stop flying. The windows here are simplified and hypothetical.',
    'A D3 fault can wait up to 72 hours.',
    'It decides whether a missing part grounds a plane at once or later.', ['rectification windows']),
  E('d0', 'D0', 'must be fixed before the next flight', 'Downtime and urgency',
    'A fault with no waiting time: the part is needed before the plane can leave again.',
    'A failed steering actuator must be replaced before departure.',
    'These parts ground a plane at once, so where they are stocked matters most.'),
  E('d3', 'D3', 'can wait up to 3 days', 'Downtime and urgency',
    'A fault that may wait up to 72 hours before it counts as downtime. A simplified, hypothetical window.',
    'If the part is fitted within 72 hours, no grounded hours are counted.',
    'There is time to ship a part from the home base.'),
  E('d10', 'D10', 'can wait up to 10 days', 'Downtime and urgency',
    'A fault that may wait up to 240 hours before it counts as downtime. A simplified, hypothetical window.',
    'A cabin item can be fixed on the next visit to the home base.',
    'These parts rarely need stock at small airports.'),
  E('mel', 'MEL', 'list of items a plane may briefly fly without', 'Downtime and urgency',
    'Minimum equipment list: an approved list of items that may be broken for a short time. This model uses simple stand-ins, not a real MEL.',
    'A reading light may be fixed within a set time.',
    'It is why some faults do not ground a plane right away.', ['minimum equipment list']),
  E('aog_desk', 'AOG desk', 'team that chases urgent parts', 'Downtime and urgency',
    'The people who find a part fast when a plane is grounded: borrow, loan, or move stock.',
    'The desk finds a loan pump in 24 hours.',
    'Their options are part of every plan tested here.', ['AOG response']),
  E('exchange', 'exchange / loan', 'getting a spare from an outside supplier', 'Downtime and urgency',
    'Getting a working repairable part from a supplier for a fee, while ours is repaired.',
    'A supplier ships a loan unit in 24 to 48 hours for a fee.',
    'It is a costly but common rescue when we have no spare.', ['exchange', 'loan', 'exchange/loan']),
  E('local_borrow', 'local borrow', 'borrowing a spare at the same airport', 'Downtime and urgency',
    'Borrowing a part from another operator or pool at the same small airport. It is quick but not always possible.',
    'A spare is found nearby in 4 to 8 hours.',
    'It can save a day of waiting at small airports.'),
  E('local_buy', 'local buy', 'buying a cheap part on the spot', 'Downtime and urgency',
    'Buying a low-cost part locally when it is out of stock.',
    'A filter is bought from a nearby supplier.',
    'It works for cheap parts, not for repairable ones.'),
  E('backorder', 'backorder', 'a request still waiting for a part', 'Stock and network',
    'A need for a part that stock could not meet yet.',
    'Two requests are waiting until the next spare comes back from repair.',
    'Waiting requests turn into grounded hours.', ['backorders']),

  // ---------------------------------------------------------------- parts
  E('consumable', 'consumable', 'part used once and replaced', 'Parts',
    'A cheap part used up in normal work, like a filter or a seal.',
    'Oil filters are replaced at each check.',
    'They are ordered in batches, not repaired.', ['consumables']),
  E('expendable', 'expendable', 'part thrown away when it fails', 'Parts',
    'A part that is not worth repairing, so it is replaced when it fails.',
    'A lamp or a small valve.',
    'Stock is kept with simple reorder rules.', ['expendables']),
  E('part_number', 'part number (PN)', 'part number', 'Parts',
    'The code that names one kind of part. All 120 here are fictional.',
    'GN-32-R014 is a steering actuator.',
    'Every plan is worked out part by part.', ['PN', 'part number']),
  E('ata', 'ATA chapter', 'aircraft system group', 'Parts',
    'A standard number for each aircraft system, like 32 for landing gear.',
    'ATA 32 covers wheels, brakes and steering.',
    'It groups parts so planners can scan by system.', ['ATA']),
  E('nff', 'NFF', 'part removed that turned out to work', 'Repair',
    'No fault found: a part taken off for a suspected fault that the shop finds working.',
    'A sensor comes back after 3 days with nothing wrong.',
    'It still uses repair time and spares.', ['no fault found']),
  E('condemnation', 'condemnation', 'part scrapped as beyond repair', 'Repair',
    'When a shop decides a repairable part cannot be fixed and must be replaced.',
    'A cracked housing is scrapped and a new unit is ordered.',
    'Each scrapped part means a long wait for a new one.', ['condemned']),
  E('serviceable', 'serviceable', 'ready to fit', 'Repair',
    'A part checked and fit for use.',
    'A pump back from the shop is serviceable.',
    'Only ready-to-fit parts can end a wait.'),
  E('unserviceable', 'unserviceable', 'broken and waiting for repair', 'Repair',
    'A part that is not fit for use until repaired.',
    'A removed pump waits to be shipped to the shop.',
    'These parts are in the repair loop, not on the shelf.'),

  // ---------------------------------------------------------------- repair and stock
  E('pipeline', 'repair pipeline', 'parts away being repaired or shipped', 'Repair',
    'All repairable parts on their way to, in, or back from the repair shop.',
    'At any time about 3 pumps are in the pipeline.',
    'The spares pool must cover the pipeline, or planes wait.', ['pipeline']),
  E('palm', "Palm's theorem", 'rule linking demand, repair time and spares', 'Repair',
    'A classic result: parts in repair on average = removals per day × days to repair.',
    '0.5 removals a day × 12 days = about 6 parts in repair.',
    'It sizes the spares pool for each repairable part.', ['Palm']),
  E('base_stock', 'base stock', 'target number of spares', 'Stock and network',
    'The number of spares a location tries to keep. Each one used is replaced.',
    'A base stock of 3 means one is reordered or repaired for each one used.',
    'It is the main dial a planner sets for repairable parts.', ['base-stock level', 'S']),
  E('reorder_point', 'reorder point', 'stock level that triggers a new order', 'Stock and network',
    'When stock falls to this level, a new order is placed.',
    'Reorder filters when 10 are left.',
    'It covers demand while the order is on its way.', ['(s, S)', 'reorder level']),
  E('lead_time', 'lead time', 'time to get a new part from the supplier', 'Stock and network',
    'Days from placing an order to having the part in stock.',
    'A new actuator takes 90 days to arrive.',
    'Long lead times need more safety stock.', ['supplier lead time']),
  E('safety_stock', 'safety stock', 'extra spares for bad luck', 'Stock and network',
    'Stock held above the average need to cover surprises.',
    'Two extra filters cover a busy month.',
    'It trades money for fewer waits.'),
  E('hub', 'hub', 'home base airport', 'Stock and network',
    'The main base where most aircraft return and most stock is held (AUH in this model).',
    'A part at the hub can reach most planes overnight.',
    'Central stock is shared by the whole fleet.', ['main base']),
  E('outstation', 'outstation', 'smaller airport away from the home base', 'Stock and network',
    'An airport the airline flies to that holds little or no stock.',
    'A spare kept at BOM saves a day of shipping from the hub.',
    'A few spares in the right outstations cut waits sharply.', ['outstations']),
  E('line_station', 'line station', 'airport with basic repair staff', 'Stock and network',
    'An airport with staff for quick checks and simple part swaps, but no big repairs.',
    'A brake change at a line station is not done in this model.',
    'It limits which parts are worth placing there.', ['line stations']),
  E('station', 'station', 'airport', 'Stock and network',
    'An airport in the network. This model has 7.',
    'AUH is the hub; the other 6 are outstations.',
    'Plans decide how many spares each station holds.', ['stations']),
  E('repositioning', 'repositioning', 'moving spares between airports', 'Stock and network',
    'Moving existing spares to where failures happen, without buying more.',
    'One pump moves from the hub to a busy outstation.',
    'It can cut waits at zero extra cost.', ['reposition']),
  E('echelon', 'multi-echelon', 'planning hub and outstations together', 'Stock and network',
    'Sizing stock at the hub and outstations as one system, not each on its own.',
    'The hub backs up every outstation, so outstations need fewer spares.',
    'It is the idea behind the Network Plan.', ['multi-echelon', 'single-echelon']),

  // ---------------------------------------------------------------- forecasting
  E('intermittent', 'intermittent demand', 'parts needed only now and then', 'Forecasting',
    'Demand with many weeks of zero and the odd spike.',
    'A valve needed in 4 weeks out of 52.',
    'It is common for aircraft parts and hard to forecast.', ['lumpy demand']),
  E('adi_cv2', 'ADI / CV²', 'how often and how evenly a part is needed', 'Forecasting',
    'Two measures: average gap between demands (ADI) and how much demand sizes vary (CV²).',
    'ADI 4 means a demand about every 4 weeks.',
    'They sort parts into types, each with a suited forecast method.', ['ADI', 'CV2', 'CV²', 'demand class']),
  E('mase', 'MASE', 'forecast error compared with a simple guess', 'Forecasting',
    'Mean absolute scaled error. Below 1 beats a naive guess; above 1 is worse.',
    'A MASE of 0.8 is 20% better than the naive guess.',
    'It lets us compare errors across very different parts.'),
  E('pinball', 'pinball loss', 'score for range forecasts', 'Forecasting',
    'A score for forecasts of a high or low level, like the 90th percentile. Lower is better.',
    'It punishes a too-low high estimate more than a too-high one.',
    'Stocking depends on the high end of demand, not just the average.', ['quantile loss']),
  E('bias', 'forecast bias', 'whether forecasts run high or low', 'Forecasting',
    'The average amount a forecast is too high or too low.',
    'A bias of +10% means forecasts are 10% too high on average.',
    'High bias buys too much; low bias causes waits.'),
  E('oem_quote', 'OEM quoted rate', "manufacturer's quoted failure rate", 'Forecasting',
    'How often the maker says a part will fail. Real use can differ.',
    'A part removed 2.5× faster than quoted needs a closer look.',
    'Plans built on quotes alone can miss the real need.', ['quoted rate', 'OEM quote']),

  // ---------------------------------------------------------------- plans and money
  E('policy', 'policy', 'stocking plan', 'Plans and money',
    'A full set of rules for how many spares to hold of each part, and where.',
    'The Network Plan is one policy.',
    'This site compares a few plans on the same test runs.', ['policies', 'plan']),
  E('capital', 'inventory capital', 'money tied up in spare parts', 'Plans and money',
    'The assumed value of the spare parts held, on average, in the simulation.',
    'AED 50M of spares on shelves and in repair.',
    'Money in spares cannot be used elsewhere.', ['capital', 'inventory value']),
  E('holding_cost', 'carrying cost', 'yearly cost of holding a spare', 'Plans and money',
    'The cost each year of owning a spare: money, storage and ageing. An assumed rate here.',
    'At 20% a year, a AED 100,000 spare costs AED 20,000 a year to hold.',
    'It is the price paid for fewer waits.', ['holding cost']),
  E('aog_penalty', 'AOG penalty', 'assumed cost of an hour grounded', 'Plans and money',
    'A planning assumption for what one grounded hour costs. Results are shown at half and double this value too.',
    'At the base value, saving 100 hours is worth a set amount of money.',
    'It turns grounded hours into money so plans can be compared.', ['downtime penalty']),
  E('guardrails', 'guardrails', 'planning limits the plan must respect', 'Plans and money',
    'Practical limits on any plan, like not putting brakes outside the hub.',
    'The Network Plan held to guardrails drops spares that break a limit.',
    'They keep the maths from suggesting things a planner would not do.', ['stocking guardrails']),
  E('marginal', 'marginal allocation', 'adding spares one at a time, best value first', 'Plans and money',
    'Buy the one spare that cuts the most waits per dirham, then repeat.',
    'The first spare cuts 40 hours, the tenth only 2.',
    'It is how the frontier plans were built.', ['greedy allocation', 'greedy']),
  E('total_cost', 'total annual cost', 'yearly cost including downtime', 'Plans and money',
    'Carrying cost of spares plus rescue costs plus the assumed cost of grounded hours.',
    'A plan with more spares can still cost less in total.',
    'It weighs money spent against downtime avoided.'),

  // ---------------------------------------------------------------- testing and results
  E('simulation', 'simulation', 'computer model of the airline', 'Testing and results',
    'A model that plays out flights, failures, repairs and shipments hour by hour. All data here is simulated.',
    'Each test run is one simulated year for a fictional airline.',
    'It lets us test plans safely, but results depend on its assumptions.', ['simulated']),
  E('seed', 'seed', 'test run', 'Testing and results',
    'A number that fixes the random events in one simulated run.',
    'Seed 2000 is the first of the 20 fresh test runs.',
    'Same seed, same events: that keeps comparisons fair.', ['seeds', 'random seed']),
  E('selection_seeds', 'selection seeds', 'tuning runs', 'Testing and results',
    'The runs used to pick and tune plans, kept apart from the fresh test runs.',
    'Seeds 100 to 119 were used to choose plans.',
    'Results are reported on fresh runs, not on these.', ['selection']),
  E('calibration', 'calibration', 'tuning the starting point', 'Testing and results',
    'Adjusting the model so the starting-point plan lands in a chosen target range. That range was an assumption.',
    'The Simple Rulebook was tuned to land in a set range of grounded hours.',
    'All results depend on this choice.'),
  E('stress_worlds', 'stress worlds', 'easier and tougher test worlds', 'Testing and results',
    'Re-runs with parts failing a little less or more often: reliability ×0.96, ×1.00 and ×1.08. A narrow range.',
    'In the tougher world parts fail 8% more often.',
    'It checks that a result is not a fluke of one setting.', ['stress world', 'variants']),
  E('postplan', 'post-plan, exploratory', 'extra analysis added after the main test', 'Testing and results',
    'Work done after the main results were frozen. It is kept apart and does not change them.',
    'A donor recount added later is marked post-plan.',
    'It keeps the main results honest.', ['post-plan']),
];

const BY_KEY = new Map(ENTRIES.map((e) => [e.key, Object.freeze(e)]));

/** All glossary entries, sorted A–Z by the Simple wording (pass {sort: 'expert'} to sort by the expert term). */
export function glossaryEntries({ sort = 'simple' } = {}) {
  const k = sort === 'expert' ? 'expert' : 'simple';
  return [...BY_KEY.values()].sort((a, b) => a[k].localeCompare(b[k], 'en-GB', { sensitivity: 'base' }));
}
/** One entry by key (or alias, case-insensitive), or null. */
export function glossaryEntry(key) {
  if (BY_KEY.has(key)) return BY_KEY.get(key);
  const k = String(key ?? '').trim().toLowerCase();
  const all = [...BY_KEY.values()];
  // precedence: exact key → key (any case) → expert term → alias (so "Croston" is the croston entry, not the group)
  return BY_KEY.get(k) || all.find((e) => e.expert.toLowerCase() === k) || all.find((e) => e.aliases.some((a) => a.toLowerCase() === k)) || null;
}

const cap1 = (s) => s.charAt(0).toUpperCase() + s.slice(1);

/** The current mode's wording as a plain string (charts, aria-labels, table headers). opts: {mode, cap}. */
export function termText(key, { mode = getMode(), cap = false } = {}) {
  const e = glossaryEntry(key);
  if (!e) { if (window.__gnmDev) console.warn(`glossary: unknown term "${key}"`); return String(key); }
  const s = mode === 'expert' ? e.expert : e.simple;
  return cap ? cap1(s) : s;
}

// --------------------------------------------------------------------------- first-use tracking (per view)
const used = new Set();
/** Forget which terms were used (the router calls this before every view render). */
export function resetTermUses() { used.clear(); }

/**
 * Inline term element (see header). opts:
 *   cap: capitalise the first letter (sentence start)
 *   first: true forces the bracketed first-use form, false suppresses it (default: automatic, once per view)
 *   label: override the visible text (the tooltip and data-term still come from the entry)
 */
export function term(key, { cap = false, first, label } = {}) {
  const e = glossaryEntry(key);
  if (!e) { if (window.__gnmDev) console.warn(`glossary: unknown term "${key}"`); return document.createTextNode(String(label ?? key)); }
  installTermTips();
  const mode = getMode();
  const el = document.createElement('span');
  el.className = 'term';
  el.tabIndex = 0;
  el.dataset.term = e.key;
  el.setAttribute('aria-describedby', defId(e));
  const text = label ?? (mode === 'expert' ? e.expert : e.simple);
  el.append(document.createTextNode(cap ? cap1(text) : text));
  const isFirst = first ?? !used.has(e.key);
  used.add(e.key);
  if (mode === 'simple' && isFirst && e.expert.toLowerCase() !== text.toLowerCase()) {
    const s = document.createElement('small');
    s.className = 'term-expert';
    s.textContent = `(${e.expert})`;
    el.append(document.createTextNode(' '), s);
  }
  return el;
}

// --------------------------------------------------------------------------- tooltip (hover, focus, tap; Esc)
let defsHost = null, pop = null, pinned = null, installed = false;
function defId(e) {
  if (!defsHost) { defsHost = document.createElement('div'); defsHost.id = 'gnm-term-defs'; defsHost.hidden = true; document.body.append(defsHost); }
  const id = `gt-${e.key}`;
  if (!document.getElementById(id)) {
    const s = document.createElement('span');
    s.id = id;
    s.textContent = e.definition;
    defsHost.append(s);
  }
  return id;
}
function showTip(el) {
  const e = glossaryEntry(el.dataset.term);
  if (!e) return;
  if (!pop) { pop = document.createElement('div'); pop.className = 'term-pop'; pop.setAttribute('role', 'tooltip'); pop.id = 'gnm-term-pop'; document.body.append(pop); }
  const title = document.createElement('div');
  title.className = 'term-pop-title';
  title.textContent = getMode() === 'expert' || e.simple === e.expert ? e.expert : `${cap1(e.simple)} (${e.expert})`;
  const body = document.createElement('p');
  body.textContent = e.definition;
  const more = document.createElement('a');
  more.href = `#/glossary?term=${encodeURIComponent(e.key)}`;
  more.className = 'term-pop-link';
  more.textContent = 'Glossary';
  more.tabIndex = -1;
  pop.replaceChildren(title, body, more);
  pop.classList.add('is-on');
  const r = el.getBoundingClientRect(), pr = pop.getBoundingClientRect();
  let x = Math.max(8, Math.min(r.left, innerWidth - pr.width - 8));
  let y = r.bottom + 6;
  if (y + pr.height > innerHeight - 8) y = Math.max(8, r.top - pr.height - 6);
  pop.style.left = `${x}px`; pop.style.top = `${y}px`;
  el.setAttribute('aria-expanded', 'true');
}
export function hideTermTip() {
  pop?.classList.remove('is-on');
  document.querySelectorAll('.term[aria-expanded="true"]').forEach((t) => t.removeAttribute('aria-expanded'));
  pinned = null;
}
/** Install the delegated tooltip listeners once (term() calls it; safe to call again). */
export function installTermTips() {
  if (installed) return;
  installed = true;
  const termOf = (t) => t?.closest?.('.term[data-term]');
  document.addEventListener('mouseover', (ev) => { const t = termOf(ev.target); if (t) showTip(t); });
  document.addEventListener('mouseout', (ev) => { const t = termOf(ev.target); if (t && !t.contains(ev.relatedTarget) && pinned !== t && document.activeElement !== t) hideTermTip(); });
  document.addEventListener('focusin', (ev) => { const t = termOf(ev.target); if (t) showTip(t); });
  document.addEventListener('focusout', (ev) => { const t = termOf(ev.target); if (t && pinned !== t) hideTermTip(); });
  document.addEventListener('click', (ev) => {
    const t = termOf(ev.target);
    if (t) { if (pinned === t) hideTermTip(); else { showTip(t); pinned = t; } return; }
    if (pinned && !ev.target.closest?.('.term-pop')) hideTermTip();
  });
  document.addEventListener('keydown', (ev) => {
    const t = termOf(ev.target);
    if (ev.key === 'Escape' && pop?.classList.contains('is-on')) { hideTermTip(); return; }
    if (t && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); if (pinned === t) hideTermTip(); else { showTip(t); pinned = t; } }
  });
  addEventListener('hashchange', hideTermTip);
  // on scroll a tip closes, unless its term has keyboard focus (focusing a term below the fold scrolls the page):
  // then it follows the term instead
  addEventListener('scroll', () => {
    if (!pop?.classList.contains('is-on')) return;
    const f = termOf(document.activeElement);
    if (f) showTip(f); else hideTermTip();
  }, { passive: true, capture: true });
}
