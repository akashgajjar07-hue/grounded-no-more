"""JS float calculator must match Python analytic module exactly."""
import json
import shutil
import subprocess

import pytest

from gnm.config import ROOT
from gnm.policy import analytic as A

CASES = [(2, 30, 2, 100000), (0.5, 60, 1, 250000), (6, 45, 9, 40000), (1.3, 15, 0, 15000), (3.7, 90, 14, 480000)]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_mirror_matches_python():
    js = f"""
    import {{ floatCalc, compareLevers }} from '{(ROOT / 'docs/js/lib/floatcalc.js').as_uri()}';
    const cases = {json.dumps(CASES)};
    console.log(JSON.stringify({{
      calc: cases.map(c => floatCalc(...c)),
      levers: cases.map(c => compareLevers(...c, 10, 1, 400)),
    }}));
    """
    out = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, check=True)
    res = json.loads(out.stdout)
    for c, js_r in zip(CASES, res["calc"]):
        py = A.float_calc(*c)
        for k, v in py.items():
            assert js_r[k] == pytest.approx(v, rel=1e-9, abs=1e-12), (c, k)
    for c, js_r in zip(CASES, res["levers"]):
        py = A.compare_levers(*c, 10, 1, 400)
        for lever in ["base", "extra_spares", "tat_cut"]:
            for k, v in py[lever].items():
                assert js_r[lever][k] == pytest.approx(v, rel=1e-9, abs=1e-12), (c, lever, k)
