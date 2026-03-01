"""Fatigue analysis service using welib.

Provides damage equivalent load (DEL) computation and rainflow cycle
counting based on welib's fatigue tools.

All functions are synchronous (CPU-bound) and should be called via
asyncio.loop.run_in_executor() from async handlers.

Key welib functions used:
  - welib.tools.fatigue.equivalent_load(time, signal, m, Teq, ..., outputMore)
  - welib.tools.fatigue.rainflow_windap (internal rainflow counting)
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from welib.tools.fatigue import equivalent_load

logger = logging.getLogger("windforge.fatigue")


# ---------------------------------------------------------------------------
# 1. Equivalent load (DEL) computation
# ---------------------------------------------------------------------------
def compute_equivalent_load(
    time: np.ndarray | list[float],
    signal: np.ndarray | list[float],
    m_exponents: list[int] | None = None,
    Teq: float = 600.0,
) -> dict:
    """Compute damage equivalent loads for one or more Woehler exponents.

    welib signature:
      equivalent_load(time, signal, m=3, Teq=1, bins=100,
                      method='rainflow_windap', meanBin=True,
                      binStartAt0=False, outputMore=False, debug=False)
      Returns: float (DEL) when outputMore=False

    Parameters
    ----------
    time : array-like
        Time vector (s).
    signal : array-like
        Load signal (same length as time).
    m_exponents : list[int], optional
        Woehler exponents to evaluate. Default [3, 4, 10, 12].
    Teq : float
        Equivalent period (s). Default 600 (10 min).

    Returns
    -------
    dict with keys: m_exponents, del_values, Teq
    """
    if m_exponents is None:
        m_exponents = [3, 4, 10, 12]

    time_arr = np.asarray(time, dtype=float)
    signal_arr = np.asarray(signal, dtype=float)

    del_values: list[float] = []
    for m in m_exponents:
        try:
            del_val = equivalent_load(time_arr, signal_arr, m=m, Teq=Teq)
            del_values.append(float(del_val))
        except Exception as exc:
            logger.warning("equivalent_load failed for m=%d: %s", m, exc)
            del_values.append(0.0)

    return {
        "m_exponents": m_exponents,
        "del_values": del_values,
        "Teq": Teq,
    }


# ---------------------------------------------------------------------------
# 2. Rainflow cycle counting
# ---------------------------------------------------------------------------
def compute_rainflow_cycles(
    time: np.ndarray | list[float],
    signal: np.ndarray | list[float],
) -> dict:
    """Compute rainflow cycle counts using welib's equivalent_load with outputMore=True.

    welib returns (DEL, ranges, cycles, bins, ranges_mid) when outputMore=True.

    Parameters
    ----------
    time : array-like
        Time vector (s).
    signal : array-like
        Load signal (same length as time).

    Returns
    -------
    dict with keys: ranges, counts, bins, del_m3
    """
    time_arr = np.asarray(time, dtype=float)
    signal_arr = np.asarray(signal, dtype=float)

    DEL, ranges, cycles, bins, ranges_mid = equivalent_load(
        time_arr, signal_arr, m=3, Teq=1.0, outputMore=True,
    )

    # Filter out zero-count bins for a cleaner response
    mask = cycles > 0
    return {
        "ranges": ranges[mask].tolist(),
        "counts": cycles[mask].tolist(),
        "bins": bins.tolist(),
        "del_m3": float(DEL),
    }


# ---------------------------------------------------------------------------
# Helper: load time series from simulation output file
# ---------------------------------------------------------------------------
def load_time_series_from_file(
    file_path: str,
    channel: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Load a time series channel from an OpenFAST output file (.out / .outb).

    Uses welib's FASTOutputFile reader if available, otherwise falls back to
    numpy column parsing.

    Parameters
    ----------
    file_path : str
        Path to the OpenFAST output file.
    channel : str
        Channel name to extract (e.g. 'TwrBsMyt', 'RootMxc1').

    Returns
    -------
    (time, signal) as numpy arrays.

    Raises
    ------
    FileNotFoundError
        If the output file does not exist.
    ValueError
        If the channel is not found in the file.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Output file not found: {file_path}")

    try:
        from welib.weio import FASTOutputFile
        f = FASTOutputFile(str(path))
        df = f.toDataFrame()
    except ImportError:
        # Fallback: try weio as standalone
        try:
            import weio
            f = weio.read(str(path))
            df = f.toDataFrame()
        except ImportError:
            raise ImportError(
                "Neither welib.weio nor weio is available for reading OpenFAST output files."
            )

    # Find the channel (case-insensitive, with or without units suffix)
    col_map = {c.split("_")[0].lower(): c for c in df.columns}
    channel_lower = channel.lower()

    matched_col = None
    for col in df.columns:
        col_base = col.split("_")[0].strip().lower()
        if col_base == channel_lower:
            matched_col = col
            break

    if matched_col is None:
        # Try partial match
        for col in df.columns:
            if channel_lower in col.lower():
                matched_col = col
                break

    if matched_col is None:
        available = [c.split("_")[0].strip() for c in df.columns[:20]]
        raise ValueError(
            f"Channel '{channel}' not found. Available channels (first 20): {available}"
        )

    # First column is typically Time
    time_col = df.columns[0]
    time_arr = df[time_col].values.astype(float)
    signal_arr = df[matched_col].values.astype(float)

    return time_arr, signal_arr
