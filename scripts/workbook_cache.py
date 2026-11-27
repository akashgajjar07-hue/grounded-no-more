"""Write cached values into every formula cell of a saved .xlsx (v2.2).

openpyxl saves formulas without results, so previews that do not recalculate (Mac Quick Look, Google
Drive/Gmail previews, phones) show blank cells. This step evaluates the workbook with the pure-Python
`formulas` engine and fills each formula cell's cached `<v>` value in the sheet XML. The formulas
themselves are unchanged, and Excel still recalculates on open (`fullCalcOnLoad`).

`SUBTOTAL(9, range)` is not supported by the engine; with no rows filtered it equals SUM(range), so it
is computed from the evaluated range.

Usage:  python scripts/workbook_cache.py <file.xlsx> [--check]
        --check: verify only (every formula cell has a cached value; no Excel error values)
"""
from __future__ import annotations

import argparse
import html
import math
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ERRORS = ("#REF!", "#DIV/0!", "#VALUE!", "#N/A", "#NAME?", "#NUM!", "#NULL!")
CELL_F = re.compile(r'<c r="([A-Z]+)(\d+)"([^>]*)><f>(.*?)</f><v></v></c>', re.S)
SUBTOTAL9 = re.compile(r"^SUBTOTAL\(9,([A-Z]+)(\d+):([A-Z]+)(\d+)\)$")


def _col_num(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def _col_name(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _scalar(v):
    try:
        v = v.value[0, 0]
    except Exception:  # noqa: BLE001
        pass
    if hasattr(v, "item"):
        v = v.item()
    return v


def evaluate(path: Path) -> dict[tuple[str, str], object]:
    import formulas
    sol = formulas.ExcelModel().loads(str(path)).finish().calculate()
    out = {}
    for k, v in sol.items():
        ref = k.split("]")[-1]
        if "!" not in ref or ":" in ref.split("!")[1]:
            continue
        sheet, cell = ref.rsplit("!", 1)
        out[(sheet.strip("'").upper(), cell.replace("$", "").upper())] = _scalar(v)
    return out


def _sheet_files(z: zipfile.ZipFile) -> dict[str, str]:
    wbx = z.read("xl/workbook.xml").decode()
    rels = z.read("xl/_rels/workbook.xml.rels").decode()
    rid_target = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels)) | {
        a: b for b, a in re.findall(r'Target="([^"]+)"[^>]*Id="(rId\d+)"', rels)}
    out = {}
    for name, rid in re.findall(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="(rId\d+)"', wbx):
        t = rid_target[rid].lstrip("/")
        out[html.unescape(name)] = t if t.startswith("xl/") else f"xl/{t}"
    return out


def _v(value) -> tuple[str, str] | None:
    """(t-attribute or '', <v> text) for a cached value; None if there is nothing to cache."""
    if value is None:
        return None
    s = str(value)
    if s in ERRORS or type(value).__name__ == "XlError":
        return ("e", html.escape(s))
    if isinstance(value, bool):
        return ("b", "1" if value else "0")
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return ("e", "#NUM!")
        return ("", repr(float(value)) if isinstance(value, float) else str(value))
    if s == "empty":
        return ("", "0")
    return ("str", html.escape(s, quote=False))


def cache(path: Path) -> dict:
    vals = evaluate(path)
    stats = {"filled": 0, "missing": [], "errors": []}
    with zipfile.ZipFile(path) as z:
        files = _sheet_files(z)
        names = z.namelist()
        payload = {n: z.read(n) for n in names}
    for sheet, f in files.items():
        xml = payload[f].decode("utf-8")
        key = sheet.upper()

        def repl(m):
            col, row, attrs, formula = m.group(1), m.group(2), m.group(3), m.group(4)
            ftxt = html.unescape(formula)
            value = vals.get((key, f"{col}{row}"))
            st = SUBTOTAL9.match(ftxt)
            if st:
                c0, r0, c1, r1 = _col_num(st[1]), int(st[2]), _col_num(st[3]), int(st[4])
                total = 0.0
                for cc in range(c0, c1 + 1):
                    for rr in range(r0, r1 + 1):
                        x = vals.get((key, f"{_col_name(cc)}{rr}"))
                        if isinstance(x, (int, float)) and not isinstance(x, bool):
                            total += x
                value = total
            cv = _v(value)
            if cv is None:
                stats["missing"].append(f"{sheet}!{col}{row}")
                return m.group(0)
            t, text = cv
            if t == "e":
                stats["errors"].append(f"{sheet}!{col}{row} {text}")
            attrs = re.sub(r'\s+t="[^"]*"', "", attrs) + (f' t="{t}"' if t else "")
            stats["filled"] += 1
            return f'<c r="{col}{row}"{attrs}><f>{formula}</f><v>{text}</v></c>'

        payload[f] = CELL_F.sub(repl, xml).encode("utf-8")
    tmp = Path(tempfile.mkstemp(suffix=".xlsx", dir=path.parent)[1])
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in names:
            zo.writestr(n, payload[n])
    shutil.move(tmp, path)
    return stats


def check(path: Path) -> list[str]:
    """Problems: formula cells without a cached value, or with an Excel error value."""
    import openpyxl
    wf = openpyxl.load_workbook(path)
    wv = openpyxl.load_workbook(path, data_only=True)
    bad = []
    for ws in wf.worksheets:
        vs = wv[ws.title]
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    v = vs[c.coordinate].value
                    if v is None or (isinstance(v, str) and v in ERRORS):
                        bad.append(f"{ws.title}!{c.coordinate}={v!r}")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("xlsx", type=Path)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not a.check:
        s = cache(a.xlsx)
        print(f"cached {s['filled']} formula cells; missing {len(s['missing'])}; errors {len(s['errors'])}")
    bad = check(a.xlsx)
    print("check:", "OK" if not bad else f"{len(bad)} problems, e.g. {bad[:5]}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
