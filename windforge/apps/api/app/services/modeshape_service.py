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
from welib.beams.theory import UniformBeamBendingModes
from welib.FEM.fem_beam import cbeam

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


# ---------------------------------------------------------------------------
# Uniform beam bending modes (analytical theory)
# ---------------------------------------------------------------------------
def compute_uniform_beam_modes(
    BC_type: str = "unloaded-clamped-free",
    EI: float = 2.1e8,
    rho: float = 7850.0,
    A: float = 0.01,
    L: float = 10.0,
    n_modes: int = 4,
    Mtop: float = 0.0,
) -> dict:
    """Compute analytical mode shapes for a uniform Euler-Bernoulli beam.

    Uses welib.beams.theory.UniformBeamBendingModes.

    Parameters
    ----------
    BC_type : str
        Boundary condition string, e.g. 'unloaded-clamped-free',
        'unloaded-clamped-clamped', 'unloaded-hinged-hinged', etc.
    EI : float
        Flexural rigidity (Nm^2).
    rho : float
        Density (kg/m^3).
    A : float
        Cross-sectional area (m^2).
    L : float
        Beam length (m).
    n_modes : int
        Number of modes to compute.
    Mtop : float
        Tip mass (kg), only for 'unloaded-topmass-clamped-free'.

    Returns
    -------
    dict with keys: x, frequencies, modes (list of {label, shape_values})
    """
    try:
        freq, x, ModesU, ModesV, ModesK = UniformBeamBendingModes(
            BC_type, EI=EI, rho=rho, A=A, L=L,
            nModes=n_modes, Mtop=Mtop,
        )

        modes = []
        for i in range(len(freq)):
            modes.append({
                "frequency": float(freq[i]),
                "label": f"Mode {i + 1}",
                "shape_values": ModesU[i].tolist(),
            })

        return {
            "x": (x / L).tolist(),  # normalize to 0..1
            "frequencies": freq.tolist(),
            "modes": modes,
        }
    except Exception as exc:
        logger.warning("Uniform beam modes failed: %s", exc)
        return {
            "x": [],
            "frequencies": [],
            "modes": [],
        }


# ---------------------------------------------------------------------------
# FEM vs Theory comparison
# ---------------------------------------------------------------------------
def compare_fem_vs_theory(
    EI: float = 2.1e8,
    rho: float = 7850.0,
    A: float = 0.01,
    L: float = 10.0,
    n_modes: int = 4,
    n_elements: int = 20,
) -> dict:
    """Compare FEM and analytical beam mode shapes side by side.

    Uses welib.FEM.fem_beam.cbeam and welib.beams.theory.UniformBeamBendingModes.

    Returns
    -------
    dict with keys: x_theory, x_fem, frequencies_theory, frequencies_fem,
                    modes_theory, modes_fem
    """
    try:
        # --- Analytical ---
        freq_th, x_th, ModesU_th, _, _ = UniformBeamBendingModes(
            "unloaded-clamped-free", EI=EI, rho=rho, A=A, L=L, nModes=n_modes,
        )

        modes_theory = []
        for i in range(len(freq_th)):
            modes_theory.append({
                "frequency": float(freq_th[i]),
                "label": f"Theory Mode {i + 1}",
                "shape_values": ModesU_th[i].tolist(),
            })

        # --- FEM ---
        m_per_l = rho * A  # mass per unit length
        x_fem_nodes = np.linspace(0, L, n_elements + 1)
        m_arr = np.full(n_elements + 1, m_per_l)
        EI_arr = np.full(n_elements + 1, EI)
        EA_val = 2.1e11 * A  # approx steel E=211 GPa

        FEM = cbeam(
            x_fem_nodes, m=m_arr,
            EIx=EI_arr, EIy=EI_arr, EIz=EI_arr,
            EA=np.full(n_elements + 1, EA_val),
            element='frame3d', nel=n_elements, BC='clamped-free',
        )

        fem_freq = FEM['freq']
        Q = FEM['Q']
        x_nodes = FEM['xNodes'][0, :]  # x-coordinates of nodes

        # Extract bending modes (uy DOFs, every 6th starting at index 1)
        modes_fem = []
        n_extracted = 0
        for mode_idx in range(min(len(fem_freq), 2 * n_modes)):
            if n_extracted >= n_modes:
                break
            # Get displacement in y-direction (DOF index 1 of 6)
            mode_shape_uy = Q[1::6, mode_idx]
            # Skip torsional/axial modes (check if the mode has significant bending)
            if np.max(np.abs(mode_shape_uy)) < 1e-10:
                continue
            # Normalize to tip value
            tip_val = mode_shape_uy[-1]
            if abs(tip_val) > 1e-12:
                mode_shape_uy = mode_shape_uy / tip_val
            modes_fem.append({
                "frequency": float(fem_freq[mode_idx]),
                "label": f"FEM Mode {n_extracted + 1}",
                "shape_values": mode_shape_uy.tolist(),
            })
            n_extracted += 1

        return {
            "x_theory": (x_th / L).tolist(),
            "x_fem": (x_nodes / L).tolist(),
            "frequencies_theory": freq_th.tolist(),
            "frequencies_fem": [m["frequency"] for m in modes_fem],
            "modes_theory": modes_theory,
            "modes_fem": modes_fem,
        }
    except Exception as exc:
        logger.warning("FEM vs Theory comparison failed: %s", exc)
        return {
            "x_theory": [],
            "x_fem": [],
            "frequencies_theory": [],
            "frequencies_fem": [],
            "modes_theory": [],
            "modes_fem": [],
        }
