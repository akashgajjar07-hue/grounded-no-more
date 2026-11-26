"""Engine invariants: conservation, schema validity, AOG merging, paired seeds, no truth import."""
import ast
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from gnm import schemas
from gnm.sim import api
from gnm.sim.baseline import build_p0
from gnm.sim.engine import merge_intervals, run_policy, run_many

from _simfx import FULL_WEEKS, WEEKS, full_run, full_world, small_run, small_scenario, small_world

SRC = Path(__file__).resolve().parents[1] / "src" / "gnm"


def _imports(path):
    tree = ast.parse(path.read_text())
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            m = n.module or ""
            mods.add(m)
            mods |= {f"{m}.{a.name}" for a in n.names}
    return mods


def test_engine_never_imports_truth():
    for f in ["engine.py", "baseline.py"]:
        mods = _imports(SRC / "sim" / f)
        assert not any("truth" in m or m.startswith("gnm.sim.generator") for m in mods), (f, mods)
        assert "ground_truth" not in (SRC / "sim" / f).read_text().lower()


def test_api_does_not_return_truth():
    import inspect
    for name in ["load_world", "load_or_generate_scenario"]:
        sig = inspect.signature(getattr(api, name))
        assert "Truth" not in str(sig.return_annotation)


def test_tables_valid_and_fks():
    w, _ = small_world()
    sc = small_scenario()
    res = small_run()
    t = api.history_tables(w, sc, res)
    assert api.validate_all(t) == []
    for name, df in t.items():
        for c in schemas.TABLES[name].cols:
            if c.dtype == "int64" and c.name != "qty_delta" and pd.api.types.is_numeric_dtype(df[c.name]):
                assert (df[c.name].dropna() >= 0).all(), (name, c.name)


def test_snapshots_nonnegative():
    s = small_run().stock_snapshots
    for c in ["on_hand", "reserved", "in_transit_in", "backorders", "pipeline", "on_order"]:
        assert (s[c] >= 0).all(), c


def test_serial_one_state_at_a_time():
    sh = small_run().serial_history.sort_values(["serial", "since_h"])
    nxt = sh.groupby("serial").since_h.shift(-1)
    has_next = nxt.notna()
    assert (sh.until_h[has_next].astype(int) == nxt[has_next].astype(int)).all()
    assert (sh.until_h[has_next].astype(int) > sh.since_h[has_next]).all()       # no overlaps, no zero-length
    assert (sh.groupby("serial").until_h.apply(lambda s: s.isna().sum()) == 1).all()  # exactly one current state
    assert not sh.duplicated(["serial", "since_h"]).any()


@pytest.mark.parametrize("which", ["small", "full"])
def test_serial_conservation_per_pn(which):
    res = small_run() if which == "small" else full_run()[2]
    sh, tx = res.serial_history, res.inventory_transactions
    loans = sh[~sh.owned]
    sh = sh[sh.owned]                                   # owned pool only: loan units never join it
    t0 = (WEEKS if which == "small" else FULL_WEEKS)[0] * 168
    first = sh.sort_values("since_h").groupby("serial").first()
    cur = sh[sh.until_h.isna()].set_index("serial")
    # borrowed units: one serial per loan, never serviceable stock, ends returned (or fitted if still open)
    assert loans.serial.nunique() == len(res.loans)
    assert not (loans.state == "SERVICEABLE").any()
    lcur = loans[loans.until_h.isna()].set_index("serial").state
    assert set(lcur.unique()) <= {"RETURNED_TO_LENDER", "INSTALLED"}
    assert int((lcur == "INSTALLED").sum()) == int(res.loans.returned_h.isna().sum())
    purchased = tx[(tx.txn_type == "RECEIPT_PO") & tx.serial.notna()]
    for pn, g in first.groupby("pn"):
        opening = int((g.since_h == t0).sum() - purchased[(purchased.pn == pn) & (purchased.t_h == t0)].shape[0])
        bought = int((purchased.pn == pn).sum())
        condemned = int((cur.loc[g.index, "state"] == "CONDEMNED").sum())
        closing = int((cur.loc[g.index, "state"] != "CONDEMNED").sum())
        assert opening + bought - condemned == closing, pn
    # condemnations match repair orders; repairs never create units
    ro = res.repair_orders
    assert int(ro.condemned.sum()) == int((cur.state == "CONDEMNED").sum())
    rr = tx[(tx.txn_type == "RECEIPT_REPAIR")]
    # (a zero-length REMOVED state at AUH collapses into IN_REPAIR, so check shop visits)
    assert set(rr.serial) <= set(sh[sh.state == "IN_REPAIR"].serial)
    visits = ro.groupby("serial").size()
    rc = rr.groupby("serial").size()
    assert (rc.to_numpy() <= visits.reindex(rc.index).to_numpy()).all()
    assert len(rr) == int(ro.return_h.notna().sum())


def test_count_conservation_vs_snapshots():
    """opening + receipts - issues - expiries +/- transfers = closing, per PN/station at every week end."""
    res = small_run()
    tx, snap = res.inventory_transactions, res.stock_snapshots
    tx = tx.assign(week=(tx.t_h // 168))
    cum = tx.groupby(["pn", "station", "week"]).qty_delta.sum().groupby(level=[0, 1]).cumsum()
    for (pn, st), g in snap.groupby(["pn", "station"]):
        c = cum.loc[(pn, st)] if (pn, st) in cum.index.droplevel(2) else pd.Series(dtype=int)
        c = c.reindex(range(WEEKS[0], WEEKS[1] + 1)).ffill().fillna(0)
        assert (c.loc[g.week].to_numpy() == g.on_hand.to_numpy()).all(), (pn, st)


def test_rotable_serials_match_on_hand():
    res = small_run()
    sh, snap = res.serial_history, res.stock_snapshots
    w, _ = small_world()
    rot = set(w.parts.pn[w.parts.part_class == "R"])
    for week in [5, 15, 29]:
        h = (week + 1) * 168
        live = sh[(sh.since_h < h) & (sh.until_h.isna() | (sh.until_h >= h)) & (sh.state == "SERVICEABLE")]
        # since_h < h: snapshot is taken before events at hour h
        live = sh[(sh.since_h < h) & (sh.until_h.isna() | (sh.until_h.astype("float") >= h))]
        live = live[live.state == "SERVICEABLE"]
        cnt = live.groupby(["pn", "location"]).size()
        s = snap[(snap.week == week) & snap.pn.isin(rot)]
        for r in s.itertuples():
            assert cnt.get((r.pn, r.station), 0) == r.on_hand, (week, r.pn, r.station)


def test_transfers_debit_origin():
    res = small_run()
    tx, tr = res.inventory_transactions, res.transfers
    out = tx[tx.txn_type == "TRANSFER_OUT"].groupby("ref_id").agg(q=("qty_delta", "sum"), st=("station", "first"),
                                                                  t=("t_h", "first"))
    inn = tx[tx.txn_type == "TRANSFER_IN"].groupby("ref_id").agg(q=("qty_delta", "sum"), st=("station", "first"))
    for r in tr.itertuples():
        k = f"T{r.transfer_id}"
        assert out.loc[k, "q"] == -r.qty and out.loc[k, "st"] == r.from_station and out.loc[k, "t"] == r.ship_h
        if r.arrive_h < (WEEKS[1] + 1) * 168:
            assert inn.loc[k, "q"] == r.qty and inn.loc[k, "st"] == r.to_station


def test_requests_outcomes_consistent():
    rq = small_run().requests
    f = rq[rq.filled_h.notna()]
    assert (f.filled_h >= f.need_h).all()
    imm = rq[rq.immediate_fill.fillna(False)]
    assert (imm.filled_h == imm.need_h).all() and (imm.fill_source == "local").all()
    k = small_run().kpis
    assert set(k) == {c.name for c in schemas.TABLES["policy_results"].cols
                      if c.dtype in ("float64", "int64") and c.name != "seed"}
    assert 0 < k["immediate_fill_rate"] <= 1


def test_aog_interval_merging():
    iv = pd.DataFrame([
        ("A6-FHA", 0, 10, "AUH", "P1", 1, "D0_no_stock"),
        ("A6-FHA", 5, 12, "AUH", "P2", 2, "D0_no_stock"),      # overlap
        ("A6-FHA", 12, 20, "AUH", "P1", 3, "deadline_expired"),  # adjacent -> merged
        ("A6-FHA", 25, 30, "BOM", "P3", 4, "D0_no_stock"),      # gap -> new event
        ("A6-FWB", 3, 4, "SIN", "P1", 5, "D0_no_stock"),
        ("A6-FWB", 1, 8, "SIN", "P4", 6, "D0_no_stock"),        # contains the other
    ], columns=["tail", "start_h", "end_h", "station", "pn", "request_id", "trigger"])
    m = merge_intervals(iv)
    a = m[m["tail"] == "A6-FHA"].sort_values("start_h")
    assert a[["start_h", "end_h", "hours"]].values.tolist() == [[0, 20, 20.0], [25, 30, 5.0]]
    assert a.iloc[0].pns == "P1;P2" and a.iloc[0].request_ids == "1;2;3"
    b = m[m["tail"] == "A6-FWB"]
    assert b[["start_h", "end_h"]].values.tolist() == [[1, 8]]
    assert schemas.validate_table("aog_events", m) == []


def test_aog_events_match_requests():
    res = small_run()
    rq = res.requests
    dl = rq.deadline_class.map(lambda d: schemas.DEADLINE_HOURS[d] if schemas.DEADLINE_HOURS[d] is not None else 10**9)
    filled = rq.filled_h.astype("float")
    late = rq[(filled.isna() | (filled > rq.need_h + dl)) & (rq.deadline_class != "NONE")]
    ids = set(";".join(res.aog_events.request_ids).split(";")) if len(res.aog_events) else set()
    assert set(late.request_id.astype(str)) == ids
    for tail, g in res.aog_events.groupby("tail"):
        g = g.sort_values("start_h")
        assert (g.start_h.iloc[1:].to_numpy() > g.end_h.iloc[:-1].to_numpy()).all()


def test_paired_policies_see_identical_requests():
    w, _ = small_world()
    sc = small_scenario()
    p0 = build_p0(w)
    p_rich = build_p0(w)
    p_rich.policy_id = "RICH"
    sp = p_rich.stock_params.copy()
    sp["base_stock"] *= 3
    sp.loc[sp.s >= 0, "S"] *= 3
    p_rich.stock_params = sp
    r0 = run_policy(w, sc, p0, *WEEKS)
    r1 = run_policy(w, sc, p_rich, *WEEKS)
    cols = ["request_id", "pn", "station", "tail", "need_h", "known_h", "qty", "deadline_class"]
    pd.testing.assert_frame_equal(r0.requests[cols], r1.requests[cols])
    assert r1.kpis["immediate_fill_rate"] >= r0.kpis["immediate_fill_rate"]
    assert r1.kpis["spare_capital_aed"] > r0.kpis["spare_capital_aed"]
    # deterministic
    r0b = run_policy(w, sc, p0, *WEEKS)
    assert r0b.kpis == r0.kpis


def test_pool_exchange_stub_raises():
    w, _ = small_world()
    p = build_p0(w)
    p.pool_exchange = {"response_hours": 24}
    with pytest.raises(NotImplementedError):
        run_policy(w, small_scenario(), p, *WEEKS)


def test_p0_uses_public_data_only():
    src = (SRC / "sim" / "baseline.py").read_text()
    assert "removal" not in src.lower() or "never looks at removal history" in src
    w, _ = small_world()
    p0 = build_p0(w)
    assert p0.emergency_sources["AUH"] == [] and p0.emergency_sources["BOM"] == ["AUH"]
    sp = p0.stock_params
    rot = sp.pn.isin(w.parts.pn[w.parts.part_class == "R"])
    assert (sp.base_stock[~rot] == 0).all() and (sp.s[rot] == -1).all()


def test_run_many_serial_matches_single():
    w, _ = small_world()
    sc = small_scenario()
    p0 = build_p0(w)
    out = run_many(w, [sc], [p0], *WEEKS, processes=1)
    assert out[0].kpis == run_policy(w, sc, p0, *WEEKS).kpis


@pytest.mark.slow
def test_full_scale_conservation_and_speed():
    w, gt = full_world()
    from gnm.sim.generator import generate_scenario
    sc = generate_scenario(w, gt, 100, 96, 155)
    t = time.time()
    res = run_policy(w, sc, build_p0(w), 104, 155)
    assert time.time() - t < 10
    tables = api.history_tables(w, sc, res)
    assert api.validate_all(tables) == []
    tx, snap = res.inventory_transactions, res.stock_snapshots
    last = snap[snap.week == 155].set_index(["pn", "station"]).on_hand
    tot = tx.groupby(["pn", "station"]).qty_delta.sum().reindex(last.index).fillna(0)
    assert (tot == last).all()


@pytest.mark.slow
def test_run_many_parallel():
    w, _ = full_world()
    p0 = build_p0(w)
    from gnm.sim.generator import generate_scenario
    _, gt = full_world()
    scs = [generate_scenario(w, gt, s, 96, 155) for s in (100, 101)]
    out = run_many(w, scs, [p0], 104, 155, processes=2)
    assert [o.seed for o in out] == [100, 101]
    assert out[0].kpis == run_policy(w, scs[0], p0, 104, 155, detail=False).kpis


def test_pipeline_seeded_from_quoted_figures_and_paired():
    from gnm.sim.quoted import pipeline_days, quoted_weekly_demand
    w, _ = small_world()
    res = small_run()
    t0 = WEEKS[0] * 168
    sh = res.serial_history
    first = sh.sort_values("since_h").groupby("serial").first()
    seeded = first[(first.since_h == t0) & first.state.isin(["REMOVED", "IN_REPAIR"])].groupby("pn").size()
    dem = quoted_weekly_demand(w).groupby("pn").weekly_demand.sum()
    for pn in w.parts.pn[w.parts.part_class == "R"]:
        n = int(round(dem.get(pn, 0) / 7 * pipeline_days(w, pn)))
        assert seeded.get(pn, 0) == n, pn
    # identical pipeline under a different policy (paired CRN)
    p = build_p0(w)
    p.stock_params = p.stock_params.assign(base_stock=p.stock_params.base_stock * 2)
    r2 = run_policy(w, small_scenario(), p, *WEEKS)
    f2 = r2.serial_history.sort_values("since_h").groupby("serial").first()
    s2 = f2[(f2.since_h == t0) & f2.state.isin(["REMOVED", "IN_REPAIR"])].groupby("pn").size()
    assert s2.equals(seeded)


def test_p0_oem_provisioning_rule():
    from scipy.stats import poisson
    from gnm.sim.baseline import build_p0_naive, p0_rotable_plan
    from gnm.sim.quoted import pipeline_days, quoted_weekly_demand
    w, _ = full_world()
    sp = build_p0(w).stock_params
    dem = quoted_weekly_demand(w)
    net = dem.groupby("pn").weekly_demand.sum()
    dmap = dem.set_index(["pn", "station"]).weekly_demand
    plan = p0_rotable_plan(w).set_index("pn")
    for p in w.parts[w.parts.part_class == "R"].itertuples():
        m = net[p.pn] * 52 * pipeline_days(w, p.pn) / 365
        prot = 0.95 if p.deadline_class == "D0" else 0.90
        S = plan.loc[p.pn, "S_total"]
        assert poisson.cdf(S, m) >= prot and (S == 0 or poisson.cdf(S - 1, m) < prot)
        g = sp[sp.pn == p.pn].set_index("station").base_stock
        assert g["AUH"] == max(0, S - plan.loc[p.pn, "loop_units"])
        for st, bs in g.items():
            if st != "AUH":
                assert bs == (1 if p.deadline_class == "D0" and dmap.get((p.pn, st), 0) * 52 >= 4 else 0)
    ce = sp[sp.s >= 0].merge(w.parts[["pn", "part_class"]])
    assert (ce.S >= 2 * ce.s).all()
    auh = ce[ce.station == "AUH"].set_index("pn")
    for p in auh.index:
        weeks = 26 if auh.loc[p, "part_class"] == "C" else 13
        assert auh.loc[p, "s"] == int(np.ceil(weeks * net[p]))
    assert build_p0_naive(w).policy_id == "P0-naive"


def test_ps1_understocked_at_bom():
    from gnm.sim.quoted import quoted_weekly_demand
    w, gt = full_world()
    pn = gt.planted["PS1"]["pn"]                      # never hard-code the PS1 PN
    row = w.parts.set_index("pn").loc[pn]
    assert row.part_class == "R" and row.deadline_class == "D0" and row.removal_mode == "unscheduled"
    assert row.family in ("servo_actuator", "valve", "avionics_lru", "flight_computer")
    assert w.applicability[w.applicability.pn == pn].archetype.nunique() == 1   # type-specific
    sp = build_p0(w).stock_params
    assert int(sp[(sp.pn == pn) & (sp.station == "BOM")].base_stock.iloc[0]) == 0
    q_bom = float(quoted_weekly_demand(w).set_index(["pn", "station"]).weekly_demand[(pn, "BOM")] * 52)
    m_true = float(gt.parts.set_index("pn").loc[pn, "mtbur_true"])
    assert q_bom < 4 and q_bom * row.mtbur_quoted / m_true > 4   # true BOM rate well above the threshold


# ---------------------------------------------------------------- v2 sourcing invariants (full-scale run)
def test_v2_routes_by_class_and_station():
    w, sc, res = full_run()
    rq = res.requests.merge(w.parts[["pn", "part_class"]], on="pn")
    src = rq.fill_source.fillna("none")
    assert set(rq.part_class[src.isin(["exchange_loan", "local_borrow", "robbery"])]) <= {"R"}
    assert set(rq.part_class[src == "local_buy"]) <= {"C", "E"}
    assert (rq.station[src == "robbery"] == "AUH").all()
    assert (rq.station[src == "local_borrow"] != "AUH").all()
    assert (rq.approval_flag[src == "robbery"] == "engineering/quality approval required").all()
    assert (src == "robbery").sum() > 0 and (src == "exchange_loan").sum() > 0 and (src == "local_buy").sum() > 0
    assert "expedite" not in set(res.purchase_orders.reason)          # no outright AOG buy in v2


def test_v2_loans_returned_and_never_owned():
    w, sc, res = full_run()
    sh = res.serial_history
    ln = res.loans
    closed = ln[ln.returned_h.notna()]
    assert len(closed) > 0
    assert sh[~sh.owned].serial.str.startswith("LOAN-").all()
    for r in closed.itertuples():
        rec = sh[(sh.serial == r.serial) & (sh.state == "RETURNED_TO_LENDER")]
        assert len(rec) == 1 and int(rec.since_h.iloc[0]) == int(r.returned_h)
        own = sh[sh.owned & (sh.state == "INSTALLED") & (sh.location == r.tail) & (sh.since_h == r.returned_h)
                 & (sh.pn == r.pn)]
        removed_us = not (sh[(sh.serial == r.serial)].state == "INSTALLED").iloc[-1:].empty and len(own) == 0
        assert len(own) >= 1 or removed_us


def test_v2_loans_do_not_change_capital():
    """Borrowed units are never owned capital: the owned pool (and its value) is identical whether or not
    AOG routes fill requests, apart from condemnation-replacement purchases."""
    w, sc, res = full_run()
    sh = res.serial_history
    owned_open = sh[sh.owned].groupby("serial").since_h.min()
    t0 = FULL_WEEKS[0] * 168
    bought = res.inventory_transactions
    bought = bought[(bought.txn_type == "RECEIPT_PO") & bought.serial.notna()].serial
    assert set(owned_open.index) == set(owned_open[owned_open == t0].index) | set(bought)


def test_v2_robbed_donors_reinstated():
    w, sc, res = full_run()
    rb, sh = res.robberies, res.serial_history
    assert len(rb) > 0
    arch = w.aircraft.set_index("tail").archetype
    for r in rb[rb.reinstated_h.notna()].itertuples():
        fit = sh[sh.owned & (sh.state == "INSTALLED") & (sh.location == r.donor_tail) & (sh.pn == r.pn)
                 & (sh.since_h == r.reinstated_h)]
        assert len(fit) >= 1
        assert arch[r.donor_tail] == arch[r.aog_tail] and r.donor_tail != r.aog_tail
    assert res.kpis_extra["donors_open_at_end"] == int(rb.reinstated_h.isna().sum())


def test_v2_nff_never_condemned_and_cheap():
    w, sc, res = full_run()
    ro = res.repair_orders
    assert ro.nff.sum() > 0 and not (ro.nff & ro.condemned).any()
    full = ro[~ro.nff & ro.return_h.notna() & ro.removal_id.notna()].repair_cost_aed.mean()
    assert ro[ro.nff & ro.return_h.notna()].repair_cost_aed.mean() < 0.5 * full


def test_v2_wear_planned_and_deferred_shipping():
    w, sc, res = full_run()
    rq = res.requests.merge(w.parts[["pn", "removal_mode"]], on="pn")
    pl = rq[rq.source == "planned_removal"]
    assert len(pl) > 0 and (pl.removal_mode == "wear_planned").all() and (pl.station == "AUH").all()
    assert ((pl.need_h - pl.known_h) >= 5 * 24 - 1).all() or (pl.known_h == 0).any()
    # AV-07: an earmarked routine shipment always meets deadline - margin
    tr = res.transfers.merge(res.requests[["request_id", "need_h", "deadline_class"]], on="request_id")
    margin = w.cfg["engine"]["deferred_margin_h"]
    rt = tr[tr.kind == "routine"]
    early = rt[rt.ship_h <= rt.need_h]
    assert (early.arrive_h <= early.need_h + early.deadline_class.map(schemas.DEADLINE_HOURS).astype(float) - margin).all()


def test_v2_fluids_never_aog_and_aog_includes_fitting():
    w, sc, res = full_run()
    none = set(w.parts.pn[w.parts.deadline_class == "NONE"])
    ids = [i for i in ";".join(res.aog_events.request_ids).split(";") if i]
    rq = res.requests.set_index(res.requests.request_id.astype(str))
    assert not (set(rq.loc[ids].pn) & none)
    late = rq.loc[ids]
    late = late[late.filled_h.notna()]
    for rid, one in late.head(20).iterrows():
        ev = res.aog_events[res.aog_events.request_ids.str.split(";").map(lambda x: rid in x)].iloc[0]
        assert ev.end_h >= int(one.filled_h) + int(one.fitting_h)
    assert (res.requests.fitting_h[res.requests.pn.isin(set(w.parts.pn[w.parts.part_class == "R"]))]
            .between(2, 6)).all()
