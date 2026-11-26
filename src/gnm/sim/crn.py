"""Counter-based common random numbers (no truth): per-request U(0,1) streams that are slice-consistent
and identical across policies. Shared by the generator and the engine (fallback)."""
from __future__ import annotations

import numpy as np

N_REQUEST_U = 7   # exchange/loan avail, exchange/loan response, borrow/robbery avail, borrow/robbery response,
                  # local-buy avail, local-buy response, fitting time
_SALT = 15


def request_uniforms(seed: int, request_ids, k: int = N_REQUEST_U) -> np.ndarray:
    """U(0,1) per (seed, request_id, j) via splitmix64."""
    ids = np.asarray(request_ids, dtype=np.uint64)
    out = np.empty((len(ids), k))
    with np.errstate(over="ignore"):
        for j in range(k):
            z = ids * np.uint64(0x9E3779B97F4A7C15) + np.uint64((int(seed) * 1_000_003 + j * 7_919 + _SALT) % 2**63)
            z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
            z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
            z = z ^ (z >> np.uint64(31))
            out[:, j] = (z >> np.uint64(11)).astype(np.float64) / float(2**53)
    return out
