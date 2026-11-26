"""REAL benchmark: Monash Time Series Forecasting Archive, "Car Parts" (monthly).

Source: Zenodo record 4656021, "Car Parts Dataset (without Missing Values)",
licence CC BY 4.0 (checked via the Zenodo records API at download time). 2674 monthly
series, Jan 1998 - Mar 2002 (51 months). Godahewa et al. (2021), Monash Time Series
Forecasting Archive; original data: Hyndman (2015) R package expsmooth.

Setup: horizon 12, last 12 months = test, first 39 months = training. Missing values:
the archive's "without missing values" version, in which the maintainers replaced the
original missing values with zeros; we use it as published and do not impute further
(missing and genuine zero demand are therefore indistinguishable). MASE uses
seasonality m = 1 (one-step naive scaling) as the primary scale; m = 12 is reported as
a secondary column. Series whose training scale is 0 (constant, e.g. all-zero training
months) get MASE = NaN, status "undefined", and are excluded from MASE means.

Only DERIVED metrics are written to outputs/forecasting/; the raw .zip/.tsf stays in
data/raw/monash/ (gitignored).
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from gnm.forecasting import metrics as M
from gnm.forecasting.classify import adi_cv2, sb_class
from gnm.forecasting.methods import METHODS

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw" / "monash"
OUT_DIR = ROOT / "outputs" / "forecasting"
MANIFEST = ROOT / "data" / "source_manifest.csv"
RECORD_ID = "4656021"
RECORD_URL = f"https://zenodo.org/records/{RECORD_ID}"
API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
ZIP_NAME = "car_parts_dataset_without_missing_values.zip"
FILE_URL = f"https://zenodo.org/records/{RECORD_ID}/files/{ZIP_NAME}"
MANIFEST_COLS = ["source_id", "name", "url", "licence", "version_or_date", "download_date", "sha256",
                 "used_for", "provenance", "notes"]
HORIZON = 12
BENCH_METHODS = ["zero", "naive", "ma", "croston", "sba", "tsb", "adida", "imapa", "bootstrap"]
QUANTILES = (0.5, 0.9, 0.95)
# Published archive results, fetched from https://forecastingdata.org/ (Results table,
# "mean MASE") on 2026-11-26. The page does not state the MASE seasonality, so these are
# context only and not strictly comparable with our m=1 primary MASE.
PUBLISHED_REFERENCE = {
    "url": "https://forecastingdata.org/", "fetched": "2026-11-26", "metric": "mean MASE",
    "note": "MASE seasonality not stated on the page; context only, not a like-for-like comparison",
    "values": {"SES": 0.897, "Theta": 0.914, "TBATS": 0.998, "ETS": 0.925, "(DHR-)ARIMA": 0.926,
               "PR": 0.755, "CatBoost": 0.853, "FFNN": 0.747, "DeepAR": 0.747, "N-BEATS": 2.836,
               "WaveNet": 0.754, "Transformer": 0.746},
}
ATTRIBUTION = ("Car Parts dataset, Monash Time Series Forecasting Archive (Godahewa, Bergmeir, Webb, "
               "Hyndman & Montero-Manso, 2021), Zenodo record 4656021, licensed CC BY 4.0; original "
               "data from Hyndman (2015), R package expsmooth.")


# --------------------------------------------------------------------------- tsf parsing
def parse_tsf(path) -> tuple[dict, pd.DataFrame]:
    """Minimal .tsf reader: returns (metadata, frame[series_name, start_timestamp, values]).

    '@attribute' lines define the colon-separated fields that precede the values;
    '?' marks a missing value (-> NaN).
    """
    meta, attrs, rows = {"attributes": []}, [], []
    in_data = False
    with open(path, encoding="latin-1") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if not in_data:
                if line.lower().startswith("@attribute"):
                    _, name, typ = line.split()[:3]
                    attrs.append((name, typ))
                    meta["attributes"].append(name)
                elif line.lower().startswith("@data"):
                    in_data = True
                elif line.startswith("@"):
                    k, *v = line[1:].split(maxsplit=1)
                    meta[k.lower()] = v[0] if v else ""
                continue
            parts = line.split(":")
            fields = parts[:len(attrs)]
            values = ":".join(parts[len(attrs):])
            vals = np.array([np.nan if v.strip() == "?" else float(v) for v in values.split(",")])
            rec = {name: fv for (name, _), fv in zip(attrs, fields)}
            rec["values"] = vals
            rows.append(rec)
    return meta, pd.DataFrame(rows)


# --------------------------------------------------------------------------- download + manifest
def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fetch_record_metadata(timeout: float = 30) -> dict:
    req = urllib.request.Request(API_URL, headers={"User-Agent": "gnm-forecasting/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    md = d.get("metadata", {})
    lic = md.get("license", {})
    return {"title": md.get("title"), "licence": lic.get("id") if isinstance(lic, dict) else lic,
            "version": md.get("version"), "publication_date": md.get("publication_date"),
            "doi": d.get("doi"), "files": [(f["key"], f.get("checksum")) for f in d.get("files", [])]}


def download(force: bool = False) -> dict:
    """Verify licence via the Zenodo API, download the zip, extract the .tsf."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    meta = fetch_record_metadata()
    if str(meta["licence"]).lower() != "cc-by-4.0":
        raise RuntimeError(f"unexpected licence {meta['licence']!r}")
    zp = RAW_DIR / ZIP_NAME
    if force or not zp.exists():
        req = urllib.request.Request(FILE_URL + "?download=1", headers={"User-Agent": "gnm-forecasting/0.1"})
        with urllib.request.urlopen(req, timeout=120) as r:
            zp.write_bytes(r.read())
    md5_expected = dict(meta["files"]).get(ZIP_NAME)
    if md5_expected and md5_expected.startswith("md5:"):
        if hashlib.md5(zp.read_bytes()).hexdigest() != md5_expected[4:]:
            raise RuntimeError("md5 mismatch against Zenodo checksum")
    with zipfile.ZipFile(zp) as z:
        names = [n for n in z.namelist() if n.endswith(".tsf") and "/" not in n and ".." not in n]
        z.extract(names[0], RAW_DIR)
    meta.update({"zip": str(zp), "tsf": str(RAW_DIR / names[0]), "sha256": _sha256(zp),
                 "download_date": dt.date.fromtimestamp(zp.stat().st_mtime).isoformat()})
    return meta


def append_manifest(meta: dict, path: Path = MANIFEST) -> None:
    """Append (or keep) the manifest rows; existing rows from other agents are preserved."""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if path.exists():
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
    new = [
        {"source_id": "monash_car_parts", "name": meta.get("title") or "Car Parts Dataset (without Missing Values)",
         "url": FILE_URL, "licence": "CC BY 4.0",
         "version_or_date": f"Zenodo v{meta.get('version')} ({meta.get('publication_date')}), doi {meta.get('doi')}",
         "download_date": meta.get("download_date", ""), "sha256": meta.get("sha256", ""),
         "used_for": "Forecasting benchmark (MASE etc.) of intermittent-demand methods",
         "provenance": "REAL",
         "notes": f"Record page {RECORD_URL}; raw zip in data/raw/monash/ (gitignored); "
                  "missing values replaced by zeros by the archive maintainers"},
        {"source_id": "monash_car_parts_metrics", "name": "Car Parts benchmark metrics (derived)",
         "url": RECORD_URL, "licence": "CC BY 4.0 (derived from)", "version_or_date": meta.get("download_date", ""),
         "download_date": meta.get("download_date", ""), "sha256": "",
         "used_for": "outputs/forecasting/monash_benchmark.json/.csv", "provenance": "DERIVED",
         "notes": "Computed by gnm.forecasting.monash; contains no raw series"},
    ]
    ids = {r["source_id"] for r in new}
    rows = [r for r in rows if r.get("source_id") not in ids] + new
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in MANIFEST_COLS})


# --------------------------------------------------------------------------- benchmark
def evaluate_series(y: np.ndarray, methods=BENCH_METHODS, horizon: int = HORIZON, seed: int = 0) -> list[dict]:
    y_tr, y_te = y[:-horizon], y[-horizon:]
    sc1, sc12 = M.mase_scale(y_tr, 1), M.mase_scale(y_tr, 12)
    out = []
    for m in methods:
        fc = METHODS[m](y_tr, horizon, seed=seed)
        f = fc.mean
        r1, r12 = M.mase(y_te, f, y_tr, 1), M.mase(y_te, f, y_tr, 12)
        row = {"method": m, "mae": M.mae(y_te, f), "mase": r1.value, "mase_status": r1.status,
               "mase_m12": r12.value, "bias": M.bias(y_te, f), "pis": M.pis(y_te, f),
               "spis": M.spis(y_te, f, y_tr), "scale_m1": sc1, "scale_m12": sc12}
        row.update(M.ltd_metrics(float(y_te.sum()), fc.ltd_dist(), QUANTILES))
        out.append(row)
    return out


def run_benchmark(tsf_path, methods=BENCH_METHODS, horizon: int = HORIZON, limit: int | None = None,
                  seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Returns (per-series long table, per-method summary, info)."""
    meta, df = parse_tsf(tsf_path)
    if limit:
        df = df.head(limit)
    rows, classes = [], []
    n_missing = 0
    for i, r in df.iterrows():
        y = r["values"]
        if np.isnan(y).any():          # not expected in this version; drop if present
            n_missing += 1
            continue
        adi, cv2, n = adi_cv2(y[:-horizon])
        classes.append(sb_class(adi, cv2, n))
        for row in evaluate_series(y, methods, horizon, seed=seed + i):
            row["series"] = r["series_name"]
            row["demand_class"] = classes[-1]
            rows.append(row)
    long = pd.DataFrame(rows)
    summ = summarise(long)
    mix = pd.Series(classes).value_counts().to_dict()
    lengths = df["values"].map(len)
    info = {"n_series": int(len(df)), "n_series_with_missing_dropped": n_missing,
            "length_min": int(lengths.min()), "length_max": int(lengths.max()),
            "frequency": meta.get("frequency"), "class_mix": {k: int(v) for k, v in mix.items()},
            "n_mase_undefined": int(long[long["method"] == methods[0]]["mase_status"].eq("undefined").sum())}
    return long, summ, info


def summarise(long: pd.DataFrame, n_boot: int = 1000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for m, g in long.groupby("method", sort=False):
        row = {"method": m, "n_series": int(len(g)), "n_mase_defined": int(g["mase"].notna().sum())}
        for c in ["mase", "mase_m12", "mae", "bias", "pis", "cov_q50", "cov_q90", "cov_q95",
                  "pinball_q50", "pinball_q90", "pinball_q95"]:
            v = g[c].dropna().to_numpy()
            row[c] = float(v.mean()) if v.size else float("nan")
            if c in ("mase", "mae") and v.size > 1:
                bs = v[rng.integers(0, v.size, (n_boot, v.size))].mean(axis=1)
                row[f"{c}_ci_lo"], row[f"{c}_ci_hi"] = (float(x) for x in np.percentile(bs, [2.5, 97.5]))
        row["mase_median"] = float(g["mase"].median())
        rows.append(row)
    return pd.DataFrame(rows)


def write_outputs(summ: pd.DataFrame, info: dict, meta: dict, by_class: pd.DataFrame | None = None,
                  out_dir: Path = OUT_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "ok", "provenance": "DERIVED", "data_provenance": "REAL",
        "dataset": "Monash Car Parts (without missing values)", "attribution": ATTRIBUTION,
        "source_url": RECORD_URL, "licence": "CC BY 4.0", "zip_sha256": meta.get("sha256"),
        "zenodo_version": meta.get("version"), "download_date": meta.get("download_date"),
        "setup": {"frequency": "monthly", "horizon": HORIZON, "test": "last 12 months",
                  "train_months": info.get("length_min", 51) - HORIZON,
                  "mase_seasonality": 1, "mase_m12_reported": True,
                  "missing_values": "archive version with missing replaced by zeros; used as published",
                  "mase_undefined_rule": "training naive MAE == 0 -> NaN, excluded from means",
                  "ltd_distribution": "bootstrap: empirical; other methods: Poisson(sum of point forecasts)",
                  "quantiles": list(QUANTILES)},
        "info": info,
        "published_reference": PUBLISHED_REFERENCE,
        "results": json.loads(summ.to_json(orient="records", double_precision=4)),
    }
    if by_class is not None:
        payload["mase_by_class"] = json.loads(by_class.to_json(orient="records", double_precision=4))
    jp, cp = out_dir / "monash_benchmark.json", out_dir / "monash_benchmark.csv"
    jp.write_text(json.dumps(payload, indent=2) + "\n")
    s = summ.copy()
    s.insert(0, "provenance", "DERIVED")
    s.insert(1, "data_provenance", "REAL")
    s["attribution"] = ATTRIBUTION
    s.to_csv(cp, index=False, float_format="%.4f")
    return {"json": str(jp), "csv": str(cp)}


def write_not_run(reason: str, out_dir: Path = OUT_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "monash_benchmark.json").write_text(
        json.dumps({"status": "not run", "reason": reason, "provenance": "DERIVED"}, indent=2) + "\n")


def main(limit: int | None = None) -> dict:
    try:
        meta = download()
    except Exception as exc:  # network / licence failure is not a blocker
        write_not_run(f"download or licence check failed: {exc}")
        return {"status": "not run", "reason": str(exc)}
    append_manifest(meta)
    long, summ, info = run_benchmark(meta["tsf"], limit=limit)
    by_class = long.groupby(["demand_class", "method"]).agg(
        n=("series", "nunique"), mase=("mase", "mean")).reset_index()
    paths = write_outputs(summ, info, meta, by_class)
    return {"status": "ok", "summary": summ, "info": info, **paths}


if __name__ == "__main__":
    res = main()
    if res["status"] == "ok":
        pd.set_option("display.width", 200)
        print(res["summary"].round(4).to_string(index=False))
        print(json.dumps(res["info"], indent=2))
    else:
        print(res)
