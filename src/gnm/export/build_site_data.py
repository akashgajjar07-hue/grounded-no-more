"""Build the web app's data files (docs/data/*.json) from pipeline outputs.

READ-ONLY with respect to the pipeline: this module only reads files that already exist in
`outputs/`, `data/processed/history/`, `data/source_manifest.csv`, `config/` and a few docs at the
repo root. It never re-runs a simulation, a forecast or the optimiser, and it never reads hidden
truth tables. The only truth-derived numbers are the evaluation results already written to
`outputs/holdout/truth_recovery.json` (DERIVED).

Every file is `{"meta": {generated_at, git_sha, provenance, source, notes}, ...payload}` and keeps
the shape of the matching fixture in docs/data/fixtures/ (fields are only ever added).

Rounding: money (keys containing aed / capital / cost / stock_value / budget / exposure ...) to the
whole AED, every other float to 4 significant digits, lat/lon to 4 decimals.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from gnm.config import HOURS_PER_WEEK, ROOT, load_config
from gnm.export import v21

OUT = ROOT / "outputs"
HIST = ROOT / "data" / "processed" / "history"
SITE = ROOT / "docs" / "data"

FILES = ["kpis", "parts", "demand_history", "forecast", "rotables", "network", "frontier",
         "policies", "aog_lab", "actions", "method", "story"]
MAX_TOTAL_BYTES = 4 * 1024 * 1024
EXPECTED_RECOMMENDED = "I125"
BASELINE = "P0"
BASE_POLICY = "P2"
HISTORY_WEEKS = 104                      # weeks 0-103
AS_OF_H = HISTORY_WEEKS * HOURS_PER_WEEK  # end of history (start of week 104)
SPLIT_WEEK = 78
ALLOC_ROWS_PER_POINT = 40

# risk bands on risk_hours (AOG h / yr attributable to the PN, see parts.json meta.notes)
RISK_URGENT_H = 25.0
SYS_URGENT_SHARE = 0.15   # ASSUMED: chapter share of fleet risk-hours for 'urgent'
SYS_REVIEW_SHARE = 0.07
RISK_REVIEW_H = 5.0
# outstation-relative risk bands (share of the riskiest OUTSTATION's P0 holdout AOG h); ASSUMED
OUT_URGENT_REL = 0.8
OUT_REVIEW_REL = 0.5
AOG_LOOKBACK_WEEKS = 52   # same window as the planner action centre (config/aog_lab.yaml depletion_lookback_weeks)
# the ONE set of per-PN AOG-hour metrics shown on Mission, Parts and Actions (parts.json -> aog_metric_labels)
AOG_METRIC_LABELS = {
    "aog_h_2y": {"label": "AOG h · 2-yr history · all stations", "short": "AOG h 2 yr",
                 "definition": "Hours of every history AOG event (weeks 0-103, P0 world) that waited on this PN, all stations."},
    "aog_h_52w": {"label": "AOG h · last 52 wk · all stations", "short": "AOG h 52 wk",
                  "definition": "Same events, last 52 weeks of history only (W52-W103), summed over all stations."},
    "aog_h_52w_max_station": {"label": "AOG h · last 52 wk · worst station", "short": "max AOG h at one station",
                              "definition": "The largest single-station total in the last 52 weeks (station in aog_h_52w_max_station_id)."},
}

METHOD_LABELS = {
    "naive": "Naive (last value)", "ma": "Moving average", "croston": "Croston", "sba": "SBA",
    "tsb": "TSB", "adida": "ADIDA", "imapa": "IMAPA", "bootstrap": "Bootstrap (Willemain)",
    "reliability": "Reliability-exposure (FH/FC)", "zero": "Zero (benchmark, not eligible)",
}
# v2.1 (A3): the exported policy label IS the display name; codes stay in policy_id / id (docs/js/lib/names.js mirrors it)
POLICY_LABELS = {k: v21.DISPLAY_NAMES[k] for k in ("P0", "P1", "P2", "I125")}
# data-story ids the story steps target for the current world (network-<station> follows the narrated incident)
STORY_IDS = ["aog-incident-ps1", "aircraft", "rotable-float-calc", "network-bom", "action-inbox", "frontier-chart"]

# ----------------------------------------------------------------------------------------------
# helpers


def git_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                           text=True, check=True)
        return r.stdout.strip() or "unknown"
    except Exception:  # pragma: no cover - no git available
        return "unknown"


_MONEY = re.compile(r"(aed|capital|cost|stock_value|budget|exposure|net_benefit|swing|spend|price)", re.I)
_NOT_MONEY = re.compile(r"(per_aed|h_star|_pct|carrying_pct|share|ratio|_per_1m)", re.I)
_DECIMAL4 = {"lat", "lon"}


def sig(x: float, n: int = 4):
    """Round to n significant digits; integral results come back as int."""
    if x == 0 or not math.isfinite(x):
        return x
    r = float(f"{x:.{n}g}")
    return int(r) if r == int(r) and abs(r) >= 1 else r


def aed(x):
    """Money to the whole AED (int)."""
    if x is None:
        return None
    x = float(x)
    if not math.isfinite(x):
        return None
    return int(round(x))


def _is_money(key: str) -> bool:
    return bool(_MONEY.search(key)) and not _NOT_MONEY.search(key)


def clean(obj, key: str = "", money: bool = False):
    """Recursively convert numpy/pandas scalars, round floats, NaN/inf -> None."""
    if isinstance(obj, dict):
        return {str(k): clean(v, str(k), money or _is_money(str(k))) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [clean(v, key, money) for v in obj]
    if isinstance(obj, np.ndarray):
        return [clean(v, key, money) for v in obj.tolist()]
    if obj is None or obj is pd.NA or obj is pd.NaT:
        return None
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        x = float(obj)
        if not math.isfinite(x):
            return None
        if key in _DECIMAL4:
            return round(x, 4)
        if money:
            return int(round(x))
        return sig(x)
    if isinstance(obj, int):
        return obj
    if isinstance(obj, (pd.Timestamp, dt.datetime, dt.date)):
        return obj.isoformat()
    return obj


def num(x):
    """float or None (NaN-safe)."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def tag(rows: list[dict], prov: str) -> list[dict]:
    for r in rows:
        r.setdefault("provenance", prov)
    return rows


def records(df: pd.DataFrame) -> list[dict]:
    return [{k: (None if (isinstance(v, float) and not math.isfinite(v)) or v is pd.NA else v)
             for k, v in r.items()} for r in df.to_dict(orient="records")]


def rel(path: Path) -> str:
    return str(Path(path).resolve().relative_to(ROOT))


def read_json(path: Path):
    with open(path) as f:
        return json.load(f)


def fmt_int(x) -> str:
    return f"{int(round(float(x))):,}"


def fmt_aed(x, digits: int = 1) -> str:
    """Same output as theme.js fmtAED (compact): AED 41.9M, AED 5M, AED 138k, AED 950."""
    v = float(x)
    a, sgn = abs(v), ("−" if v < 0 else "")
    def trim(t: str) -> str:
        return re.sub(r"\.0(?=\D|$)", "", t, count=1)
    if a >= 1e9:
        return f"AED {sgn}{trim(f'{a / 1e9:.{digits}f}')}B"
    if a >= 1e6:
        return f"AED {sgn}{trim(f'{a / 1e6:.{digits}f}')}M"
    if a >= 1e3:
        return f"AED {sgn}{int(a / 1e3 + 0.5)}k"
    return f"AED {sgn}{int(a + 0.5)}"


fmt_aed_m = fmt_aed   # legacy name: story money uses the site's ONE compact money format


def fmt_pct(x, d=1) -> str:
    return f"{100 * float(x):.{d}f}%"


def nondominated(points: list[tuple[str, float, float]]) -> dict[str, bool]:
    """Return {id: dominated} for (id, capital, aog_hours) minimisation on both axes.

    A point is dominated when another point is no worse on both axes and strictly better on at
    least one. Ties on both axes do not dominate each other."""
    out = {}
    for pid, c, a in points:
        out[pid] = any((c2 <= c and a2 <= a) and (c2 < c or a2 < a)
                       for pid2, c2, a2 in points if pid2 != pid)
    return out


# ----------------------------------------------------------------------------------------------
# cached inputs


@lru_cache(maxsize=None)
def cfg() -> dict:
    return load_config()


@lru_cache(maxsize=None)
def hist(name: str) -> pd.DataFrame:
    return pd.read_parquet(HIST / f"{name}.parquet")


@lru_cache(maxsize=None)
def jload(relpath: str):
    return read_json(ROOT / relpath)


@lru_cache(maxsize=None)
def csv(relpath: str) -> pd.DataFrame:
    return pd.read_csv(ROOT / relpath)


@lru_cache(maxsize=None)
def pq(relpath: str) -> pd.DataFrame:
    return pd.read_parquet(ROOT / relpath)


def stations() -> list[str]:
    n = cfg()["network"]
    return [n["hub"], *n["outstations"]]


def ata_names() -> dict:
    return {str(k): v for k, v in cfg()["parts"]["ata_chapters"].items()}


def ps1() -> dict:
    """The narrated PS1 incident: read from aog_lab incidents.json (ps1_incident_id), never hard-coded."""
    a = jload("outputs/aog_lab/incidents.json")
    iid = a.get("ps1_incident_id")
    inc = next((i for i in a["incidents"] if i["id"] == iid), None) or next((i for i in a["incidents"] if i.get("planted") == "PS1"), a["incidents"][0])
    return {"incident_id": inc["id"], "pn": inc["pn"], "station": inc["station"], "incident": inc}


def planted_meta() -> dict:
    """Planted situations (truth_recovery.json, evaluation-only metadata): {PS1: {pn, station, weeks, note}, ...}."""
    return jload("outputs/holdout/truth_recovery.json").get("planted", {})


@lru_cache(maxsize=None)
def applicability() -> pd.DataFrame:
    """Fleet applicability per PN from config/part_catalogue.csv (NB / WB / BOTH, QPA by type), joined on ATA + description."""
    cat = pd.read_csv(ROOT / "config" / "part_catalogue.csv")
    pm = hist("part_master")[["pn", "ata", "description"]].copy()
    cat["ata"] = cat.ata.astype(str).str.zfill(2)
    pm["ata"] = pm.ata.astype(str).str.zfill(2)
    m = pm.merge(cat[["ata", "description", "applic", "qty_nb", "qty_wb"]], on=["ata", "description"], how="left")
    return m.set_index("pn")


def brake_note() -> str:
    """Parts-screen brake disclosure, from outputs/calibration/v2_p0_gap_diagnosis.md (the short '> Brakes:' draft)."""
    path = OUT / "calibration" / "v2_p0_gap_diagnosis.md"
    txt = path.read_text() if path.exists() else ""
    line = next((l[1:].strip() for l in txt.splitlines() if l.startswith("> Brakes:")), "")
    if not line:
        return ""
    return (line.replace("Any brake AOG shown", "Any brake downtime shown").replace("the WB/NB exchange", "the exchange"))


def holdout_central() -> dict:
    return jload("outputs/holdout/policy_summary.json")["variants"]["central"]


def frontier_holdout() -> pd.DataFrame:
    return csv("outputs/holdout/frontier_points.csv").set_index("id")


def selection_points(variant: str = "central") -> pd.DataFrame:
    s = csv("outputs/frontier/selection_points.csv")
    return s[s.variant == variant].set_index("id")


def recommended_id() -> str:
    summ = jload("outputs/frontier/summary.json")
    rid = summ["recommendation"]["recommended"]
    flagged = selection_points().query("recommended == True").index.tolist()
    if rid != EXPECTED_RECOMMENDED or flagged != [rid]:
        raise RuntimeError(f"recommended point is {rid} (flagged {flagged}); expected {EXPECTED_RECOMMENDED}")
    return rid


@lru_cache(maxsize=None)
def stock_table() -> pd.DataFrame:
    """Target units per (pn, station) for P0, P1, P2 and the recommended allocation.

    Rotables: serviceable base_stock (excludes the units the engine seeds in the repair loop).
    C/E: the order-up-to level S. The recommended allocation = P2 with the rows of
    outputs/frontier/allocations.json[<rec>] applied (proposed replaces current)."""
    frames = []
    for pid in ["P0", "P1", "P2"]:
        p = csv(f"outputs/policies/{pid}_stock_params.csv")
        frames.append(p.set_index(["pn", "station"])["target_units"].rename(pid))
    base = csv("outputs/policies/P2_stock_params.csv").set_index(["pn", "station"])
    t = pd.concat(frames, axis=1)
    t["unit_cost_aed"] = base["unit_cost_aed"]
    t["part_class"] = base["part_class"]
    rid = recommended_id()
    t[rid] = t["P2"]
    mism = []
    for r in jload("outputs/frontier/allocations.json")["allocations"][rid]:
        k = (r["pn"], r["station"])
        if int(t.at[k, "P2"]) != int(r["current"]):
            mism.append(k)
        t.at[k, rid] = r["proposed"]
    if mism:
        raise RuntimeError(f"allocation 'current' does not match P2 target units for {mism[:5]}")
    return t.reset_index()


@lru_cache(maxsize=None)
def part_attributes() -> pd.DataFrame:
    """ADI / CV2 / demand class / ABC on TRAINING weeks 0-77 (gnm.forecasting.classify)."""
    from gnm.forecasting.classify import build_part_attributes
    pm = hist("part_master")
    mr = hist("material_requests")
    d = (mr.groupby(["pn", "week"]).qty.sum().unstack(fill_value=0)
         .reindex(columns=range(HISTORY_WEEKS), fill_value=0).reindex(pm.pn, fill_value=0))
    return build_part_attributes(d, pm, (0, SPLIT_WEEK - 1))


@lru_cache(maxsize=None)
def demand_matrix() -> pd.DataFrame:
    pm = hist("part_master")
    mr = hist("material_requests")
    return (mr.groupby(["pn", "week"]).qty.sum().unstack(fill_value=0)
            .reindex(columns=range(HISTORY_WEEKS), fill_value=0).reindex(pm.pn, fill_value=0).astype(int))


@lru_cache(maxsize=None)
def risk_table() -> pd.DataFrame:
    """Transparent per-PN risk (see parts.json meta.notes)."""
    pm = hist("part_master").set_index("pn")
    years = HISTORY_WEEKS / 52.0
    ae = hist("aog_events").copy()
    ae["pn_list"] = ae.pns.astype(str).str.split(";")
    ae["share"] = ae.hours / ae.pn_list.str.len()
    ex = ae.explode("pn_list")
    hist_h = ex.groupby("pn_list").share.sum() / years
    hist_n = ex.groupby("pn_list").size()
    lev = csv("outputs/frontier/levers.csv").groupby("pn").base_aog_hours.first()
    rid = recommended_id()
    alloc = pd.DataFrame(jload("outputs/frontier/allocations.json")["allocations"][rid])
    red = alloc[alloc.part_class == "R"].groupby("pn").modelled_aog_hour_reduction.sum()
    t = pd.DataFrame(index=pm.index)
    t["aog_hours_hist_per_yr"] = hist_h.reindex(t.index).fillna(0.0)
    t["aog_events_hist"] = hist_n.reindex(t.index).fillna(0).astype(int)
    t["residual_modelled"] = t.index.isin(lev.index)
    t["residual_aog_h_per_yr"] = (lev.reindex(t.index).fillna(0.0) - red.reindex(t.index).fillna(0.0)).clip(lower=0.0)
    t["risk_hours"] = t.aog_hours_hist_per_yr + t.residual_aog_h_per_yr
    mx = float(t.risk_hours.max())
    t["risk_score"] = np.log1p(t.risk_hours) / math.log1p(mx) if mx > 0 else 0.0
    t["risk_level"] = np.where(t.risk_hours >= RISK_URGENT_H, "urgent",
                               np.where(t.risk_hours >= RISK_REVIEW_H, "review", "ok"))
    return t


@lru_cache(maxsize=None)
def aog_metrics() -> pd.DataFrame:
    """Canonical per-PN AOG-hour metrics (whole event hours for every event that lists the PN; same window and
    counting as the action centre's aog_hours_lookback, so per-station values reconcile with actions.json)."""
    pm = hist("part_master")
    ae = hist("aog_events").copy()
    ae["pn_list"] = ae.pns.astype(str).str.split(";")
    ex = ae.explode("pn_list").rename(columns={"pn_list": "pn"})
    lo = AS_OF_H - AOG_LOOKBACK_WEEKS * HOURS_PER_WEEK
    recent = ex[(ex.start_h >= lo) & (ex.start_h < AS_OF_H)]
    by_st = recent.groupby(["pn", "station"]).hours.sum().reset_index().sort_values(["pn", "hours", "station"], ascending=[True, False, True])
    top = by_st.groupby("pn").head(1).set_index("pn")
    t = pd.DataFrame(index=pd.Index(pm.pn, name="pn"))
    t["aog_h_2y"] = ex.groupby("pn").hours.sum().reindex(t.index).fillna(0.0)
    t["aog_events_2y"] = ex.groupby("pn").size().reindex(t.index).fillna(0).astype(int)
    t["aog_h_52w"] = recent.groupby("pn").hours.sum().reindex(t.index).fillna(0.0)
    t["aog_events_52w"] = recent.groupby("pn").size().reindex(t.index).fillna(0).astype(int)
    t["aog_h_52w_max_station"] = top.hours.reindex(t.index).fillna(0.0)
    t["aog_h_52w_max_station_id"] = top.station.reindex(t.index)
    return t


def _stress_scales():
    v = load_config()["generator"]["variants"] if "variants" in load_config().get("generator", {}) else {}
    def g(k):
        x = v.get(k, {})
        return float(x.get("true_mtbur_scale", float("nan"))) if isinstance(x, dict) else float("nan")
    return g("low_stress"), g("high_stress")


def meta(provenance: str, sources: list[str], notes: str, **extra) -> dict:
    m = {"generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
         "git_sha": git_sha(), "provenance": provenance, "source": sources, "notes": notes}
    m.update(extra)
    return m


# ----------------------------------------------------------------------------------------------
# KPIs + policies

KPI_DEFS = [
    # id, label, unit, better, frontier column, policy_summary metric
    ("immediate_fill_rate", "Immediate fill rate", "%", "higher", "fill_rate", "immediate_fill_rate"),
    ("aog_hours", "Material AOG hours / year", "h", "lower", "aog_hours", "aog_hours"),
    ("spare_capital_aed", "Spare capital", "AED", "lower", "capital", "spare_capital_aed"),
    ("total_annual_cost_aed", "Total annual cost", "AED", "lower", "total_cost", "total_annual_cost_aed"),
    ("expedite_cost_aed", "Expedite spend / year", "AED", "lower", "expedite_cost", "expedite_cost_aed"),
    ("aog_events", "AOG events / year", "", "lower", "aog_events", "aog_events"),
]


def _v(unit, x):
    return aed(x) if unit == "AED" else num(x)


def _ci(d: dict) -> dict:
    return {"mean": d["mean"], "ci": [d["ci_lo"], d["ci_hi"]]}


@lru_cache(maxsize=None)
def build_headline() -> dict:
    """The v2 site headline, computed from the outputs (never typed): P2 vs P0 is the core finding; I125 is a frontier
    option for additional capital; the honest findings stay next to it."""
    ps = jload("outputs/holdout/policy_summary.json")
    rid = recommended_id()
    hub = cfg()["network"]["hub"]
    out_rot = {}
    for pid in ["P0", "P1", "P2"]:
        t = csv(f"outputs/policies/{pid}_stock_params.csv")
        out_rot[pid] = int(t[(t.part_class == "R") & (t.station != hub)].target_units.sum())
    # AV2-03: P2 is a re-mix of the rotable float, not a repositioning of P0's: units bought and shed per PN (all stations)
    _r = {pid: csv(f"outputs/policies/{pid}_stock_params.csv").query("part_class == 'R'").groupby("pn")
          .agg(u=("target_units", "sum"), c=("unit_cost_aed", "first")) for pid in ("P0", "P2")}
    _d = (_r["P2"].u - _r["P0"].u).fillna(0)
    _c = _r["P0"].c.combine_first(_r["P2"].c)
    remix = {"rotable_units": {"P0": int(_r["P0"].u.sum()), "P2": int(_r["P2"].u.sum())},
             "buy_units": int(_d[_d > 0].sum()), "buy_aed": float((_d[_d > 0] * _c[_d > 0]).sum()),
             "shed_units": int(-_d[_d < 0].sum()), "shed_aed": float((-_d[_d < 0] * _c[_d < 0]).sum()),
             "basis": "P0 vs P2 rotable target units x unit cost (outputs/policies/*_stock_params.csv); the KPI capital "
                      "is the simulated time-average stock value, so the net differs slightly"}
    pc = ps["variants"]["central"]["paired"]["P2-P0"]
    worlds = []
    for v in ["low_stress", "central", "high_stress"]:
        pr = ps["variants"][v]["paired"].get("P2-P0")
        if pr:
            worlds.append({"variant": v, "aog_hours": _ci(pr["aog_hours"]), "capital_aed": _ci(pr["spare_capital_aed"]),
                           "significant": bool(pr["aog_hours"]["ci_hi"] < 0)})
    pen = {k.replace("total_cost_pen_", ""): _ci(pc[k]) for k in ["total_cost_pen_x0.5", "total_cost_pen_x1", "total_cost_pen_x2"] if k in pc}
    fh = frontier_holdout()
    r = fh.loc[rid]
    summ = jload("outputs/frontier/summary.json")
    tor = csv("outputs/frontier/tornado.csv").set_index(["factor", "setting"])
    def tor_row(f, st):
        try:
            x = tor.loc[(f, st)]
        except KeyError:
            return None
        return {"net_benefit_aed": {"mean": x.net_benefit_mean, "ci": [x.net_benefit_lo, x.net_benefit_hi]},
                "aog_reduction": {"mean": x.aog_reduction_mean, "ci": [x.aog_reduction_lo, x.aog_reduction_hi]},
                "net_benefit_significant": bool(x.net_benefit_lo > 0)}
    pp = jload("outputs/holdout/postplan_i125_stress.json")
    post = []
    for w, rows in pp.get("worlds", {}).items():
        row = next((q for q in rows if q["id"] == rid), None)
        if row:
            post.append({"variant": w, "aog_hours": {"mean": row["d_aog_hours_vs_base_mean"], "ci": [row["d_aog_hours_vs_base_lo"], row["d_aog_hours_vs_base_hi"]]},
                         "total_cost_aed": {"mean": row["d_total_cost_vs_base_mean"], "ci": [row["d_total_cost_vs_base_lo"], row["d_total_cost_vs_base_hi"]]},
                         "capital_aed": row["d_capital_vs_base_mean"]})
    chk = csv("outputs/holdout/forecast_champion_check.csv")
    sba = chk[(chk.demand_class == "intermittent") & (chk.part_class == "R")]
    tr = jload("outputs/holdout/truth_recovery.json")["reliability"]["all"]
    p1 = ps["variants"]["central"]["paired"]["P1-P0"]["immediate_fill_rate"]
    off = tor_row("aog_desk_expedite", "off")
    offx = tor.loc[("aog_desk_expedite", "off")] if off else None
    return {
        "core": {"id": "P2", "vs": "P0", "label": "network positioning",
                 "baseline_label": f"a starting-point OEM-quote policy holding only {out_rot['P0']} outstation rotables",
                 "outstation_rotables": out_rot, "remix": remix,
                 "aog_reduction": {"mean": -pc["aog_hours"]["mean"], "ci": [-pc["aog_hours"]["ci_hi"], -pc["aog_hours"]["ci_lo"]]},
                 "capital_aed": _ci(pc["spare_capital_aed"]), "total_cost_aed": _ci(pc["total_annual_cost_aed"]),
                 "immediate_fill_pts": {"mean": 100 * pc["immediate_fill_rate"]["mean"], "ci": [100 * pc["immediate_fill_rate"]["ci_lo"], 100 * pc["immediate_fill_rate"]["ci_hi"]]},
                 "worlds": worlds, "holds_all_worlds": all(w["significant"] for w in worlds) and len(worlds) == 3,
                 "penalty_range": pen, "holds_penalty_range": all(v["ci"][1] < 0 for v in pen.values()),
                 "split": "holdout", "variant": "central", "paired": True, "seeds": ps["seeds"]},
        "frontier_option": {"id": rid, "vs": "P2",
                            "extra_capital_aed": {"mean": r.d_capital_vs_base_mean, "ci": [r.d_capital_vs_base_lo, r.d_capital_vs_base_hi]},
                            "aog_reduction": {"mean": -r.d_aog_hours_vs_base_mean, "ci": [-r.d_aog_hours_vs_base_hi, -r.d_aog_hours_vs_base_lo]},
                            "total_cost_aed": {"mean": r.d_total_cost_vs_base_mean, "ci": [r.d_total_cost_vs_base_lo, r.d_total_cost_vs_base_hi]},
                            "aog_hours": r.aog_hours_mean, "capital_aed": r.capital_mean,
                            "rule_shifts": [x for x in summ["recommendation_stability"] if x["recommended"] != rid],
                            "repair_tat_x0_75": tor_row("repair_tat", "x0.75"),
                            "postplan_stress": post, "postplan_note": pp.get("note", "post-plan check (D015)")},
        "honest": {"forecast_champions_best": int((chk.champion_rank == 1).sum()), "forecast_cells": int(len(chk)),
                   "sba_intermittent_rotables_rank": (int(sba.champion_rank.iloc[0]) if len(sba) and sba.champion.iloc[0] == "sba" else None),
                   "sba_intermittent_rotables_n_methods": (int(sba.n_methods.iloc[0]) if len(sba) else None),
                   "mtbur_history_error": tr["estimated_mdale"], "mtbur_quote_error": tr["quoted_mdale"],
                   "fill_pts_P2_vs_P0": 100 * pc["immediate_fill_rate"]["mean"], "fill_pts_P1_vs_P0": 100 * p1["mean"],
                   "routes_off": ({"p0_aog_hours": offx.p0_base_aog_hours, "p2_aog_hours": offx.base_aog_hours, "rec_aog_hours": offx.rec_aog_hours,
                                   "central_p0_aog_hours": tor.loc[("base case", "central")].p0_base_aog_hours,
                                   "central_p2_aog_hours": tor.loc[("base case", "central")].base_aog_hours} if off else None),
                   "routes_note": summ.get("aog_desk_dependence", ""),
                   # v2.2 (5.1): one plain line for README / deck / workbook / Mission Control; numbers from routes_off
                   "routes_line": (
                       "All four plans rely on emergency sourcing (borrowing from another aircraft, loans, local purchase). "
                       "With those routes switched off, every plan's downtime rises sharply — e.g. Network Plan from "
                       f"≈{fmt_int(sig(tor.loc[('base case', 'central')].base_aog_hours))} h to ≈{fmt_int(sig(offx.base_aog_hours))} h "
                       "a year (selection runs). See Limitations." if off else None)},
        "provenance": "SIMULATED",
    }


def landing_stats() -> dict:
    """A1 stat strip, computed from config / history / seeds (never typed)."""
    c = cfg()
    n_ac = int(c["fleet"]["narrowbody"]["count"]) + int(c["fleet"]["widebody"]["count"])
    am = hist("aircraft_master")
    if len(am) != n_ac:
        raise RuntimeError(f"aircraft_master has {len(am)} tails, config fleet {n_ac}")
    lo, hi = c["seeds"]["holdout_seeds"]
    n_runs = int(hi) - int(lo) + 1
    if n_runs != len(jload("outputs/holdout/policy_summary.json")["seeds"]):
        raise RuntimeError("holdout seed count differs between config and policy_summary.json")
    stats = [{"id": "aircraft", "value": n_ac, "label": "aircraft"},
             {"id": "part_numbers", "value": int(len(hist("part_master"))), "label": "part numbers"},
             {"id": "stations", "value": len(stations()), "label": "stations"},
             {"id": "test_runs", "value": n_runs, "label": "fresh test runs"}]
    return {"stats": stats, "text": " · ".join(f"{x['value']} {x['label']}" for x in stats),
            "title": v21.A1_TITLE, "sub": v21.A1_SUB, "footer": v21.A1_FOOTER,
            "sources": ["config/assumptions.yaml (fleet, network, seeds.holdout_seeds)",
                        "data/processed/history/part_master.parquet", "data/processed/history/aircraft_master.parquet"],
            "provenance": "ASSUMED"}


def capital_table(remix: dict) -> dict:
    """A4: rotables bought / removed going P0 -> P2 (stock tables x unit cost) and the net change in the simulated
    time-average spare inventory (holdout P2 - P0 capital means). Never the net alone."""
    fh = frontier_holdout()
    net = float(fh.at[BASE_POLICY, "capital_mean"] - fh.at[BASELINE, "capital_mean"])
    def fmt_aed(x):   # the A4 table always reads in AED millions (one decimal), so +AED 0.6M is never shown as 615k
        return f"AED {abs(float(x)) / 1e6:.1f}M"
    rows = [
        {"id": "bought", "label": "New rotables bought", "units": remix["buy_units"], "aed": remix["buy_aed"],
         "text": f"+{remix['buy_units']} units ≈ {fmt_aed(remix['buy_aed'])} assumed value"},
        {"id": "removed", "label": "Rotables removed", "units": -remix["shed_units"], "aed": -remix["shed_aed"],
         "text": f"−{remix['shed_units']} units ≈ {fmt_aed(remix['shed_aed'])}"},
        {"id": "net_inventory", "label": "Net change in average simulated spare inventory", "units": None, "aed": net,
         "text": ("+" if net >= 0 else "−") + fmt_aed(net)},
    ]
    return {"from": BASELINE, "to": BASE_POLICY, "from_display_name": v21.display_name(BASELINE),
            "to_display_name": v21.display_name(BASE_POLICY),
            "bought_units": remix["buy_units"], "bought_aed": remix["buy_aed"],
            "removed_units": remix["shed_units"], "removed_aed": remix["shed_aed"],
            "net_inventory_change_aed": net, "rows": rows, "note": v21.A4_NOTE,
            "basis": ("bought / removed = P0 vs P2 rotable target units x unit cost per PN (outputs/policies/*_stock_params.csv); "
                      "net = holdout P2 minus P0 simulated time-average spare capital (outputs/holdout/frontier_points.csv), "
                      "so it is not bought minus removed"),
            "provenance": "SIMULATED"}


def stress_worlds() -> dict:
    v = cfg()["generator"]["variants"]
    sc = {k: float(v[k]["true_mtbur_scale"]) for k in ("high_stress", "central", "low_stress")}
    return {"scales": sc, "text": v21.a6_text(sc["high_stress"], sc["central"], sc["low_stress"]),
            "ranges_note": v21.A6_RANGES, "parameter": "true MTBUR scale (reliability only)",
            "source": "config/assumptions.yaml generator.variants", "provenance": "ASSUMED"}


def frontier_insight(headline: dict) -> dict:
    t = headline["frontier_option"].get("repair_tat_x0_75") or {}
    return {"text": v21.A8_INSIGHT, "levers": v21.A8_LEVERS, "levers_text": " · ".join(v21.A8_LEVERS),
            "evidence": {"factor": "repair_tat", "setting": "x0.75",
                         "net_benefit_vs_P2_aed": t.get("net_benefit_aed"),
                         "net_benefit_significant": t.get("net_benefit_significant"),
                         "source": "outputs/frontier/tornado.csv (selection seeds, one-at-a-time)"},
            "provenance": "SIMULATED"}


def donor_recount_block() -> dict:
    """Workstream B (post-plan, exploratory): read outputs/postplan/donor_recount.json; kept apart from frozen KPIs."""
    path = OUT / "postplan" / "donor_recount.json"
    if not path.exists():
        return {"status": "not run", "label": v21.DONOR_LABEL, "postplan": True,
                "note": "run scripts/donor_recount.py", "provenance": "SIMULATED"}
    j = read_json(path)
    h, hi = j["holdout"], j["historical_p0"]
    def mci(r):
        return ({"mean": r["mean"], "ci": [r["ci_lo"], r["ci_hi"]]} if "mean" in r else {"status": r["status"]})
    rob = {p: {**mci(r), "display_name": v21.display_name(p)} for p, r in h["robbery_count_per_year"].items()}
    return {
        "label": v21.DONOR_LABEL, "status": "post-plan, exploratory", "postplan": True, "decision": j.get("decision", "V21-B"),
        "separate_from_frozen": True,
        "holdout": {"split": "holdout", "seeds": [min(h["seeds"]), max(h["seeds"])], "variant": h["variant"],
                    "robberies_per_year": rob,
                    "robberies_paired": {k: mci(v) for k, v in h["robbery_count_paired"].items()},
                    "robberies_note": h["robbery_count_note"],
                    "donor_hours": v21.NOT_RECONSTRUCTIBLE, "donor_hours_why": h["donor_hours_why"],
                    "combined_hours": v21.NOT_RECONSTRUCTIBLE,
                    "recipient_hours_note": h["recipient_hours_note"], "provenance": "SIMULATED"},
        "historical_p0": {"label": hi["label"], "split": "history", "policy": "P0",
                          "robberies": hi["robberies"], "robberies_per_year": hi["robberies_per_year"],
                          "donor_tails": hi["donor_tails"], "mean_days_held": hi["mean_days_held"],
                          "share_d3_d10": hi["share_d3_d10"],
                          "gross_donor_hours_per_year": hi["gross_donor_hours_per_year"],
                          "donor_hours_per_tail_union_per_year": hi["donor_hours_per_tail_union_per_year"],
                          "counted_material_aog_hours_per_year": hi["counted_material_aog_hours_per_year"],
                          "provenance": "SIMULATED"},
        "source": "outputs/postplan/donor_recount.json (scripts/donor_recount.py)", "provenance": "SIMULATED",
    }


def names_v21() -> dict:
    """{code: {display_name, short_name}} for every policy / frontier code (A3)."""
    return v21.names_map(frontier_holdout().index.tolist())


def build_kpis() -> dict:
    rid = recommended_id()
    fh = frontier_holdout()
    fs = selection_points()
    acts = jload("outputs/actions/actions.json")
    headline = build_headline()
    for blk in ("core", "frontier_option"):
        headline[blk]["scope"] = v21.SCOPE_LINE
        headline[blk]["display_name"] = v21.display_name(headline[blk]["id"])
        headline[blk]["vs_display_name"] = v21.display_name(headline[blk]["vs"])
    kpis, consistency = [], []
    for kid, label, unit, better, col, _ in KPI_DEFS:
        # v2 framing (user decision): the KPI value is the CORE finding P2 vs P0; I125 is a frontier option (frontier_option)
        b, r, p2 = fh.loc[BASELINE], fh.loc[BASE_POLICY], fh.loc[rid]
        bv, rv = _v(unit, b[f"{col}_mean"]), _v(unit, r[f"{col}_mean"])
        sel_b, sel_r = fs.loc[BASELINE], fs.loc[BASE_POLICY]
        k = {
            "id": kid, "label": label, "value": rv, "unit": unit, "baseline": bv, "recommended": rv,
            "delta": (aed(r[f"{col}_mean"] - b[f"{col}_mean"]) if unit == "AED" else num(r[f"{col}_mean"] - b[f"{col}_mean"])),
            "better": better, "provenance": "SIMULATED",
            "ci": [_v(unit, r[f"{col}_lo"]), _v(unit, r[f"{col}_hi"])],
            "baseline_ci": [_v(unit, b[f"{col}_lo"]), _v(unit, b[f"{col}_hi"])],
            "reference": {"id": rid, "value": _v(unit, p2[f"{col}_mean"]),
                          "ci": [_v(unit, p2[f"{col}_lo"]), _v(unit, p2[f"{col}_hi"])], "role": "frontier option"},
            "baseline_id": BASELINE, "core_id": BASE_POLICY, "recommended_id": rid, "split": "holdout", "n_seeds": int(r.n_seeds),
            "scope": v21.SCOPE_LINE, "display_name": v21.display_name(BASE_POLICY),
            "baseline_display_name": v21.display_name(BASELINE), "reference_display_name": v21.display_name(rid),
            "selection": {"baseline": _v(unit, sel_b[f"{col}_mean"]), "recommended": _v(unit, sel_r[f"{col}_mean"]),
                          "ci": [_v(unit, sel_r[f"{col}_lo"]), _v(unit, sel_r[f"{col}_hi"])]},
        }
        kpis.append(k)
        consistency.append({"id": kid, "unit": unit,
                            "selection_baseline": k["selection"]["baseline"], "holdout_baseline": bv,
                            "selection_recommended": k["selection"]["recommended"], "holdout_recommended": rv,
                            "holdout_ci": k["ci"], "selection_ci": k["selection"]["ci"],
                            "selection_inside_holdout_ci": bool(k["ci"][0] <= k["selection"]["recommended"] <= k["ci"][1]),
                            "provenance": "SIMULATED"})
    sev = Counter(a["severity"] for a in acts["actions"])
    kpis.append({"id": "open_exceptions", "label": "Open planner actions", "value": len(acts["actions"]),
                 "unit": "", "better": "lower", "provenance": "DERIVED",
                 "by_severity": {s: int(sev.get(s, 0)) for s in ["urgent", "review", "info"]},
                 "as_of_week": int(acts["as_of_week"]), "split": "history",
                 "note": "Exceptions raised on the history at week 103 (P0 world); no baseline/recommended pair and no CI."})
    return {
        "meta": meta("SIMULATED", ["outputs/holdout/frontier_points.csv", "outputs/frontier/summary.json",
                                   "outputs/frontier/selection_points.csv", "outputs/actions/actions.json"],
                     f"Mission Control KPIs (v2). value = {BASE_POLICY} network positioning, the CORE finding; baseline = {BASELINE} "
                     f"starting-point OEM-quote provisioning (Simple Rulebook); reference = {rid}, the frontier option for additional capital (the rule's pick); "
                     "headline = the computed site headline (core / frontier_option / honest). Holdout seeds 2000-2019, central variant, "
                     "KPI weeks 104-155 annualised; ci = 95% t-interval over 20 seeds. 'selection' repeats the same numbers on "
                     "selection seeds 100-119. No 'spark' field: there is no genuine time series for these KPIs, so none is "
                     "exported (UI must handle a missing spark). open_exceptions is DERIVED from history week 103.",
                     provenance_by_key={"seeds": "ASSUMED", "kpi_weeks": "ASSUMED"}),
        "split": "holdout", "recommended_id": rid, "core_id": BASE_POLICY, "baseline_id": BASELINE, "reference_id": rid,
        "headline": headline,
        "seeds": jload("outputs/holdout/policy_summary.json")["seeds"], "kpi_weeks": [104, 155],
        "kpis": kpis, "consistency": consistency,
        # v2.1 (additive)
        "scope_line": v21.SCOPE_LINE, "reading_note": v21.A2_READING_NOTE, "footer": v21.E4_FOOTER,
        "display_names": names_v21(), "landing": landing_stats(),
        "capital_table": capital_table(headline["core"]["remix"]), "stress_worlds": stress_worlds(),
        "frontier_insight": frontier_insight(headline), "donor_recount": donor_recount_block(),
    }


POLICY_METRICS = ["immediate_fill_rate", "aog_hours", "aog_events", "backorder_unit_hours", "spare_capital_aed",
                  "total_annual_cost_aed", "holding_cost_aed", "repair_cost_aed", "logistics_cost_aed",
                  "expedite_cost_aed", "aog_penalty_aed", "aog_event_cost_aed", "aog_hourly_penalty_aed", "purchase_spend_aed",
                  "total_cost_pen_x0.5", "total_cost_pen_x1", "total_cost_pen_x2"]
FRONTIER_TO_POLICY = {"fill_rate": "immediate_fill_rate", "aog_hours": "aog_hours", "aog_events": "aog_events",
                      "capital": "spare_capital_aed", "total_cost": "total_annual_cost_aed",
                      "holding_cost": "holding_cost_aed", "repair_cost": "repair_cost_aed",
                      "expedite_cost": "expedite_cost_aed", "aog_penalty": "aog_penalty_aed"}


def _policy_rows(block: dict, split: str) -> list[dict]:
    labels = {p["policy_id"]: p["label"] for p in jload("outputs/policies/policies.json")["policies"]}
    rows = []
    for pid, kp in block["policies"].items():
        base_id = pid.split("@")[0]
        rows.append({"policy_id": pid,
                     "label": POLICY_LABELS.get(base_id, labels.get(base_id, pid)) + (" (central plan)" if "@" in pid else ""),
                     "display_name": v21.display_name(pid), "short_name": v21.display_name(pid, short=True),
                     "description": labels.get(base_id, ""), "kind": "policy", "split": split,
                     "kpi": {m: {"mean": kp[m]["mean"], "ci_lo": kp[m]["ci_lo"], "ci_hi": kp[m]["ci_hi"]}
                             for m in POLICY_METRICS if m in kp},
                     "provenance": "SIMULATED"})
    return rows


def _paired(block: dict) -> dict:
    keep = ["immediate_fill_rate", "aog_hours", "aog_events", "spare_capital_aed", "total_annual_cost_aed", "expedite_cost_aed"]
    return {pair: {m: {k: v[m][k] for k in ["mean", "ci_lo", "ci_hi", "share_seeds_better"] if k in v[m]}
                   for m in keep if m in v}
            for pair, v in block["paired"].items()}


def _frontier_policy_row(fr: pd.Series, pid: str, split: str) -> dict:
    return {"policy_id": pid, "label": POLICY_LABELS.get(pid, pid),
            "display_name": v21.display_name(pid), "short_name": v21.display_name(pid, short=True),
            "description": "P2 C/E parameters and network rules with greedy rotable additions up to 1.25 x P2's allocation capital (frozen candidate)",
            "kind": "recommended", "split": split,
            "kpi": {pm: {"mean": fr[f"{c}_mean"], "ci_lo": fr[f"{c}_lo"], "ci_hi": fr[f"{c}_hi"]}
                    for c, pm in FRONTIER_TO_POLICY.items()},
            "provenance": "SIMULATED"}


def build_policies() -> dict:
    ps = jload("outputs/holdout/policy_summary.json")
    sel = jload("outputs/policies/selection_summary.json")
    rid = recommended_id()
    fh, fs = frontier_holdout(), selection_points()
    c = ps["variants"]["central"]
    pols = _policy_rows(c, "holdout") + [_frontier_policy_row(fh.loc[rid], rid, "holdout")]
    r = fh.loc[rid]
    rec_vs_p2 = {m: {"mean": r[f"d_{m}_vs_base_mean"], "ci_lo": r[f"d_{m}_vs_base_lo"], "ci_hi": r[f"d_{m}_vs_base_hi"]}
                 for m in ["capital", "aog_hours", "total_cost"]}
    sens = {}
    for v in ["low_stress", "high_stress"]:
        sens[v] = {"n_seeds": ps["variants"][v]["n_seeds"], "policies": _policy_rows(ps["variants"][v], "holdout"),
                   "paired": _paired(ps["variants"][v]), "provenance": "SIMULATED"}
    sel_c = sel["variants"]["central"]
    return {
        "meta": meta("SIMULATED", ["outputs/holdout/policy_summary.json", "outputs/holdout/frontier_points.csv",
                                   "outputs/policies/selection_summary.json", "outputs/policies/policies.json"],
                     "Holdout seeds 2000-2019, central variant (headline). Means with 95% paired-t CIs over 20 seeds; "
                     "KPI weeks 104-155 annualised; money in AED; total annual cost = holding + repair + logistics + "
                     "expedite + AOG penalty (capital excluded). The frontier option I125 is a frontier candidate "
                     "evaluated by the frozen frontier holdout run (frontier_points.csv), so it carries fewer metrics. "
                     f"'sensitivity' = low/high-stress worlds (true MTBUR x{_stress_scales()[0]:.2f} / x{_stress_scales()[1]:.2f}), P1/P2 re-planned per world; "
                     "'@central' = the central plan dropped into that world. 'selection' = the same table on selection "
                     "seeds 100-119 (for the selection-vs-holdout consistency check).",
                     provenance_by_key={"seeds": "ASSUMED", "n_seeds": "ASSUMED"}),
        "split": "holdout", "n_seeds": c["n_seeds"], "seeds": ps["seeds"], "ci_method": ps["ci_method"],
        "recommended_id": rid, "baseline_id": BASELINE, "reference_id": BASE_POLICY,
        "display_names": names_v21(), "scope_line": v21.SCOPE_LINE, "reading_note": v21.A2_READING_NOTE,
        "policies": pols,
        "paired": {**_paired(c), "provenance": "SIMULATED"},
        "recommended_vs_P2": {**rec_vs_p2, "provenance": "SIMULATED",
                              "note": "paired over the 20 holdout seeds (frontier_points.csv d_*_vs_base)"},
        "by_class": tag([{k: v for k, v in r_.items()} for r_ in ps["by_class"] if r_["variant"] == "central"], "SIMULATED"),
        "sensitivity": {**sens, "provenance": "SIMULATED"},
        "selection": {"split": "selection", "seeds": sel["seeds"], "n_seeds": sel_c["n_seeds"],
                      "policies": _policy_rows(sel_c, "selection") + [_frontier_policy_row(fs.loc[rid], rid, "selection")],
                      "paired": _paired(sel_c), "provenance": "SIMULATED"},
    }


# ----------------------------------------------------------------------------------------------
# parts + demand history


# planner exception types in plain words (the Action Centre, the Parts risk-vs-action chip and the CSV use the same labels)
ACTION_TYPE_LABEL = {
    "OVERDUE_REPAIR": "Overdue repair", "OUTSTATION_DEPLETION": "Outstation depletion",
    "EXCESS_DECLINING_DEMAND": "Excess · declining demand", "CONDEMNED_AWAITING_REPLACEMENT": "Condemned · awaiting replacement",
    "QUARANTINE_DOCS": "Quarantine · documents", "LEAD_TIME_DRIFT": "Lead-time drift", "EXPIRY_RISK": "Shelf-life expiry risk",
    "KIT_SHORTAGE": "Kit shortage",
}


@lru_cache(maxsize=None)
def brake_pns() -> frozenset:
    """Brake assemblies (part_master.family brake_*): changed only at the hub in this model (A9)."""
    pm = hist("part_master")
    return frozenset(pm[pm.family.astype(str).str.startswith("brake")].pn)


def invalid_brake_allocations() -> list[dict]:
    """A9: outstation brake units in the frozen P2 / frontier-option allocations. Flagged, never removed."""
    rid = recommended_id()
    hub = cfg()["network"]["hub"]
    st = stock_table()
    rows = []
    for pid in (BASE_POLICY, rid):
        sub = st[st.pn.isin(brake_pns()) & (st.station != hub) & (st[pid] > 0)]
        for r in sub.sort_values(["pn", "station"]).itertuples():
            rows.append({"policy": pid, "display_name": v21.display_name(pid), "pn": r.pn, "station": r.station,
                         "units": int(getattr(r, pid)), "flag": "invalid_recommendation", "text": v21.A9_FLAG,
                         "provenance": "DERIVED"})
    return rows


def escalation_flags() -> dict:
    """A7: rotables whose history-estimated MTBUR is >= 2x shorter than quoted -> escalate to reliability/warranty first.
    The ratio is mtbur_quoted / mtbur_post (final_forecasts, hub row; estimated on history only). The text quotes the
    planted quote multiple where the evaluation metadata states one (truth_recovery.json planted note), else the
    estimated ratio."""
    ff = pq("outputs/forecasting/final_forecasts.parquet")
    h = ff[(ff.station == cfg()["network"]["hub"]) & (ff.part_class == "R")].set_index("pn")
    ratio = (h.mtbur_quoted / h.mtbur_post).dropna()
    planted_x = {}
    for k, v in planted_meta().items():
        m = re.search(r"true MTBUR (\d+(?:\.\d+)?) FC vs quoted (\d+(?:\.\d+)?)", str(v.get("note", "")))
        if m and v.get("pn"):
            planted_x[v["pn"]] = float(m.group(2)) / float(m.group(1))
    out = {}
    for pn, x in ratio.items():
        if x >= 2.0:
            shown = x   # V21-A7: planner-facing claim uses the HISTORY estimate only; the planted truth stays evaluation-only
            out[pn] = {"flag": "escalate_reliability_warranty", "estimated_ratio": float(x),
                       "quoted_multiple_shown": round(shown, 1),
                       "quoted_multiple_basis": "history estimate (vendor-quoted MTBUR / history-based MTBUR)",
                       "true_multiple_evaluation_only": planted_x.get(pn),
                       "text": v21.A7_ESCALATION_TMPL.format(x=f"{shown:.1f}"), "threshold": 2.0,
                       "first_action": "reliability engineering and warranty review", "provenance": "DERIVED"}
    return out


def build_parts() -> dict:
    rid = recommended_id()
    esc = escalation_flags()
    bad = invalid_brake_allocations()
    bad_by_pn: dict = {}
    for b in bad:
        bad_by_pn.setdefault(b["pn"], []).append(b)
    pm = hist("part_master").set_index("pn")
    attrs = part_attributes()
    risk = risk_table()
    am = aog_metrics()
    st = stock_table()
    ff = pq("outputs/forecasting/final_forecasts.parquet")
    hub = ff[ff.station == cfg()["network"]["hub"]].set_index("pn")
    mr = hist("material_requests")
    nreq = mr.groupby("pn").size()
    acts_all = jload("outputs/actions/actions.json")["actions"]
    acts = Counter(a["pn"] for a in acts_all)
    sev_rank = {"urgent": 0, "review": 1, "info": 2}
    exc_by_pn: dict = {}
    for a in sorted(acts_all, key=lambda a: (sev_rank.get(a["severity"], 9), a["exception_id"])):
        exc_by_pn.setdefault(a["pn"], []).append({"exception_id": a["exception_id"], "type": a["type"],
                                                  "type_label": ACTION_TYPE_LABEL.get(a["type"], a["type"].replace("_", " ").capitalize()),
                                                  "severity": a["severity"], "station": a["station"]})
    piv = {pid: st.pivot(index="pn", columns="station", values=pid).reindex(columns=stations()) for pid in ["P0", "P2", rid]}
    parts = []
    app = applicability()
    for pn in pm.index:
        p, a, r = pm.loc[pn], attrs.loc[pn], risk.loc[pn]
        sbs = {s: int(piv["P2"].at[pn, s]) for s in stations()}
        parts.append({
            "pn": pn, "desc": p.description, "ata": str(p.ata), "ata_name": ata_names().get(str(p.ata), ""),
            "cls": p.part_class, "deadline": p.deadline_class,
            "removal_mode": (None if pd.isna(p.get("removal_mode")) else str(p.removal_mode)), "family": (None if pd.isna(p.get("family")) else str(p.family)),
            "applicability": (None if pd.isna(app.at[pn, "applic"]) else str(app.at[pn, "applic"])) if pn in app.index else None,
            "qpa_nb": (int(app.at[pn, "qty_nb"]) if pn in app.index and not pd.isna(app.at[pn, "qty_nb"]) else None),
            "qpa_wb": (int(app.at[pn, "qty_wb"]) if pn in app.index and not pd.isna(app.at[pn, "qty_wb"]) else None),
            "demand_class": a.demand_class, "adi": num(a.adi), "cv2": num(a.cv2), "abc": a.abc,
            "annual_usage_qty": num(a.annual_usage_qty), "annual_usage_value_aed": num(a.annual_usage_value_aed),
            "stock_total": int(sum(sbs.values())), "stock_by_station": sbs,
            "stock_total_p0": int(piv["P0"].loc[pn].sum()), "stock_total_p2": int(piv["P2"].loc[pn].sum()),
            "risk_score": num(r.risk_score), "risk_level": r.risk_level, "risk_hours": num(r.risk_hours),
            "aog_hours_hist_per_yr": num(r.aog_hours_hist_per_yr), "aog_events_hist": int(r.aog_events_hist),
            "residual_aog_h_per_yr": num(r.residual_aog_h_per_yr), "residual_modelled": bool(r.residual_modelled),
            "aog_h_2y": num(am.at[pn, "aog_h_2y"]), "aog_events_2y": int(am.at[pn, "aog_events_2y"]),
            "aog_h_52w": num(am.at[pn, "aog_h_52w"]), "aog_events_52w": int(am.at[pn, "aog_events_52w"]),
            "aog_h_52w_max_station": num(am.at[pn, "aog_h_52w_max_station"]),
            "aog_h_52w_max_station_id": (None if pd.isna(am.at[pn, "aog_h_52w_max_station_id"]) else str(am.at[pn, "aog_h_52w_max_station_id"])),
            "unit_cost": num(p.unit_cost_aed),
            "planted": (None if pd.isna(p.planted) else str(p.planted)),
            "requests_hist": int(nreq.get(pn, 0)), "n_actions": int(acts.get(pn, 0)),
            "exceptions": exc_by_pn.get(pn, [])[:3],
            "champion": hub.at[pn, "champion"], "lt_quoted_d": num(hub.at[pn, "lt_quoted_d"]),
            "lt_est_d": num(hub.at[pn, "lt_est_d"]),
            "escalation": esc.get(pn), "allocation_flags": bad_by_pn.get(pn, []),
            "provenance": "SIMULATED",
        })
    systems = []
    for ata, name in ata_names().items():
        ps = [x for x in parts if x["ata"] == ata]
        if not ps:
            continue
        top = max(ps, key=lambda x: x["risk_score"])
        systems.append({"ata": ata, "name": name, "n_parts": len(ps), "risk": max(x["risk_score"] for x in ps),
                        "risk_hours": sum(x["risk_hours"] for x in ps),
                        "n_urgent": sum(x["risk_level"] == "urgent" for x in ps),
                        "n_review": sum(x["risk_level"] == "review" for x in ps),
                        "top_pn": top["pn"], "provenance": "DERIVED"})
    tot = sum(x["risk_hours"] for x in systems) or 1.0
    for x in systems:   # system level is RELATIVE: share of fleet risk-hours (part bands applied to sums made every system urgent)
        x["risk_share"] = round(x["risk_hours"] / tot, 4)
        x["risk_level"] = ("urgent" if x["risk_share"] >= SYS_URGENT_SHARE else
                           "review" if x["risk_share"] >= SYS_REVIEW_SHARE else "ok")
        # explicit, separate fields (wave-3 #2): the system rating vs "does it hold an urgent part"
        x["system_level"] = x["risk_level"]
        x["has_urgent_part"] = x["n_urgent"] > 0
        nu = x["n_urgent"]
        urg = f"{nu} urgent PN{'s' if nu != 1 else ''}"
        if x["system_level"] == "ok" and nu:
            x["status"], x["status_label"] = "review", f"WATCH · {urg}"   # never a bare OK next to urgent parts
        else:
            x["status"] = x["system_level"]
            x["status_label"] = x["system_level"].upper() + (f" · {urg}" if nu else "")
    systems.sort(key=lambda x: x["ata"])
    return {
        "meta": meta("SIMULATED", ["data/processed/history/part_master.parquet", "data/processed/history/material_requests.parquet",
                                   "data/processed/history/aog_events.parquet", "outputs/forecasting/final_forecasts.parquet",
                                   "outputs/policies/P0_stock_params.csv", "outputs/policies/P2_stock_params.csv",
                                   "outputs/frontier/allocations.json", "outputs/frontier/levers.csv",
                                   "outputs/actions/actions.json", "config/assumptions.yaml (ATA names)"],
                     "Part master is SIMULATED (fictional PNs). adi / cv2 / demand_class / abc from "
                     "gnm.forecasting.classify.build_part_attributes on TRAINING weeks 0-77 only. "
                     f"stock_by_station = stock_basis (see field). RISK: risk_hours = aog_hours_hist_per_yr + "
                     "residual_aog_h_per_yr, where aog_hours_hist_per_yr = P0 history AOG hours attributable to the PN "
                     "(each aog_events row's hours split equally across its PNs) / 2 years, and residual_aog_h_per_yr = "
                     f"the optimiser's modelled expected AOG h/yr for the PN at the P2 allocation (levers.csv base_aog_hours) "
                     f"minus the modelled reductions of the {rid} rows for that PN (allocations.json, leave-one-out), floored "
                     "at 0; rotables only (residual_modelled=false for C/E, residual 0). risk_score = ln(1+risk_hours) / "
                     f"ln(1+max risk_hours) in [0,1]. risk_level: urgent if risk_hours >= {RISK_URGENT_H:g}, review if >= "
                     f"{RISK_REVIEW_H:g}, else ok. ata_systems.risk = max risk_score in the chapter; ata_systems.risk_level is relative: urgent if the chapter holds >= 15% of fleet risk-hours, review if >= 7%, else ok (ASSUMED bands, DERIVED values); system_level = that rating, has_urgent_part = n_urgent > 0, status/status_label = what to print on the system pill (an OK system with urgent parts reads 'WATCH · n urgent PNs', status review). CANONICAL AOG METRICS (the same numbers on every screen, labels in aog_metric_labels): aog_h_2y / aog_events_2y = whole hours of every history AOG event listing the PN (all stations, weeks 0-103); aog_h_52w / aog_events_52w = the last 52 weeks only (W52-W103, the action centre's lookback); aog_h_52w_max_station(_id) = the worst single station in that window (equals the largest actions.json aog_hours_lookback for the PN when that station has a depletion exception). risk_hours instead splits multi-PN events equally and is per year. adi/cv2 are null "
                     "when demand_class = insufficient_data (fewer than 3 non-zero training weeks: undefined). exceptions = up to 3 "
                     "actions.json exceptions for the PN (most severe first, with a plain type_label): an exception's severity is "
                     "planning urgency, not grounding risk, so a risk-0 PN can carry an urgent lead-time-drift action.",
                     provenance_by_key={"risk_bands_h": "ASSUMED", "system_risk_bands_share": "ASSUMED",
                                        "aog_lookback_weeks": "ASSUMED"}),
        "stock_basis": ("P2 (the core recommendation) target units from outputs/policies/P2_stock_params.csv. "
                        "Rotables = serviceable base stock (excludes units already in the repair loop); "
                        "consumables/expendables = order-up-to level S."),
        "stock_basis_id": "P2", "stations": stations(),
        "risk_bands_h": {"urgent": RISK_URGENT_H, "review": RISK_REVIEW_H},
        "system_risk_bands_share": {"urgent": SYS_URGENT_SHARE, "review": SYS_REVIEW_SHARE},
        "aog_metric_labels": AOG_METRIC_LABELS, "aog_lookback_weeks": AOG_LOOKBACK_WEEKS,
        "brake_note": brake_note(), "applicability_source": "config/part_catalogue.csv (applic: NB / WB / BOTH)",
        "parts": parts, "ata_systems": systems,
        # v2.1 (additive): A7 escalation (hero part first), A9 invalid outstation brake allocations (frozen, flagged)
        "escalation_rule": {"threshold_ratio": 2.0, "text_template": v21.A7_ESCALATION_TMPL,
                            "pns": sorted(esc), "provenance": "ASSUMED"},
        "invalid_allocations": bad, "invalid_allocation_text": v21.A9_FLAG,
        "display_names": names_v21(),
    }


def build_demand_history() -> dict:
    d = demand_matrix()
    return {
        "meta": meta("SIMULATED", ["data/processed/history/material_requests.parquet"],
                     "Weekly unconstrained demand (sum of material_requests.qty) per PN, history weeks 0-103 only "
                     f"(training 0-{SPLIT_WEEK - 1}, selection {SPLIT_WEEK}-103). No holdout data. split_week marks the "
                     "train/selection boundary for every series.",
                     provenance_by_key={"series": "SIMULATED", "weeks": "ASSUMED", "split_week": "ASSUMED",
                                        "splits": "ASSUMED", "split_by_pn": "ASSUMED"}),
        "weeks": [0, HISTORY_WEEKS - 1], "split_week": SPLIT_WEEK,
        "splits": {"train": [0, SPLIT_WEEK - 1], "selection": [SPLIT_WEEK, HISTORY_WEEKS - 1]},
        "split_by_pn": {pn: SPLIT_WEEK for pn in d.index},
        "series": {pn: [int(x) for x in row] for pn, row in zip(d.index, d.to_numpy())},
    }


# ----------------------------------------------------------------------------------------------
# forecast


def _lb_rows(df: pd.DataFrame, split: str, by_class_only=False) -> list[dict]:
    rows = []
    for r in df.to_dict(orient="records"):
        row = {"demand_class": r.get("demand_class", "all") if not by_class_only else "all",
               "part_class": r["part_class"], "method": r["method"], "method_label": METHOD_LABELS.get(r["method"], r["method"]),
               "mase": r["mase"], "mase_ci": [r["mase_ci_lo"], r["mase_ci_hi"]], "bias": r["bias"],
               "bias_ci": [r["bias_ci_lo"], r["bias_ci_hi"]], "pis": r["pis"], "coverage": r["cov_q90"],
               "coverage_ci": [r["cov_q90_ci_lo"], r["cov_q90_ci_hi"]], "pinball_q90": r["pinball_q90"],
               "cov_q50": r["cov_q50"], "cov_q95": r["cov_q95"], "mae": r["mae"], "n": int(r["n_parts"]),
               "n_undefined": int(r["n_undefined"]), "split": split, "provenance": "DERIVED"}
        rows.append(row)
    return rows


@lru_cache(maxsize=None)
def _p2_resupply() -> dict:
    """(pn, station) -> outstation resupply days from AUH as P2 sizes station stock: routine transit + expected hub wait."""
    d = csv("outputs/policies/p2_positioning.csv")
    return {(r.pn, r.station): float(r.resupply_days) + float(r.hub_wait_days) for r in d.itertuples()}


def _pmf(kind: str, mean: float, var: float) -> list[dict]:
    from scipy import stats
    if kind == "nbinom" and var > mean:
        n, p = mean * mean / (var - mean), mean / var
        dist = stats.nbinom(n, p)
    else:
        kind = "poisson"
        dist = stats.poisson(mean)
    hi = int(max(dist.ppf(0.999), 3))
    return [{"q": q, "p": float(dist.pmf(q))} for q in range(0, min(hi, 80) + 1)]


def _ci_pair(s: str):
    vals = re.findall(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?|[-+]?\d+(?:[eE][-+]?\d+)?", str(s).replace("np.float64", ""))
    return [float(v) for v in vals[-2:]]


def build_forecast() -> dict:
    sel_lb = csv("outputs/forecasting/leaderboard.csv")
    hold_lb = csv("outputs/holdout/forecast_leaderboard.csv")
    champs = csv("outputs/forecasting/champions.csv")
    check = csv("outputs/holdout/forecast_champion_check.csv").set_index(["demand_class", "part_class"])
    champions = []
    for r in champs.to_dict(orient="records"):
        k = (r["demand_class"], r["part_class"])
        c = check.loc[k] if k in check.index else None
        champions.append({"demand_class": r["demand_class"], "part_class": r["part_class"], "method": r["champion"],
                          "method_label": METHOD_LABELS.get(r["champion"], r["champion"]), "mase": r["mean_mase"],
                          "bias": r["mean_bias"], "basis": r["basis"], "runner_up": r["runner_up"],
                          "n_parts": int(r["n_parts_cell"]), "frozen": True,
                          "holdout_mase": None if c is None else c["champion_mase"],
                          "holdout_rank": None if c is None else int(c["champion_rank"]),
                          "n_methods": None if c is None else int(c["n_methods"]),
                          "holdout_best": None if c is None else c["best_in_hindsight"],
                          "provenance": "DERIVED"})
    champion_check = tag(records(check.reset_index()), "DERIVED")
    se = csv("outputs/forecasting/stock_eval_summary.csv")
    stock_eval = tag([{"part_class": r["part_class"], "method": r["method"], "method_label": METHOD_LABELS.get(r["method"], r["method"]),
                       "fill_rate": r["fill_rate"], "capital_aed": r["avg_stock_value_aed"],
                       "backorder_units": r["backorder_units"], "n": int(r["n_part_origins"])} for r in se.to_dict(orient="records")],
                     "DERIVED")
    tr = jload("outputs/holdout/truth_recovery.json")
    rel_ = tr["reliability"]
    truth = []
    for key, lab in [("all", "MTBUR (rotables + expendables)"), ("R", "MTBUR (rotables)"), ("E", "MTBUR (expendables)")]:
        b = rel_[key]
        truth.append({"param": lab, "metric": "median abs log error", "vendor_quoted": b["quoted_mdale"],
                      "estimated": b["estimated_mdale"], "n_parts": b["n_parts"],
                      "share_estimate_closer": b["share_estimate_closer"], "provenance": "DERIVED"})
    lt = tr["lead_time"]
    truth.append({"param": "Purchase lead time (all PNs)", "metric": "median abs log error", "vendor_quoted": lt["quoted_mdale"],
                  "estimated": lt["estimated_mdale"], "n_parts": lt["n_parts"], "provenance": "DERIVED"})
    mon = jload("outputs/forecasting/monash_benchmark.json")
    monash = {k: mon[k] for k in mon if k not in ("zip_sha256",)}
    monash["provenance"] = mon.get("provenance", "DERIVED")
    monash["data_provenance"] = mon.get("data_provenance", "REAL")
    monash["licence_url"] = "https://creativecommons.org/licenses/by/4.0/"
    ff = pq("outputs/forecasting/final_forecasts.parquet")
    pm = hist("part_master").set_index("pn")

    def ltd(pn, station):
        r = ff[(ff.pn == pn) & (ff.station == station)].iloc[0]
        rs = _p2_resupply().get((pn, station)) if station != "AUH" and r.part_class == "R" else None
        if rs is not None:
            # wave C (AV2-14): an outstation rotable is re-supplied from AUH, so its station demand is over the resupply
            # time (transit + expected hub wait), as P2 sizes station stock; the repair pipeline belongs to the pooled view
            m_ = float(r.removal_rate_day) * rs
            return {"pn": pn, "desc": pm.at[pn, "description"], "station": station, "part_class": r.part_class,
                    "lead_time_days": rs, "dist_kind": "poisson", "mean": m_, "var": m_, "champion": r.champion,
                    "rate_source": r.rate_source, "dist": _pmf("poisson", m_, m_), "provenance": "DERIVED",
                    "pipeline_days": num(r.pipeline_days),
                    "basis": ("outstation rotable: demand over the AUH resupply time (routine transit + expected hub wait), "
                              "as P2 sizes station stock; the network repair pipeline is the pooled view on Rotable & Repair")}
        return {"pn": pn, "desc": pm.at[pn, "description"], "station": station, "part_class": r.part_class,
                "lead_time_days": num(r.lead_time_d), "dist_kind": r.dist_kind, "mean": num(r.ltd_mean),
                "var": num(r.ltd_var), "champion": r.champion, "rate_source": r.rate_source,
                "dist": _pmf(r.dist_kind, float(r.ltd_mean), float(r.ltd_var)), "provenance": "DERIVED",
                "basis": ("rotable: pipeline demand over the repair pipeline (reliability-exposure rate x pipeline days)"
                          if r.part_class == "R" else "lead-time demand over the estimated purchase lead time")}
    hubc = ff[(ff.station == "AUH") & (ff.part_class == "C") & (ff.dist_kind == "nbinom")]
    cons_pn = hubc.sort_values("ltd_mean").pn.iloc[len(hubc) // 2]   # the median-demand hub consumable (no hard-coded PN)
    _p1 = ps1()
    ex_r, ex_c = ltd(_p1["pn"], _p1["station"]), ltd(cons_pn, "AUH")
    rvc = csv("outputs/forecasting/reliability_vs_croston.csv")
    rel_vs = tag([{"part_class": r["part_class"], "reliability_mase": r["reliability_mase"],
                   "reliability_ci": _ci_pair(r["reliability_ci"]), "best_croston_family": r["best_croston_family"],
                   "croston_family_mase": r["croston_family_mase"], "croston_family_ci": _ci_pair(r["croston_family_ci"]),
                   "reliability_better": bool(r["reliability_better"]), "cis_overlap": bool(r["cis_overlap"]),
                   "reliability_pinball_q90": r["reliability_pinball_q90"],
                   "croston_family_pinball_q90": r["croston_family_pinball_q90"]} for r in rvc.to_dict(orient="records")],
                 "DERIVED")
    attrs = part_attributes()
    mix = (attrs.groupby(["demand_class", "part_class"]).size().rename("n").reset_index())
    return {
        "meta": meta("DERIVED", ["outputs/forecasting/leaderboard.csv", "outputs/forecasting/leaderboard_by_class.csv",
                                 "outputs/holdout/forecast_leaderboard.csv", "outputs/holdout/forecast_leaderboard_by_class.csv",
                                 "outputs/forecasting/champions.csv", "outputs/holdout/forecast_champion_check.csv",
                                 "outputs/forecasting/stock_eval_summary.csv", "outputs/holdout/truth_recovery.json",
                                 "outputs/forecasting/monash_benchmark.json", "outputs/forecasting/final_forecasts.parquet",
                                 "outputs/forecasting/reliability_vs_croston.csv"],
                     "Forecast metrics are DERIVED from the SIMULATED history. leaderboard = selection (rolling origins "
                     "78-98, h=4 weeks, history weeks 0-103); leaderboard_holdout = the frozen methods scored on holdout "
                     "weeks. mase_ci = 95% bootstrap CI over parts; coverage = q90 coverage of the lead-time distribution. "
                     "Champions were frozen on selection (lowest mean MASE per cell, 'zero' excluded); champion_check "
                     "reports their holdout rank as-is (v2: the intermittent-rotable champion is read from "
                     "outputs/holdout/forecast_champion_check.csv; the policies size rotables on the reliability rate, not this champion). truth_recovery is an evaluation "
                     "output (estimates use history only; truth read only to score). Monash = REAL data, DERIVED metrics."),
        "leaderboard": _lb_rows(sel_lb, "selection"),
        "leaderboard_holdout": _lb_rows(hold_lb, "holdout"),
        "leaderboard_by_class": _lb_rows(csv("outputs/forecasting/leaderboard_by_class.csv"), "selection", True),
        "leaderboard_by_class_holdout": _lb_rows(csv("outputs/holdout/forecast_leaderboard_by_class.csv"), "holdout", True),
        "method_labels": METHOD_LABELS,
        "champions": champions, "champion_check": champion_check,
        "stock_eval": stock_eval, "truth_recovery": truth,
        "truth_recovery_detail": {"metric": tr["metric"], "note": tr["note"],
                                  "lead_time_changed_parts": lt["changed_parts"], "provenance": "DERIVED"},
        "monash": monash,
        "ltd_example": ex_r, "ltd_examples": [ex_r, ex_c],
        "reliability_vs_croston": rel_vs,
        "class_mix": tag(records(mix), "DERIVED"),
    }


# ----------------------------------------------------------------------------------------------
# rotables


def build_rotables() -> dict:
    rid = recommended_id()
    sc = hist("serialised_components").sort_values(["serial", "since_h"])
    n_loan = int((~sc.owned.astype(bool)).groupby(sc.serial).any().sum()) if "owned" in sc else 0
    # v2: borrowed exchange/loan units (owned = False) are not the airline's float; the lifecycle shows owned serials only
    if "owned" in sc:
        sc = sc[sc.owned.astype(bool)]
    nxt = sc.groupby("serial").state.shift(-1)
    flows = (pd.DataFrame({"from": sc.state, "to": nxt}).dropna().value_counts().rename("count").reset_index())
    last = sc.groupby("serial").tail(1)
    states = ["SERVICEABLE", "INSTALLED", "REMOVED", "IN_TRANSIT", "IN_REPAIR", "CONDEMNED"]
    counts = last.state.value_counts().reindex(states, fill_value=0)
    pm = hist("part_master").set_index("pn")
    ro = hist("repair_orders").copy()
    planted = pm.planted.dropna().to_dict()
    open_ = ro[ro.return_h.isna() & ~ro.condemned.astype(bool)].copy()   # condemned ROs close without a return
    recent = ro[ro.return_h.notna() & (ro.return_h >= AS_OF_H - 8 * HOURS_PER_WEEK)].copy()
    q = pd.concat([open_, recent])
    q["overdue"] = q.return_h.isna() & (q.quoted_due_h < AS_OF_H)
    # PS2 = the planted shop-TAT situation: the first RO of the PS2 PN removed inside its planted week window (truth metadata)
    pm2 = planted_meta().get("PS2", {})
    ps2_ro = None
    if pm2.get("pn") and isinstance(pm2.get("weeks"), list):
        w0, w1 = pm2["weeks"]
        cand = ro[(ro.pn == pm2["pn"]) & (ro.removed_h >= w0 * HOURS_PER_WEEK) & (ro.removed_h < (w1 + 1) * HOURS_PER_WEEK)].sort_values("removed_h")
        ps2_ro = int(cand.ro_id.iloc[0]) if len(cand) else None
    queue = []
    for r in q.sort_values(["overdue", "quoted_due_h"], ascending=[False, True]).itertuples():
        is_open = pd.isna(r.return_h)
        late_h = (AS_OF_H - r.quoted_due_h) if is_open else (r.return_h - r.quoted_due_h)
        queue.append({"ro_id": f"RO-{int(r.ro_id)}", "ro_num": int(r.ro_id), "serial": r.serial, "pn": r.pn,
                      "shop": r.shop, "removed_h": int(r.removed_h), "shop_in_h": int(r.shop_in_h),
                      "start_h": int(r.start_h), "due_h": int(r.quoted_due_h),
                      "return_h": None if is_open else int(r.return_h),
                      "status": "open" if is_open else ("condemned" if bool(r.condemned) else "returned"),
                      "overdue": bool(r.overdue), "weeks_late": round(max(late_h, 0) / HOURS_PER_WEEK, 1),
                      "planted": "PS2" if int(r.ro_id) == ps2_ro else (planted.get(r.pn) if r.pn in planted and planted.get(r.pn) != "PS2" else None),
                      "provenance": "SIMULATED"})
    # TAT: completed, non-condemned ROs for real removals (exclude units seeded at t0)
    done = ro[ro.return_h.notna() & ~ro.condemned.astype(bool) & ro.removal_id.notna()].copy()
    done["shop_tat_d"] = (done.return_h - done.shop_in_h) / 24.0
    done["cycle_d"] = (done.return_h - done.removed_h) / 24.0
    tat = []
    for (pn, shop), g in done.groupby(["pn", "shop"]):
        tat.append({"pn": pn, "desc": pm.at[pn, "description"], "shop": shop, "quoted_d": num(pm.at[pn, "repair_tat_mean_d"]),
                    "actual_mean_d": g.shop_tat_d.mean(), "median_d": g.shop_tat_d.median(),
                    "p90_d": g.shop_tat_d.quantile(0.9), "cycle_mean_d": g.cycle_d.mean(), "n": int(len(g)),
                    "planted": planted.get(pn), "provenance": "SIMULATED"})
    bins = list(range(0, 301, 10))
    dist = []
    for shop, g in done.groupby("shop"):
        h_, _ = np.histogram(g.cycle_d.clip(upper=299.9), bins=bins)
        dist.append({"shop": shop, "bin_width_d": 10, "bins_d": bins[:-1], "counts": [int(x) for x in h_],
                     "n": int(len(g)), "mean_d": g.cycle_d.mean(), "median_d": g.cycle_d.median(),
                     "p90_d": g.cycle_d.quantile(0.9), "quoted_mean_d": num(pm.loc[g.pn.unique(), "repair_tat_mean_d"].mean()),
                     "provenance": "SIMULATED"})
    # float examples
    ff = pq("outputs/forecasting/final_forecasts.parquet")
    hub = ff[(ff.station == "AUH") & (ff.part_class == "R")].set_index("pn")
    pvs = csv("outputs/policies/palm_vs_sim.csv")
    loop = (pvs[pvs.station == "AUH"].set_index("pn").eval("total_spares - base_stock"))
    st = stock_table()
    tot = st[st.part_class == "R"].groupby("pn")[["P0", "P1", "P2", rid]].sum()
    reasons = {r["pn"]: r["reason"] for r in jload("outputs/frontier/allocations.json")["allocations"][rid] if r.get("reason")}
    # station view (wave 4, C9): the pooled network float hides the outstation reality. For each rotable, one outstation:
    # the narrated incident's station for the planted PN that has one, else the outstation with the highest removal rate.
    from gnm.policy.analytic import float_calc
    outs_ff = ff[(ff.station != "AUH") & (ff.part_class == "R")]
    st_idx = st.set_index(["pn", "station"])
    _p1 = ps1()
    inc_st = {_p1["pn"]: _p1["station"]}

    def station_view(pn):
        g = outs_ff[outs_ff.pn == pn]
        if g.empty:
            return None
        s_ = inc_st.get(pn) if inc_st.get(pn) in set(g.station) else g.sort_values("removal_rate_day", ascending=False).station.iloc[0]
        r_ = g[g.station == s_].iloc[0]
        rate30, loop_d = float(r_.removal_rate_day) * 30.0, float(r_.t_eff_out_d)
        rs = _p2_resupply().get((pn, s_))
        units = {k: int(st_idx.at[(pn, s_), c]) for k, c in (("P0", "P0"), ("P2", "P2"), ("recommended", rid))}
        # wave C (AV2-14): station availability on the AUH resupply time (as P2 sizes it), not on the repair loop
        basis_d = rs if rs is not None else loop_d
        return {"station": s_, "rate_per_30d": rate30, "loop_days": loop_d, "resupply_days": rs,
                "basis": "resupply" if rs is not None else "loop", "units": units,
                "availability": {k: float(float_calc(rate30, basis_d, u, 0.0)["availability"]) for k, u in units.items()},
                "provenance": "DERIVED"}
    def station_views(pn):
        """A10: every outstation's own float on the AUH resupply time (P2 positioning), no pooling with the hub."""
        out = []
        for r_ in outs_ff[outs_ff.pn == pn].itertuples():
            rs = _p2_resupply().get((pn, r_.station))
            if rs is None:
                continue
            rate30 = float(r_.removal_rate_day) * 30.0
            units = {k: int(st_idx.at[(pn, r_.station), c]) for k, c in (("P0", "P0"), ("P1", "P1"), ("P2", "P2"), ("recommended", rid))}
            if rate30 <= 0 and not any(units.values()):
                continue   # part not flown to / not held at this station
            out.append({"station": r_.station, "rate_per_30d": rate30, "resupply_days": rs, "basis": "resupply",
                        "units": units,
                        "availability": {k: float(float_calc(rate30, rs, u, 0.0)["availability"]) for k, u in units.items()},
                        "invalid_recommendation": bool(pn in brake_pns() and (units["P2"] > 0 or units["recommended"] > 0)),
                        "provenance": "DERIVED"})
        return out
    floats = []
    for pn in hub.index:
        r = hub.loc[pn]
        floats.append({"pn": pn, "desc": pm.at[pn, "description"], "deadline": pm.at[pn, "deadline_class"],
                       "station": "network", "rate_per_30d": float(r.net_removal_rate_day) * 30.0,
                       "pipeline_days": num(r.t_eff_hub_d), "unit_cost_aed": num(pm.at[pn, "unit_cost_aed"]),
                       "loop_units": int(loop.get(pn, 0)),
                       "p0_units": int(tot.at[pn, "P0"]), "p1_units": int(tot.at[pn, "P1"]),
                       "p2_units": int(tot.at[pn, "P2"]), "rec_units": int(tot.at[pn, rid]),
                       "current": int(tot.at[pn, "P0"]), "recommended": int(tot.at[pn, rid]),
                       # S as the float calculator defines it: serviceable base stock + the units already in the loop
                       "spares_total": {k: int(tot.at[pn, c]) + int(loop.get(pn, 0))
                                        for k, c in (("P0", "P0"), ("P1", "P1"), ("P2", "P2"), ("recommended", rid))},
                       "reason": reasons.get(pn, ""), "planted": planted.get(pn), "station_view": station_view(pn),
                       "station_views": station_views(pn),
                       "provenance": "DERIVED"})
    floats.sort(key=lambda x: (x["planted"] is None, x["pn"]))
    keep = ["pn", "station", "deadline_class", "base_stock", "total_spares", "rate_per_year", "pipeline_days",
            "pipeline_mean", "palm_availability", "palm_ebo", "palm_availability_hub_resupply", "sim_requests",
            "sim_immediate_fill", "sim_avg_backorders", "fill_gap_sim_minus_palm"]
    pvs_rows = tag(records(pvs[(pvs.total_spares > 0) | (pvs.sim_requests > 0)][keep]), "DERIVED")
    return {
        "meta": meta("SIMULATED", ["data/processed/history/serialised_components.parquet",
                                   "data/processed/history/repair_orders.parquet", "data/processed/history/part_master.parquet",
                                   "outputs/forecasting/final_forecasts.parquet", "outputs/policies/palm_vs_sim.csv",
                                   "outputs/policies/P0_stock_params.csv", "outputs/policies/P1_stock_params.csv",
                                   "outputs/policies/P2_stock_params.csv", "outputs/frontier/allocations.json"],
                     f"History weeks 0-103 under P0 (SIMULATED). lifecycle.flows = consecutive state transitions per serial; "
                     f"counts = each serial's state at the end of history. repair_queue = ROs open at h {AS_OF_H} (end of "
                     "history; condemned ROs close without a return and are excluded) plus ROs returned in the last 8 weeks; overdue = open and past the quoted due date; PS2 = "
                     "the first RO of the PS2 PN removed in its planted window (truth metadata). tat = completed, non-condemned ROs of real removals (units seeded at t0 excluded): shop TAT "
                     "= return - shop in; cycle = return - removal. float_examples feed the float calculator: rate_per_30d "
                     "= network reliability-exposure removal rate, pipeline_days = hub effective pipeline (T_eff), units = "
                     f"serviceable base stock (P0/P1/P2/{rid}); loop_units = units the engine seeds in the repair loop "
                     "(palm_vs_sim total_spares - base_stock at AUH), so Palm total spares = units + loop_units. station_view = one "
                     "outstation's own float (the PS1 incident's station for its PN, else the outstation with the highest removal rate): "
                     "its removal rate, effective loop days (T_eff_out), the units P0/P2/the frontier option place there and "
                     "Palm availability for each (no pooling with the hub). "
                     "palm_vs_sim = P1 floats on selection seeds 100-119 (Palm analytic vs simulated fill; inventory-policy note section 7), DERIVED.",
                     provenance_by_key={"as_of_h": "ASSUMED"}),
        "as_of_h": AS_OF_H, "recommended_id": rid,
        "lifecycle": {"states": states, "counts": {s: int(counts[s]) for s in states}, "n_loan_serials_excluded": n_loan,
                      "flows": records(flows), "n_serials": int(sc.serial.nunique()), "provenance": "SIMULATED"},
        "repair_queue": queue,
        "repair_summary": {"open": int(len(open_)), "overdue": int(q.overdue.sum()),
                           "returned_last_8w": int(len(recent)), "provenance": "SIMULATED"},
        "tat": tat, "tat_distribution": dist,
        "float_examples": floats, "palm_vs_sim": pvs_rows, "palm_vs_sim_policy": "P1",
        # v2.1 A10: which time each calculator view uses
        "calculator_modes": {
            "hub": {"label": "Hub pooled view", "basis": "network repair-loop time",
                    "fields": {"rate": "float_examples[].rate_per_30d", "days": "float_examples[].pipeline_days",
                               "spares": "float_examples[].spares_total"},
                    "note": "network removal rate over the hub effective repair-loop time (T_eff); spares = serviceable base stock + units already in the loop"},
            "outstation": {"label": "Outstation view", "basis": "resupply time from AUH",
                           "fields": {"rate": "float_examples[].station_views[].rate_per_30d",
                                      "days": "float_examples[].station_views[].resupply_days",
                                      "spares": "float_examples[].station_views[].units"},
                           "note": "station removal rate over the routine resupply time from AUH plus the expected hub wait "
                                   "(outputs/policies/p2_positioning.csv), as the Network Plan sizes station stock"},
        },
        "outstation_mode": "enabled",
        "resupply_source": "outputs/policies/p2_positioning.csv (resupply_days + hub_wait_days)",
    }


# ----------------------------------------------------------------------------------------------
# network


def build_network() -> dict:
    rid = recommended_id()
    net = cfg()["network"]
    sm = hist("station_master").set_index("station")
    st = stock_table()
    st_val = {}
    for pid in ["P0", "P1", "P2", rid]:
        x = st.assign(v=st[pid] * st.unit_cost_aed)
        st_val[pid] = {"units": x[x.part_class == "R"].groupby("station")[pid].sum(),
                       "value": x.groupby("station").v.sum()}
    mr = hist("material_requests")
    req = mr.groupby("station").size()
    req_d0 = mr[mr.deadline_class == "D0"].groupby("station").size()
    skp = pq("outputs/holdout/policy_station_kpis.parquet")
    skp = skp[skp.variant == "central"]
    means = skp.groupby(["policy_id", "station"])[["immediate_fill_rate", "rotable_fill_rate", "aog_hours", "aog_events", "aog_hours_D0", "requests"]].mean()
    ps = jload("outputs/holdout/policy_summary.json")
    bys = {(r["policy_id"], r["station"]): r for r in ps["by_station"] if r["variant"] == "central"}
    aog_hist = {r["station"]: r for r in jload("outputs/aog_lab/summary.json")["by_station"]}
    p0max = max(means.loc[("P0", s), "aog_hours"] for s in stations())
    outs = [s for s in stations() if s != net["hub"]]
    out_max = max(means.loc[("P0", s), "aog_hours"] for s in outs) or 1.0
    out_rank = {s: i + 1 for i, s in enumerate(sorted(outs, key=lambda s: -means.loc[("P0", s), "aog_hours"]))}
    acts_ = jload("outputs/actions/actions.json")["actions"]
    n_act = Counter(a["station"] for a in acts_)
    n_urg = Counter(a["station"] for a in acts_ if a["severity"] == "urgent")

    def out_level(s):
        rel = means.loc[("P0", s), "aog_hours"] / out_max
        lvl = "urgent" if rel >= OUT_URGENT_REL else "review" if rel >= OUT_REVIEW_REL else "ok"
        return "review" if lvl == "ok" and n_urg.get(s, 0) else lvl   # open urgent actions never read OK
    st_rows = []
    for s in stations():
        st_rows.append({
            "station": s, "name": sm.at[s, "name"], "lat": float(sm.at[s, "lat"]), "lon": float(sm.at[s, "lon"]),
            "role": sm.at[s, "role"],
            "serviceable_units": int(st_val[rid]["units"].get(s, 0)), "stock_value": aed(st_val[rid]["value"].get(s, 0)),
            "by_policy": {pid: {"rotable_units": int(st_val[pid]["units"].get(s, 0)),
                                "stock_value_aed": aed(st_val[pid]["value"].get(s, 0))} for pid in st_val},
            "requests": int(req.get(s, 0)), "requests_d0": int(req_d0.get(s, 0)),
            "aog_events_hist": int(aog_hist.get(s, {}).get("events", 0)), "aog_hours_hist": num(aog_hist.get(s, {}).get("aog_hours", 0)),
            "risk": float(means.loc[("P0", s), "aog_hours"] / p0max),
            "risk_vs_outstations": (None if s == net["hub"] else float(means.loc[("P0", s), "aog_hours"] / out_max)),
            "outstation_rank": (None if s == net["hub"] else out_rank[s]),
            "outstation_risk_level": (None if s == net["hub"] else out_level(s)),
            "n_actions": int(n_act.get(s, 0)), "n_urgent_actions": int(n_urg.get(s, 0)),
            "aog_hours_by_policy": {pid: {"mean": float(means.loc[(pid, s), "aog_hours"]),
                                          "ci": bys[(pid, s)]["aog_hours_ci"]} for pid in ["P0", "P1", "P2"]},
            "coord_provenance": "REAL", "provenance": "SIMULATED",
        })
    tr = hist("transfers")
    arcs = []
    for s in net["outstations"]:
        g = tr[(tr.from_station == net["hub"]) & (tr.to_station == s)]
        arcs.append({"from": net["hub"], "to": s, "aog_transport_h": num(net["aog_transport_hours"][net["hub"]][s]),
                     "transfers": int(len(g)), "routine": int((g.kind == "routine").sum()),
                     "emergency": int((g.kind == "emergency").sum()),
                     "qty": int(g.qty.sum()), "provenance": "SIMULATED"})
    other = tr[tr.from_station != net["hub"]]
    lateral = tag(records(other.groupby(["from_station", "to_station", "kind"]).size().rename("count").reset_index()), "SIMULATED")
    # transfer replay around the PS1 incident (incidents.json ps1_incident_id)
    inc = ps1()["incident"]
    tid = next(s["evidence"]["transfer_id"] for s in inc["timeline"] if s["step"] == "shipped")
    t0 = int(inc["need_h"])
    w = [t0 - 72, t0 + 96]
    win = tr[(tr.ship_h >= w[0]) & (tr.ship_h <= w[1])].sort_values("ship_h")
    events = [{"t_h": int(r.ship_h), "arrive_h": int(r.arrive_h), "from": r.from_station, "to": r.to_station,
               "pn": r.pn, "qty": int(r.qty), "kind": r.kind, "transfer_id": int(r.transfer_id),
               "focus": int(r.transfer_id) == tid} for r in win.itertuples()]
    focus = tr[tr.transfer_id == tid].iloc[0]
    replay = {"window_h": w, "events": events,
              "focus": {"incident_id": inc["id"], "planted": "PS1", "pn": inc["pn"], "desc": inc["desc"], "tail": inc["tail"],
                        "station": inc["station"], "deadline": inc["deadline"], "need_h": t0, "transfer_id": tid,
                        "ship_h": int(focus.ship_h), "arrive_h": int(focus.arrive_h), "cost_aed": num(focus.cost_aed),
                        "aog_hours": num(inc["aog_hours"]),
                        "timeline": [{k: s[k] for k in ["t_h", "abs_h", "station", "event", "step"]} for s in inc["timeline"]]},
              "provenance": "SIMULATED"}
    compare = []
    for pid in ["P0", "P1", "P2"]:
        for s in stations():
            m, b = means.loc[(pid, s)], bys[(pid, s)]
            compare.append({"policy_id": pid, "display_name": v21.display_name(pid), "station": s, "fill_rate": float(m.immediate_fill_rate),
                            "fill_ci": b["immediate_fill_rate_ci"], "rotable_fill_rate": float(m.rotable_fill_rate),
                            "aog_hours": float(m.aog_hours), "aog_ci": b["aog_hours_ci"],
                            "aog_hours_D0": float(m.aog_hours_D0), "aog_events": float(m.aog_events),
                            "requests": float(m.requests), "provenance": "SIMULATED"})
    paired = tag([r for r in ps["paired_by_station"] if r["variant"] == "central"], "SIMULATED")
    return {
        "meta": meta("SIMULATED", ["data/processed/history/station_master.parquet", "config/assumptions.yaml (network)",
                                   "data/processed/history/material_requests.parquet", "data/processed/history/transfers.parquet",
                                   "outputs/holdout/policy_station_kpis.parquet", "outputs/holdout/policy_summary.json",
                                   "outputs/aog_lab/incidents.json", "outputs/aog_lab/summary.json",
                                   "outputs/policies/P0_stock_params.csv", "outputs/policies/P1_stock_params.csv",
                                   "outputs/policies/P2_stock_params.csv", "outputs/frontier/allocations.json"],
                     "Station coordinates are REAL (OurAirports via station_master / config); everything else SIMULATED. "
                     f"serviceable_units / stock_value = the recommended {rid} plan's rotable serviceable target units and "
                     "all-class stock value at target (by_policy gives P0/P1/P2/" + rid + "). requests = history material "
                     "requests (2 years, P0). risk = the station's holdout P0 material AOG h/yr divided by the worst "
                     "station's (0-1; the hub is the worst, so outstations look small on it). For outstations, "
                     "risk_vs_outstations = the same AOG h divided by the riskiest OUTSTATION's, outstation_rank (1 = riskiest) and "
                     f"outstation_risk_level (urgent >= {OUT_URGENT_REL:g}, review >= {OUT_REVIEW_REL:g}, ASSUMED bands; an outstation "
                     "with open urgent planner actions is at least review); n_actions / n_urgent_actions = actions.json "
                     "exceptions at the station. Hub: those fields are null. aog_hours_by_policy and policy_compare = holdout seeds 2000-2019, central, means "
                     "over seeds (from policy_station_kpis.parquet) with 95% CIs from policy_summary.json. The recommended "
                     f"{rid} plan has no per-station holdout breakdown (frontier holdout reports network totals only). "
                     "arcs = history transfers AUH->station by kind; transfer_replay = real history transfers around the "
                     f"PS1 incident {inc['id']} ({inc['pn']} at {inc['station']})."),
        "hub": net["hub"], "recommended_id": rid,
        "stations": st_rows, "arcs": arcs, "lateral_flows": lateral,
        "transfer_replay": replay, "policy_compare": compare, "paired_by_station": paired,
        "display_names": names_v21(),
    }


# ----------------------------------------------------------------------------------------------
# frontier

KIND_MAP = {"policy": "policy", "budget": "greedy", "incremental": "greedy", "reposition": "greedy",
            "lever": "lever", "combo": "combo"}


def _point(pid: str, r: pd.Series, sel: pd.Series, split: str) -> dict:
    p = {"id": pid, "label": sel.label, "display_name": v21.display_name(pid), "short_name": v21.display_name(pid, short=True),
         "kind": KIND_MAP.get(sel.kind, sel.kind), "subkind": sel.kind,
         "capital_aed": r.capital_mean, "capital_ci": [r.capital_lo, r.capital_hi],
         "aog_hours": r.aog_hours_mean, "aog_ci": [r.aog_hours_lo, r.aog_hours_hi],
         "total_cost_aed": r.total_cost_mean, "total_cost_ci": [r.total_cost_lo, r.total_cost_hi],
         "fill_rate": r.fill_rate_mean, "fill_ci": [r.fill_rate_lo, r.fill_rate_hi],
         "aog_events": r.aog_events_mean, "expedite_cost_aed": r.expedite_cost_mean,
         "d_aog_vs_P2": r.d_aog_hours_vs_base_mean, "d_aog_vs_P2_ci": [r.d_aog_hours_vs_base_lo, r.d_aog_hours_vs_base_hi],
         "d_total_cost_vs_P2_aed": r.d_total_cost_vs_base_mean, "d_total_cost_vs_P2_ci": [r.d_total_cost_vs_base_lo, r.d_total_cost_vs_base_hi],
         "d_capital_vs_P2_ci": [r.d_capital_vs_base_lo, r.d_capital_vs_base_hi],
         "d_capital_vs_P2_aed": r.d_capital_vs_base_mean, "split": split, "n_seeds": int(r.n_seeds),
         "allocation_capital_aed": num(sel.allocation_capital_aed), "model_aog_hours": num(sel.model_aog_hours),
         "provenance": "SIMULATED"}
    if num(sel.budget_aed) is not None:
        p["budget_aed"] = num(sel.budget_aed)
    return p


def build_frontier() -> dict:
    rid = recommended_id()
    summ = jload("outputs/frontier/summary.json")
    fh, fs = frontier_holdout(), selection_points()
    dom = nondominated([(i, float(r.capital_mean), float(r.aog_hours_mean)) for i, r in fh.iterrows()])
    points = []
    for pid, r in fh.iterrows():
        p = _point(pid, r, fs.loc[pid], "holdout")
        p.update({"dominated": dom[pid], "recommended": pid == rid, "baseline": pid == BASELINE,
                  "base_policy": pid == BASE_POLICY,
                  "selection_dominated": bool(fs.at[pid, "dominated"]), "selection_on_hull": bool(fs.at[pid, "on_hull"]),
                  "selection_capital_aed": fs.at[pid, "capital_mean"], "selection_aog_hours": fs.at[pid, "aog_hours_mean"]})
        points.append(p)
    points.sort(key=lambda p: p["capital_aed"])
    sel_points = []
    for pid, r in fs.iterrows():
        p = _point(pid, r, r, "selection")
        p.update({"dominated": bool(r.dominated), "on_hull": bool(r.on_hull), "recommended": bool(r.recommended)})
        sel_points.append(p)
    sel_points.sort(key=lambda p: p["capital_aed"])
    # allocations (trimmed)
    allocs, totals = {}, {}
    for pid, rows in jload("outputs/frontier/allocations.json")["allocations"].items():
        df = pd.DataFrame(rows)
        totals[pid] = {"n_rows": int(len(df)), "delta_units": int(df.delta_units.sum()),
                       "delta_capital_aed": aed(df.incremental_capital_aed.sum()),
                       "risk_reduction": num(df.modelled_aog_hour_reduction.sum()),
                       "n_flagged_more_than_doubles_p0": int(df.flag_more_than_doubles_p0.sum()),
                       "n_rows_shown": int(min(len(df), ALLOC_ROWS_PER_POINT)), "provenance": "DERIVED"}
        df = df.reindex(df.modelled_aog_hour_reduction.abs().sort_values(ascending=False).index).head(ALLOC_ROWS_PER_POINT)
        out = []
        for r in df.to_dict(orient="records"):
            row = {"pn": r["pn"], "station": r["station"], "part_class": r["part_class"], "level": r["level"],
                   "current": int(r["current"]), "proposed": int(r["proposed"]), "delta_units": int(r["delta_units"]),
                   "delta_capital": r["incremental_capital_aed"], "risk_reduction": r["modelled_aog_hour_reduction"],
                   "alt_action": r["best_alternative_action"], "flag_more_than_doubles_p0": bool(r["flag_more_than_doubles_p0"])}
            if pid == rid and r.get("reason"):
                row["reason"] = r["reason"]
            if r["pn"] in brake_pns() and r["station"] != cfg()["network"]["hub"] and int(r["proposed"]) > 0:
                row["invalid_recommendation"] = True     # A9: flagged, kept (frozen)
                row["flag_text"] = v21.A9_FLAG
            out.append(row)
        allocs[pid] = out
    lev = csv("outputs/frontier/levers.csv")
    levers = tag([{"pn": r["pn"], "lever": r["lever"], "detail": r["detail"], "unit_cost_aed": r["unit_cost_aed"],
                   "annual_removals": r["annual_removals"], "pipeline_days": r["pipeline_days"],
                   "current_units": int(r["current_units"]), "base_aog_hours": r["base_aog_hours"],
                   "incremental_capital_aed": r["incremental_capital_aed"], "annual_cost_aed": r["annual_cost_aed"],
                   "aog_hours_reduction": r["aog_hours_reduction"], "penalty_saved_aed": r["penalty_saved_aed"],
                   "net_annual_benefit_aed": r["net_annual_benefit_aed"],
                   "annual_cost_per_aog_hour_aed": r["annual_cost_per_aog_hour_aed"]} for r in lev.to_dict(orient="records")],
                 "DERIVED")
    tor = csv("outputs/frontier/tornado.csv")
    base = tor[tor.factor == "base case"].iloc[0]
    tornado = []
    for f, g in tor[(tor.factor != "base case")].groupby("factor", sort=False):
        if len(g) < 2:
            continue
        lo, hi = g.iloc[0], g.iloc[1]
        tornado.append({"param": f"{f.replace('_', ' ')} {lo.setting} / {hi.setting}", "factor": f,
                        "low_setting": str(lo.setting), "high_setting": str(hi.setting), "method": lo.method,
                        "low": lo.net_benefit_mean - base.net_benefit_mean, "high": hi.net_benefit_mean - base.net_benefit_mean,
                        "base": base.net_benefit_mean,
                        "low_value": lo.net_benefit_mean, "low_ci": [lo.net_benefit_lo, lo.net_benefit_hi],
                        "high_value": hi.net_benefit_mean, "high_ci": [hi.net_benefit_lo, hi.net_benefit_hi],
                        "low_aog_saved": lo.aog_reduction_mean, "high_aog_saved": hi.aog_reduction_mean,
                        "low_vs_p0": lo.p0_net_benefit_mean, "high_vs_p0": hi.p0_net_benefit_mean,
                        "provenance": "SIMULATED"})
    off = tor[tor.factor.str.contains("expedite")]
    desk = {"text": summ["aog_desk_dependence"], "provenance": "SIMULATED"}
    if len(off):
        o = off.iloc[0]
        desk.update({"factor": o.factor, "setting": str(o.setting), "rec_aog_hours": o.rec_aog_hours,
                     "base_aog_hours": o.base_aog_hours, "p0_aog_hours": o.p0_base_aog_hours,
                     "central_rec_aog_hours": base.rec_aog_hours, "central_base_aog_hours": base.base_aog_hours,
                     "central_p0_aog_hours": base.p0_base_aog_hours})
    robust = []
    for v in ["low_stress", "central", "high_stress"]:
        sp = selection_points(v)
        row = {"variant": v}
        for pid in [x for x in ["P0", "P1", "P2", rid] if x in sp.index]:   # v2 stress worlds evaluate P0 / P2 / I125 only
            row[pid] = {"aog_hours": sp.at[pid, "aog_hours_mean"], "capital_aed": sp.at[pid, "capital_mean"]}
        if v == "central":
            rv = summ["recommended_vs_base_policy"]
            row["rule_recommends"] = rid
        else:
            rv = summ["variants"][v]["recommended_point_vs_base_policy"]
            row["rule_recommends"] = summ["variants"][v]["rule_would_recommend"]
        row["rec_vs_P2"] = {"aog_reduction": rv["aog_reduction_mean"], "aog_reduction_ci": [rv["aog_reduction_lo"], rv["aog_reduction_hi"]],
                            "net_benefit_aed": rv["net_benefit_mean"], "net_benefit_ci": [rv["net_benefit_lo"], rv["net_benefit_hi"]]}
        row["provenance"] = "SIMULATED"
        robust.append(row)
    rec = summ["recommendation"]
    return {
        "meta": meta("SIMULATED", ["outputs/holdout/frontier_points.csv", "outputs/frontier/selection_points.csv",
                                   "outputs/frontier/summary.json", "outputs/frontier/allocations.json",
                                   "outputs/frontier/levers.csv", "outputs/frontier/tornado.csv"],
                     "points = the 25 frozen candidates on holdout seeds 2000-2019 (central): capital = simulated time-average "
                     "spare capital, aog_hours = material AOG h/yr, 95% CIs over seeds. kind: policy (P0/P1/P2) / greedy "
                     "(subkind budget = re-optimised allocation, incremental = P2 + greedy additions) / lever / combo. "
                     "dominated = computed here from the HOLDOUT means over all 25 points (minimise capital and AOG h); "
                     "selection_dominated / selection_on_hull = the optimiser's selection-seed flags. recommended = the "
                     "pre-stated rule applied on SELECTION seeds (summary.json), not re-chosen on holdout. B250 has one "
                     "unstable holdout seed (very wide CI); reported, not removed (D011). allocations = rows vs P2, top "
                     f"{ALLOC_ROWS_PER_POINT} per point by |modelled AOG-hour reduction| (analytic model, leave-one-out, "
                     "not simulated) with untrimmed totals in allocation_totals; 'reason' kept for the recommended point "
                     "only. levers = levers.csv (annual-basis lever comparison at the P2 allocation, modelled). tornado = "
                     "net benefit of the recommended point vs P2 (AED/yr); low/high are differences from the base case.",
                     provenance_by_key={"allocations": "DERIVED"}),
        "split": "holdout", "baseline": BASELINE, "base_policy": BASE_POLICY, "recommended": rid,
        "seeds_label": (lambda sd: f"holdout seeds {min(sd)}–{max(sd)}")(jload("outputs/holdout/policy_summary.json")["seeds"]),
        "selection_seeds_label": "selection seeds 100–119",
        "points": points, "selection_points": sel_points,
        "recommendation": {"rule": summ["recommendation_rule"], "h_star_per_aed_1m": rec["h_star_per_aed_1m"],
                           "aed_per_aog_hour": rec["aed_per_aog_hour"], "carrying_pct": rec["carrying_pct"],
                           "hull": rec["hull"], "segments": rec["segments"],
                           "stability": summ["recommendation_stability"],
                           "recommended_vs_P2_selection": summ["recommended_vs_base_policy"],
                           "recommended_vs_P0_selection": summ["recommended_vs_P0"],
                           "beats_P2_significantly_selection": summ["recommended_beats_base_policy_significantly"],
                           "provenance": "SIMULATED"},
        "allocations": allocs, "allocation_totals": totals,
        "levers": levers, "lever_findings": summ["lever_findings"],
        "tornado": tornado, "variant_robustness": robust, "aog_desk_dependence": desk,
        # v2.1 (additive)
        "display_names": names_v21(), "scope_line": v21.SCOPE_LINE,
        "insight": frontier_insight(build_headline()), "capital_table": capital_table(build_headline()["core"]["remix"]),
        "stress_worlds": stress_worlds(), "invalid_allocation_text": v21.A9_FLAG,
        "subtitle": "how much readiness each extra dirham buys",
    }


# ----------------------------------------------------------------------------------------------
# aog lab, actions


def build_aog_lab() -> dict:
    inc = jload("outputs/aog_lab/incidents.json")
    summ = jload("outputs/aog_lab/summary.json")
    payload = {k: v for k, v in inc.items() if k not in ("meta",)}
    payload["summary"] = {k: v for k, v in summ.items() if k not in ("meta",)}
    payload["summary"].setdefault("provenance", "SIMULATED")
    cal = cfg()["calendar"]
    # simulated calendar for timestamps (theme.js fmtSimTime: "W103 · d4 06:00"); never real dates
    payload["sim_calendar"] = {"epoch": cal["epoch"], "hours_per_week": HOURS_PER_WEEK, "day1": "Monday",
                               "provenance": "ASSUMED"}
    for i in payload["incidents"]:
        i.setdefault("provenance", "SIMULATED")
        rec = next((o for o in i["options"] if o.get("rank") == 1), None)
        i["recommended_option"] = None if rec is None else rec["key"]
        d_ = i.get("decision") or {}
        # one MEL sentence site-wide (wave C)
        d_["checks"] = [re.sub(r"\(D0/D3/D10 are hypothetical simulation classes, not operator MEL decisions\)",
                               "(D0/D3/D10 are hypothetical rectification windows; D3/D10 are simplified analogues of MEL "
                               "repair-interval categories B and C, not operator MEL decisions)", c) for c in d_.get("checks") or []]
    return {
        "meta": meta("SIMULATED", ["outputs/aog_lab/incidents.json", "outputs/aog_lab/summary.json"],
                     inc["meta"]["notes"] + " NOTE: exposure_aed ALREADY INCLUDES direct_cost - never add them; the best "
                     "option is the rank===1 option (recommended_option / decision.recommended). Infeasible options carry "
                     "wait_h/exposure_aed null except pool (indicative, greyed) and acceleration (estimate)."),
        **payload,
    }


def build_actions() -> dict:
    a = jload("outputs/actions/actions.json")
    def plural_fix(txt):
        """'Position 1 unit(s)' -> 'Position 1 unit', '3 unit(s)' -> '3 units' (F5: never 'unit(s)')."""
        if not isinstance(txt, str):
            return txt
        txt = re.sub(r"(\d+(?:\.\d+)?) (\w+)\(s\)", lambda m: f"{m.group(1)} {m.group(2)}{'' if m.group(1) == '1' else 's'}", txt)
        # '1 D0 requests' -> '1 D0 request' (counts printed by the rule engine without plural())
        txt = re.sub(r"\b1 ((?:D\d+ |AOG )?)(request|event|unit|exception|week)s\b", r"1 \1\2", txt)
        # '(2.0x)' -> '(×2.0)': the design system's multiplication sign, leading (wave 5, F6)
        return re.sub(r"\b(\d+(?:\.\d+)?)x\b", "\u00d7\\1", txt)
    acts = [dict(x, provenance=x.get("provenance", "SIMULATED" if x["type"] == "QUARANTINE_DOCS" else "DERIVED"),
                 summary=plural_fix(x.get("summary")), recommended_action=plural_fix(x.get("recommended_action")),
                 type_label=ACTION_TYPE_LABEL.get(x["type"], x["type"].replace("_", " ").capitalize()),
                 severity_label=str(x["severity"]).capitalize())
            for x in a["actions"]]
    return {
        "meta": meta("DERIVED", ["outputs/actions/actions.json"], a["meta"]["notes"] + " type_label / severity_label = "
                     "plain-language labels for type / severity (the UI and the CSV export use them).",
                     provenance_by_key={"as_of_week": "ASSUMED"}),
        "as_of_week": a["as_of_week"], "counts": {**a["counts"], "provenance": "DERIVED"}, "actions": acts,
    }


# ----------------------------------------------------------------------------------------------
# method


def parse_test_results(path: Path) -> dict:
    if not path.exists():
        return {"status": "not run", "tests_passed": None, "tests_total": None,
                "reason": f"{rel(path)} not found"}
    txt = path.read_text()
    tail = txt.strip().splitlines()[-5:]
    line = next((l for l in reversed(txt.splitlines()) if re.search(r"\d+ (passed|failed)", l)), "")

    def n(word):
        m = re.search(rf"(\d+) {word}", line)
        return int(m.group(1)) if m else 0
    passed, failed, errors = n("passed"), n("failed"), n("errors?")
    cmd = next((l.split(":", 1)[1].strip() for l in txt.splitlines() if l.lower().startswith("# command:")), None)
    return {"status": "pass" if failed == 0 and errors == 0 and passed > 0 else "fail",
            "tests_passed": passed, "tests_failed": failed, "tests_errors": errors, "tests_skipped": n("skipped"),
            "tests_deselected": n("deselected"), "tests_total": passed + failed + errors,
            "summary_line": line.strip("= ").strip(), "command": cmd,
            "ran_at": dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).replace(microsecond=0).isoformat(),
            "tail": tail}


def parse_junit(path: Path) -> dict:
    """v2.2: test counts from reports/junit.xml (the same file README and VALIDATION_REPORT read). No test file names."""
    import xml.etree.ElementTree as ET
    if not path.exists():
        return {"status": "not run", "tests_passed": None, "tests_total": None, "reason": f"{rel(path)} not found"}
    root = ET.parse(path).getroot()
    suite = next(root.iter("testsuite")).attrib
    total, failed, errors, skipped = (int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    mods = {tc.get("classname", "").split(".")[-1] for tc in root.iter("testcase")}
    browser = any(m.startswith("test_site_") and m != "test_site_data" for m in mods)
    scope = ("full suite: fast, slow and browser tests" if browser else
             "non-browser suite: fast and slow tests; the Playwright browser suite runs separately")
    passed = total - failed - errors - skipped
    ts = dt.datetime.fromisoformat(suite["timestamp"])
    ran_at = (ts.astimezone(dt.timezone.utc) if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)).replace(microsecond=0)
    return {"status": "pass" if failed == 0 and errors == 0 and passed > 0 else "fail",
            "tests_passed": passed, "tests_failed": failed, "tests_errors": errors, "tests_skipped": skipped,
            "tests_deselected": 0, "tests_total": total - skipped, "scope": scope,
            "summary_line": f"{passed} of {total - skipped} tests passed, {failed + errors} failed ({scope})",
            "command": ("GNM_RELEASE=1 pytest -p no:cacheprovider -q --junitxml=reports/junit.xml" if browser else
                        'GNM_RELEASE=1 pytest -m "not browser" -p no:cacheprovider -q --junitxml=reports/junit.xml'),
            "ran_at": ran_at.isoformat(), "tail": []}


def _author_wording(t: str) -> str:
    """Site wording for decision/assumption text: the author made these choices before calibration (wave C)."""
    t = re.sub(r"(?:chosen by )?the user's fewest-changes rule", "the fewest-changes rule chosen before calibration", t)
    t = re.sub(r"\(user request,", "(author's request,", t)
    t = re.sub(r"\bChosen by the user\b", "Chosen by the author", t)
    t = re.sub(r"\bby the user\b", "by the author", t)
    return t


def v1_archive() -> dict:
    """The archived v1 headline (archive/v1/README.md), shown on Method as superseded, never as a finding."""
    path = ROOT / "archive" / "v1" / "README.md"
    if not path.exists():
        return {"status": "not found"}
    txt = path.read_text()
    rows = []
    for line in txt.splitlines():
        m = re.match(r"\|\s*(P0|P1|P2|I125)\b([^|]*)\|\s*([\d,]+)\s*\[([\d,]+)[–-]([\d,]+)\]\s*\|\s*AED ([\d.]+)M\s*\|", line)
        if m:
            rows.append({"policy": m.group(1), "label": (m.group(1) + m.group(2)).strip().replace("recommended", "v1 frontier pick"), "aog_hours": int(m.group(3).replace(",", "")),
                         "aog_ci": [int(m.group(4).replace(",", "")), int(m.group(5).replace(",", ""))], "capital_aed": float(m.group(6)) * 1e6})
    reasons = [l[2:].strip() for l in txt.split("## Why it was superseded", 1)[-1].splitlines() if l.startswith("- ")]
    tag_m = re.search(r"Git tag: `([^`]+)` \(commit ([0-9a-f]+)\)", txt)
    return {"tag": tag_m.group(1) if tag_m else None, "commit": tag_m.group(2) if tag_m else None, "holdout_seeds": "retired v1 holdout (archived)",
            "headline": rows, "superseded_because": reasons,
            "note": "v1 overstated P0's AOG and the size of the improvement; these numbers are not findings (archive/v1/README.md).",
            "provenance": "SIMULATED"}


def av2_findings() -> list[dict]:
    """A12: every AV2 finding (reports/review_aviation_v2.md) with its v2.1 status. fixed = the VALIDATION_REPORT
    'v2 reviews' fixed list; next experiment = answered by a listed next experiment; disclosed = LIMITATIONS 29-39."""
    txt = (ROOT / "reports" / "review_aviation_v2.md").read_text()
    rows = []
    for m in re.finditer(r"^\|\s*(AV2-\d{2})\s*\|\s*\**(critical|major|minor)\**\s*\|", txt, re.M):
        fid, sev = m.group(1), m.group(2)
        if fid in v21.AV2_FIXED:
            status, detail, lim = "fixed", v21.AV2_FIXED[fid], None
        else:
            lim = v21.AV2_LIMITATION.get(fid, v21.AV2_MINOR_LIMITATION)
            if fid in v21.AV2_NEXT:
                status, detail = "next experiment", v21.AV2_NEXT[fid]
            else:
                status, detail = "disclosed", f"LIMITATIONS {lim}"
        rows.append({"id": fid, "severity": sev, "title": v21.AV2_TITLES[fid], "status": status, "status_detail": detail,
                     "limitation": lim, "v21_note": v21.AV2_V21_NOTE.get(fid), "provenance": "DERIVED"})
    ids = [r["id"] for r in rows]
    if ids != [f"AV2-{i:02d}" for i in range(1, 26)]:
        raise RuntimeError(f"expected AV2-01..AV2-25 in reports/review_aviation_v2.md, got {ids}")
    return rows


def next_experiments() -> list[dict]:
    path = ROOT / "docs" / "content" / "next_experiments.md"
    if not path.exists():
        return []
    out = []
    for m in re.finditer(r"^## (\d+)\. (.+?)\n+(.+?)(?=\n\n|\Z)", path.read_text(), re.M | re.S):
        summ = m.group(3).strip().split("\n")[0]
        summ = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", summ).replace("`", "")
        summ = re.sub(r"\*+([^*]+)\*+", r"\1", summ)
        out.append({"n": int(m.group(1)), "title": m.group(2).strip(), "summary": summ,
                    "status": "proposed, not run", "provenance": "ASSUMED"})
    return out


def build_method() -> dict:
    sm = pd.read_csv(ROOT / "data" / "source_manifest.csv")
    src = [{"id": r["source_id"], "name": r["name"], "url": r["url"], "licence": r["licence"],
            "version": r["version_or_date"], "download_date": r["download_date"],
            "sha256": None if pd.isna(r["sha256"]) else r["sha256"], "used_for": r["used_for"],
            "provenance": r["provenance"], "notes": None if pd.isna(r["notes"]) else r["notes"]} for r in sm.to_dict(orient="records")]
    src.append({"id": "generator", "name": "Synthetic world generator (this repo)", "url": "", "licence": "MIT (this repo)",
                "used_for": "Fleet, parts, demand, repairs, AOG events (fictional)", "provenance": "SIMULATED"})
    from gnm.config import assumption_register
    ar = assumption_register()
    assumptions = [{"key": r["key"], "value": str(r["value"]), "provenance": r["provenance"] or "ASSUMED",
                    "rationale": None if (r["rationale"] is None or (isinstance(r["rationale"], float) and math.isnan(r["rationale"]))) else str(r["rationale"])}
                   for r in ar.to_dict(orient="records")]
    val = parse_junit(ROOT / "reports" / "junit.xml")
    cal = jload("outputs/calibration/p0_history_summary.json")
    checks = []
    hc = cal["variants"]["central"]["history"]
    # v2 band (V2-SIM-CAL): rotable immediate fill, material AOG h/yr, AOG events/yr (only the targets that exist)
    tmap = {k: k for k in ["immediate_fill_rate", "rotable_immediate_fill_rate", "aog_hours_per_year", "aog_events_per_year"]
            if k in cal["targets"]}
    calib = []
    for k, tk in tmap.items():
        lo, hi = cal["targets"][tk]
        ach = hc[k]
        calib.append({"metric": k, "target_lo": lo, "target_hi": hi, "achieved": ach,
                      "in_band": bool(cal["variants"]["central"]["in_central_band"][k]), "provenance": "SIMULATED"})
        checks.append({"name": f"P0 calibration (central history): {k.replace('_', ' ')} {sig(ach)} in [{lo}, {hi}]",
                       "status": "pass" if lo <= ach <= hi else "fail", "group": "calibration"})
    try:
        from gnm.freeze import verify
        verify()
        freeze_ok = True
    except Exception as e:  # pragma: no cover
        freeze_ok, _err = False, str(e)
    fman = jload("outputs/freeze/manifest.json")
    hlog = jload("outputs/freeze/holdout_log.json")
    checks.append({"name": f"Frozen artefacts unchanged since {fman['frozen_at'][:19]}Z ({len(fman['artefacts'])} SHA-256 hashes)",
                   "status": "pass" if freeze_ok else "fail", "group": "freeze"})
    # v2 chain: only the v2 blocks count against the v2 freeze; the v1 entries stay in the log (archived world, D014)
    hlog_v2 = [h for h in hlog if str(h.get("run", "")).startswith("v2_")]
    hlog_v1 = [h for h in hlog if not str(h.get("run", "")).startswith("v2_")]
    n_forced = sum(bool(h.get("forced")) for h in hlog_v2)
    main_v2 = [h for h in hlog_v2 if "postplan" not in h["run"]]
    post_v2 = [h for h in hlog_v2 if "postplan" in h["run"]]
    checks.append({"name": f"v2 holdout blocks logged after the v2 freeze: {len(main_v2)} main + {len(post_v2)} post-plan (D015), {n_forced} forced",
                   "status": "pass" if hlog_v2 and all(h["at"] > fman["frozen_at"] for h in hlog_v2) else "fail", "group": "freeze"})
    aog = jload("outputs/aog_lab/summary.json")
    checks.append({"name": f"AOG incident reconstruction reconciles to aog_events ({fmt_int(aog['aog_hours_reconstructed'])} of {fmt_int(aog['aog_hours_total'])} h)",
                   "status": "pass" if aog["reconciles"] else "fail", "group": "reconciliation"})
    checks.append({"name": f"Frontier option chosen by the pre-stated rule is {recommended_id()} (selection seeds); P2 is the core recommendation",
                   "status": "pass", "group": "selection"})
    checks.append({"name": (f"Automated tests: {val['tests_passed']} of {val['tests_total']} passed"
                             if val.get("tests_total") else "Automated tests: not run"),
                   "status": val["status"], "group": "tests", "detail": val.get("scope")})
    lic_rows = []
    lic_kind = "runtime"
    for line in (ROOT / "THIRD_PARTY_LICENSES.md").read_text().splitlines():
        if line.startswith("## "):
            lic_kind = "data" if "Data" in line else ("dev-only" if "Development" in line else lic_kind)
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) >= 3 and not set(cells[0]) <= set("-: ") and cells[0] not in ("Component", "Data", "Tool"):
            if len(cells) >= 5:
                lic_rows.append({"name": cells[0], "version": cells[1], "licence": cells[2], "kind": "runtime"})
            elif len(cells) == 3:
                lic_rows.append({"name": cells[0], "version": "", "licence": cells[1], "kind": lic_kind, "use": cells[2]})
    lic_rows.append({"name": "Monash Car Parts dataset", "version": "Zenodo v2", "licence": "CC BY 4.0", "kind": "benchmark data"})
    lim = []
    section = None
    for line in (ROOT / "LIMITATIONS.md").read_text().splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        m = re.match(r"\*\*(\d+)\. (.+?)\*\*\s*(.*)", line)
        if m and section:
            lim.append({"n": int(m.group(1)), "section": section, "title": m.group(2).rstrip("."),
                        "detail": m.group(3).split(". ")[0].strip()[:220], "provenance": "DERIVED"})
    decisions = {}
    dec_path = ROOT / "docs" / "DECISIONS.md"
    if dec_path.exists():
        for line in dec_path.read_text().splitlines():
            m = re.match(r"\|\s*(D010|D011|D012|D013|D014|D015|V2-SIM-CAL|V2-OPT-4)\s*\|[^|]*\|\s*(.+?)\s*\|", line)
            if m:
                decisions[m.group(1)] = _author_wording(re.sub(r"\*\*", "", m.group(2)))
    # v2 reporting note, generated from the champion check (D011's v1 sentence named a v1 champion and is superseded)
    _cc = csv("outputs/holdout/forecast_champion_check.csv")
    _ir = _cc[(_cc.demand_class == "intermittent") & (_cc.part_class == "R")]
    _best = int((_cc.champion_rank == 1).sum())
    reporting_note = (f"Forecast champions were frozen on selection seeds and are reported at their holdout rank as-is: "
                      f"{_best} of {len(_cc)} champions ranked first on the holdout"
                      + (f"; the intermittent-rotable champion ({METHOD_LABELS.get(_ir.champion.iloc[0], _ir.champion.iloc[0])}) "
                         f"ranked {int(_ir.champion_rank.iloc[0])}/{int(_ir.n_methods.iloc[0])}" if len(_ir) else "")
                      + ". The policies size rotables on the reliability-exposure rate, not on this champion.")
    for a_ in assumptions:
        for k_ in ("value", "rationale", "note", "source"):
            if isinstance(a_.get(k_), str):
                a_[k_] = _author_wording(a_[k_])
    return {
        "meta": meta("DERIVED", ["data/source_manifest.csv", "config/assumptions.yaml (gnm.config.assumption_register)",
                                 "reports/junit.xml", "outputs/calibration/p0_history_summary.json",
                                 "outputs/freeze/manifest.json", "outputs/freeze/holdout_log.json",
                                 "outputs/aog_lab/summary.json", "THIRD_PARTY_LICENSES.md", "LIMITATIONS.md", "docs/DECISIONS.md"],
                     "Method & provenance. validation reads reports/junit.xml (the same test run README and "
                     "VALIDATION_REPORT report); 'not run' if absent. Calibration targets are ASSUMED bands; achieved values are the "
                     "central P0 history. Freeze hashes from outputs/freeze/manifest.json."),
        "source_manifest": src,
        "assumptions": assumptions,
        "validation": {**val, "checks": checks, "provenance": "DERIVED"},
        "calibration": {"targets_vs_achieved": calib, "policy": cal.get("policy", "P0 only"), "provenance": "SIMULATED"},
        "freeze": {"frozen_at": fman["frozen_at"], "note": fman.get("note", ""),
                   "artefacts": [{"path": k, "sha256": v} for k, v in fman["artefacts"].items()],
                   "holdout_log": hlog_v2, "holdout_log_v1": hlog_v1, "forced_rerun_note": decisions.get("D010", ""),
                   "reporting_note": reporting_note, "verified": freeze_ok,
                   "chain": [{"id": d, "text": decisions[d]} for d in ["V2-SIM-CAL", "D013", "D014", "D015"] if d in decisions],
                   "provenance": "DERIVED"},
        "v1_archive": v1_archive(),
        # v2.1 (additive)
        "calibration_note": {"text": v21.A5_CALIBRATION,
                             "line_kit_variant_aog_h": jload("outputs/calibration/v2_p0_variants.json")["V3 = V1 + V2"]["history"]["aog_hours_per_year"],
                             "target_range_aog_h": cal["targets"].get("aog_hours_per_year"),
                             "source": "outputs/calibration/v2_p0_variants.json (V3 = V1 + V2 line kit), outputs/calibration/p0_history_summary.json",
                             "provenance": "SIMULATED"},
        "av2_findings": av2_findings(),
        "av2_counts": {**{k: sum(r["status"] == k for r in av2_findings()) for k in ("fixed", "disclosed", "next experiment")},
                       "provenance": "DERIVED"},
        "av2_source": ("reports/review_aviation_v2.md (findings); reports/VALIDATION_REPORT.md 'v2 reviews' (fixed); "
                       "LIMITATIONS.md 29-39 (disclosed); docs/content/next_experiments.md (next experiments)"),
        "next_experiments": next_experiments(),
        "stress_worlds": stress_worlds(), "scope_line": v21.SCOPE_LINE,
        "licences": lic_rows,
        "limitations": lim,
    }


# ----------------------------------------------------------------------------------------------
# story


_STORY_NAMES = {"P0": "the Simple Rulebook", "P1": "Each Airport for Itself", "P2": "the Network Plan", "I125": "Network Plan + Extra Spares"}


def displayname(code: str) -> str:
    """A3 display name for story text (mirrors docs/js/lib/names.js); frontier budget points → 'Frontier point B150'."""
    if code in _STORY_NAMES:
        n = _STORY_NAMES[code]
        return n[0].upper() + n[1:] if n.startswith("the ") else n
    return f"Frontier point {code}" if re.fullmatch(r"[BI]\d{2,3}", str(code)) else str(code)


STORY_BODY_MAX = 240   # v2.2: every step body fits the fixed-size tour card (desktop 360 x 340, phone sheet 300 px) unscrolled


def build_story(data: dict) -> dict:
    """Story-mode steps. The narrated part is the planted PS1 part (incidents.json ps1_incident_id) and its station is that
    part's first replayed AOG incident; every number is read from the exported files or the history.
    Selectors are tight targets (wave-2 design review #10): the KPI row, the whole aircraft drawing, the selected
    PN's demand strip, ... so the step card never covers what the step talks about."""
    k = {x["id"]: x for x in data["kpis"]["kpis"]}
    rid = data["kpis"]["recommended_id"]
    n_seeds = len(data["kpis"].get("seeds") or []) or 20
    parts_ = data["parts"]["parts"]
    _p1 = ps1()
    part = next((p for p in parts_ if p.get("planted") == "PS1"), None) or next(p for p in parts_ if p["pn"] == _p1["pn"])
    pn, ata = part["pn"], part["ata"]
    noun = re.sub(r"\((nb|wb)\)", lambda m: f"({m.group(1).upper()})", part["desc"].lower())   # keep NB / WB type tags
    sys_ = next(s for s in data["parts"]["ata_systems"] if s["ata"] == ata)
    incs = data["aog_lab"]["incidents"]
    inc = next((i for i in incs if i["id"] == _p1["incident_id"]), None) or next(i for i in incs if i["pn"] == pn)
    st = inc["station"]
    mr = hist("material_requests")
    at_st = mr[(mr.pn == pn) & (mr.station == st)]
    st_d0 = int((at_st.deadline_class == "D0").sum())
    ae = hist("aog_events")
    ae_st = ae[(ae.station == st) & ae.pns.astype(str).str.contains(pn)]
    chk = next((c for c in data["forecast"]["champions"] if c["demand_class"] == part["demand_class"] and c["part_class"] == part["cls"]), None)
    fl = next((f for f in data["rotables"]["float_examples"] if f["pn"] == pn), data["rotables"]["float_examples"][0])
    ffr = pq("outputs/forecasting/final_forecasts.parquet")
    st_ff = ffr[(ffr.pn == pn) & (ffr.station == st)].iloc[0]
    stt = stock_table()
    st_units = stt[(stt.pn == pn) & (stt.station == st)].iloc[0]
    net = {(r["policy_id"], r["station"]): r for r in data["network"]["policy_compare"]}
    pts = {p["id"]: p for p in data["frontier"]["points"]}
    rec = data["frontier"]["recommendation"]
    acts = data["actions"]["actions"]
    act = next((a for a in acts if a["pn"] == pn and a["station"] == st), None)
    nurg = sum(a["severity"] == "urgent" for a in acts)
    fill, aog, cap = k["immediate_fill_rate"], k["aog_hours"], k["spare_capital_aed"]
    from gnm.policy.analytic import float_calc
    p2_st = int(st_units.P2)
    a_st = float_calc(float(st_ff.removal_rate_day) * 30.0, float(st_ff.t_eff_out_d), p2_st, 0.0)["availability"]
    arc = next((a for a in data["network"]["arcs"] if a["to"] == st), None)
    bands = data["parts"].get("system_risk_bands_share") or {}

    # step 2: reconcile the system badge on the aircraft (share of fleet risk-hours) with the part-level status
    risk = round(100 * part["risk_score"])
    if sys_["risk_level"] != part["risk_level"]:
        bar = f", under the {fmt_pct(bands['urgent'], 0)} urgent bar" if sys_["risk_level"] == "review" and "urgent" in bands else ""
        lead = (f"ATA {ata} rates {sys_['risk_level'].upper()} as a system ({fmt_pct(sys_['risk_share'], 0)} of fleet "
                f"risk-hours{bar}), but one part in it is {part['risk_level'].upper()}: {pn}, a {part['deadline']} {noun}, risk {risk}/100.")
        art = "An" if part['risk_level'][0] in "aeiou" else "A"
        t2 = f"{art} {part['risk_level']} part inside a {sys_['risk_level']}-rated system"
    else:
        lead = f"ATA {ata} rates {sys_['risk_level'].upper()}, led by {pn} ({part['deadline']} {noun}), risk {risk}/100."
        t2 = f"{pn}: never in stock at {st}"
    # wave 5: cite the numbers the part drawer shows (52-week AOG hours, all stations and the worst station)
    if part.get("aog_h_52w_max_station_id") == st:
        body2 = (f"{lead} With {int(st_units.P0)} units at {st} under the Simple Rulebook, it caused {fmt_int(part['aog_h_52w'])} AOG h in "
                 f"W52–W103, {fmt_int(part['aog_h_52w_max_station'])} h of them at {st}.")
    else:
        body2 = (f"{lead} With {int(st_units.P0)} units at {st} under the Simple Rulebook, it caused {fmt_int(part['aog_h_52w'])} AOG h "
                 "across all stations in W52–W103.")

    body3 = (f"Its weekly demand is {part['demand_class']} (ADI {part['adi']:.2f} weeks, CV² {part['cv2']:.2f} on training "
             "weeks W0–W77).")
    if chk:
        body3 += (f" The frozen MASE champion for this cell, '{chk['method']}', ranked {chk['holdout_rank']}/{chk['n_methods']} "
                  "on the holdout, so the policies size rotables on the reliability-exposure rate.")
    p2_s = fl['spares_total'].get('P2', fl['spares_total']['recommended'])
    p2_st, p0_st = int(st_units["P2"]), int(st_units["P0"])
    rs_d = _p2_resupply().get((pn, st))
    a_pool = float_calc(round(fl['rate_per_30d'], 1), round(fl['pipeline_days']), p2_s, 0.0)["availability"]
    pool_txt = "over 99.9%" if a_pool > 0.9995 else fmt_pct(a_pool)
    if rs_d is not None:
        a_p2_st = float_calc(float(st_ff.removal_rate_day) * 30.0, rs_d, p2_st, 0.0)["availability"]
        st_txt = "over 99.9%" if a_p2_st > 0.9995 else fmt_pct(a_p2_st, 1)
        body4 = (f"Pooled over the {fl['pipeline_days']:.0f}-day repair loop, the Network Plan's {p2_s} spares cover {pool_txt} of removals. "
                 f"At {st} the Network Plan holds {p2_st} unit{'s' if p2_st != 1 else ''} (Simple Rulebook: {p0_st}), refilled from AUH "
                 f"in {rs_d:.1f} days: {st_txt} of D0 needs find one on the shelf.")
    else:
        body4 = f"Pooled over the repair loop, the Network Plan's {p2_s} spares cover {pool_txt} of removals."
    # wave C: narrated around P2 (the core recommendation); I125 is the frontier option.
    st_row = next(x for x in data["network"]["stations"] if x["station"] == st)
    u_rec, u_p2 = st_row["by_policy"][rid]["rotable_units"], st_row["by_policy"]["P2"]["rotable_units"]
    d_u = u_rec - u_p2
    # v2.1: display names (no bare codes) and the scope wherever downtime totals appear
    n_pn = len(parts_)
    scope_txt = f"In this simulation, across {n_pn} modelled part numbers"
    body5 = (f"{scope_txt}: at {st}, holdout material AOG falls from {fmt_int(net[('P0', st)]['aog_hours'])} h/yr (Simple "
             f"Rulebook) to {fmt_int(net[('P2', st)]['aog_hours'])} (Network Plan, {u_p2} rotables here). "
             f"Network-wide, the Network Plan's total is {fmt_int(pts['P2']['aog_hours'])} h/yr.")
    fo = data["kpis"]["headline"]["frontier_option"]
    shifts = "; ".join(f"{x['recommended']} at {x['setting'].replace('x', '×')} the hourly rate" for x in fo["rule_shifts"] if x["factor"] == "aog_penalty")
    body6 = (f"If you invest an additional {fmt_aed(fo['extra_capital_aed']['mean'])}, the pre-stated rule stops at {rid}: a further "
             f"{fmt_int(fo['aog_reduction']['mean'])} AOG h/yr [{fmt_int(fo['aog_reduction']['ci'][0])}–{fmt_int(fo['aog_reduction']['ci'][1])}] "
             f"below P2 (paired holdout). It picks {shifts}." if shifts else
             f"If you invest an additional {fmt_aed(fo['extra_capital_aed']['mean'])}, the rule stops at {rid}.")
    body7 = (f"{inc['id']}: {inc['tail']} (fictional) grounded at {st} for {fmt_int(inc['aog_hours'])} h waiting for a {noun}. "
             f"Ranked on what the desk knew then, the top option was: {inc['decision']['recommended_label']}.")
    body8 = (f"On today's starting-point stock (Simple Rulebook): {len(acts)} exceptions for "
             f"W{data['actions']['as_of_week']}, {nurg} urgent.")
    if act and act["type"] == "OUTSTATION_DEPLETION":
        e = act["evidence"]
        body8 += (f" At {st}, {pn} has {e['on_hand']} of {e['target']} on hand: {e['d0_requests_lookback']} D0 requests "
                  f"and {fmt_int(e['aog_hours_lookback'])} AOG h there in W{data['actions']['as_of_week'] + 1 - e['lookback_weeks']}–W{data['actions']['as_of_week']}.")
    elif act:
        body8 += f" Including: {act['summary']}."
    if act and act.get("recommended_action"):
        _ra = act["recommended_action"].split(";")[0].strip()   # v2.2 card budget: the action itself, not its sourcing note
        if len(body8) + len(_ra) + 10 <= STORY_BODY_MAX:
            body8 += f" Action: {_ra}."

    aog_sel = ('[data-story="aog-incident-ps1"]' if inc["id"] == _p1["incident_id"] else f'[data-incident="{inc["id"]}"]') + ' [data-story="aog-timeline"]'
    # wave B: six steps following the v2 hero part (PS1): problem -> diagnose -> pipeline -> trade-offs -> action -> value
    core = data["kpis"]["headline"]["core"]
    _tl = {x["step"]: x["t_h"] for x in inc.get("timeline") or []}
    _at, _rel = _tl.get("fitted"), _tl.get("released")
    _dur = (f"The part arrived at {fmt_int(_at)} h; release came at {fmt_int(_rel)} h. " if _at is not None and _rel is not None and _rel > _at
            else f"It was on the ground {fmt_int(inc['aog_hours'])} h. ")
    body_problem = (f"{inc['tail']} (fictional) is grounded at {st}: a {part['deadline']} {noun} failed with none held there. "
                    + _dur + f"Best route on what the desk knew then: {inc['decision']['recommended_label']}.")
    # A4: never the net capital alone — gross buys and removals first, then the net (same rounding as the site table)
    rm6 = core.get("remix") or {}
    aedm = lambda v: f"AED {abs(float(v)) / 1e6:.1f}M"   # noqa: E731
    netc = float(core["capital_aed"]["mean"])
    cap_txt = (f"It buys {rm6['buy_units']} rotables (≈{aedm(rm6['buy_aed'])}) and removes {rm6['shed_units']} (≈{aedm(rm6['shed_aed'])}); "
               f"average simulated inventory {'+' if netc >= 0 else '−'}{aedm(netc)}. ") if rm6.get("buy_units") is not None else ""
    fo_txt = (f"{displayname(rid)} adds {fmt_aed(fo['extra_capital_aed']['mean'])} for {fmt_int(fo['aog_reduction']['mean'])} h/yr less "
              f"[{fmt_int(fo['aog_reduction']['ci'][0])}–{fmt_int(fo['aog_reduction']['ci'][1])}].")
    body_value = (f"{scope_txt}, the Network Plan cuts material AOG by {fmt_int(core['aog_reduction']['mean'])} h a year "
                  f"vs the Simple Rulebook. " + cap_txt + fo_txt)
    if len(body_value) > STORY_BODY_MAX:   # keep the gross + net capital lines; drop the frontier sentence first
        body_value = body_value[: -len(fo_txt)].rstrip()
    steps = [
        # (route, story_id, selector, title, body)
        # wave C: the timeline's chart body (the AOG bar and the 9 h / 14 h nodes), so the card fits beside it at 1440x900
        (f"#/aog?incident={inc['id']}", "aog-incident-ps1", aog_sel + " .chart-body", "1 · The operational problem", body_problem),
        (f"#/parts?ata={ata}&pn={pn}", "aircraft", '[data-story="aircraft"]', "2 · Diagnose the shortage", body2),
        (f"#/rotables?pn={pn}", "rotable-float-calc", '[data-story="rotable-float-calc"] .fc-results', "3 · The repair pipeline", body4),
        (f"#/network?station={st}", f"network-{st.lower()}", f'[data-story="network-{st.lower()}"]', "4 · Compare the trade-offs", body5),
        (f"#/actions?station={st}", "action-inbox", (f'[data-story="action-inbox"] [data-id="{act["exception_id"]}"]' if act else '[data-story="action-inbox"]'),
         "5 · Recommend the action", body8),
        ("#/capital", "frontier-chart", '[data-story="frontier-chart"]', "6 · Business value on the Readiness Frontier", body_value),
    ]
    # phones (<= 480 px): a narrower child to spotlight so the bottom sheet does not cover the subject (wave-3 #4).
    # Hooks are stable view markup (see internal development notes (kept privately)); the UI falls back to `selector` if absent.
    tl = aog_sel.replace(' [data-story="aog-timeline"]', ' [data-story="aog-timeline"] .chart-body')
    mobile = {
        "network-" + st.lower(): f'[data-story="network-{st.lower()}"] .np-pol',
        "frontier-chart": '[data-story="frontier-chart"] .chart-body',
        "rotable-float-calc": '[data-story="rotable-float-calc"] .fc-outs',   # v2.2: the KPI tiles (> 99.9 % on the shelf) the card cites
        "aog-incident-ps1": tl,
        "action-inbox": (f'[data-story="action-inbox"] [data-id="{act["exception_id"]}"]' if act else None),
    }
    # v2.2: smaller targets, in order, for when the step's target is taller than the free band of the viewport (the tour
    # spotlights the first one that fits whole, so the light never runs past the screen edge)
    fit = {
        "aircraft": ['[data-story="aircraft"] svg'],
        "rotable-float-calc": ['[data-story="rotable-float-calc"] .fc-outs', '[data-story="rotable-float-calc"] .fc-out.is-key'],
        "network-" + st.lower(): [f'[data-story="network-{st.lower()}"] .np-pol'],
        "frontier-chart": ['[data-story="frontier-chart"] .chart-body'],
    }
    # v2.1: Simple-mode (plain English) titles and bodies; every number is read from the same data as the expert text
    def city(code: str) -> str:
        nm = next((x["name"] for x in data["network"]["stations"] if x["station"] == code), code)
        nm = nm.split(",")[-1].strip()
        return re.sub(r"\s+(International|Heathrow|Changi|am Main)$", "", nm)
    c_st, c_hub = city(st), city("AUH")
    gap_txt = (f"The part arrived after {fmt_int(_at)} hours, and the plane flew again after {fmt_int(_rel)} hours."
               if _at is not None and _rel is not None and _rel > _at else f"It stayed on the ground for {fmt_int(inc['aog_hours'])} hours.")
    s_problem = (f"A plane is stuck at {c_st}. A part it needs before its next flight broke, and no spare was kept there. " + gap_txt)
    s_diag = (f"The {sys_['name'].lower()} group is the biggest risk, and one part leads it. "
              f"With {'no spare' if p0_st == 0 else f'{p0_st} spares'} at {c_st}, it kept planes grounded for "
              f"{fmt_int(part['aog_h_52w'])} hours across all airports in the last year of history.")
    s_pipe = (f"Broken parts spend about {fl['pipeline_days']:.0f} days in repair, so the airline needs spares to cover them. "
              f"The Network Plan keeps {p2_s} in total, so one is almost always on the shelf."
              + (f" At {c_st} it keeps {p2_st}, refilled from {c_hub} in about {rs_d:.0f} days." if rs_d is not None else ""))
    s_trade = (f"In this simulation, planes at {c_st} were grounded {fmt_int(net[('P0', st)]['aog_hours'])} hours a year under the Simple Rulebook, "
               f"and {fmt_int(net[('P2', st)]['aog_hours'])} under the Network Plan. "
               f"Across all {n_pn} modelled part numbers, the Network Plan brings the network total to {fmt_int(pts['P2']['aog_hours'])} hours a year.")
    s_act = f"The planner's list shows today's starting-point stock (Simple Rulebook): {len(acts)} alerts this week, {nurg} of them urgent."
    if act and act["type"] == "OUTSTATION_DEPLETION":
        e = act["evidence"]
        need = int(e["target"]) - int(e["on_hand"])
        s_act += (f" {c_st} has {e['on_hand']} of the {e['target']} spares the Network Plan puts there for this part. "
                  f"The advice is to send {need} there.")
    rm = core.get("remix") or {}
    s_value = (f"{scope_txt}, the Network Plan cuts grounded time by {fmt_int(core['aog_reduction']['mean'])} hours a year. "
               + (f"It buys {rm['buy_units']} repairable spares (about {aedm(rm['buy_aed'])}) and removes {rm['shed_units']} (about {aedm(rm['shed_aed'])}), "
                  f"so stock value rises by about {aedm(netc)}." if rm.get("buy_units") is not None else
                  f"Spending {fmt_aed(fo['extra_capital_aed']['mean'])} more saves about {fmt_int(fo['aog_reduction']['mean'])} hours more."))
    simple = [("1 · The problem", s_problem), ("2 · Find the cause", s_diag), ("3 · Repairs take time", s_pipe),
              ("4 · Compare the plans", s_trade), ("5 · What to do", s_act), ("6 · Is it worth it?", s_value)]
    ids = [sid for _, sid, _, _, _ in steps]
    return {
        "meta": meta("DERIVED", ["docs/data/kpis.json", "docs/data/parts.json", "docs/data/forecast.json",
                                 "docs/data/rotables.json", "docs/data/network.json", "docs/data/frontier.json",
                                 "docs/data/aog_lab.json", "docs/data/actions.json",
                                 "data/processed/history/material_requests.parquet", "data/processed/history/aog_events.parquet"],
                     "Story-mode steps; bodies are templated at export time from the exported numbers. Each selector starts "
                     "with the data-story attribute the screen renders (story_id), optionally narrowed to a child element so "
                     "the step card does not cover its subject: " + ", ".join(ids) + ". mobile_selector (or null) is the narrower "
                     "target used at <= 480 px (bottom-sheet layout); it also starts with the story_id hook. fit_selectors are smaller fallback targets, in order, used when the target is taller than the free part of the viewport. title_simple / body_simple are the Simple-mode (plain English) text, computed from the same numbers; title / body are the Expert text."),
        "selector_ids": ids,
        "steps": [{"route": r, "selector": sel, "mobile_selector": mobile.get(sid), "fit_selectors": fit.get(sid, []), "story_id": sid, "title": t, "body": b,
                   "title_simple": ts, "body_simple": bs, "provenance": "DERIVED"}
                  for (r, sid, sel, t, b), (ts, bs) in zip(steps, simple)],
    }


# ----------------------------------------------------------------------------------------------
# driver

BUILDERS = {"kpis": build_kpis, "policies": build_policies, "parts": build_parts,
            "demand_history": build_demand_history, "forecast": build_forecast, "rotables": build_rotables,
            "network": build_network, "frontier": build_frontier, "aog_lab": build_aog_lab,
            "actions": build_actions, "method": build_method}


def dumps(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def build_all(out_dir: Path = SITE, write: bool = True) -> dict:
    """Build every file; returns {name: payload}. Writes docs/data/<name>.json and the manifest."""
    data = {name: v21.scrub(clean(fn())) for name, fn in BUILDERS.items()}
    data["story"] = v21.scrub(clean(build_story(data)))
    bad = [(n, *v) for n, d in data.items() for v in v21.text_violations(d)]
    if bad:
        raise RuntimeError(f"v2.1 text gate: {len(bad)} exported strings break it, e.g. {bad[:3]}")
    data = {n: data[n] for n in FILES}
    sizes = {n: len(dumps(d).encode()) for n, d in data.items()}
    total = sum(sizes.values())
    if total >= MAX_TOTAL_BYTES:
        raise RuntimeError(f"site data is {total} bytes (limit {MAX_TOTAL_BYTES})")
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        for n, d in data.items():
            (out_dir / f"{n}.json").write_text(dumps(d) + "\n")
        manifest = {"meta": {"generated_at": data["kpis"]["meta"]["generated_at"], "git_sha": git_sha(),
                             "provenance": "DERIVED", "source": ["gnm.export.build_site_data"],
                             "notes": "Lists the real exports present in docs/data/ (written by scripts/export_site.py). "
                                      "Any file not listed falls back to docs/data/fixtures/<name>.json."},
                    "files": FILES, "sizes_bytes": sizes, "total_bytes": total}
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    return data
