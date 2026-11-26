"""AOG Response Lab + Planner Action Centre from the history (weeks 0-103).

Writes
  outputs/aog_lab/incidents.json   showcase incidents: timelines, options, decision panel, counterfactual
  outputs/aog_lab/summary.json     stats over all incidents + counterfactual summary
  outputs/actions/actions.json     planner exceptions for week 103 (parsed evidence)
  outputs/actions/actions.csv      the same, schemas.planner_exceptions layout (evidence as JSON)
"""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone

from gnm.aog.actions import ACTION_FIELDS, generate_actions, to_table
from gnm.aog.data import default_view, load_aog_config
from gnm.aog.incidents import ROUTE_LABELS, build_all_incidents, select_showcase, summarise
from gnm.aog.options import OPTION_LABELS, REASON_CODES
from gnm.config import OUTPUTS, ROOT
from gnm.schemas import validate_table


def _meta(source, notes, provenance="SIMULATED"):
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                             timeout=5).stdout.strip() or "unknown"
    except Exception:
        sha = "unknown"
    return {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_sha": sha,
            "provenance": provenance, "source": source, "notes": notes}


def _dump(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))


def main():
    t0 = time.time()
    view = default_view()
    acfg = load_aog_config()
    incidents = build_all_incidents(view)
    summary = summarise(view, incidents)
    assert summary["reconciles"], "incident hours do not reconcile to aog_events"
    ids = select_showcase(incidents, int(acfg["showcase"]["n"]), view)
    by_id = {i["id"]: i for i in incidents}
    show = [by_id[i] for i in ids]
    out = OUTPUTS / "aog_lab"
    notes = ("Falcon Hub Airways (fictional). v2 history weeks 0-103 under P0. Options evaluated at request time from "
             "information available then (stock before the request, open POs/ROs at quoted dates, published AOG-route "
             "odds; never the per-request draws). Material shortage exposure = expected material-related downtime "
             "hours (wait beyond the rectification window + fitting/RTS) x rate/h + fixed cost per event (if late) + "
             "direct cost; exposure_aed already includes direct_cost. Robbery = engineering/quality approval required, "
             "human decision, never ranked. Rectification windows are hypothetical, not operator MEL decisions.")
    _dump({"meta": _meta("scripts/run_aog_lab.py (gnm.aog.incidents/options)", notes),
           "showcase_ids": ids, "ps1_incident_id": next((i for i in ids if by_id[i].get("planted") == "PS1"), None),
           "option_labels": OPTION_LABELS, "reason_codes": REASON_CODES,
           "route_labels": ROUTE_LABELS, "incidents": show, "provenance": "SIMULATED"}, out / "incidents.json")
    _dump({"meta": _meta("scripts/run_aog_lab.py (gnm.aog.incidents)", notes),
           **summary, "showcase_ids": ids, "provenance": "SIMULATED"}, out / "summary.json")

    df = generate_actions(view)
    tab = to_table(df)
    errs = validate_table("planner_exceptions", tab)
    assert not errs, errs
    aout = OUTPUTS / "actions"
    aout.mkdir(parents=True, exist_ok=True)
    tab.to_csv(aout / "actions.csv", index=False)
    counts = {"by_type": {k: int(v) for k, v in df.type.value_counts().sort_index().items()},
              "by_severity": {k: int(v) for k, v in df.severity.value_counts().items()},
              "by_type_severity": {f"{a}|{b}": int(n) for (a, b), n in df.groupby(["type", "severity"]).size().items()}}
    _dump({"meta": _meta("scripts/run_aog_lab.py (gnm.aog.actions)",
                         "Planner exceptions for v2 history week 103 (DERIVED from the SIMULATED history). Only "
                         "exception types the simulation produces; no documentation data exists, so none is invented. "
                         "KIT_SHORTAGE checks projected A-checks for weeks 104-106 (history schedule ends at week 103).",
                         provenance="DERIVED"),
           "as_of_week": int(acfg["actions"]["as_of_week"]), "counts": counts,
           "owners": sorted(df.owner.unique().tolist()), "action_fields": ACTION_FIELDS,
           "actions": json.loads(df.to_json(orient="records")), "provenance": "DERIVED"}, aout / "actions.json")
    cf = summary["counterfactual"]
    print(f"incidents {summary['n_incidents']} ({summary['n_requests']} requests), AOG h {summary['aog_hours_total']:.0f} "
          f"reconciled={summary['reconciles']}; showcase {len(ids)}: {', '.join(ids)}")
    print(f"counterfactual: history took best option in {cf['history_took_best_option']}/{cf['requests_compared']}; "
          f"request AOG h actual {cf['actual_request_aog_h']:.0f} vs best {cf['best_option_request_aog_h']:.0f}; "
          f"net exposure saving AED {cf['net_exposure_saving_aed']:,.0f}")
    print(f"actions: {len(df)} exceptions {counts['by_severity']} {counts['by_type']}")
    print(f"done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
