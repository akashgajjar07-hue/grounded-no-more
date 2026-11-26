"""Unit-style browser checks for the shared UI / chart APIs added by design-fix-shared."""
from __future__ import annotations

import pytest

from _sitefx import browser, open_page, site  # noqa: F401

pytestmark = pytest.mark.browser

JS = r"""async () => {
  const T = await import('./js/charts/theme.js');
  const U = await import('./js/ui.js');
  const out = {};
  out.weeks = [T.fmtWeek(103), T.fmtWeek('W103'), T.fmtWeek(102.6), T.fmtWeek(null), T.fmtWeekRange(104, 155)];
  out.capital = [T.fmtCapitalDelta(5.04e6), T.fmtCapitalDelta(-3.6e6)];
  // dodge: two labels on top of each other + a marker under the first one
  const obstacles = [T.markerRect(10, 50, 5)];
  const labels = T.dodge([{ x: 0, y: 50, text: 'Reliability-exposure' }, { x: 0, y: 52, text: 'Moving average' }],
                         { gap: 14, obstacles, bounds: { x: -20, y: 0, width: 300, height: 200 } });
  const boxes = labels.map((l) => T.labelBox({ ...l, height: 14 }));
  const ov = (a, b) => Math.max(0, Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x)) * Math.max(0, Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y));
  out.dodgeLabelOverlap = ov(boxes[0], boxes[1]);
  out.dodgeMarkerOverlap = boxes.reduce((s, b) => s + ov(b, obstacles[0]), 0);
  // labelAround: away from the centroid
  const p = T.labelAround({ x: 100, y: 100 }, { r: 5, text: 'Label', centroid: { x: 50, y: 100 } });
  out.around = p;
  // chipLabel + refLine draw into an attached svg
  const host = document.createElement('div'); document.body.append(host);
  const svg = T.svgIn(host, 200, 100);
  const chip = T.chipLabel(svg, { x: 100, y: 50, text: '39' });
  out.chipBox = chip.datum().box;
  out.chipHasRect = !!chip.select('rect').node();
  T.refLine(svg, { x1: 0, y1: 20, x2: 200, y2: 20, label: 'naive = 1.0' });
  out.refDash = getComputedStyle(svg.select('.gnm-ref-line').node()).strokeDasharray;
  const lbl = T.directLabel(svg, { x: 10, y: 10, text: 'x' });
  out.halo = getComputedStyle(lbl.node()).paintOrder;
  out.accents = T.lintAccents(host);
  host.remove();
  out.series = Object.keys(T.theme.series);
  // story card never overlaps the target when there is room
  const r = { left: 100, top: 100, right: 500, bottom: 400, width: 400, height: 300 };
  out.card = U.storyCardPosition(r, { cw: 380, ch: 240, vw: 1440, vh: 900 });
  // KPI capital delta is neutral
  const k = U.kpiTile({ id: 'spare_capital_aed', label: 'Spare capital', value: 41e6, baseline: 36e6, delta: 5e6, better: 'lower', provenance: 'SIMULATED' }, { format: T.fmtAED });
  out.kpiClass = k.querySelector('.kpi-delta').className;
  out.kpiText = k.querySelector('.kpi-delta').textContent;
  const k2 = U.kpiTile({ id: 'aog', label: 'AOG', value: 300, baseline: 200, delta: 100, better: 'lower', provenance: 'SIMULATED' }, { format: T.fmtHours });
  out.kpi2Class = k2.querySelector('.kpi-delta').className;
  return out;
}"""

TABLE_JS = r"""async () => {
  const U = await import('./js/ui.js');
  const rows = Array.from({ length: 6 }, (_, i) => ({ pn: `GN-32-R0${10 + i}`, desc: 'Brake assembly', risk: 90 - i, stock: i, station: 'BOM' }));
  const t = U.dataTable({ columns: [{ key: 'pn', label: 'Part number', mono: true }, { key: 'desc', label: 'Description' }, { key: 'station', label: 'Station' },
    { key: 'risk', label: 'Risk', num: true }, { key: 'stock', label: 'Stock', num: true }], rows, sort: { key: 'risk', dir: 'desc' },
    mobileColumns: ['pn', 'risk', 'stock'], stickyFirst: true, caption: 'test' });
  document.querySelector('#view').prepend(t);
  await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 50)));
  const vis = (el) => !!el && getComputedStyle(el).display !== 'none' && el.getBoundingClientRect().height > 0;
  const res = {
    tableVisible: vis(t.querySelector('table')),
    stackRows: t.querySelectorAll('.dts-row').length,
    stackVisible: vis(t.querySelector('.data-table-stack')),
    firstPrimary: t.querySelector('.dts-primary')?.textContent,
    firstMetric: t.querySelector('.dts-metric')?.textContent,
    descHidden: !vis(t.querySelector('tbody td:nth-child(2)')),
    sticky: getComputedStyle(t.querySelector('tbody td:first-child')).position,
  };
  t.querySelector('.dts-sort button')?.click();
  res.afterToggle = t.querySelector('.dts-primary')?.textContent;
  t.remove();
  return res;
}"""


def test_shared_chart_and_ui_apis(site, browser):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/method", "1440")
    try:
        out = page.evaluate(JS)
        assert out["weeks"] == ["W103", "W103", "W103", "—", "W104–W155"]
        assert out["capital"] == ["+AED 5M more capital", "AED 3.6M less capital"]
        assert out["dodgeLabelOverlap"] == 0 and out["dodgeMarkerOverlap"] == 0, out
        assert out["around"]["anchor"] == "start" and out["around"]["x"] > 100
        assert out["chipHasRect"] and out["chipBox"]["width"] > 12
        assert out["refDash"].replace("px", "").replace(",", " ").split()[:2] == ["4", "4"]
        assert out["halo"].startswith("stroke")
        assert set(["baseline", "recommended", "reference", "neutral"]) <= set(out["series"])
        assert out["card"]["overlap"] == 0 and out["card"]["side"] == "right"
        assert "is-neutral" in out["kpiClass"] and "more capital" in out["kpiText"]
        assert "is-bad" in out["kpi2Class"]
        assert not problems, problems
    finally:
        ctx.close()


@pytest.mark.parametrize("vp", ["1440", "390"])
def test_data_table_mobile_modes(site, browser, vp):  # noqa: F811
    ctx, page, problems = open_page(browser, site + "#/method", vp)
    try:
        res = page.evaluate(TABLE_JS)
        assert res["sticky"] == "sticky"
        if vp == "1440":
            assert res["tableVisible"] and not res["stackVisible"] and not res["descHidden"], res
        else:
            assert not res["tableVisible"] and res["stackVisible"], res
            assert res["stackRows"] == 6
            assert res["firstPrimary"] == "GN-32-R010" and "90" in res["firstMetric"], res
            assert res["afterToggle"] == "GN-32-R015", res  # ascending risk after the direction toggle
        assert not problems, problems
    finally:
        ctx.close()
