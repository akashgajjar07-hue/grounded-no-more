import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = "/Users/akashgajjar/grounded-no-more"

HEADER = ("> **Independent educational simulation. Not an airline system or an approved maintenance, airworthiness or "
          "dispatch tool.** Falcon Hub Airways is fictional and every airline number below is SIMULATED by this repo's "
          "code: a simulated planning snapshot, not operator data. Provenance tags: **REAL** (public data), "
          "**DERIVED** (computed by code), **ASSUMED** (a config planning assumption), **SIMULATED** (simulator output).")

SETUP = '''import sys, json
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))            # notebooks/_style.py
import numpy as np, pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
from _style import *                            # palette, ROOT, stamp(), aed_m(), load_json(), ci()
sys.path.insert(0, str(ROOT / "src"))
pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
print("project root:", ROOT)'''


def build(path, cells):
    nb = new_notebook()
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb.metadata["language_info"] = {"name": "python"}
    for kind, src in cells:
        nb.cells.append(new_markdown_cell(src.strip("\n")) if kind == "md" else new_code_cell(src.strip("\n")))
    nbformat.write(nb, path)
