# Third-party licences

GROUNDED NO MORE is released under the [MIT licence](LICENSE). It depends on the third-party components below, each under its own licence. Front-end assets (fonts, vendored JavaScript, map data) are listed by the design-system maintainer in their own section of this file.

## Python packages

Versions as pinned in [`requirements.txt`](requirements.txt). Licences checked from installed package metadata (`importlib.metadata` / `pip show`) on 2026-11-26.

| Package | Version | Licence | Use in this project |
|---|---|---|---|
| numpy | 2.5.5 | BSD-3-Clause (bundled parts: 0BSD, MIT, Zlib, CC0-1.0) | Arrays, random number generation |
| pandas | 2.3.3 | BSD-3-Clause | Tables |
| scipy | 1.18.1 | BSD-3-Clause | Distributions (Poisson, negative binomial), statistics |
| pyarrow | 26.0.1 | Apache-2.0 | Parquet storage |
| duckdb | 2.0.1 | MIT | Analytical SQL views over Parquet |
| PyYAML | 6.0.4 | MIT | Reading `config/assumptions.yaml` |
| statsforecast | 2.1.1 | Apache-2.0 | Croston-family forecasting methods |
| openpyxl | 3.1.5 | MIT | Excel workbook output |
| python-pptx | 1.0.2 | MIT | Presentation output |
| matplotlib | 3.11.2 | Matplotlib licence (PSF-based, BSD-compatible) | Static charts |
| playwright | 1.65.2 | Apache-2.0 | Browser tests and screenshots of the web app |
| pytest | 9.2.0 | MIT | Test suite |

Development-only tools listed in `requirements.txt` (pytest-xdist, nbconvert, jupyter) are not redistributed with the web app.
