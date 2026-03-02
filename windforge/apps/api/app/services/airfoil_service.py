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
from scipy.integrate import solve_ivp
from welib.airfoils.DynamicStall import (
    dynstall_mhh_param_from_polar,
    dynstall_oye_param_from_polar,
    dynstall_mhh_dxdt_simple,
    dynstall_mhh_outputs_simple,
    dynstall_oye_dxdt_simple,
    dynstall_oye_output_simple,
    wagner,
)
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
def _naca4_profile(digits: str, n_points: int = 100) -> tuple:
    """Full NACA 4-digit airfoil generator supporting symmetric and cambered.

    Standard NACA 4-digit equations:
      - 1st digit: max camber (% chord)
      - 2nd digit: location of max camber (tenths of chord)
      - 3rd-4th digits: max thickness (% chord)

    Returns (x, y_upper, y_lower) arrays each of length n_points.
    """
    if len(digits) != 4:
        raise ValueError(f"Expected 4-digit NACA designation, got '{digits}'")

    max_camb = int(digits[0]) / 100.0       # max camber as fraction of chord
    p = int(digits[1]) / 10.0               # location of max camber
    t = int(digits[2:4]) / 100.0            # max thickness as fraction of chord

    # Cosine-spaced x distribution for better LE resolution
    beta = np.linspace(0, np.pi, n_points)
    x = 0.5 * (1.0 - np.cos(beta))

    # Thickness distribution (standard NACA formula)
    yt = 5.0 * t * (
        0.2969 * np.sqrt(x)
        - 0.1260 * x
        - 0.3516 * x**2
        + 0.2843 * x**3
        - 0.1015 * x**4
    )

    if max_camb == 0 or p == 0:
        # Symmetric airfoil
        y_upper = yt
        y_lower = -yt
    else:
        # Cambered airfoil — compute camber line
        yc = np.where(
            x <= p,
            (max_camb / p**2) * (2 * p * x - x**2),
            (max_camb / (1 - p)**2) * ((1 - 2 * p) + 2 * p * x - x**2),
        )
        dyc_dx = np.where(
            x <= p,
            (2 * max_camb / p**2) * (p - x),
            (2 * max_camb / (1 - p)**2) * (p - x),
        )
        theta = np.arctan(dyc_dx)

        y_upper = yc + yt * np.cos(theta)
        y_lower = yc - yt * np.cos(theta)

    return x, y_upper, y_lower


def generate_naca_profile(
    digits: str = "0012",
    n_points: int = 100,
) -> dict:
    """Generate NACA 4-digit airfoil coordinates (symmetric or cambered).

    Parameters
    ----------
    digits : str
        NACA 4-digit designation (e.g. "0012", "2412", "4415").
    n_points : int
        Number of points per surface.

    Returns
    -------
    dict with keys: x, y_upper, y_lower
    """
    x, y_upper, y_lower = _naca4_profile(digits, n_points)

    return {
        "x": x.tolist(),
        "y_upper": y_upper.tolist(),
        "y_lower": y_lower.tolist(),
    }


# ---------------------------------------------------------------------------
# 5. Dynamic stall simulation (Cl-α hysteresis)
# ---------------------------------------------------------------------------
def compute_dynamic_stall_simulation(
    alpha: list[float],
    cl: list[float],
    cd: list[float],
    cm: list[float] | None = None,
    chord: float = 1.0,
    U0: float = 10.0,
    mean_alpha_deg: float = 8.0,
    amplitude_deg: float = 6.0,
    freq: float = 1.0,
    n_cycles: int = 4,
    dt: float = 0.005,
) -> dict:
    """Simulate dynamic stall hysteresis using Oye model.

    Uses the simple (non-callable) interface of the Oye model for
    time-domain simulation of pitch oscillation.

    Parameters
    ----------
    alpha, cl, cd : list[float]
        Static polar data (alpha in degrees).
    cm : list[float] | None
        Moment coefficients.
    chord, U0 : float
        Chord and freestream velocity.
    mean_alpha_deg, amplitude_deg : float
        Mean and amplitude of sinusoidal oscillation (degrees).
    freq : float
        Oscillation frequency (Hz).
    n_cycles : int
        Number of oscillation cycles.
    dt : float
        Time step (s).

    Returns
    -------
    dict with keys: time, alpha_dynamic, cl_static, cl_oye
    """
    alpha_arr = np.asarray(alpha, dtype=float)
    cl_arr = np.asarray(cl, dtype=float)
    cd_arr = np.asarray(cd, dtype=float)
    cm_arr = np.asarray(cm, dtype=float) if cm is not None else np.zeros_like(cl_arr)

    try:
        # Build Oye parameter dict (needs radians polar)
        alpha_rad = np.radians(alpha_arr)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            polar_rad = Polar(
                alpha=alpha_rad, cl=cl_arr, cd=cd_arr, cm=cm_arr,
                Re=1e6, compute_params=True, radians=True,
            )

        tau_chord = 3.0  # time constant in chord lengths
        oye_p = dynstall_oye_param_from_polar(polar_rad, tau_chord=tau_chord)
        # Actual time constant from parameters
        tau = oye_p.get("tau", tau_chord * chord / U0)

        # Build interpolation functions from polar
        from scipy.interpolate import interp1d
        cl_interp = interp1d(alpha_rad, cl_arr, kind='linear',
                             bounds_error=False, fill_value='extrapolate')
        cd_interp = interp1d(alpha_rad, cd_arr, kind='linear',
                             bounds_error=False, fill_value='extrapolate')
        cm_interp = interp1d(alpha_rad, cm_arr, kind='linear',
                             bounds_error=False, fill_value='extrapolate')

        F_st = oye_p.get("F_st", None)
        Clinv = oye_p.get("Clinv", None)
        Clfs = oye_p.get("Clfs", None)

        if F_st is None or Clinv is None or Clfs is None:
            raise ValueError("Missing Oye parameter functions")

        # Time simulation
        t_max = n_cycles / freq
        time = np.arange(0, t_max, dt)
        alpha_dyn_rad = np.radians(mean_alpha_deg) + np.radians(amplitude_deg) * np.sin(2 * np.pi * freq * time)
        alpha_dyn_deg = np.degrees(alpha_dyn_rad)

        # Static Cl for reference
        cl_static = cl_interp(alpha_dyn_rad).tolist()

        # Oye simulation: simple Euler integration
        fs = float(F_st(alpha_dyn_rad[0]))  # initial separation
        cl_oye_list = []

        for i, a_rad in enumerate(alpha_dyn_rad):
            # Get separation function at current alpha
            fs_alpha = float(F_st(a_rad))
            # Update separation state
            fs_dot = (fs_alpha - fs) / tau
            fs = fs + fs_dot * dt

            # Compute lift
            cl_inv = float(Clinv(a_rad))
            cl_fs = float(Clfs(a_rad))
            cl_val = fs * cl_inv + (1.0 - fs) * cl_fs
            cl_oye_list.append(cl_val)

        return {
            "time": time.tolist(),
            "alpha_dynamic": alpha_dyn_deg.tolist(),
            "cl_static": cl_static,
            "cl_oye": cl_oye_list,
        }
    except Exception as exc:
        logger.warning("Dynamic stall simulation failed: %s", exc)
        t_max = n_cycles / freq
        time = np.arange(0, t_max, dt)
        alpha_dyn = mean_alpha_deg + amplitude_deg * np.sin(2 * np.pi * freq * time)
        return {
            "time": time.tolist(),
            "alpha_dynamic": alpha_dyn.tolist(),
            "cl_static": [0.0] * len(time),
            "cl_oye": [0.0] * len(time),
        }


# ---------------------------------------------------------------------------
# 6. Wagner indicial lift function
# ---------------------------------------------------------------------------
def compute_wagner_response(
    s_max: float = 30.0,
    n_points: int = 500,
) -> dict:
    """Compute Wagner indicial lift response for Jones and OpenFAST constants.

    Parameters
    ----------
    s_max : float
        Maximum semi-chord travel distance.
    n_points : int
        Number of points.

    Returns
    -------
    dict with keys: s, phi_jones, phi_openfast
    """
    s = np.linspace(0, s_max, n_points)

    try:
        phi_jones = wagner(s, constants='Jones')
        phi_openfast = wagner(s, constants='OpenFAST')
        return {
            "s": s.tolist(),
            "phi_jones": phi_jones.tolist(),
            "phi_openfast": phi_openfast.tolist(),
        }
    except Exception as exc:
        logger.warning("Wagner computation failed: %s", exc)
        return {
            "s": s.tolist(),
            "phi_jones": [0.0] * n_points,
            "phi_openfast": [0.0] * n_points,
        }
