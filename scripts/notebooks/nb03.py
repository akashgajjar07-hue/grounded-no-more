from nbtools import HEADER, ROOT, SETUP, build

cells = [
("md", f"""
# 03 · Policies and the capital frontier (v2 world)

{HEADER}

**The decision.** How should Falcon Hub Airways position its spare parts across the AUH hub and six outstations? Three policies were frozen before the holdout:

* **P0, legacy:** OEM-recommended provisioning on quoted data. A Poisson protection level at AUH, plus a line-station unit only where a D0 part has at least 4 quoted removals a year at that station. In practice this is **a legacy OEM-quote policy holding only 8 outstation rotables**.
* **P1, local:** each station optimised on its own, from the history-based forecasts.
* **P2, network:** the same forecasts, but positioned as a network: a pooled hub float plus outstation units where the value of avoiding a D0 miss (hub transfer, local borrow, exchange/loan odds, the hourly rate and the fixed cost per event) justifies the holding cost.

**Core finding: P2.** Network positioning cuts material AOG hours against P0 by a large, significant amount for a small amount of extra capital, in all three worlds and across the ×0.5–×2 hourly-rate range (section 1). **Frontier option: I125.** If the airline invests an additional AED 7.6M, the optimiser's recommended point cuts downtime further, with sensitivities that are shown, not hidden (sections 3–6).

Headline numbers come from the **v2 holdout** (seeds 2000–2019, never used for any choice), central world unless stated. Selection-seed numbers (100–119) are labelled as such. A v1 world was archived after a domain review; see `archive/v1`.
"""),
("code", SETUP + '''
ps = load_json("outputs/holdout/policy_summary.json")
sel = load_json("outputs/policies/selection_summary.json")
kp = load_json("docs/data/kpis.json")
fs = load_json("outputs/frontier/summary.json")
cen = ps["variants"]["central"]
print(ps["split"], "seeds", ps["seeds"][0], "-", ps["seeds"][-1], "|", ps["ci_method"])
out = {}
for p in ["P0", "P1", "P2"]:
    sp = pd.read_csv(ROOT / f"outputs/policies/{p}_stock_params.csv")
    out[p] = int(sp[(sp.part_class == "R") & (sp.station != "AUH")].target_units.sum())
print("outstation rotable units at target (central plans):", out)
assert out == kp["headline"]["core"]["outstation_rotables"]'''),

("md", """
## 1. Core finding: P2 against the legacy baseline, on the holdout

Means over 20 holdout seeds with 95% intervals; the paired differences use the same seeds and the same per-request random numbers for every policy, so they are much tighter than the raw intervals.
"""),
("code", '''
metrics = [("immediate_fill_rate", "fill", "{:.4f}", 1), ("aog_hours", "material AOG h/yr", "{:,.0f}", 1),
           ("aog_events", "AOG events/yr", "{:.1f}", 1), ("spare_capital_aed", "capital AED M", "{:.2f}", 1e6),
           ("total_annual_cost_aed", "total cost AED M/yr", "{:.2f}", 1e6), ("expedite_cost_aed", "AOG-route spend AED M/yr", "{:.2f}", 1e6)]
tab = pd.DataFrame({lab: {p: ci(cen["policies"][p][k], f, s) for p in ["P0", "P1", "P2"]} for k, lab, f, s in metrics})
tab.insert(0, "outstation rotables", pd.Series(out))
display(tab)
pair = pd.DataFrame({lab: {pr: ci(cen["paired"][pr][k], f, s, signed=True) for pr in ["P2-P0", "P1-P0", "P2-P1"]} for k, lab, f, s in metrics})
pair["seeds with lower AOG"] = [f"{cen['paired'][pr]['aog_hours']['share_seeds_better']:.0%}" for pr in pair.index]
print("Paired differences (mean [95% paired-t CI]):"); display(pair)
d = cen["paired"]["P2-P0"]
print(f"P2 vs P0: {ci(d['aog_hours'], signed=True)} material AOG h/yr for {ci(d['spare_capital_aed'], '{:.2f}', 1e6, signed=True)} AED M capital; "
      f"immediate fill {ci(d['immediate_fill_rate'], '{:.2f}', 0.01, signed=True)} pts")'''),
("code", '''
fig, axes = plt.subplots(1, 3, figsize=(12, 3.4))
prs = ["P2-P0", "P1-P0", "P2-P1"]
for ax, (k, lab, scale) in zip(axes, [("aog_hours", "Δ material AOG h/yr", 1), ("spare_capital_aed", "Δ capital (AED M)", 1e6),
                                      ("total_annual_cost_aed", "Δ total cost (AED M/yr)", 1e6)]):
    for i, pr in enumerate(prs):
        dd = cen["paired"][pr][k]
        col = TEAL if dd["ci_hi"] < 0 else (RED if dd["ci_lo"] > 0 else TITANIUM)
        ax.errorbar(dd["mean"] / scale, i, xerr=[[(dd["mean"] - dd["ci_lo"]) / scale], [(dd["ci_hi"] - dd["mean"]) / scale]],
                    fmt="o", color=col, capsize=0, ms=6)
    ax.axvline(0, color=SLATE, lw=0.8); ax.set_yticks(range(3)); ax.set_yticklabels(prs); ax.invert_yaxis(); ax.set_title(lab)
fig.suptitle("Paired holdout differences, central world (teal = significantly lower, red = significantly higher)", color=ICE, y=1.05, fontsize=11)
stamp(axes[-1], "policy_summary.json (holdout)"); plt.show()'''),
("md", """
P2 removes most of P0's material AOG hours, on every holdout seed. The extra capital is small because P2 mostly *positions* rather than adds: it places 44 rotables at the outstations where D0 removals actually happen, sized from history-based removal rates instead of vendor quotes. P1, which optimises each station on its own, buys a smaller reduction for far more capital, and P2 beats it on downtime, capital and cost.

**The honest trade-off.** P1 and P2 have a slightly *lower* immediate fill than P0 (the fill row above). P0's consumable and expendable min/max levels (26/13 weeks of cover) are generous, so P0 fills more count-part requests from the shelf; P1/P2 stock C/E to a cycle service level. Those misses are cheap, because consumables are never D0 and expendables recover through local buy. The rotable fill moves the other way. It is reported, not tuned away:
"""),
("code", '''
bc = pd.DataFrame(ps["by_class"])
fill = bc[bc.variant == "central"].pivot(index="part_class", columns="policy_id", values="immediate_fill_rate")[["P0", "P1", "P2"]]
aogc = bc[bc.variant == "central"].pivot(index="part_class", columns="policy_id", values="aog_hours")[["P0", "P1", "P2"]]
display(pd.concat({"immediate fill": fill.round(4), "material AOG h/yr": aogc.round(0)}, axis=1))'''),

("md", """
### Does P2 hold in all three worlds and across the hourly-rate range?

In the low- and high-stress worlds P1 and P2 are re-planned from each world's own history (`P2`), and the central-built plans are also evaluated unchanged (`P2@central`). The hourly-rate sensitivity scales only the hourly part of the downtime cost; the fixed cost per AOG event stays at ×1.
"""),
("code", '''
rows = []
for wv in ["low_stress", "central", "high_stress"]:
    v = ps["variants"][wv]
    for pr in [p for p in ["P2-P0", "P2@central-P0"] if p in v["paired"]]:
        dd = v["paired"][pr]
        rows.append(dict(world=wv, pair=pr, d_aog_h=ci(dd["aog_hours"], signed=True),
                         d_capital_M=ci(dd["spare_capital_aed"], "{:.2f}", 1e6, signed=True),
                         **{f"d_cost_M_{m}": ci(dd[f"total_cost_pen_{m}"], "{:.1f}", 1e6, signed=True) for m in ["x0.5", "x1", "x2"]},
                         significant_all=all(dd[k]["ci_hi"] < 0 for k in ["aog_hours", "total_cost_pen_x0.5", "total_cost_pen_x1", "total_cost_pen_x2"])))
wt = pd.DataFrame(rows); display(wt)
assert wt.significant_all.all()'''),
("code", '''
fig, ax = plt.subplots(figsize=(8.5, 3.6))
worlds = ["low_stress", "central", "high_stress"]
for j, p in enumerate(["P0", "P1", "P2"]):
    m = [ps["variants"][w]["policies"][p]["aog_hours"] for w in worlds]
    x = np.arange(3) + (j - 1) * 0.26
    ax.bar(x, [d["mean"] for d in m], width=0.26, color=POLICY_COLORS[p], label=p,
           yerr=[[d["mean"] - d["ci_lo"] for d in m], [d["ci_hi"] - d["mean"] for d in m]], error_kw=dict(ecolor=ICE, lw=0.8))
ax.set_xticks(range(3)); ax.set_xticklabels(["low stress", "central", "high stress"])
ax.set(ylabel="material AOG h/yr (holdout, 95% CI)", title="P0 / P1 / P2 in the three worlds (plans re-built per world)")
ax.legend(frameon=False); stamp(ax, "policy_summary.json (holdout)"); plt.show()'''),
("md", """
The P2 advantage is significant in every world and at ×0.5, ×1 and ×2 the hourly rate, for both the re-planned and the central-built P2.

### Selection → holdout consistency

The selection seeds were used to build and choose; the holdout was run once after the freeze. If the selection numbers sit inside the holdout intervals, the choices were not fitted to noise:
"""),
("code", '''
rows = []
for p in ["P0", "P1", "P2"]:
    for k in ["immediate_fill_rate", "aog_hours", "spare_capital_aed"]:
        h, s = cen["policies"][p][k], sel["variants"]["central"]["policies"][p][k]
        rows.append(dict(policy=p, metric=k, selection=s["mean"], holdout=h["mean"], holdout_ci=(round(h["ci_lo"], 4), round(h["ci_hi"], 4)),
                         selection_inside_holdout_ci=h["ci_lo"] <= s["mean"] <= h["ci_hi"]))
cons = pd.DataFrame(rows); display(cons.round(4))
fsel = pd.read_csv(ROOT / "outputs/frontier/selection_points.csv").query("variant == 'central'").set_index("id")
fp = pd.read_csv(ROOT / "outputs/holdout/frontier_points.csv").set_index("id")
common = sorted(fsel.index.intersection(fp.index))
sm, hl, hh = (fsel.loc[common, "aog_hours_mean"].to_numpy(), fp.loc[common, "aog_hours_lo"].to_numpy(), fp.loc[common, "aog_hours_hi"].to_numpy())
inside = (sm >= hl) & (sm <= hh)
rho = np.corrcoef(np.log(fsel.loc[common, "aog_hours_mean"]), np.log(fp.loc[common, "aog_hours_mean"]))[0, 1]
print(f"policies: {cons.selection_inside_holdout_ci.sum()} of {len(cons)} selection means inside the holdout CI")
print(f"frontier candidates: {inside.sum()} of {len(common)} selection AOG means inside the holdout CI; log-AOG correlation selection vs holdout r = {rho:.3f}")'''),

("md", """
## 2. Hub vs outstation

Where is the downtime, and where does P2 remove it? Holdout material AOG hours by station (central world), with the paired P2 − P0 difference per station:
"""),
("code", '''
bs = pd.DataFrame([r for r in ps["by_station"] if r["variant"] == "central"])
order = ["AUH", "LHR", "FRA", "CAI", "JED", "BOM", "SIN"]
piv = bs.pivot(index="station", columns="policy_id", values="aog_hours").reindex(order)[["P0", "P1", "P2"]]
pbs = pd.DataFrame([r for r in ps["paired_by_station"] if r["variant"] == "central" and r["pair"] == "P2-P0" and r["metric"] == "aog_hours"]).set_index("station").reindex(order)
piv["P2-P0 [95% CI]"] = [f"{m:+.0f} [{lo:+.0f}, {hi:+.0f}]" for m, lo, hi in zip(pbs["mean"], pbs.ci_lo, pbs.ci_hi)]
routes = bs[bs.policy_id.isin(["P0", "P2"])].pivot(index="station", columns="policy_id", values="route_robbery_per_year").reindex(order)
piv["robberies/yr P0 → P2"] = [f"{a:.1f} → {b:.1f}" for a, b in zip(routes.P0, routes.P2)]
display(piv.round(0))
fig, ax = plt.subplots()
x = np.arange(len(piv)); wd = 0.27
for i, p in enumerate(["P0", "P1", "P2"]):
    ax.bar(x + (i - 1) * wd, piv[p], width=wd, color=POLICY_COLORS[p], label=p)
ax.set_xticks(x); ax.set_xticklabels(piv.index); ax.set(ylabel="material AOG h/yr (holdout mean)", title="Material AOG hours by station")
ax.legend(frameon=False); stamp(ax, "policy_summary.json by_station"); plt.show()
hub = piv.loc["AUH", ["P0", "P2"]] / piv[["P0", "P2"]].sum()
print(f"hub share of material AOG hours: P0 {hub.P0:.0%}, P2 {hub.P2:.0%}; outstation hours P0 {piv.loc[order[1:], 'P0'].sum():,.0f} -> P2 {piv.loc[order[1:], 'P2'].sum():,.0f}")'''),
("md", """
Under P0 most downtime sits at the **outstations**: D0 removals there find an empty shelf and wait for a hub transfer or a local borrow (PS1 in notebook 01 is the clearest case). P2's 44 outstation rotables remove most of it, and the pooled hub float also improves, so robbery at AUH (which needs engineering/quality approval) is needed less often.
"""),

("md", """
## 3. The capital frontier: P2 as the core, I125 as the frontier option

25 frozen candidates (P0/P1/P2, budget points B015–B250 re-optimised from scratch, 'P2 within guardrails + greedy additions' points I110/I125, a repositioning and TAT levers) were simulated on the holdout. The recommendation rule was stated before computing and applied on the selection seeds: walk up the lower convex hull of capital vs downtime, and stop where the next segment's downtime reduction per extra AED 1M falls below the break-even h* implied by the holding cost and the realised cost per downtime hour.
"""),
("code", '''
rec = fs["recommendation"]
fr_site = load_json("docs/data/frontier.json")
dom = {p["id"]: p["dominated"] for p in fr_site["points"]}
print(f"rule (selection): h* = {rec['h_star_per_aed_1m']:.2f} downtime h per AED 1M (AED {rec['aed_per_aog_hour']:,.0f} per downtime h, "
      f"carry {rec['carrying_pct']:.0%}) -> {rec['recommended']}")
fig, ax = plt.subplots(figsize=(9.5, 5.2))
for pid, r in fp.iterrows():
    x, y = r.capital_mean / 1e6, r.aog_hours_mean
    if pid in ("P0", "P1", "P2"):
        col, mk, sz = POLICY_COLORS[pid], "s", 80
    elif pid == rec["recommended"]:
        col, mk, sz = COPPER, "*", 260
    else:
        col, mk, sz = (TITANIUM if not dom.get(pid, False) else SLATE), "o", 30
    ax.errorbar(x, y, yerr=[[y - r.aog_hours_lo], [r.aog_hours_hi - y]], fmt="none", ecolor=col, alpha=0.5, lw=0.8)
    ax.scatter(x, y, color=col, marker=mk, s=sz, zorder=3, edgecolor="none")
    if pid in ("P0", "P1", "P2", rec["recommended"], "I110", "B150", "B030"):
        ax.annotate(pid, (x, y), xytext=(6, 6), textcoords="offset points", color=ICE, fontsize=8.5)
nd = fp.loc[[k for k in fp.index if not dom.get(k, True)]].sort_values("capital_mean")
ax.plot(nd.capital_mean / 1e6, nd.aog_hours_mean, color=TEAL, lw=1, alpha=0.6, label="holdout non-dominated set")
ax.set(yscale="log", xlabel="simulated spare capital (AED M)", ylabel="material AOG h/yr (log, 95% CI)",
       title="Capital vs material AOG hours on the holdout (25 frozen candidates)")
ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax.legend(frameon=False, loc="upper right"); stamp(ax, "outputs/holdout/frontier_points.csv"); plt.show()'''),
("code", '''
keep = ["P0", "P1", "P2", "P2_GUARD", "B100", "I110", "I125", "B150", "B200", "LEV_TAT10_TOP6"]
ft = fp.loc[[k for k in keep if k in fp.index], ["capital_mean", "aog_hours_mean", "aog_hours_lo", "aog_hours_hi", "d_aog_hours_vs_base_mean",
                   "d_aog_hours_vs_base_lo", "d_aog_hours_vs_base_hi", "total_cost_mean", "fill_rate_mean", "aog_events_mean"]].copy()
for c in ["capital_mean", "total_cost_mean"]:
    ft[c] = ft[c] / 1e6
ft["dominated_on_holdout"] = [dom.get(k) for k in ft.index]
print("Holdout; d_* columns are paired differences vs P2 (the base policy):"); display(ft.round(2))
i = fp.loc["I125"]
fo = kp["headline"]["frontier_option"]
print(f"I125 vs P2 (paired, holdout): {i.d_aog_hours_vs_base_mean:+.0f} material AOG h/yr [{i.d_aog_hours_vs_base_lo:+.0f}, {i.d_aog_hours_vs_base_hi:+.0f}] "
      f"for an additional {aed_m(i.d_capital_vs_base_mean)} of capital; total cost {aed_m(i.d_total_cost_vs_base_mean)}/yr "
      f"[{aed_m(i.d_total_cost_vs_base_lo)}, {aed_m(i.d_total_cost_vs_base_hi)}]")
assert abs(i.d_capital_vs_base_mean - fo["extra_capital_aed"]["mean"]) < 1 and abs(-i.d_aog_hours_vs_base_mean - fo["aog_reduction"]["mean"]) < 0.06
b = fp.loc["B150"]
print(f"next hull step on the holdout, I125 -> B150: {i.aog_hours_mean - b.aog_hours_mean:.0f} h/yr fewer for {aed_m(b.capital_mean - i.capital_mean)} more "
      f"= {(i.aog_hours_mean - b.aog_hours_mean) / ((b.capital_mean - i.capital_mean) / 1e6):.1f} h per AED 1M (break-even h* = {rec['h_star_per_aed_1m']:.1f})")'''),
("md", """
**Reading the frontier.** P2 sits close to the frontier at its own capital: at P2's budget no re-optimised candidate beats it significantly. The way to cut downtime further is to spend more. **If you invest an additional AED 7.6M**, I125 (P2 within guardrails plus greedy additions at 1.25 × P2's allocation capital) cuts material AOG hours further, significantly on paired seeds, and lowers total annual cost. Beyond I125 the hull flattens: on the selection seeds, and again on the holdout (printed above), the next step buys fewer hours per extra AED 1M than the break-even h*. This is a frontier option for the budget holder to weigh, not a second headline.

## 4. I125's sensitivity, the post-plan stress check and guardrails

### One-at-a-time tornado (selection seeds)

Net annual benefit of I125 vs P2 (penalty saved minus extra holding), paired over the 20 selection seeds, moving **one assumption at a time** with the others at base. The hourly rate is scaled with the fixed per-event cost kept at ×1. The rule's recommended point under each setting is printed below.
"""),
("code", '''
tor = pd.read_csv(ROOT / "outputs/frontier/tornado.csv")
base = tor[tor.factor == "base case"].iloc[0]
t = tor[(tor.factor != "base case") & (~tor.factor.str.contains("expedite"))].copy()
t["label"] = t.factor.str.replace("_", " ") + " " + t.setting.astype(str)
t = t.iloc[np.argsort(-abs(t.net_benefit_mean - base.net_benefit_mean).values)]
fig, ax = plt.subplots(figsize=(8.5, 4))
y = np.arange(len(t))
ax.barh(y, (t.net_benefit_mean - base.net_benefit_mean) / 1e6, left=base.net_benefit_mean / 1e6,
        color=[TEAL if v > base.net_benefit_mean else COPPER for v in t.net_benefit_mean], height=0.6)
ax.errorbar(t.net_benefit_mean / 1e6, y, xerr=[(t.net_benefit_mean - t.net_benefit_lo) / 1e6, (t.net_benefit_hi - t.net_benefit_mean) / 1e6],
            fmt="none", ecolor=ICE, lw=0.8)
ax.axvline(base.net_benefit_mean / 1e6, color=ICE, lw=1); ax.axvline(0, color=SLATE, lw=0.8, ls=":")
ax.set_yticks(y); ax.set_yticklabels(t.label); ax.invert_yaxis()
ax.set(xlabel="net benefit of I125 vs P2 (AED M / yr, 95% CI)", title=f"One-at-a-time tornado around the base case (AED {base.net_benefit_mean/1e6:.1f} M/yr)")
stamp(ax, "tornado.csv (selection seeds)"); plt.show()
t["significant"] = t.net_benefit_lo > 0
display(t[["label", "net_benefit_mean", "net_benefit_lo", "net_benefit_hi", "aog_reduction_mean", "base_aog_hours", "rec_aog_hours", "significant"]].round(0))
print("rule's pick under one-at-a-time changes (selection):", [(r["factor"], r["setting"], r["recommended"]) for r in fs["recommendation_stability"]])
ns = t[~t.significant].label.tolist()
print("settings where I125's lead over P2 is NOT significant in cost:", ns or "none")'''),
("md", """
I125's lead over P2 is **not significant in cost if repair is 25% faster**: a faster repair loop makes the extra float less valuable. The hourly rate scales the benefit, and the rule's recommended point shifts to **I110 at ×0.5** and **B150 at ×2** the hourly rate. The carrying rate barely matters. These are one-at-a-time changes; they say nothing about combinations.

### Post-plan stress check (D015, added after the main holdout)

At the user's request, and **after** the main v2 holdout, the frozen central-built candidates P0, P2 and I125 were evaluated on the same holdout seeds in the low- and high-stress worlds, paired against the central-built P2, with no re-selection. It is labelled post-plan because it was not part of the frozen run plan.
"""),
("code", '''
pp = load_json("outputs/holdout/postplan_i125_stress.json")
print(pp["note"])
rows = []
for wv, lst in pp["worlds"].items():
    r = next(x for x in lst if x["id"] == "I125")
    rows.append(dict(world=wv, P2_central_built_aog_h=r["aog_hours_mean"] - r["d_aog_hours_vs_base_mean"], I125_aog_h=r["aog_hours_mean"],
                     d_aog_h=f"{r['d_aog_hours_vs_base_mean']:+.0f} [{r['d_aog_hours_vs_base_lo']:+.0f}, {r['d_aog_hours_vs_base_hi']:+.0f}]",
                     d_total_cost=f"{aed_m(r['d_total_cost_vs_base_mean'])} [{aed_m(r['d_total_cost_vs_base_lo'])}, {aed_m(r['d_total_cost_vs_base_hi'])}]",
                     d_capital=aed_m(r["d_capital_vs_base_mean"]),
                     significant=r["d_aog_hours_vs_base_hi"] < 0 and r["d_total_cost_vs_base_hi"] < 0))
display(pd.DataFrame(rows).round(1))'''),
("md", """
Post-plan, I125 keeps a significant downtime and cost advantage over the central-built P2 in both stress worlds, smaller in the low-stress world and larger in the high-stress world. The extra AED 7.6M behaves like insurance against a harsher reliability world.

### Guardrails (stated before computing)

A planner does not stack stock far beyond what a stocking point actually sees. Two ceilings were applied to every optimised rotable allocation: **G1** the Palm total at a stocking point stays at or below the 99.5% fill quantile of its own pipeline; **G2** a station with at most 6 requests a year holds at most 1 unit. The as-built policies are evaluated unchanged, and their exceedances are reported:
"""),
("code", '''
g = fs["guardrails"]
print({k: g["config"][k] for k in ["fill_quantile", "low_rate_per_year", "low_rate_max_units"]}, "| overrides:", g["config"]["overrides"] or "none")
ex = {k: len(v) for k, v in g["pns_exceeding_by_candidate"].items() if k in ("P0", "P1", "P2", "P2_GUARD", "I110", "I125", "B150")}
print("PNs exceeding a guardrail:", ex)
pg = fp.loc["P2_GUARD"]
print(f"cost of the guardrails at P2's capital (P2_GUARD - P2, holdout): {pg.d_aog_hours_vs_base_mean:+.0f} h/yr "
      f"[{pg.d_aog_hours_vs_base_lo:+.0f}, {pg.d_aog_hours_vs_base_hi:+.0f}], capital {aed_m(pg.d_capital_vs_base_mean)}")'''),

("md", """
## 5. Levers: buy spares or cut repair TAT?

Per rotable, the optimiser compares buying 1–2 spares with paying the shop to cut 10 days of TAT (modelled, annual basis, at the P2 allocation; `outputs/frontier/levers.csv`, DERIVED).
"""),
("code", '''
lv = pd.read_csv(ROOT / "outputs/frontier/levers.csv")
w = lv.pivot_table(index="pn", columns="lever", values=["aog_hours_reduction", "annual_cost_aed"])
w.columns = [f"{a}|{b}" for a, b in w.columns]
w["cost_per_h_buy1"] = w["annual_cost_aed|buy_1"] / w["aog_hours_reduction|buy_1"].where(w["aog_hours_reduction|buy_1"] > 0)
w["cost_per_h_tat"] = w["annual_cost_aed|tat_cut_10d"] / w["aog_hours_reduction|tat_cut_10d"].where(w["aog_hours_reduction|tat_cut_10d"] > 0)
w = w.dropna(subset=["cost_per_h_buy1", "cost_per_h_tat"])
print(f"buying 1 spare is cheaper per avoided downtime hour than a 10-day TAT cut for {(w.cost_per_h_buy1 < w.cost_per_h_tat).sum()} of {len(w)} rotables "
      f"with a modelled reduction from both levers")
fig, ax = plt.subplots(figsize=(6.2, 5))
ax.scatter(w.cost_per_h_buy1, w.cost_per_h_tat, color=TEAL, s=24, edgecolor="none")
lim = [min(w.cost_per_h_buy1.min(), w.cost_per_h_tat.min()) * 0.7, max(w.cost_per_h_buy1.max(), w.cost_per_h_tat.max()) * 1.4]
ax.plot(lim, lim, color=TITANIUM, ls="--", lw=0.8)
ax.set(xscale="log", yscale="log", xlim=lim, ylim=lim, xlabel="AED / avoided downtime h: buy 1 spare",
       ylabel="AED / avoided downtime h: TAT −10 d", title="Lever cost per avoided downtime hour")
ax.text(lim[0] * 1.3, lim[1] / 2, "above the line: spares cheaper", color=TITANIUM, fontsize=8)
stamp(ax, "levers.csv (modelled)", "DERIVED"); plt.show()
for s in fs["lever_findings"]["tat_vs_buy_1"][:4]:
    print("·", s)
lt = fp.loc["LEV_TAT10_TOP6"]
print(f"simulated on the holdout: TAT -10 d on the top 6 PNs (built on P2 within guardrails) = {lt.d_aog_hours_vs_base_mean:+.0f} h/yr "
      f"[{lt.d_aog_hours_vs_base_lo:+.0f}, {lt.d_aog_hours_vs_base_hi:+.0f}] vs P2")'''),
("md", """
Per avoided downtime hour, buying a spare is the cheaper lever for most rotables in the model; a TAT cut wins on only a few. Simulated on the holdout, a 10-day TAT cut on the top 6 PNs does not beat P2 significantly. Repair-shop TAT is a second-order lever next to positioning in this world (although a faster repair loop does shrink I125's lead over P2, section 4).

## 6. Dependence on the AOG recovery routes

Every policy, P0 included, leans on the AOG recovery routes (ASSUMED odds and response times in `config/assumptions.yaml: aog_sourcing`): robbery at AUH (engineering/quality approval required), local borrow at outstations, exchange/loan by fleet type, and local buy for consumables and expendables. In practice that means access to an AOG exchange/loan market and to borrow agreements. Switching the routes off is a **structural stress, not a calibrated scenario** (selection seeds):
"""),
("code", '''
off = tor[tor.factor.str.contains("expedite")].iloc[0]
dep = pd.DataFrame({"material AOG h/yr, routes on": {"P0": base.p0_base_aog_hours, "P2": base.base_aog_hours, "I125": base.rec_aog_hours},
                    "routes off": {"P0": off.p0_base_aog_hours, "P2": off.base_aog_hours, "I125": off.rec_aog_hours}})
dep["multiple"] = dep["routes off"] / dep["material AOG h/yr, routes on"]
display(dep.round(1))
fig, ax = plt.subplots(figsize=(7, 3.4))
x = np.arange(3)
ax.bar(x - 0.2, dep.iloc[:, 0], width=0.4, color=TEAL, label="routes on")
ax.bar(x + 0.2, dep.iloc[:, 1], width=0.4, color=COPPER, label="routes off")
ax.set_xticks(x); ax.set_xticklabels(dep.index); ax.set(yscale="log", ylabel="material AOG h/yr (log)", title="Without AOG recovery routes, every policy degrades sharply")
ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
ax.legend(frameon=False); stamp(ax, "tornado.csv 'routes off' row (selection)"); plt.show()
print(fs["aog_desk_dependence"])'''),
("md", """
The ranking survives (P2 and I125 still beat P0 by a wide margin), but the absolute levels do not: the frontier is conditional on those markets existing at roughly the assumed availability. This is stated in `LIMITATIONS.md`.

## Summary

* **Core finding: P2.** Network positioning, with 44 instead of 8 outstation rotables, cuts material AOG hours sharply against a legacy OEM-quote policy holding only 8 outstation rotables, for a small capital increase. It holds in all three worlds and across the ×0.5–×2 hourly-rate range (section 1). The cost is a slightly lower immediate fill on cheap count parts.
* **Frontier option: I125.** If you invest an additional AED 7.6M, I125 cuts downtime further, significantly on paired holdout seeds. Its lead over P2 is not significant in cost if repair is 25% faster, and the rule's pick shifts to I110 / B150 at ×0.5 / ×2 the hourly rate. The post-plan stress check keeps its advantage in both stress worlds.
* Selection and holdout agree, the guardrails cost little, spares beat TAT cuts on most rotables, and every result depends on the AOG recovery routes being available.

*Independent educational simulation. Not an airline system or an approved maintenance, airworthiness or dispatch tool.*
"""),
]

build(f"{ROOT}/notebooks/03_policy_and_frontier.ipynb", cells)
print("ok")
