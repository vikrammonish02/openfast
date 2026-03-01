"""Mode shape analysis service using welib beam functions.

Wraps welib's cantilever beam routines for computing mode shapes and
static deflections of tower and blade components.

All functions are synchronous (CPU-bound) and should be called via
asyncio.loop.run_in_executor() from async handlers.

Key welib functions used:
  - welib.beams.cantilever1d.compute_modes(n_modes, r, EI, m)
      Returns (freqs_hz, mode_shapes) where freqs_hz is 1-D array of
      length n_modes and mode_shapes is (n_modes, n_stations) array.
  - welib.beams.cantilever2d.compute_modes(n_modes, r, EI1, EI2, m, beta)
      Returns (freqs_hz_list, modes_list) where each mode is a tuple
      (shape_dir1, shape_dir2), both 1-D arrays of length n_stations.
  - welib.beams.cantilever1d.deflection(p, z, EI, Ftip=, Mtip=)
      Returns (u, theta, kappa, S, M) tuple of arrays.
"""

from __future__ import annotations

import logging
import math

import numpy as np

# numpy compat: welib may use np.trapezoid (numpy >= 2.0) which is absent
# in numpy 1.x where the function is called np.trapz.
if not hasattr(np, "trapezoid"):
    np.trapezoid = np.trapz  # type: ignore[attr-defined]

from welib.beams.cantilever1d import compute_modes as _compute_modes_1d
from welib.beams.cantilever1d import deflection as _deflection_1d
from welib.beams.cantilever2d import compute_modes as _compute_modes_2d

logger = logging.getLogger("windforge.modeshape")


# ---------------------------------------------------------------------------
# Tower mode shapes (1-D cantilever)
# ---------------------------------------------------------------------------
def compute_tower_mode_shapes(
    stations: list[dict],
    tower_height: float,
    tip_mass: float = 0.0,
    n_modes: int = 5,
) -> dict:
    """Compute tower mode shapes using welib cantilever1d.compute_modes.

    Parameters
    ----------
    stations : list[dict]
        Tower station data with keys: frac, mass_den, fa_stiff.
    tower_height : float
        Tower height in metres.
    tip_mass : float
        Lumped mass at tower top (RNA mass) in kg.  Added to the last
        station's mass density as a point-mass approximation.
    n_modes : int
        Number of modes to compute.

    Returns
    -------
    dict with keys:
        span_positions : list[float] — fractional span positions
        modes : list[dict] — each with frequency, label, shape_values
    """
    if not stations or len(stations) < 2:
        return {"span_positions": [], "modes": []}

    sorted_st = sorted(stations, key=lambda s: s["frac"])
    z = np.array([s["frac"] * tower_height for s in sorted_st])
    EI = np.array([s["fa_stiff"] for s in sorted_st])
    m = np.array([s["mass_den"] for s in sorted_st])

    # Apply tip mass as lumped mass on last station
    if tip_mass > 0 and len(z) >= 2:
        dz_last = z[-1] - z[-2]
        if dz_last > 0:
            m = m.copy()
            m[-1] += tip_mass / dz_last

    n_modes = min(n_modes, len(z) - 1)

    # welib cantilever1d.compute_modes:
    #   signature: (n_modes, r, EI, m, maxiter=500, abs_tol=0.01, method='cumtrapz')
    #   returns: (freqs_hz, mode_shapes) — 1-D(n_modes,) and 2-D(n_modes, n_stations)
    freqs, shapes = _compute_modes_1d(n_modes, z, EI, m)

    span_positions = [float(s["frac"]) for s in sorted_st]
    modes = []
    for i in range(len(freqs)):
        modes.append({
            "frequency": float(freqs[i]),
            "label": f"Tower FA Mode {i + 1}",
            "shape_values": shapes[i].tolist(),
        })

    return {"span_positions": span_positions, "modes": modes}


# ---------------------------------------------------------------------------
# Blade mode shapes (2-D coupled cantilever)
# ---------------------------------------------------------------------------
def compute_blade_mode_shapes(
    structural_stations: list[dict],
    blade_length: float,
    n_modes: int = 5,
) -> dict:
    """Compute blade mode shapes using welib cantilever2d.compute_modes.

    Parameters
    ----------
    structural_stations : list[dict]
        Blade station data with keys: frac, mass_den, flap_stiff,
        edge_stiff, struct_twist.
    blade_length : float
        Blade span in metres.
    n_modes : int
        Number of modes to compute.

    Returns
    -------
    dict with keys:
        span_positions : list[float] — fractional span positions
        modes : list[dict] — each with frequency, label, flap_shape, edge_shape
    """
    if not structural_stations or len(structural_stations) < 2:
        return {"span_positions": [], "modes": []}

    sorted_st = sorted(structural_stations, key=lambda s: s["frac"])
    r = np.array([s["frac"] * blade_length for s in sorted_st])
    EI_flap = np.array([s["flap_stiff"] for s in sorted_st])
    EI_edge = np.array([s.get("edge_stiff", s["flap_stiff"]) for s in sorted_st])
    m = np.array([s["mass_den"] for s in sorted_st])
    beta = np.array([
        math.radians(s.get("struct_twist", 0.0)) for s in sorted_st
    ])

    n_modes = min(n_modes, len(r) - 1)

    # welib cantilever2d.compute_modes:
    #   signature: (n_modes, r, EI1, EI2, m, beta, maxiter=500, abs_tol=0.01)
    #   returns: (freqs_list, modes_list)
    #     freqs_list: list of n_modes floats (Hz)
    #     modes_list: list of n_modes tuples (shape_dir1, shape_dir2)
    freqs, mode_shapes = _compute_modes_2d(n_modes, r, EI_flap, EI_edge, m, beta)

    span_positions = [float(s["frac"]) for s in sorted_st]
    modes = []
    for i in range(len(freqs)):
        flap_shape, edge_shape = mode_shapes[i]
        modes.append({
            "frequency": float(freqs[i]),
            "label": f"Blade Mode {i + 1}",
            "flap_shape": flap_shape.tolist(),
            "edge_shape": edge_shape.tolist(),
        })

    return {"span_positions": span_positions, "modes": modes}


# ---------------------------------------------------------------------------
# Static deflection (1-D cantilever)
# ---------------------------------------------------------------------------
def compute_static_deflection(
    stations: list[dict],
    length: float,
    tip_load: float = 0.0,
    distributed_load: float = 0.0,
) -> dict:
    """Compute static deflection using welib cantilever1d.deflection.

    Parameters
    ----------
    stations : list[dict]
        Station data with keys: frac, fa_stiff (or flap_stiff).
    length : float
        Component length in metres.
    tip_load : float
        Point force at tip in N.
    distributed_load : float
        Uniform distributed load in N/m.

    Returns
    -------
    dict with keys:
        span_positions : list[float] — fractional span positions
        deflection : list[float] — deflection values in metres
    """
    if not stations or len(stations) < 2:
        return {"span_positions": [], "deflection": []}

    sorted_st = sorted(stations, key=lambda s: s["frac"])
    z = np.array([s["frac"] * length for s in sorted_st])

    # Accept either tower (fa_stiff) or blade (flap_stiff) station format
    EI = np.array([
        s.get("fa_stiff", s.get("flap_stiff", 0.0)) for s in sorted_st
    ])

    # Distributed load array (uniform)
    p = np.full(len(z), distributed_load, dtype=float)

    # welib cantilever1d.deflection:
    #   signature: (p, z, EI, method='cumtrapz', Ftip=0, Mtip=0)
    #   returns: (u, theta, kappa, S, M)
    #     u     — deflection array (metres)
    #     theta — slope array (rad)
    #     kappa — curvature array (1/m)
    #     S     — shear force array (N)
    #     M     — bending moment array (N m)
    u, theta, kappa, S, M = _deflection_1d(p, z, EI, Ftip=tip_load)

    span_positions = [float(s["frac"]) for s in sorted_st]

    return {
        "span_positions": span_positions,
        "deflection": u.tolist(),
    }
