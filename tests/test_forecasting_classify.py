"""ADI / CV^2 (Syntetos-Boylan) and ABC classification against hand-computed fixtures."""
import math

import numpy as np
import pandas as pd
import pytest

from gnm.forecasting.classify import abc_from_values, adi_cv2, classify_demand, sb_class

# Each fixture: (series, ADI, CV^2, n_nonzero, class). Arithmetic in comments.
FIXTURES = {
    # all periods non-zero -> intervals all 1 -> ADI 1; sizes 2,3,.. mean 2.5, std 0.5 -> CV^2 = (0.5/2.5)^2 = 0.04
    "smooth": ([2, 3, 2, 3, 2, 3, 2, 3], 1.0, 0.04, 8, "smooth"),
    # ADI 1; sizes 1,9,.. mean 5, std 4 -> CV^2 = (4/5)^2 = 0.64
    "erratic": ([1, 9, 1, 9, 1, 9], 1.0, 0.64, 6, "erratic"),
    # non-zero at 2,5,8,11 -> diffs 3,3,3 -> ADI 3; sizes all 4 -> CV^2 0
    "intermittent": ([0, 0, 4, 0, 0, 4, 0, 0, 4, 0, 0, 4], 3.0, 0.0, 4, "intermittent"),
    # non-zero at 1,4,7,10 -> ADI 3; sizes 1,9,1,9 -> CV^2 0.64
    "lumpy": ([0, 1, 0, 0, 9, 0, 0, 1, 0, 0, 9], 3.0, 0.64, 4, "lumpy"),
    # 2 non-zero (< 3) -> insufficient; ADI = 6-2 = 4; sizes 5,3 mean 4 std 1 -> CV^2 1/16
    "insufficient": ([0, 0, 5, 0, 0, 0, 3, 0], 4.0, 0.0625, 2, "insufficient_data"),
}


@pytest.mark.parametrize("name", list(FIXTURES))
def test_adi_cv2_hand_fixtures(name):
    y, adi, cv2, n, cls = FIXTURES[name]
    a, c, k = adi_cv2(y)
    assert a == pytest.approx(adi) and c == pytest.approx(cv2) and k == n
    assert sb_class(a, c, k) == cls


def test_all_zero_and_single_demand_are_insufficient():
    a, c, k = adi_cv2([0, 0, 0])
    assert math.isnan(a) and math.isnan(c) and k == 0
    assert sb_class(a, c, k) == "insufficient_data"
    assert sb_class(*adi_cv2([0, 7, 0])) == "insufficient_data"


def test_cutoffs_are_inclusive_on_the_intermittent_side():
    assert sb_class(1.32, 0.0, 10) == "intermittent"
    assert sb_class(1.3199, 0.49, 10) == "erratic"
    assert sb_class(1.32, 0.49, 10) == "lumpy"


def test_classify_uses_training_window_only():
    weeks = list(range(0, 16))
    base = [2, 3, 2, 3, 2, 3, 2, 3]  # smooth over weeks 0..7
    df = pd.DataFrame([base + [0] * 8], index=["P1"], columns=weeks)
    out1 = classify_demand(df, train_weeks=(0, 7))
    df2 = df.copy()
    df2.loc["P1", list(range(8, 16))] = [0, 0, 50, 0, 0, 0, 0, 90]  # future turns lumpy
    out2 = classify_demand(df2, train_weeks=(0, 7))
    pd.testing.assert_frame_equal(out1, out2)
    assert out1.loc["P1", "demand_class"] == "smooth"


def test_abc_hand_fixture():
    # total 1000. Cum share BEFORE each part: a 0 -> A, b .80 -> B, c .90 -> B, d .96 -> C, e .99 -> C
    v = pd.Series({"a": 800.0, "b": 100.0, "c": 60.0, "d": 30.0, "e": 10.0, "z": 0.0})
    assert abc_from_values(v).to_dict() == {"a": "A", "b": "B", "c": "B", "d": "C", "e": "C", "z": "C"}


def test_abc_crossing_part_is_A():
    # 50 (before 0) A, 40 (before .5) A, 10 (before .9) B
    v = pd.Series({"x": 50.0, "y": 40.0, "w": 10.0})
    assert abc_from_values(v).to_dict() == {"x": "A", "y": "A", "w": "B"}
