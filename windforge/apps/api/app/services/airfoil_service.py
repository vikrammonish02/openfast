"""Airfoil analysis service using welib.

Provides polar analysis, 3-D rotational corrections, dynamic stall
parameter extraction, and NACA profile generation.

All functions are synchronous (CPU-bound) and should be called via
asyncio.loop.run_in_executor() from async handlers.

Key welib functions/classes used:
  - welib.airfoils.Polar.Polar(alpha, cl, cd, cm, Re, compute_params, radians)
  - Polar.cl_max() -> (cl_max_val, alpha_at_cl_max)
  - Polar.alpha0() -> float
  - Polar.cl_linear_slope() -> (slope, intercept)
  - Polar.correction3D(r_over_R, chord_over_r, tsr, ...) -> Polar
  - Polar.unsteadyParams(dictOut=True) -> dict
  - welib.airfoils.DynamicStall.dynstall_mhh_param_from_polar(P, chord, ...)
  - welib.airfoils.DynamicStall.dynstall_oye_param_from_polar(P, tau_chord=...)
  - welib.airfoils.naca.naca_shape(digits, n=...) -> (x, y)
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
from welib.airfoils.DynamicStall import (
    dynstall_mhh_param_from_polar,
    dynstall_oye_param_from_polar,
)
from welib.airfoils.naca import naca_shape
from welib.airfoils.Polar import Polar

logger = logging.getLogger("windforge.airfoil")


# ---------------------------------------------------------------------------
# 1. Polar analysis
# ---------------------------------------------------------------------------
def analyze_polar(
    alpha: list[float],
    cl: list[float],
    cd: list[float],
    cm: list[float] | None = None,
    re: float = 1e6,
) -> dict:
    """Analyze an airfoil polar to extract key aerodynamic parameters.

    Parameters
    ----------
    alpha : list[float]
        Angle of attack in degrees.
    cl, cd : list[float]
        Lift and drag coefficient arrays.
    cm : list[float] | None
        Moment coefficient array (optional).
    re : float
        Reynolds number.

    Returns
    -------
    dict with keys: cl_max, alpha_stall, cl_cd_max, zero_lift_alpha,
                    linear_slope, unsteady_params
    """
    alpha_arr = np.asarray(alpha, dtype=float)
    cl_arr = np.asarray(cl, dtype=float)
    cd_arr = np.asarray(cd, dtype=float)
    cm_arr = np.asarray(cm, dtype=float) if cm is not None else None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        polar = Polar(
            alpha=alpha_arr, cl=cl_arr, cd=cd_arr, cm=cm_arr,
            Re=re, compute_params=True,
        )

    # cl_max() returns (cl_max_value, alpha_at_cl_max)
    cl_max_val, alpha_stall = polar.cl_max()

    # Best L/D ratio
    cd_safe = np.where(cd_arr > 0, cd_arr, 1e-10)
    cl_cd_ratio = cl_arr / cd_safe
    cl_cd_max = float(np.max(cl_cd_ratio))

    # Zero-lift angle of attack
    zero_lift_alpha = float(polar.alpha0())

    # Linear slope: cl_linear_slope() returns (slope, intercept)
    linear_slope, _ = polar.cl_linear_slope()

    # Unsteady parameters for AeroDyn
    unsteady = polar.unsteadyParams(dictOut=True)

    return {
        "cl_max": float(cl_max_val),
        "alpha_stall": float(alpha_stall),
        "cl_cd_max": cl_cd_max,
        "zero_lift_alpha": zero_lift_alpha,
        "linear_slope": float(linear_slope),
        "unsteady_params": {
            "alpha0": float(unsteady.get("alpha0", 0.0)),
            "alpha1": float(unsteady.get("alpha1", 0.0)),
            "alpha2": float(unsteady.get("alpha2", 0.0)),
            "C_nalpha": float(unsteady.get("C_nalpha", 0.0)),
            "Cn1": float(unsteady.get("Cn1", 0.0)),
            "Cn2": float(unsteady.get("Cn2", 0.0)),
            "Cd0": float(unsteady.get("Cd0", 0.0)),
            "Cm0": float(unsteady.get("Cm0", 0.0)),
        },
    }


# ---------------------------------------------------------------------------
# 2. 3-D rotational correction
# ---------------------------------------------------------------------------
def apply_3d_correction(
    alpha: list[float],
    cl: list[float],
    cd: list[float],
    r_over_R: float,
    chord_over_r: float,
    tsr: float = 7.0,
) -> dict:
    """Apply 3-D rotational correction (Du-Selig method) to a 2-D polar.

    welib signature:
      Polar.correction3D(r_over_R, chord_over_r, tsr, ...) -> Polar

    Parameters
    ----------
    alpha, cl, cd : list[float]
        2-D polar data (alpha in degrees).
    r_over_R : float
        Local radial position / rotor radius.
    chord_over_r : float
        Local chord / local radial position.
    tsr : float
        Tip-speed ratio.

    Returns
    -------
    dict with keys: alpha, cl_corrected, cd_corrected
    """
    alpha_arr = np.asarray(alpha, dtype=float)
    cl_arr = np.asarray(cl, dtype=float)
    cd_arr = np.asarray(cd, dtype=float)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        polar = Polar(
            alpha=alpha_arr, cl=cl_arr, cd=cd_arr,
            Re=1e6, compute_params=True,
        )

        polar_3d = polar.correction3D(
            r_over_R=r_over_R,
            chord_over_r=chord_over_r,
            tsr=tsr,
        )

    return {
        "alpha": polar_3d.alpha.tolist(),
        "cl_corrected": polar_3d.cl.tolist(),
        "cd_corrected": polar_3d.cd.tolist(),
    }


# ---------------------------------------------------------------------------
# 3. Dynamic stall parameters
# ---------------------------------------------------------------------------
def compute_dynamic_stall_params(
    alpha: list[float],
    cl: list[float],
    cd: list[float],
    cm: list[float] | None = None,
    chord: float = 1.0,
    tau_oye: float = 4.0,
) -> dict:
    """Compute dynamic stall parameters (MHH and Oye models).

    MHH requires polar in radians. Oye requires tau or tau_chord.

    welib signatures:
      dynstall_mhh_param_from_polar(P, chord, Tf0, Tp0, ...) -> dict
      dynstall_oye_param_from_polar(P, tau=None, tau_chord=None, ...) -> dict

    Parameters
    ----------
    alpha, cl, cd : list[float]
        Polar data (alpha in degrees -- will be converted to radians for MHH).
    cm : list[float] | None
        Moment coefficients (optional).
    chord : float
        Chord length (m).
    tau_oye : float
        Oye time constant in chord lengths (tau_chord).

    Returns
    -------
    dict with keys: mhh_params, oye_params
    """
    alpha_deg = np.asarray(alpha, dtype=float)
    alpha_rad = np.radians(alpha_deg)
    cl_arr = np.asarray(cl, dtype=float)
    cd_arr = np.asarray(cd, dtype=float)
    cm_arr = np.asarray(cm, dtype=float) if cm is not None else None

    # MHH requires radians
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        polar_rad = Polar(
            alpha=alpha_rad, cl=cl_arr, cd=cd_arr, cm=cm_arr,
            Re=1e6, compute_params=True, radians=True,
        )

    # MHH parameters
    try:
        mhh_raw = dynstall_mhh_param_from_polar(polar_rad, chord=chord)
        # Extract only serializable scalar parameters (skip function references)
        mhh_params = {}
        for k, v in mhh_raw.items():
            if isinstance(v, (int, float, bool, str)):
                mhh_params[k] = v
            elif hasattr(v, 'item'):  # numpy scalar
                mhh_params[k] = float(v)
    except Exception as exc:
        logger.warning("MHH dynamic stall parameter extraction failed: %s", exc)
        mhh_params = {"error": str(exc)}

    # Oye parameters (also needs radians polar)
    try:
        oye_raw = dynstall_oye_param_from_polar(polar_rad, tau_chord=tau_oye)
        oye_params = {}
        for k, v in oye_raw.items():
            if isinstance(v, (int, float, bool, str)):
                oye_params[k] = v
            elif hasattr(v, 'item'):  # numpy scalar
                oye_params[k] = float(v)
    except Exception as exc:
        logger.warning("Oye dynamic stall parameter extraction failed: %s", exc)
        oye_params = {"error": str(exc)}

    return {
        "mhh_params": mhh_params,
        "oye_params": oye_params,
    }


# ---------------------------------------------------------------------------
# 4. NACA profile generation
# ---------------------------------------------------------------------------
def generate_naca_profile(
    digits: str = "0012",
    n_points: int = 100,
) -> dict:
    """Generate NACA 4-digit airfoil coordinates.

    welib signature:
      naca_shape(digits, chord=1, n=151, thickTEZero=False, pitch=0, xrot=0.25)
      Returns (x, y) where the profile goes around the airfoil:
        upper surface (LE to TE) then lower surface (TE to LE).

    Parameters
    ----------
    digits : str
        NACA 4-digit designation (e.g. "0012", "2412").
    n_points : int
        Number of points per surface.

    Returns
    -------
    dict with keys: x, y_upper, y_lower
    """
    # naca_shape returns a wrap-around profile: upper (0->1) then lower (1->0)
    # Total points = 2 * n_points
    x_full, y_full = naca_shape(digits, n=n_points)

    # Split into upper and lower surfaces
    # Upper surface: first n_points values (x: 0 -> 1)
    # Lower surface: last n_points values (x: 1 -> 0, reversed)
    x_upper = x_full[:n_points]
    y_upper = y_full[:n_points]
    x_lower = x_full[n_points:]
    y_lower = y_full[n_points:]

    # Reverse lower surface so x goes 0 -> 1 (same direction as upper)
    x_lower = x_lower[::-1]
    y_lower = y_lower[::-1]

    return {
        "x": x_upper.tolist(),
        "y_upper": y_upper.tolist(),
        "y_lower": y_lower.tolist(),
    }
