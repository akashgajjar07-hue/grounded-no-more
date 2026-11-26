"""Monash .tsf parsing (fast, synthetic file) and the real Car Parts run (slow)."""
import numpy as np
import pytest

from gnm.forecasting import monash

TSF = """# synthetic test file
@relation Test
@attribute series_name string
@attribute start_timestamp date
@frequency monthly
@missing true
@equallength false
@data
T1:1998-01-01 00-00-00:0,1,0,2
T2:1998-01-01 00-00-00:3,?,0
"""


def test_parse_tsf(tmp_path):
    p = tmp_path / "x.tsf"
    p.write_text(TSF)
    meta, df = monash.parse_tsf(p)
    assert meta["frequency"] == "monthly" and meta["attributes"] == ["series_name", "start_timestamp"]
    assert list(df["series_name"]) == ["T1", "T2"]
    np.testing.assert_array_equal(df.loc[0, "values"], [0, 1, 0, 2])
    assert np.isnan(df.loc[1, "values"][1])


def test_evaluate_series_shapes():
    y = np.r_[np.tile([0, 0, 2, 0, 1], 8), np.zeros(12)]
    rows = monash.evaluate_series(y.astype(float), methods=["zero", "croston"])
    assert [r["method"] for r in rows] == ["zero", "croston"]
    assert rows[0]["mae"] == 0.0


@pytest.mark.slow
def test_car_parts_benchmark_runs():
    tsf = monash.RAW_DIR / "car_parts_dataset_without_missing_values.tsf"
    if not tsf.exists():
        pytest.skip("Car Parts data not downloaded")
    long, summ, info = monash.run_benchmark(tsf, limit=100)
    assert info["length_min"] == 51
    assert set(summ["method"]) == set(monash.BENCH_METHODS)
    assert np.isfinite(summ["mase"]).all()
