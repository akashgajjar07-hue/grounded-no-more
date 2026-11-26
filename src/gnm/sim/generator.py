"""Synthetic world + scenario generator for Falcon Hub Airways (fictional).

Everything here is SIMULATED. The generator is the only production module that reads
the hidden :class:`~gnm.sim.truth.GroundTruth`; downstream code gets Scenarios through
:mod:`gnm.sim.api`, which never hands the truth out.

Determinism and streams
-----------------------
* World master data: ``SeedSequence([world_seed, SALT_WORLD])``.
* Flight schedule + A-checks: world-level (same for every scenario seed; a planned
  schedule is not random across seeds), one stream per tail:
  ``SeedSequence([world_seed, SALT_SCHED, tail_index])``. Generated sequentially from week 0,
  so a longer horizon reproduces the shorter one as a prefix.
* Scenario demand: one stream per (seed, departure-week):
  ``SeedSequence([SALT_WEEK, seed, week])``. A scenario for weeks 104–155 therefore equals the
  same slice of a longer range, without generating anything before it. Ids are encoded by
  need-week (``removal_id = week*10_000 + rank``, ``request_id = week*100_000 + rank``).
* Lead-time and transport-jitter streams: one stream per (seed, PN) / (seed, kind).
"""
from __future__ import annotations

import copy
import csv
import datetime as _dt
import hashlib
import json
import math
import re
import urllib.request
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from gnm import schemas
from gnm.config import CONFIG_PATH, DATA, HOURS_PER_WEEK, load_config
from gnm.contracts import Scenario, World
from gnm.sim.truth import GroundTruth

SALT_WORLD, SALT_SCHED, SALT_WEEK, SALT_LT, SALT_JIT, SALT_KITS = 11, 12, 13, 14, 15, 16
ARCHS = ("narrowbody", "widebody")
CLASS_KEY = {"C": "consumable", "E": "expendable", "R": "rotable"}
LT_STREAM_LEN = 400
GEN_VERSION = "3"                 # bump when sampling logic changes (invalidates scenario caches)
JITTER_LEN = 20000


def _rng(*keys) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([int(k) for k in keys]))


# --------------------------------------------------------------------------------------
# Fictional nomenclature per ATA chapter and part class
# --------------------------------------------------------------------------------------
NAMES = {
    "21": {"R": ["Pack flow control valve", "Air cycle machine", "Cabin pressure controller", "Outflow valve actuator",
                 "Trim air pressure regulating valve", "Zone temperature controller", "Recirculation fan"],
           "E": ["Duct temperature sensor", "Pack outlet check valve", "Cabin pressure switch", "Ram air inlet actuator rod end",
                 "Mixer unit temperature sensor"],
           "C": ["Recirculation air filter element", "Water extractor coalescer bag", "Duct clamp seal kit",
                 "O-ring kit (pack valves)", "Duct gasket set"]},
    "24": {"R": ["Integrated drive generator", "Generator control unit", "Transformer rectifier unit", "Static inverter",
                 "Battery charger", "Bus power control unit", "Main ship's battery"],
           "E": ["Current transformer", "Power contactor", "Power relay", "Circuit breaker (3-phase)",
                 "External power receptacle"],
           "C": ["Fuse (5 A)", "Indicator lamp", "Cable tie kit", "Terminal lug kit", "Connector sealing plug kit"]},
    "27": {"R": ["Elevator servo control", "Aileron servo actuator", "Spoiler servo actuator", "Flap power control unit",
                 "Rudder trim actuator", "Flight control computer", "Trimmable horizontal stabiliser actuator"],
           "E": ["Flap position sensor", "Control rod end bearing", "Slat proximity sensor", "Cable tension regulator"],
           "C": ["Flight control bushing kit", "Grease cartridge (flight controls)", "Self-locking nut kit", "Cotter pin kit"]},
    "28": {"R": ["Fuel boost pump", "Fuel quantity indicating computer", "Fuel crossfeed valve actuator"],
           "E": ["Fuel quantity probe", "Fuel level sensor", "Refuel valve"],
           "C": ["Fuel filter element", "Fuel pump seal kit", "O-ring kit (fuel system)"]},
    "29": {"R": ["Engine-driven hydraulic pump", "Electric motor pump", "Power transfer unit", "Priority valve module",
                 "Hydraulic accumulator"],
           "E": ["Hydraulic pressure transducer", "Hydraulic fuse", "Hydraulic check valve", "Quick-disconnect coupling"],
           "C": ["Hydraulic filter element", "Hydraulic O-ring kit", "Backup ring kit", "Hydraulic fluid (1 US gal)"]},
    "30": {"R": ["Wing anti-ice valve", "Windshield heat controller", "Probe heat computer"],
           "E": ["Windshield wiper motor", "Anti-ice pressure switch", "Drain mast heater"],
           "C": ["Wiper blade", "Rain repellent cartridge", "Heater element gasket"]},
    "32": {"R": ["Brake temperature monitoring unit", "Main wheel assembly", "Nose wheel assembly", "Brake control unit",
                 "Nose wheel steering actuator", "Main gear retraction actuator", "Nose gear shock strut"],
           "E": ["Brake temperature sensor", "Wheel speed transducer", "Main wheel tyre", "Nose wheel tyre",
                 "Gear proximity switch"],
           "C": ["Wheel bearing grease", "Brake wear indicator pin", "Tyre valve core kit", "Axle nut lock kit",
                 "Wheel bearing seal"]},
    "33": {"R": ["Strobe light power supply", "Emergency lighting control unit"],
           "E": ["Landing light module", "Navigation light assembly", "Logo light assembly", "Emergency light battery pack"],
           "C": ["Reading light lamp", "Cabin lighting lamp", "Light lens gasket"]},
    "34": {"R": ["Air data module", "Inertial reference unit", "Weather radar transceiver", "Radio altimeter transceiver",
                 "Multi-mode receiver", "Air data computer", "Angle-of-attack sensor"],
           "E": ["Pitot probe", "Static port heater", "Total air temperature probe", "ADF antenna"],
           "C": ["Pitot probe cover seal", "Antenna gasket", "Connector backshell kit"]},
    "35": {"R": ["Crew oxygen regulator", "Crew oxygen cylinder"],
           "E": ["Passenger oxygen mask assembly", "Oxygen pressure transducer", "Chemical oxygen generator"],
           "C": ["Crew mask hose seal", "Oxygen mask cleaning kit", "Oxygen valve seal kit"]},
    "36": {"R": ["Bleed air valve", "High-pressure shutoff valve", "Fan air valve", "Bleed monitoring computer",
                 "Pressure regulating and shutoff valve"],
           "E": ["Bleed temperature sensor", "Duct overheat detection sensor", "Bleed pressure transducer"],
           "C": ["V-band clamp", "Pneumatic duct seal ring", "Pneumatic gasket kit"]},
    "38": {"R": ["Vacuum generator", "Potable water heater", "Waste control unit"],
           "E": ["Toilet flush valve", "Water quantity transmitter", "Water drain valve"],
           "C": ["Potable water filter cartridge", "Toilet seal kit", "Faucet aerator"]},
    "49": {"R": ["APU starter generator", "APU electronic control box", "APU fuel control unit", "APU inlet door actuator",
                 "APU bleed valve"],
           "E": ["APU ignition exciter", "APU igniter plug", "APU oil level sensor"],
           "C": ["APU oil filter element", "APU igniter lead seal", "APU turbine oil (1 qt)"]},
}


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
def config_hash(cfg: dict) -> str:
    return hashlib.sha256((GEN_VERSION + json.dumps(cfg, sort_keys=True, default=str)).encode()).hexdigest()[:12]


def small_config(cfg: dict | None = None, counts=(8, 6, 6), outstations=("BOM",)) -> dict:
    """Development / CI override: fewer PNs and stations (default 20 PNs, AUH + BOM)."""
    cfg = copy.deepcopy(cfg or load_config())
    cfg["parts"]["counts"] = {"consumable": counts[0], "expendable": counts[1], "rotable": counts[2]}
    net = cfg["network"]
    outs = list(outstations)
    net["outstations"] = outs
    keep = [net["hub"]] + outs
    net["stations"] = {k: v for k, v in net["stations"].items() if k in keep}
    for arch in ARCHS:
        mix = {k: v for k, v in net["route_mix"][arch].items() if k in outs}
        if not mix:
            mix = {outs[0]: 1.0}
        tot = sum(mix.values())
        net["route_mix"][arch] = {k: v / tot for k, v in mix.items()}
    net["aog_transport_hours"] = {k: {kk: vv for kk, vv in v.items() if kk in keep}
                                  for k, v in net["aog_transport_hours"].items() if k in keep}
    return cfg


def _tail_names(prefix: str, n: int) -> list[str]:
    if n > 26:
        raise ValueError("tail naming supports up to 26 aircraft per archetype")
    return [prefix + chr(ord("A") + i) for i in range(n)]


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _aog_matrix(cfg: dict, stations: list[str]) -> pd.DataFrame:
    raw = cfg["network"]["aog_transport_hours"]
    m = pd.DataFrame(0.0, index=stations, columns=stations)
    for a in stations:
        for b in stations:
            if a == b:
                continue
            v = raw.get(a, {}).get(b)
            if v is None:
                v = raw.get(b, {}).get(a)
            m.loc[a, b] = float(v)
    return m


def _lognormal_params(mean, cv):
    sigma2 = np.log1p(np.asarray(cv, float) ** 2)
    return np.log(np.asarray(mean, float)) - sigma2 / 2, np.sqrt(sigma2)


def season_factor(cfg: dict, t_h: float) -> float:
    s = cfg["fleet"]["seasonality"]
    day = int(t_h // 24)
    woy = int(t_h // HOURS_PER_WEEK) % 52
    month = min(11, woy * 12 // 52)
    f = s["weekly"][day % 7] * s["monthly"][month]
    if (woy + 1) in s["holiday_peaks_weeks_of_year"]:
        f *= s["holiday_factor"]
    return f


# --------------------------------------------------------------------------------------
# World
# --------------------------------------------------------------------------------------
VARIANTS = ("central", "low_stress", "high_stress")


def generate_world(cfg: dict | None = None, variant: str = "central") -> tuple[World, GroundTruth]:
    """Master data + hidden truth, deterministic from ``seeds.world_seed``.

    ``variant`` (generator.variants) scales the TRUE MTBUR of rotables/expendables only; all public
    master data (incl. quoted figures) is identical across variants, so P0 is the same policy."""
    cfg = cfg or load_config()
    vcfg = (cfg["generator"].get("variants") or {}).get(variant)
    if vcfg is None:
        raise ValueError(f"unknown variant {variant!r}")
    ws = int(cfg["seeds"]["world_seed"])
    rng = _rng(ws, SALT_WORLD)
    pc, gc = cfg["parts"], cfg["generator"]

    # ---- fleet ----
    ac_rows = []
    for arch in ARCHS:
        f = cfg["fleet"][arch]
        for tail in _tail_names(f["tail_prefix"], f["count"]):
            fh = float(max(1.0, rng.normal(f["fh_per_day"]["mean"], f["fh_per_day"]["sd"])))
            ac_rows.append({"tail": tail, "archetype": arch, "type_label": f["archetype"], "entry_week": 0,
                            "fh_per_day_mean": round(fh, 2), "fc_per_day_mean": np.nan})
    aircraft = pd.DataFrame(ac_rows)

    # ---- stations ----
    net = cfg["network"]
    st_codes = [net["hub"]] + list(net["outstations"])
    stations = pd.DataFrame([{"station": s, "name": net["stations"][s]["name"], "lat": float(net["stations"][s]["lat"]),
                              "lon": float(net["stations"][s]["lon"]), "role": net["stations"][s]["role"]}
                             for s in st_codes])

    # planned FC/day follows schedule geometry (FH/day ÷ mean leg FH of the archetype's route mix)
    legfh = _leg_fh_table(cfg, stations)
    for arch in ARCHS:
        mix = net["route_mix"][arch]
        mean_leg = sum(w * legfh[arch][x] for x, w in mix.items()) / sum(mix.values())
        sel = aircraft.archetype == arch
        aircraft.loc[sel, "fc_per_day_mean"] = (aircraft.loc[sel, "fh_per_day_mean"] / mean_leg).round(2)

    # ---- parts ----
    counts = pc["counts"]
    classes = ["C"] * counts["consumable"] + ["E"] * counts["expendable"] + ["R"] * counts["rotable"]
    n = len(classes)
    atas = list(pc["ata_weights"].keys())
    w = np.array([pc["ata_weights"][a] for a in atas], float)
    w /= w.sum()
    ata_draw = rng.choice(len(atas), size=n, p=w)
    U = {k: rng.random(n) for k in ["cost", "lt", "ltcv", "dl", "drv", "mtbur", "nb", "nbk", "use", "tat", "tatcv",
                                     "rcost", "cond", "shelf", "shelfm", "app", "qtyn", "qtyw", "kit"]}
    Z = {k: rng.standard_normal(n) for k in ["qmtbur", "qtat", "qcond", "quse", "ltt"]}

    shop_of_ata = {}
    for shop, body in cfg["repair_shops"].items():
        if isinstance(body, dict) and "atas" in body:
            for a in body["atas"]:
                shop_of_ata[str(a)] = shop

    fc_atas = set(gc["fc_driven_atas"])
    n_re = sum(1 for c in classes if c != "C")
    n_forced = sum(1 for i, c in enumerate(classes) if c != "C" and atas[ata_draw[i]] in fc_atas)
    p_fc = max(0.0, (pc["fc_driven_share"] * n_re - n_forced) / max(1, n_re - n_forced))

    def logu(u, lo, hi):
        return float(np.exp(np.log(lo) + u * (np.log(hi) - np.log(lo))))

    def lin(u, lo, hi):
        return float(lo + u * (hi - lo))

    def pick(u, mix: dict):
        keys = list(mix.keys())
        cdf = np.cumsum([mix[k] for k in keys])
        return keys[int(np.searchsorted(cdf / cdf[-1], u, side="right"))]

    seq = {"C": 0, "E": 0, "R": 0}
    used_names: dict[str, int] = {}
    prow, trow, arow = [], [], []
    kit_eligible = []
    for i, cls in enumerate(classes):
        ata = atas[ata_draw[i]]
        ck = CLASS_KEY[cls]
        seq[cls] += 1
        pn = f"GN-{ata}-{cls}{seq[cls]:03d}"
        names = NAMES[ata][cls]
        k = used_names.get(ata + cls, 0)
        used_names[ata + cls] = k + 1
        desc = names[k % len(names)] + ("" if k < len(names) else f" – variant {chr(ord('A') + k // len(names))}")
        unit_cost = logu(U["cost"][i], *pc["unit_cost_aed"][ck])
        lt_q = lin(U["lt"][i], *pc["lead_time_days"][ck])
        lt_cv = lin(U["ltcv"][i], *pc["lead_time_days"]["cv"])
        lt_true = lt_q * float(np.exp(gc["lead_time_true_noise_sd_log"] * Z["ltt"][i]))
        dl = pick(U["dl"][i], pc["deadline_class_mix"][ck])
        nb_k = lin(U["nbk"][i], *pc["overdispersion"]["k_range"]) if U["nb"][i] < pc["overdispersion"]["share_of_parts"] else np.nan
        row = {"pn": pn, "description": desc, "ata": ata, "part_class": cls, "deadline_class": dl,
               "unit_cost_aed": round(unit_cost, 2), "lead_time_mean_d": round(lt_q, 1), "lead_time_cv": round(lt_cv, 3),
               "driver": None, "mtbur_quoted": np.nan, "repair_shop": None, "repair_tat_mean_d": np.nan,
               "repair_cost_aed": np.nan, "condemnation_prob_quoted": np.nan, "shelf_life_months": np.nan, "planted": None}
        t = {"pn": pn, "mtbur_true": np.nan, "nb_k": nb_k, "usage_per_1000_fc_true": np.nan,
             "condemnation_prob_true": np.nan, "repair_tat_mean_true_d": np.nan, "lead_time_mean_true_d": lt_true,
             "lead_time_change_week": pd.NA, "lead_time_after_d": np.nan, "trend_per_year": np.nan,
             "repair_tat_cv_true": np.nan, "lead_time_cv_true": lt_cv}
        if cls == "C":
            row["driver"] = "FC_usage"
            use = logu(U["use"][i], *pc["consumable_usage_per_1000_fc"])
            t["usage_per_1000_fc_true"] = use
            q_use = use * float(np.exp(gc["quoted_usage_noise_sd_log"] * Z["quse"][i]))
            row["mtbur_quoted"] = round(1000.0 / q_use, 1)          # quoted FC per unit consumed (per aircraft)
            if U["shelf"][i] < pc["shelf_life"]["share_of_consumables"]:
                row["shelf_life_months"] = float(round(lin(U["shelfm"][i], *pc["shelf_life"]["months"])))
            if U["kit"][i] < pc["scheduled_kit_share_consumable"]:
                kit_eligible.append(pn)
        else:
            drv = "FC" if (ata in fc_atas or U["drv"][i] < p_fc) else "FH"
            row["driver"] = drv
            m = logu(U["mtbur"][i], *(pc["mtbur_fc"] if drv == "FC" else pc["mtbur_fh"]))
            t["mtbur_true"] = m
            row["mtbur_quoted"] = round(m * float(np.exp(pc["quoted_mtbur_noise_sd_log"] * Z["qmtbur"][i]))
                                        * pc["quoted_mtbur_optimism"], 0)
        if cls == "R":
            shop = shop_of_ata[ata]
            tat = lin(U["tat"][i], *pc["repair_tat_days"])
            t["repair_tat_mean_true_d"] = tat
            t["repair_tat_cv_true"] = lin(U["tatcv"][i], *pc["repair_tat_cv"])
            cond = lin(U["cond"][i], *pc["condemnation_prob"])
            t["condemnation_prob_true"] = cond
            row["repair_shop"] = shop
            row["repair_tat_mean_d"] = round(tat * float(np.exp(gc["quoted_tat_noise_sd_log"] * Z["qtat"][i]))
                                             * gc["quoted_tat_optimism"], 1)
            row["repair_cost_aed"] = round(unit_cost * lin(U["rcost"][i], *pc["repair_cost_pct_of_unit"]), 2)
            row["condemnation_prob_quoted"] = round(min(0.5, cond * float(np.exp(gc["quoted_condemn_noise_sd_log"] * Z["qcond"][i]))), 4)
        # applicability
        app = pick(U["app"][i], gc["applicability_mix"])
        qr = pc["qty_per_aircraft"][ck]
        for arch, u in (("narrowbody", U["qtyn"][i]), ("widebody", U["qtyw"][i])):
            if app in ("both", arch):
                arow.append({"pn": pn, "archetype": arch, "qty_per_aircraft": int(qr[0] + math.floor(u * (qr[1] - qr[0] + 1)))})
        prow.append(row)
        trow.append(t)

    parts = pd.DataFrame(prow)
    gt = pd.DataFrame(trow)
    appl = pd.DataFrame(arow)

    planted = _plant(cfg, parts, gt, appl, aircraft, legfh)
    gt["mtbur_true"] = gt["mtbur_true"] * float(vcfg.get("true_mtbur_scale", 1.0))

    parts = parts.astype({"driver": "string", "repair_shop": "string", "planted": "string"})
    world = World(aircraft=aircraft, stations=stations, parts=parts, applicability=appl,
                  aog_hours=_aog_matrix(cfg, st_codes), repair_shops=_shops(cfg), cfg=cfg,
                  kit_eligible=kit_eligible)
    truth = GroundTruth(parts=gt, world_seed=ws, planted=planted)
    truth.variant = variant
    return world, truth


def shop_of_ata(cfg) -> dict:
    out = {}
    for shop, body in cfg["repair_shops"].items():
        if isinstance(body, dict) and "atas" in body:
            for a in body["atas"]:
                out[str(a)] = shop
    return out


def _shops(cfg) -> dict:
    rs = cfg["repair_shops"]
    out = {}
    for shop, body in rs.items():
        if isinstance(body, dict) and "capacity_slots" in body:
            out[shop] = {"location": body["location"], "capacity_slots": int(body["capacity_slots"]),
                         "transit_days": float(rs["vendor_transit_days_from_auh"][shop]), "atas": list(body["atas"])}
    return out


def _leg_fh_table(cfg, stations: pd.DataFrame) -> dict:
    gc = cfg["generator"]
    hub = cfg["network"]["hub"]
    c = stations.set_index("station")
    out = {}
    for arch in ARCHS:
        sp = gc["airborne_speed_kmh"][arch]
        out[arch] = {}
        for s in c.index:
            if s == hub:
                continue
            d = _haversine_km(c.loc[hub, "lat"], c.loc[hub, "lon"], c.loc[s, "lat"], c.loc[s, "lon"])
            out[arch][s] = round(d * gc["route_distance_factor"] / sp, 2)
    return out


def _weekly_rate(cfg, parts, gt, appl, aircraft, legfh) -> np.ndarray:
    """Expected fleet removals/usage per week from TRUE parameters (planting only)."""
    expo = {}
    for arch in ARCHS:
        a = aircraft[aircraft.archetype == arch]
        expo[(arch, "FH")] = a.fh_per_day_mean.sum() * 7
        expo[(arch, "FC")] = a.fc_per_day_mean.sum() * 7
    rate = np.zeros(len(parts))
    q = appl.pivot(index="pn", columns="archetype", values="qty_per_aircraft").reindex(parts.pn).fillna(0)
    for i, r in parts.iterrows():
        for arch in ARCHS:
            qa = q.loc[r.pn].get(arch, 0)
            if qa <= 0:
                continue
            if r.part_class == "C":
                rate[i] += expo[(arch, "FC")] * gt.loc[i, "usage_per_1000_fc_true"] / 1000
            else:
                rate[i] += qa * expo[(arch, r.driver)] / gt.loc[i, "mtbur_true"]
    return rate


def _plant(cfg, parts, gt, appl, aircraft, legfh) -> dict:
    """Implement PS1–PS4 (config planted_situations / generator.planted). Mutates frames."""
    pl = cfg["generator"]["planted"]
    planted = {}
    taken = set()
    outs = cfg["network"]["outstations"]
    focus = "BOM" if "BOM" in outs else outs[0]

    # PS1: understocked D0 rotable with high BOM exposure on both fleets (relabelled to the configured PN)
    c1 = pl["PS1"]
    rot = parts.index[parts.part_class == "R"].tolist()
    target_seq = int(c1.get("pn_seq", 14))
    cand = [i for i in rot if int(parts.loc[i, "pn"][-3:]) == target_seq] or rot
    i1 = cand[0]
    ata = str(c1.get("ata", parts.loc[i1, "ata"]))
    if ata not in shop_of_ata(cfg):
        raise ValueError(f"PS1 ATA {ata} has no repair shop")
    old_p = parts.loc[i1, "pn"]
    p1 = f"GN-{ata}-R{int(old_p[-3:]):03d}"
    parts.loc[i1, ["pn", "ata", "description", "repair_shop"]] = [p1, ata, c1.get("description", parts.loc[i1, "description"]),
                                                                  shop_of_ata(cfg)[ata]]
    gt.loc[i1, "pn"] = p1
    appl.drop(appl.index[appl.pn == old_p], inplace=True)
    for arch in ARCHS:
        appl.loc[len(appl) + 1000] = {"pn": p1, "archetype": arch, "qty_per_aircraft": int(c1.get("qty_per_aircraft", 1))}
    appl.reset_index(drop=True, inplace=True)
    drv = c1.get("driver", "FC")
    m_true = float(c1["mtbur_fc"] if drv == "FC" else c1["mtbur_fh"])
    parts.loc[i1, ["driver", "deadline_class", "planted"]] = [drv, c1["deadline_class"], "PS1"]
    gt.loc[i1, "mtbur_true"] = m_true
    parts.loc[i1, "mtbur_quoted"] = round(m_true * c1["quoted_multiple"], 0)
    if "tat_days" in c1:
        gt.loc[i1, "repair_tat_mean_true_d"] = float(c1["tat_days"])
        parts.loc[i1, "repair_tat_mean_d"] = float(c1["quoted_tat_days"])
    taken.add(i1)
    planted["PS1"] = {"pn": p1, "station": focus, "weeks": "all history",
                      "note": "D0 rotable on both fleets; true MTBUR %.0f %s vs quoted %.0f, so P0 sees < 4 removals/yr at %s "
                              "and holds no unit there while the true %s rate is well above that"
                              % (m_true, drv, parts.loc[i1, "mtbur_quoted"], focus, focus)}

    rate = _weekly_rate(cfg, parts, gt, appl, aircraft, legfh)
    # PS2: long-TAT rotable at the EU vendor with an overdue repair order (history seed)
    eu = [i for i in rot if i not in taken and parts.loc[i, "repair_shop"] == "EU_VENDOR"] or [i for i in rot if i not in taken]
    i2 = max(eu, key=lambda i: rate[i])
    gt.loc[i2, "repair_tat_mean_true_d"] = float(pl["PS2"]["tat_days"])
    parts.loc[i2, "repair_tat_mean_d"] = float(pl["PS2"]["quoted_tat_days"])
    parts.loc[i2, "planted"] = "PS2"
    taken.add(i2)
    planted["PS2"] = {"pn": parts.loc[i2, "pn"], "station": parts.loc[i2, "repair_shop"], "weeks": list(pl["PS2"]["weeks"]),
                      "note": "true shop TAT %.0f d vs quoted %.0f d; on the history seed the first removal in weeks %s gets %.0f shop work days -> that RO is still open and far past its quoted due date at week 103"
                              % (pl["PS2"]["tat_days"], pl["PS2"]["quoted_tat_days"], pl["PS2"]["weeks"], pl["PS2"]["stuck_repair_days"])}

    # PS3: declining-demand consumable
    cons = [i for i in parts.index[parts.part_class == "C"] if i not in taken]
    i3 = max(cons, key=lambda i: rate[i])
    gt.loc[i3, "trend_per_year"] = float(pl["PS3"]["trend_per_year"])
    parts.loc[i3, "mtbur_quoted"] = round(1000.0 / (gt.loc[i3, "usage_per_1000_fc_true"] * pl["PS3"]["quoted_usage_multiple"]), 1)
    parts.loc[i3, "planted"] = "PS3"
    taken.add(i3)
    planted["PS3"] = {"pn": parts.loc[i3, "pn"], "station": "network (AUH largest)", "weeks": "0-103 (declining)",
                      "note": "true usage multiplies by %.2f per year; quoted usage reflects the week-0 rate, so static min/max over-stocks"
                              % pl["PS3"]["trend_per_year"]}

    # PS4: lead-time jump on an expendable
    exps = [i for i in parts.index[parts.part_class == "E"] if i not in taken]
    i4 = max(exps, key=lambda i: rate[i])
    gt.loc[i4, "lead_time_change_week"] = int(pl["PS4"]["change_week"])
    gt.loc[i4, "lead_time_after_d"] = float(gt.loc[i4, "lead_time_mean_true_d"] * pl["PS4"]["lead_time_factor"])
    parts.loc[i4, "planted"] = "PS4"
    planted["PS4"] = {"pn": parts.loc[i4, "pn"], "station": cfg["network"]["hub"], "weeks": int(pl["PS4"]["change_week"]),
                      "note": "supplier change: true PO lead time %.0f d -> %.0f d for orders placed from week %d; part master still quotes %.0f d"
                              % (gt.loc[i4, "lead_time_mean_true_d"], gt.loc[i4, "lead_time_after_d"], pl["PS4"]["change_week"],
                                 parts.loc[i4, "lead_time_mean_d"])}
    gt["lead_time_change_week"] = gt["lead_time_change_week"].astype("Int64")
    return planted


# --------------------------------------------------------------------------------------
# Schedule (world-level, prefix-consistent)
# --------------------------------------------------------------------------------------
_SCHED_CACHE: dict = {}


def build_schedule(world: World, n_weeks: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flight legs + maintenance schedule (A-check kit lines) for weeks [0, n_weeks)."""
    cfg = world.cfg
    key = (config_hash(cfg), int(n_weeks))
    if key in _SCHED_CACHE:
        return _SCHED_CACHE[key]
    gc, net = cfg["generator"], cfg["network"]
    hub = net["hub"]
    ws = int(cfg["seeds"]["world_seed"])
    H = n_weeks * HOURS_PER_WEEK
    legfh = _leg_fh_table(cfg, world.stations)
    taxi, ming, jit = gc["taxi_hours_per_leg"], gc["min_ground_hours"], gc["ground_time_jitter"]
    intervals = cfg["maintenance"]["scheduled_checks"]["A_check_interval_fh"]
    down = gc["a_check_downtime_h"]
    # precompute season factor per hour-of-horizon at daily resolution
    days = H // 24 + 40
    sf = np.array([season_factor(cfg, d * 24) for d in range(days)])
    legs, checks = [], []
    for ti, r in enumerate(world.aircraft.itertuples(index=False)):
        rng = _rng(ws, SALT_SCHED, ti)
        mix = net["route_mix"][r.archetype]
        outs = list(mix.keys())
        cdf = np.cumsum([mix[o] for o in outs])
        cdf /= cdf[-1]
        F0 = r.fh_per_day_mean
        interval = intervals[r.archetype]
        t = rng.uniform(0, 12)
        since = rng.uniform(0, interval)
        fhmap = legfh[r.archetype]
        while t < H:
            if since >= interval:
                checks.append((r.tail, r.archetype, int(round(t))))
                t += down
                since = 0.0
                continue
            u = rng.random(2)
            x = outs[int(np.searchsorted(cdf, u[0], side="right"))]
            fh = fhmap[x]
            blk = fh + taxi
            for k, (a, b) in enumerate(((hub, x), (x, hub))):
                dep_h = int(round(t))
                arr_h = max(dep_h + 1, int(round(t + blk)))
                legs.append((r.tail, a, b, dep_h, arr_h, fh))
                since += fh
                F = F0 * sf[min(days - 1, arr_h // 24)]
                g = max(ming, fh * 24.0 / F - blk) * (1 + jit * (2 * u[1] - 1) * (1 if k == 0 else -1))
                t = t + blk + g
    fl = pd.DataFrame(legs, columns=["tail", "dep_station", "arr_station", "dep_h", "arr_h", "fh"])
    fl = fl[fl.dep_h < H].sort_values(["dep_h", "tail"], kind="mergesort").reset_index(drop=True)
    fl.insert(0, "leg_id", np.arange(len(fl), dtype=np.int64))
    fl["fc"] = np.int64(1)
    fl["week"] = (fl.dep_h // HOURS_PER_WEEK).astype(np.int64)
    fl = fl[schemas.TABLES["flight_exposure"].colnames]

    # maintenance schedule (A-checks at AUH with consumable kits)
    sc = cfg["maintenance"]["scheduled_checks"]
    ch = pd.DataFrame(checks, columns=["tail", "archetype", "due_h"])
    ch = ch[ch.due_h < H].sort_values(["due_h", "tail"], kind="mergesort").reset_index(drop=True)
    appl = world.applicability
    elig = {arch: [p for p in world.kit_eligible if
                   ((appl.pn == p) & (appl.archetype == arch)).any()] for arch in ARCHS}
    rows = []
    for tid, c in enumerate(ch.itertuples(index=False)):
        rng = _rng(ws, SALT_KITS, tid)
        pool = elig[c.archetype]
        nl = int(rng.integers(sc["kit_lines_per_check"][0], sc["kit_lines_per_check"][1] + 1))
        chosen = rng.choice(len(pool), size=min(nl, len(pool)), replace=False) if pool else []
        qlo, qhi = gc["kit_line_qty"]
        qty = rng.integers(qlo, qhi + 1, size=len(chosen))
        for j, q in zip(sorted(chosen), qty):
            rows.append({"task_id": tid, "tail": c.tail, "check_type": "A-check", "station": sc["A_check_station"],
                         "due_h": int(c.due_h), "notice_h": int(max(0, c.due_h - sc["kit_notice_days"] * 24)),
                         "pn": pool[j], "qty": int(q)})
    ms = pd.DataFrame(rows, columns=schemas.TABLES["maintenance_schedule"].colnames)
    ms = ms.astype({"task_id": np.int64, "due_h": np.int64, "notice_h": np.int64, "qty": np.int64})
    _SCHED_CACHE[key] = (fl, ms)
    return fl, ms


def schedule_for(world: World, week_to: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    ev = world.cfg["calendar"]["evaluation_weeks"][1] + 1
    return build_schedule(world, max(ev, int(week_to) + 2))


# --------------------------------------------------------------------------------------
# Scenario
# --------------------------------------------------------------------------------------
class _Static:
    """Per-world arrays used by the scenario sampler (built once, cached)."""

    def __init__(self, world: World, truth: GroundTruth):
        p = world.parts.reset_index(drop=True)
        gt = truth.parts.set_index("pn").loc[p.pn].reset_index()
        self.pn = p.pn.to_numpy()
        self.cls = p.part_class.to_numpy()
        self.dl = p.deadline_class.to_numpy()
        tails = world.aircraft["tail"].tolist()
        self.tails = np.array(tails)
        self.tail_idx = {t: i for i, t in enumerate(tails)}
        arch = world.aircraft.archetype.to_numpy()
        q = np.zeros((len(p), len(tails)))
        for r in world.applicability.itertuples(index=False):
            i = int(np.where(self.pn == r.pn)[0][0])
            q[i, arch == r.archetype] = r.qty_per_aircraft
        self.re = np.where(self.cls != "C")[0]
        self.c = np.where(self.cls == "C")[0]
        self.Q_re = q[self.re]
        self.A_c = (q[self.c] > 0).astype(float)
        drv = p.driver.to_numpy()
        self.fc_driven = (drv[self.re] == "FC")
        self.inv_mtbur = 1.0 / gt.mtbur_true.to_numpy()[self.re]
        self.use = gt.usage_per_1000_fc_true.to_numpy()[self.c] / 1000.0
        k = gt.nb_k.to_numpy()
        self.k_re, self.k_c = k[self.re], k[self.c]
        tr = gt.trend_per_year.fillna(1.0).to_numpy()
        self.trend_re, self.trend_c = tr[self.re], tr[self.c]
        self.tat_mu, self.tat_sig = _lognormal_params(gt.repair_tat_mean_true_d.fillna(30).to_numpy(),
                                                      gt.repair_tat_cv_true.fillna(0.3).to_numpy())
        self.cond = gt.condemnation_prob_true.fillna(0).to_numpy()
        self.lt_mean = gt.lead_time_mean_true_d.to_numpy()
        self.lt_cv = gt.lead_time_cv_true.to_numpy()
        self.lt_change = gt.lead_time_change_week.to_numpy()
        self.lt_after = gt.lead_time_after_d.to_numpy()
        mix = world.cfg["parts"]["deadline_class_mix"]
        self.mix = {c: (list(mix[CLASS_KEY[c]].keys()), np.cumsum(list(mix[CLASS_KEY[c]].values()))) for c in "CER"}
        st = world.stations.station.tolist()
        self.st = np.array(st)
        self.ps2_pn = truth.planted.get("PS2", {}).get("pn")


_STATIC_CACHE: dict = {}


def _static(world, truth) -> _Static:
    key = (config_hash(world.cfg), id(truth))
    if key not in _STATIC_CACHE:
        _STATIC_CACHE.clear()
        _STATIC_CACHE[key] = _Static(world, truth)
    return _STATIC_CACHE[key]


def _sample_week(S: _Static, flights_w: pd.DataFrame, seed: int, w: int, cfg: dict):
    """All random demand for legs departing in week w (stream (seed, w)).

    ``flights_w`` carries ``next_hub_arr_h`` (the tail's next arrival at the hub, -1 if none): a
    deferrable (D3/D10) removal found at an outstation is rectified there with probability
    1 - generator.deferred_to_hub_share, otherwise at the hub on that next arrival."""
    rng = _rng(SALT_WEEK, seed, w)
    hub = cfg["network"]["hub"]
    nxt = flights_w.next_hub_arr_h.to_numpy()
    L = len(flights_w)
    ti = flights_w["tail"].map(S.tail_idx).to_numpy()
    fh = flights_w.fh.to_numpy()
    arr_h = flights_w.arr_h.to_numpy()
    arr_st = flights_w.arr_station.to_numpy()
    yrs = (w + 0.5) / 52.0
    # weekly gamma frailty (fleet-wide) -> weekly counts NB with var = mu + mu^2/k
    k_all = np.concatenate([S.k_re, S.k_c])
    g = rng.standard_gamma(np.where(np.isnan(k_all), 1.0, k_all))
    frail = np.where(np.isnan(k_all), 1.0, g / np.where(np.isnan(k_all), 1.0, k_all))
    fr_re, fr_c = frail[: len(S.re)], frail[len(S.re):]
    expo = np.where(S.fc_driven[:, None], 1.0, fh[None, :])
    lam = S.Q_re[:, ti] * expo * (S.inv_mtbur * fr_re * S.trend_re ** yrs)[:, None]
    cnt = rng.poisson(lam) if L else np.zeros((len(S.re), 0), int)
    lam_c = S.A_c[:, ti] * (S.use * fr_c * S.trend_c ** yrs)[:, None]
    cnt_c = rng.poisson(lam_c) if L else np.zeros((len(S.c), 0), int)

    # removal events (one per unit)
    pi, li = np.nonzero(cnt)
    reps = cnt[pi, li]
    pi, li = np.repeat(pi, reps), np.repeat(li, reps)
    ne = len(pi)
    u_alt, u_cls, z_rep, u_con = rng.random(ne), rng.random(ne), rng.standard_normal(ne), rng.random(ne)
    gidx = S.re[pi]
    dl = S.dl[gidx].copy()
    alt = u_alt < cfg["generator"]["deadline_class_alt_prob"]
    for e in np.where(alt)[0]:
        keys, cdf = S.mix[S.cls[gidx[e]]]
        dl[e] = keys[int(np.searchsorted(cdf / cdf[-1], u_cls[e], side="right"))]
    rep_days = np.exp(S.tat_mu[gidx] + S.tat_sig[gidx] * z_rep)
    condemn = u_con < S.cond[gidx]
    u_def = rng.random(ne)
    st_e, nh_e = arr_st[li].copy(), arr_h[li].copy()
    defer = (st_e != hub) & (dl != "D0") & (u_def < cfg["generator"]["deferred_to_hub_share"]) & (nxt[li] >= 0)
    st_e[defer] = hub
    nh_e[defer] = nxt[li][defer]
    rem = pd.DataFrame({"pidx": gidx, "tidx": ti[li], "station": st_e, "need_h": nh_e,
                        "deadline_class": dl, "repair_days": rep_days, "condemn": condemn,
                        "dep_week": w, "gen": np.arange(ne)})
    # line usage events (qty = count per leg)
    ci, cl = np.nonzero(cnt_c)
    nu = len(ci)
    u_alt2, u_cls2 = rng.random(nu), rng.random(nu)
    gidx2 = S.c[ci]
    dl2 = S.dl[gidx2].copy()
    for e in np.where(u_alt2 < cfg["generator"]["deadline_class_alt_prob"])[0]:
        keys, cdf = S.mix["C"]
        dl2[e] = keys[int(np.searchsorted(cdf / cdf[-1], u_cls2[e], side="right"))]
    use = pd.DataFrame({"pidx": gidx2, "tidx": ti[cl], "station": arr_st[cl], "need_h": arr_h[cl],
                        "qty": cnt_c[ci, cl].astype(np.int64), "deadline_class": dl2, "dep_week": w, "gen": np.arange(nu)})
    return rem, use


def generate_scenario(world: World, truth: GroundTruth, seed: int, week_from: int, week_to: int) -> Scenario:
    """Exogenous demand + common random numbers for weeks [week_from, week_to] (inclusive)."""
    cfg = world.cfg
    S = _static(world, truth)
    seed, week_from, week_to = int(seed), int(week_from), int(week_to)
    flights_all, ms_all = schedule_for(world, week_to)
    h0, h1 = week_from * HOURS_PER_WEEK, (week_to + 1) * HOURS_PER_WEEK
    flights = flights_all[(flights_all.week >= week_from) & (flights_all.week <= week_to)].reset_index(drop=True)
    fa = flights_all.sort_values(["tail", "dep_h"], kind="mergesort")
    nxt_arr = fa.groupby("tail").arr_h.shift(-1)
    nxt_st = fa.groupby("tail").arr_station.shift(-1)
    hub = cfg["network"]["hub"]
    fa = fa.assign(next_hub_arr_h=np.where((nxt_st == hub).to_numpy(), nxt_arr.fillna(-1).to_numpy(), -1).astype(np.int64))
    fa = fa.sort_values("leg_id")
    gen_fl = fa[(fa.week >= max(0, week_from - 2)) & (fa.week <= week_to)]
    rems, uses = [], []
    for w, fw in gen_fl.groupby("week", sort=True):
        r, u = _sample_week(S, fw, seed, int(w), cfg)
        rems.append(r)
        uses.append(u)
    rem = pd.concat(rems, ignore_index=True)
    use = pd.concat(uses, ignore_index=True)
    rem = rem[(rem.need_h >= h0) & (rem.need_h < h1)]
    use = use[(use.need_h >= h0) & (use.need_h < h1)]

    # planted PS2: overdue repair on the history seed
    ps2 = cfg["generator"]["planted"]["PS2"]
    if S.ps2_pn is not None and seed == int(cfg["seeds"]["history_seed"]):
        pidx2 = int(np.where(S.pn == S.ps2_pn)[0][0])
        wk = rem.need_h // HOURS_PER_WEEK
        sel = (rem.pidx == pidx2) & (wk >= ps2["weeks"][0]) & (wk <= ps2["weeks"][1])
        if sel.any():   # only the first such removal (in time order) gets the stuck repair
            first = rem[sel].sort_values(["need_h", "tidx", "dep_week", "gen"], kind="mergesort").index[0]
            rem.loc[first, "repair_days"] = max(float(rem.loc[first, "repair_days"]), float(ps2["stuck_repair_days"]))

    # removal ids by need week
    rem = rem.sort_values(["need_h", "pidx", "tidx", "dep_week", "gen"], kind="mergesort").reset_index(drop=True)
    rem["week"] = (rem.need_h // HOURS_PER_WEEK).astype(np.int64)
    rank = rem.groupby("week").cumcount().to_numpy()
    if len(rank) and rank.max() >= 10000:
        raise OverflowError("more than 10,000 removals in a week")
    rem["removal_id"] = (rem.week * 10000 + rank).astype(np.int64)
    rem["pn"] = S.pn[rem.pidx]
    rem["tail"] = S.tails[rem.tidx]
    removals = rem[["removal_id", "tail", "pn", "station", "need_h", "deadline_class", "week"]].rename(
        columns={"need_h": "removal_h"}).astype({"removal_h": np.int64})

    # material requests: removals + line usage + scheduled kits
    rq_r = pd.DataFrame({"pidx": rem.pidx, "tidx": rem.tidx, "station": rem.station, "need_h": rem.need_h,
                         "known_h": rem.need_h, "qty": np.int64(1), "source": "unscheduled_removal",
                         "deadline_class": rem.deadline_class, "removal_id": rem.removal_id, "src_rank": 0,
                         "dep_week": rem.dep_week, "gen": rem.gen})
    rq_u = pd.DataFrame({"pidx": use.pidx, "tidx": use.tidx, "station": use.station, "need_h": use.need_h,
                         "known_h": use.need_h, "qty": use.qty, "source": "line_usage",
                         "deadline_class": use.deadline_class, "removal_id": pd.NA, "src_rank": 1,
                         "dep_week": use.dep_week, "gen": use.gen})
    ms = ms_all[(ms_all.due_h >= h0) & (ms_all.due_h < h1)].reset_index(drop=True)
    pn_idx = {p: i for i, p in enumerate(S.pn)}
    rq_k = pd.DataFrame({"pidx": ms.pn.map(pn_idx).astype(int), "tidx": ms["tail"].map(S.tail_idx).astype(int),
                         "station": ms.station, "need_h": ms.due_h, "known_h": ms.notice_h, "qty": ms.qty,
                         "source": "scheduled_kit", "deadline_class": S.dl[ms.pn.map(pn_idx).astype(int).to_numpy()]
                         if len(ms) else [], "removal_id": pd.NA, "src_rank": 2, "dep_week": 0, "gen": ms.task_id})
    rq = pd.concat([d for d in (rq_r, rq_u, rq_k) if len(d)], ignore_index=True)
    rq = rq.sort_values(["need_h", "src_rank", "pidx", "tidx", "dep_week", "gen"], kind="mergesort").reset_index(drop=True)
    rq["week"] = (rq.need_h // HOURS_PER_WEEK).astype(np.int64)
    rank = rq.groupby("week").cumcount().to_numpy()
    if len(rank) and rank.max() >= 100000:
        raise OverflowError("more than 100,000 requests in a week")
    requests = pd.DataFrame({
        "request_id": (rq.week * 100000 + rank).astype(np.int64), "pn": S.pn[rq.pidx.to_numpy()],
        "station": rq.station.astype(str), "tail": S.tails[rq.tidx.to_numpy()],
        "need_h": rq.need_h.astype(np.int64), "known_h": rq.known_h.astype(np.int64), "qty": rq.qty.astype(np.int64),
        "source": rq.source, "deadline_class": rq.deadline_class.astype(str),
        "removal_id": rq.removal_id.astype("Int64"), "week": rq.week,
        "filled_h": pd.array([pd.NA] * len(rq), dtype="Int64"), "fill_source": pd.array([None] * len(rq), dtype="string"),
        "immediate_fill": pd.array([pd.NA] * len(rq), dtype="boolean")})

    # common random numbers
    is_rot = S.cls[rem.pidx.to_numpy()] == "R"
    repair_days = dict(zip(rem.removal_id[is_rot].tolist(), rem.repair_days[is_rot].astype(float).tolist()))
    condemn_flag = dict(zip(rem.removal_id[is_rot].tolist(), rem.condemn[is_rot].astype(bool).tolist()))
    lead, regimes = {}, {}
    for i, pn in enumerate(S.pn):
        mu, sg = _lognormal_params(S.lt_mean[i], S.lt_cv[i])
        base = np.exp(mu + sg * _rng(seed, SALT_LT, i).standard_normal(LT_STREAM_LEN))
        lead[pn] = base
        cw = S.lt_change[i]
        if cw is not pd.NA and not (isinstance(cw, float) and np.isnan(cw)):
            mu2, sg2 = _lognormal_params(S.lt_after[i], S.lt_cv[i])
            after = np.exp(mu2 + sg2 * _rng(seed, SALT_LT, i, 1).standard_normal(LT_STREAM_LEN))
            regimes[pn] = [(0, base), (int(cw) * HOURS_PER_WEEK, after)]
            if week_from * HOURS_PER_WEEK >= int(cw) * HOURS_PER_WEEK:
                lead[pn] = after
    jitter = {k: _rng(seed, SALT_JIT, j).random(JITTER_LEN) for j, k in enumerate(["routine", "core_return", "pipeline", "initial"])}

    sc = Scenario(seed=seed, week_from=week_from, week_to=week_to, flights=flights, maintenance=ms,
                  removals=removals.reset_index(drop=True), requests=requests, repair_days=repair_days,
                  condemn_flag=condemn_flag, lead_time_days=lead, transport_jitter=jitter,
                  lead_time_regimes=regimes)
    return sc


# --------------------------------------------------------------------------------------
# Station coordinate verification (OurAirports, public domain)
# --------------------------------------------------------------------------------------
OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
MANIFEST_COLS = ["source_id", "name", "url", "licence", "version_or_date", "download_date", "sha256", "used_for",
                 "provenance", "notes"]


def _upsert_manifest(path: Path, row: dict):
    rows = []
    if path.exists():
        with open(path, newline="") as f:
            rows = [r for r in csv.DictReader(f) if r.get("source_id") != row["source_id"]]
    rows.append(row)
    with open(path, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=MANIFEST_COLS)
        wr.writeheader()
        for r in rows:
            wr.writerow({k: r.get(k, "") for k in MANIFEST_COLS})


def verify_station_coordinates(tol: float = 0.01, download: bool = True, config_path: Path = CONFIG_PATH,
                               raw_dir: Path = DATA / "raw" / "ourairports",
                               manifest: Path = DATA / "source_manifest.csv") -> dict:
    """Compare config station coordinates with OurAirports; fix config lines that differ by > tol degrees."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    f = raw_dir / "airports.csv"
    today = _dt.date.today().isoformat()
    report = {"verified": False, "changes": {}, "max_abs_diff": None}
    try:
        if download or not f.exists():
            req = urllib.request.Request(OURAIRPORTS_URL, headers={"User-Agent": "gnm-sim/0.1"})
            with urllib.request.urlopen(req, timeout=60) as r, open(f, "wb") as out:
                out.write(r.read())
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        ap = pd.read_csv(f, keep_default_na=False, usecols=["ident", "iata_code", "name", "latitude_deg", "longitude_deg", "type"])
    except Exception as e:  # offline fallback
        _upsert_manifest(manifest, {"source_id": "ourairports_airports", "name": "OurAirports airports.csv",
                                    "url": OURAIRPORTS_URL, "licence": "Public Domain", "version_or_date": "n/a",
                                    "download_date": "", "sha256": "", "used_for": "station_master lat/lon",
                                    "provenance": "REAL",
                                    "notes": f"REAL (from published airport reference, not re-verified): download failed ({e})"})
        report["error"] = str(e)
        return report
    text = Path(config_path).read_text()
    cfg = load_config()
    diffs = []
    for st, body in cfg["network"]["stations"].items():
        m = ap[(ap.iata_code == st) & (ap.type == "large_airport")]
        if m.empty:
            m = ap[ap.iata_code == st]
        lat, lon = float(m.latitude_deg.iloc[0]), float(m.longitude_deg.iloc[0])
        d = max(abs(lat - body["lat"]), abs(lon - body["lon"]))
        diffs.append(d)
        if d > tol:
            pat = re.compile(r"(^\s+%s: \{name: \"[^\"]*\", lat: )([-\d.]+)(, lon: )([-\d.]+)" % st, re.M)
            text, nsub = pat.subn(lambda mm: f"{mm.group(1)}{lat:.4f}{mm.group(3)}{lon:.4f}", text)
            report["changes"][st] = {"old": [body["lat"], body["lon"]], "new": [round(lat, 4), round(lon, 4)],
                                     "ident": m.ident.iloc[0], "replaced": nsub}
    if report["changes"]:
        Path(config_path).write_text(text)
        load_config.cache_clear()
    report["verified"] = True
    report["max_abs_diff"] = max(diffs)
    _upsert_manifest(manifest, {
        "source_id": "ourairports_airports", "name": "OurAirports airports.csv", "url": OURAIRPORTS_URL,
        "licence": "Public Domain (OurAirports data dump)", "version_or_date": f"nightly dump retrieved {today}",
        "download_date": today, "sha256": sha, "used_for": "station_master lat/lon (7 stations)", "provenance": "REAL",
        "notes": ("verified tolerance %.2f deg; updated in config: %s" % (tol, ", ".join(
            f"{k} {v['old']}->{v['new']}" for k, v in report["changes"].items()) or "none"))})
    return report
