"""BEM & Rotor aerodynamics service using welib.

Provides steady BEM analysis (CP-λ-pitch surfaces, power curves),
high-thrust corrections, ideal rotor planforms, optimal CP (Betz),
wake expansion models, and Øye dynamic inflow.

All functions are synchronous (CPU-bound) and should be called via
asyncio.loop.run_in_executor() from async handlers.

Key welib functions/classes used:
  - welib.BEM.steadyBEM.calcSteadyBEM
  - welib.BEM.highthrust.Ct_a
  - welib.BEM.idealrotors.planform_wakerot, planform_nowakerot
  - welib.wt_theory.idealrotors.CP_lambda_AD, ADMTO_inductions
  - welib.wt_theory.wakeexpansion.wake_expansion
  - welib.dyninflow.DynamicInflow.dyninflow_oye_sim, tau1_oye, tau2_oye
"""

from __future__ import annotations

import logging
import warnings

import numpy as np
from welib.BEM.highthrust import Ct_a
from welib.BEM.idealrotors import planform_nowakerot, planform_wakerot
from welib.BEM.steadyBEM import calcSteadyBEM
from welib.dyninflow.DynamicInflow import (
    dyninflow_oye_sim,
    tau1_oye,
    tau2_oye,
)
try:
    from welib.wt_theory.idealrotors import ADMTO_CP, ADMTO_inductions
    from welib.wt_theory.wakeexpansion import wake_expansion
except ImportError:
    ADMTO_CP = None  # type: ignore[assignment]
    ADMTO_inductions = None  # type: ignore[assignment]
    wake_expansion = None  # type: ignore[assignment]

logger = logging.getLogger("windforge.bem")


# ---------------------------------------------------------------------------
# 1. CP-Lambda-Pitch surface
# ---------------------------------------------------------------------------
def compute_cp_lambda_pitch_surface(
    r: list[float],
    chord: list[float],
    twist: list[float],
    polar_alpha: list[float],
    polar_cl: list[float],
    polar_cd: list[float],
    V0: float = 10.0,
    nB: int = 3,
    cone: float = 0.0,
    R: float | None = None,
    tsr_min: float = 1.0,
    tsr_max: float = 15.0,
    tsr_steps: int = 30,
    pitch_min: float = -5.0,
    pitch_max: float = 25.0,
    pitch_steps: int = 25,
) -> dict:
    """Sweep TSR × pitch to build CP and CT surfaces.

    Parameters
    ----------
    r : list[float]
        Radial stations from hub to tip (m).
    chord, twist : list[float]
        Chord (m) and twist (deg) at each station.
    polar_alpha, polar_cl, polar_cd : list[float]
        Single polar table shared across all stations (alpha in deg).
    V0 : float
        Reference wind speed (m/s).
    nB : int
        Number of blades.
    cone : float
        Cone angle (deg).
    R : float or None
        Rotor radius (m).  If None, max(r) is used.
    tsr_min, tsr_max, tsr_steps : float, float, int
        Tip-speed ratio sweep parameters.
    pitch_min, pitch_max, pitch_steps : float, float, int
        Pitch angle sweep parameters (deg).

    Returns
    -------
    dict with keys: tsr_values, pitch_values, cp_matrix, ct_matrix,
                    max_cp, optimal_tsr, optimal_pitch
    """
    r_arr = np.asarray(r, dtype=float)
    chord_arr = np.asarray(chord, dtype=float)
    twist_arr = np.asarray(twist, dtype=float)

    if R is None:
        R = float(r_arr[-1])

    # Build polar table: list of nSpan identical (nAlpha, 4) arrays
    # columns: [alpha_deg, Cl, Cd, Cm]
    alpha_arr = np.asarray(polar_alpha, dtype=float)
    cl_arr = np.asarray(polar_cl, dtype=float)
    cd_arr = np.asarray(polar_cd, dtype=float)
    cm_arr = np.zeros_like(cl_arr)
    polar_table = np.column_stack([alpha_arr, cl_arr, cd_arr, cm_arr])
    polars = [polar_table] * len(r_arr)

    tsr_values = np.linspace(tsr_min, tsr_max, tsr_steps)
    pitch_values = np.linspace(pitch_min, pitch_max, pitch_steps)

    cp_matrix = np.zeros((tsr_steps, pitch_steps))
    ct_matrix = np.zeros((tsr_steps, pitch_steps))

    for i, tsr in enumerate(tsr_values):
        Omega_rpm = tsr * V0 / R * 60.0 / (2.0 * np.pi)
        for j, pitch in enumerate(pitch_values):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    BEM = calcSteadyBEM(
                        Omega_rpm, pitch, V0, 0, 0,
                        nB, cone, r_arr, chord_arr, twist_arr, polars,
                        nItMax=100, aTol=1e-6,
                    )
                cp_matrix[i, j] = float(BEM.CP)
                ct_matrix[i, j] = float(BEM.CT)
            except Exception:
                cp_matrix[i, j] = 0.0
                ct_matrix[i, j] = 0.0

    # Find global maximum CP
    idx = np.unravel_index(np.argmax(cp_matrix), cp_matrix.shape)
    max_cp = float(cp_matrix[idx])
    optimal_tsr = float(tsr_values[idx[0]])
    optimal_pitch = float(pitch_values[idx[1]])

    return {
        "tsr_values": tsr_values.tolist(),
        "pitch_values": pitch_values.tolist(),
        "cp_matrix": cp_matrix.tolist(),
        "ct_matrix": ct_matrix.tolist(),
        "max_cp": max_cp,
        "optimal_tsr": optimal_tsr,
        "optimal_pitch": optimal_pitch,
    }


# ---------------------------------------------------------------------------
# 2. Power curve
# ---------------------------------------------------------------------------
def compute_power_curve(
    r: list[float],
    chord: list[float],
    twist: list[float],
    polar_alpha: list[float],
    polar_cl: list[float],
    polar_cd: list[float],
    R: float | None = None,
    nB: int = 3,
    cone: float = 0.0,
    rpm: float = 12.0,
    pitch: float = 0.0,
    wind_speeds: list[float] | None = None,
) -> dict:
    """Compute aerodynamic power curve at fixed RPM and pitch.

    Returns power, thrust, torque, CP, CT vs wind speed.
    """
    r_arr = np.asarray(r, dtype=float)
    chord_arr = np.asarray(chord, dtype=float)
    twist_arr = np.asarray(twist, dtype=float)

    if R is None:
        R = float(r_arr[-1])

    # Polar table
    alpha_arr = np.asarray(polar_alpha, dtype=float)
    cl_arr = np.asarray(polar_cl, dtype=float)
    cd_arr = np.asarray(polar_cd, dtype=float)
    cm_arr = np.zeros_like(cl_arr)
    polar_table = np.column_stack([alpha_arr, cl_arr, cd_arr, cm_arr])
    polars = [polar_table] * len(r_arr)

    if wind_speeds is None:
        ws = np.arange(3.0, 26.0, 1.0)
    else:
        ws = np.asarray(wind_speeds, dtype=float)

    power = []
    thrust = []
    torque = []
    cp = []
    ct = []

    for V0 in ws:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                BEM = calcSteadyBEM(
                    rpm, pitch, float(V0), 0, 0,
                    nB, cone, r_arr, chord_arr, twist_arr, polars,
                    nItMax=100, aTol=1e-6,
                )
            power.append(float(BEM.Power))
            thrust.append(float(BEM.Thrust))
            torque.append(float(BEM.Torque))
            cp.append(float(BEM.CP))
            ct.append(float(BEM.CT))
        except Exception:
            power.append(0.0)
            thrust.append(0.0)
            torque.append(0.0)
            cp.append(0.0)
            ct.append(0.0)

    return {
        "wind_speeds": ws.tolist(),
        "power": power,
        "thrust": thrust,
        "torque": torque,
        "cp": cp,
        "ct": ct,
    }


# ---------------------------------------------------------------------------
# 3. High thrust corrections
# ---------------------------------------------------------------------------
def compute_high_thrust_corrections(
    methods: list[str] | None = None,
    a_min: float = 0.0,
    a_max: float = 1.0,
    n_points: int = 200,
) -> dict:
    """Compare Ct(a) for multiple high-thrust correction methods.

    Parameters
    ----------
    methods : list[str] or None
        Correction methods.  If None, a standard set is used.
    a_min, a_max : float
        Induction factor range.
    n_points : int
        Number of points.

    Returns
    -------
    dict with keys: a_values, ct_curves (dict of method → values list)
    """
    if methods is None:
        methods = [
            "MomentumTheory",
            "Glauert",
            "Spera",
            "Buhl",
            "Leishman",
            "Branlard",
        ]

    a_values = np.linspace(a_min, a_max, n_points)
    ct_curves: dict[str, list[float]] = {}

    for method in methods:
        try:
            ct_vals = Ct_a(a_values, method=method)
            ct_curves[method] = np.asarray(ct_vals, dtype=float).tolist()
        except Exception as exc:
            logger.warning("High-thrust method %s failed: %s", method, exc)
            ct_curves[method] = [float("nan")] * n_points

    return {
        "a_values": a_values.tolist(),
        "ct_curves": ct_curves,
    }


# ---------------------------------------------------------------------------
# 4. Ideal rotor planform
# ---------------------------------------------------------------------------
def compute_ideal_rotor_planform(
    R: float = 63.0,
    r_hub: float = 1.5,
    TSR_design: float = 7.0,
    Cl_design: float = 1.0,
    B: int = 3,
    n_points: int = 50,
) -> dict:
    """Compute ideal rotor chord and twist distributions.

    Returns results both with and without wake rotation.

    Parameters
    ----------
    R : float
        Rotor radius (m).
    r_hub : float
        Hub radius (m).
    TSR_design : float
        Design tip-speed ratio.
    Cl_design : float
        Design lift coefficient.
    B : int
        Number of blades.
    n_points : int
        Number of radial stations.

    Returns
    -------
    dict with keys: r_over_R, chord_wake, twist_wake, chord_nowake,
                    twist_nowake, a_wake, ap_wake
    """
    r = np.linspace(r_hub, R, n_points)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        chord_wr, phi_wr, a_wr, ap_wr = planform_wakerot(
            r, R, TSR_design, Cl_design, B,
        )
        chord_nwr, phi_nwr, a_nwr, ap_nwr = planform_nowakerot(
            r, R, TSR_design, Cl_design, B,
        )

    return {
        "r_over_R": (r / R).tolist(),
        "chord_wake": chord_wr.tolist(),
        "twist_wake": phi_wr.tolist(),
        "chord_nowake": chord_nwr.tolist(),
        "twist_nowake": phi_nwr.tolist(),
        "a_wake": a_wr.tolist(),
        "ap_wake": ap_wr.tolist(),
    }


# ---------------------------------------------------------------------------
# 5. Optimal CP vs TSR (Betz limit)
# ---------------------------------------------------------------------------
def compute_optimal_cp_betz(
    tsr_min: float = 0.5,
    tsr_max: float = 15.0,
    n_points: int = 200,
) -> dict:
    """Compute optimal CP vs TSR using actuator-disc momentum theory.

    Also computes optimal induction factors.

    Returns
    -------
    dict with keys: tsr, cp_optimal, cp_betz, a_optimal, ap_optimal
    """
    tsr = np.linspace(tsr_min, tsr_max, n_points)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        cp_opt, a_opt = ADMTO_CP(tsr, method="analytical")
        _, ap_opt = ADMTO_inductions(tsr, method="analytical")

    # Betz limit
    cp_betz = np.full_like(tsr, 16.0 / 27.0)

    return {
        "tsr": tsr.tolist(),
        "cp_optimal": np.asarray(cp_opt).tolist(),
        "cp_betz": cp_betz.tolist(),
        "a_optimal": np.asarray(a_opt).tolist(),
        "ap_optimal": np.asarray(ap_opt).tolist(),
    }


# ---------------------------------------------------------------------------
# 6. Wake expansion
# ---------------------------------------------------------------------------
def compute_wake_expansion(
    CT: float = 0.8,
    models: list[str] | None = None,
    x_max_over_D: float = 20.0,
    n_points: int = 200,
) -> dict:
    """Compute wake expansion r/R vs downstream distance for multiple models.

    Parameters
    ----------
    CT : float
        Thrust coefficient.
    models : list[str] or None
        Wake models.  If None, a standard set is used.
    x_max_over_D : float
        Maximum downstream distance in rotor diameters.
    n_points : int
        Number of downstream stations.

    Returns
    -------
    dict with keys: x_over_D, curves (dict of model → r_over_R list)
    """
    if models is None:
        models = ["momentum", "cylinder", "Rathmann", "Frandsen"]

    # Convert x/D to x/R (welib uses x/R = xb)
    x_over_D = np.linspace(0.1, x_max_over_D, n_points)
    xb = x_over_D * 2.0  # x/R = 2 * x/D

    curves: dict[str, list[float]] = {}

    for model in models:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r_over_R = wake_expansion(xb, CT=CT, model=model)
            curves[model] = np.asarray(r_over_R, dtype=float).tolist()
        except Exception as exc:
            logger.warning("Wake expansion model %s failed: %s", model, exc)
            curves[model] = [float("nan")] * n_points

    return {
        "x_over_D": x_over_D.tolist(),
        "curves": curves,
    }


# ---------------------------------------------------------------------------
# 7. Dynamic inflow (Øye model)
# ---------------------------------------------------------------------------
def compute_dynamic_inflow(
    R: float = 63.0,
    U0: float = 10.0,
    a_init: float = 0.2,
    a_final: float = 0.35,
    r_bar: float = 0.7,
    t_max: float = 30.0,
    dt: float = 0.05,
) -> dict:
    """Simulate dynamic inflow response to a step change in induction.

    Uses the Øye dynamic inflow model (discrete formulation).

    Parameters
    ----------
    R : float
        Rotor radius (m).
    U0 : float
        Free-stream wind speed (m/s).
    a_init : float
        Initial axial induction factor.
    a_final : float
        Final axial induction factor (step target).
    r_bar : float
        Normalised radial position r/R for time constants.
    t_max : float
        Simulation duration (s).
    dt : float
        Time step (s).

    Returns
    -------
    dict with keys: time, a_dynamic, a_quasi_steady, tau1, tau2
    """
    time = np.arange(0, t_max, dt)

    # Time constants using average induction
    a_bar = (a_init + a_final) / 2.0
    t1 = tau1_oye(a_bar, R, U0)
    t2 = tau2_oye(r_bar, t1)

    # Quasi-steady velocity (step change at t=0)
    V_init = U0 * (1 - a_init)
    V_final = U0 * (1 - a_final)

    # Quasi-steady function
    def Vqs_func(t):
        return V_final if t > 0 else V_init

    # Parameters dict
    p = {"tau1": t1, "tau2": t2, "k": 0.6}
    u = {"Vqs": Vqs_func}

    try:
        df = dyninflow_oye_sim(time, u, p, method="discrete")
        V_dyn = df["Vdyn_[m/s]"].values
        V_qs = df["Vqs_[m/s]"].values

        # Convert velocities back to induction: a = 1 - V/U0
        a_dynamic = 1.0 - V_dyn / U0
        a_quasi_steady = 1.0 - V_qs / U0
    except Exception as exc:
        logger.warning("Dynamic inflow simulation failed: %s", exc)
        # Fallback: manual exponential response
        a_quasi_steady = np.where(time > 0, a_final, a_init)
        a_dynamic = a_final - (a_final - a_init) * np.exp(-time / t1)

    return {
        "time": time.tolist(),
        "a_dynamic": a_dynamic.tolist(),
        "a_quasi_steady": a_quasi_steady.tolist(),
        "tau1": float(t1),
        "tau2": float(t2),
    }
